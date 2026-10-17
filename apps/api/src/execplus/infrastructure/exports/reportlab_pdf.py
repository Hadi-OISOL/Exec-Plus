"""Use case: Renders exact saved-answer content into a portable PDF.

What it does: Uses pinned ReportLab and a bundled licensed font, escapes all text,
checks glyph coverage, repeats table headers and refuses oversized output.
"""

import re
from dataclasses import replace
from datetime import timezone
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)
from reportlab.platypus.doctemplate import LayoutError

from execplus.domain.exports import ExportChart
from execplus.domain.ingestion import IngestionError
from execplus.domain.pdf_exports import (
    MAX_PDF_BYTES,
    MAX_PDF_PAGES,
    PdfDocument,
    PdfTable,
    document_text,
    validate_document,
)

FONT_NAME = "ExecPlusManrope"
FONT_PATH = Path(__file__).with_name("assets") / "Manrope-Variable.ttf"
FONT_LOCK = Lock()
RENDER_LOCK = Lock()


class PdfPageLimitError(ValueError):
    pass


def literal_text(text: str) -> str:
    escaped = escape(text)
    spaced = re.sub(
        r"^ +| +$| {2,}", lambda value: "&#160;" * len(value[0]), escaped, flags=re.MULTILINE
    )
    return spaced.replace("\n", "<br/>")


class ReportLabPdfRenderer:
    def __init__(self) -> None:
        with FONT_LOCK:
            if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))
        self._glyphs = frozenset(pdfmetrics.getFont(FONT_NAME).face.charToGlyph)

    def validate(self, document: PdfDocument) -> None:
        validate_document(document)
        if any(
            char != "\n" and ord(char) not in self._glyphs
            for value in document_text(document)
            for char in value
        ):
            raise IngestionError(
                "pdf_export_text",
                "This answer uses characters that the PDF font cannot display accurately. "
                "The saved answer remains available; this export does not yet support "
                "every writing system or emoji.",
                422,
            )

    def render(self, document: PdfDocument) -> bytes:
        self.validate(document)
        buffer = BytesIO()
        width, _ = A4
        content_width = width - 88
        body = ParagraphStyle(
            "ExecPlusBody",
            fontName=FONT_NAME,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#233a36"),
            spaceAfter=7,
            splitLongWords=True,
        )
        heading = ParagraphStyle(
            "ExecPlusHeading",
            parent=body,
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#176c64"),
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
        )
        title = ParagraphStyle(
            "ExecPlusTitle",
            parent=heading,
            fontSize=22,
            leading=28,
            spaceBefore=0,
        )
        cell = ParagraphStyle(
            "ExecPlusCell",
            parent=body,
            fontSize=8,
            leading=11,
            spaceAfter=0,
        )

        def paragraph(text: str, style: ParagraphStyle = body) -> Paragraph:
            return Paragraph(literal_text(text), style)

        story: list[Any] = [paragraph(document.title, title)]
        if document.charts:
            from execplus.infrastructure.exports.chart_png import png_chart

            for chart in (part for original in document.charts for part in chart_pages(original)):
                encoded = png_chart(
                    chart,
                    {"title": document.title, "generated_at": document.generated_at.isoformat()},
                )
                figure = Image(BytesIO(encoded))
                ratio = min(content_width / figure.imageWidth, 600 / figure.imageHeight)
                figure.drawWidth = figure.imageWidth * ratio
                figure.drawHeight = figure.imageHeight * ratio
                story.extend((paragraph(chart.title, heading), figure, PageBreak()))
        for section in document.sections:
            story.append(paragraph(section.title, heading))
            story.extend(paragraph(text) for text in section.paragraphs)
            if section.table:
                story.extend(self._tables(section.table, content_width, cell, body))

        def page_footer(canvas: Any, template: Any) -> None:
            page = canvas.getPageNumber()
            if page > MAX_PDF_PAGES:
                raise PdfPageLimitError("PDF page limit exceeded")
            canvas.saveState()
            canvas.setFont(FONT_NAME, 8)
            canvas.setFillColor(colors.HexColor("#53625f"))
            canvas.drawString(44, 26, f"ExecPlus | Page {page}")
            canvas.drawRightString(
                width - 44,
                26,
                "Generated "
                + document.generated_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
            canvas.restoreState()

        template = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=44,
            rightMargin=44,
            topMargin=42,
            bottomMargin=45,
            title=document.title,
            author="ExecPlus",
            subject="Report generated " + document.generated_at.isoformat(),
            pageCompression=1,
            invariant=1,
        )
        try:
            with RENDER_LOCK:
                template.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
        except PdfPageLimitError as error:
            raise IngestionError(
                "pdf_export_limit",
                "This PDF would exceed 100 pages. Choose a smaller saved answer.",
                422,
            ) from error
        except LayoutError as error:
            raise IngestionError(
                "pdf_export_limit",
                "This answer cannot fit the supported PDF layout. Choose a smaller saved answer.",
                422,
            ) from error
        content = buffer.getvalue()
        if len(content) > MAX_PDF_BYTES:
            raise IngestionError(
                "pdf_export_limit", "This PDF exceeds 4 MiB. Choose a smaller saved answer.", 422
            )
        return content

    def _tables(
        self, table: PdfTable, width: float, cell: ParagraphStyle, body: ParagraphStyle
    ) -> list[Any]:
        flowables: list[Any] = []
        for start in range(0, len(table.columns), 5):
            end = min(start + 5, len(table.columns))
            if len(table.columns) > 5:
                flowables.append(
                    Paragraph(
                        f"Columns {start + 1}-{end} of {len(table.columns)}. "
                        "Row numbers refer to the original returned table.",
                        body,
                    )
                )
            values = [("Row", *table.columns[start:end])]
            values.extend((str(index), *row[start:end]) for index, row in enumerate(table.rows, 1))
            cells = [[Paragraph(literal_text(value), cell) for value in row] for row in values]
            rendered = LongTable(
                cells,
                colWidths=[32] + [(width - 32) / (end - start)] * (end - start),
                repeatRows=1,
                splitByRow=1,
                splitInRow=1,
                hAlign="LEFT",
            )
            rendered.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9f1ed")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#9bb8ad")),
                        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#dde7e2")),
                    ]
                )
            )
            flowables.extend((rendered, Spacer(1, 12)))
        return flowables


