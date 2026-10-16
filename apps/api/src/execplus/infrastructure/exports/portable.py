"""Use case: Delivers exact results as spreadsheets, CSV evidence bundles and charts.

What it does: Keeps types and provenance, disables spreadsheet formula interpretation,
refuses truncation and uses only local trusted renderers.
"""

import csv
import json
import re
from dataclasses import asdict, replace
from io import BytesIO, StringIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill

from execplus.domain.exports import (
    MAX_EXPORT_BYTES,
    ExportContent,
    cell_type,
    exact_text,
    validate_export,
)
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.exports.chart_png import png_chart
from execplus.infrastructure.exports.reportlab_pdf import ReportLabPdfRenderer

FORMULA = re.compile(r"^[\s\ufeff]*[=+@-]")
NUMERIC = re.compile(r"^-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def manifest(content: ExportContent) -> dict[str, Any]:
    return {
        "version": "execplus-export-v1",
        "title": content.document.title,
        "generated_at": content.document.generated_at.isoformat(),
        "sections": [asdict(section) for section in content.document.sections],
        "tables": [
            {
                "name": table.name,
                "columns": table.columns,
                "rows": [
                    [{"type": cell_type(value), "value": exact_text(value)} for value in row]
                    for row in table.rows
                ],
            }
            for table in content.tables
        ],
        "charts": [asdict(chart) for chart in content.charts],
        "notice": (
            "Exact scalar strings and original types are retained here. "
            "CSV may prefix formula-like text with an apostrophe; Excel cells are explicitly text. "
            "Null and empty string differ by type. CSV readers may infer numbers or dates; "
            "use this evidence or the text-only Excel workbook for exact originals. "
            "A downloaded copy cannot be recalled."
        ),
    }


class PortableRenderer:
    def __init__(self, pdf: ReportLabPdfRenderer | None = None) -> None:
        self.pdf = pdf or ReportLabPdfRenderer()

    def render(self, content: ExportContent, format: str, chart_index: int = 0) -> bytes:
        validate_export(content)
        evidence = manifest(content)
        if format == "pdf":
            value = self.pdf.render(replace(content.document, charts=content.charts))
        elif format == "xlsx":
            value = self.xlsx(content, evidence)
        elif format == "csv":
            value = self.csv_bundle(content, evidence)
        elif format == "png":
            if chart_index < 0 or chart_index >= len(content.charts):
                raise IngestionError(
                    "export_chart", "Choose one of this result's available charts.", 422
                )
            value = png_chart(content.charts[chart_index], evidence)
        else:
            raise IngestionError("export_format", "Choose PDF, Excel, CSV or PNG.", 422)
        if len(value) > MAX_EXPORT_BYTES:
            raise IngestionError(
                "export_limit", "This export exceeds 16 MiB. Choose a smaller result.", 422
            )
        return value

    def csv_bundle(self, content: ExportContent, evidence: dict[str, Any]) -> bytes:
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for index, table in enumerate(content.tables, 1):
                stream = StringIO(newline="")
                writer = csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
                for row in (table.columns, *table.rows):
                    cells = []
                    for item in row:
                        value = exact_text(item)
                        cells.append(
                            "'" + value
                            if FORMULA.match(value) and not NUMERIC.fullmatch(value)
                            else value
                        )
                    writer.writerow(cells)
                archive.writestr(f"result-{index}.csv", stream.getvalue().encode("utf-8-sig"))
            archive.writestr(
                "evidence.json", json.dumps(evidence, ensure_ascii=False, default=str, indent=2)
            )
            archive.writestr(
                "README.txt",
                evidence["notice"]
                + (
                    "\nEach result-N.csv corresponds to table N in evidence.json. Every "
                    "returned row is included.\n"
                ),
            )
        return output.getvalue()

    def xlsx(self, content: ExportContent, evidence: dict[str, Any]) -> bytes:
        for table in content.tables:
            for row in ((table.name,), table.columns, *table.rows):
                for item in row:
                    value = exact_text(item)
                    if len(value.encode("utf-16-le")) // 2 > 32767 or re.search(
                        r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value
                    ):
                        raise IngestionError(
                            "export_text",
                            "An Excel cell is too long or contains unsupported control characters. "
                            "Use the CSV evidence bundle.",
                            422,
                        )
        workbook = Workbook(write_only=True)

        def append(sheet: Any, values: tuple[str, ...], *, header: bool = False) -> None:
            cells = []
            for value in values:
                if len(value.encode("utf-16-le")) // 2 > 32767 or re.search(
                    r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value
                ):
                    raise IngestionError(
                        "export_text",
                        (
                            "An Excel cell exceeds its text limit or contains unsupported "
                            "control characters. Use the CSV evidence bundle."
                        ),
                        422,
                    )
                cell = WriteOnlyCell(sheet, value=value)
                cell.data_type = "s"
                cell.number_format = "@"
                if header:
                    cell.font = Font(bold=True, color="176C64")
                    cell.fill = PatternFill("solid", fgColor="E9F1ED")
                cells.append(cell)
            sheet.append(cells)

        for index, table in enumerate(content.tables, 1):
            sheet = workbook.create_sheet(f"Result {index}")
            sheet.freeze_panes = "A2"
            append(sheet, table.columns, header=True)
            for row in table.rows:
                append(sheet, tuple(exact_text(value) for value in row))
        meta = workbook.create_sheet("Evidence")
        append(meta, ("Part", "Exact JSON text (concatenate in order)"), header=True)
        serialized = json.dumps(evidence, ensure_ascii=True, default=str, indent=2)
        for start in range(0, len(serialized), 30000):
            append(meta, (str(start // 30000 + 1), serialized[start : start + 30000]))
        guide = workbook.create_sheet("Read me")
        append(guide, ("ExecPlus exact result export",), header=True)
        append(guide, (evidence["notice"],))
        for index, table in enumerate(content.tables, 1):
            append(guide, (f"Result {index}", table.name, f"{len(table.rows)} rows"))
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