def chart_pages(chart: ExportChart) -> tuple[ExportChart, ...]:
    if chart.kind == "bar":
        return tuple(
            replace(
                chart,
                title=(
                    f"{chart.title} · rows {start + 1}-"
                    f"{min(start + 12, len(chart.labels))} of {len(chart.labels)}"
                ),
                labels=chart.labels[start : start + 12],
                series=tuple(
                    replace(series, values=series.values[start : start + 12])
                    for series in chart.series
                ),
            )
            for start in range(0, len(chart.labels), 12)
        )
    if chart.kind == "diagram":
        fields = [node for node in chart.nodes if node["kind"] == "field"]
        result = []
        for start in range(0, len(fields), 10):
            selected = fields[start : start + 10]
            ids = {node["id"] for node in selected}
            groups = {edge["source"] for edge in chart.edges if edge["target"] in ids}
            nodes = tuple(
                node
                for node in chart.nodes
                if node["kind"] == "dataset" or node["id"] in ids | groups
            )
            all_ids = {node["id"] for node in nodes}
            result.append(
                replace(
                    chart,
                    title=(
                        f"{chart.title} · fields {start + 1}-"
                        f"{min(start + 10, len(fields))} of {len(fields)}"
                    ),
                    nodes=nodes,
                    edges=tuple(
                        edge
                        for edge in chart.edges
                        if edge["source"] in all_ids and edge["target"] in all_ids
                    ),
                )
            )
        return tuple(result)
    return (chart,)
