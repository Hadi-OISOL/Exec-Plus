"""Use case: Draws portable images from trusted, source-backed chart specifications.

What it does: Renders exact labels and approximate geometry locally, preserves null
line gaps and signed zero baselines, and embeds complete provenance in PNG metadata.
"""

import json
import textwrap
from dataclasses import asdict
from decimal import Decimal, InvalidOperation, localcontext
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from reportlab.pdfbase.ttfonts import TTFont

from execplus.domain.exports import MAX_EXPORT_BYTES, ExportChart
from execplus.domain.ingestion import IngestionError

FONT_PATH = Path(__file__).with_name("assets") / "Manrope-Variable.ttf"
GLYPHS = frozenset(TTFont("ExportGlyphCheck", str(FONT_PATH)).face.charToGlyph)
COLORS = ("#176c64", "#7960aa", "#b95538", "#3c719a")


def number(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value)
        if parsed.is_finite():
            return parsed
    except InvalidOperation:
        pass
    raise IngestionError("export_chart", "The chart contains a non-finite value.", 422)


def png_chart(chart: ExportChart, evidence: dict[str, Any]) -> bytes:
    if chart.kind not in {"bar", "line", "scatter", "diagram"}:
        raise IngestionError("export_chart", "This result has no supported chart encoding.", 422)
    if chart.kind != "diagram" and (
        not chart.labels
        or not chart.series
        or len(chart.series) > 4
        or any(len(item.values) != len(chart.labels) for item in chart.series)
    ):
        raise IngestionError("export_chart", "The chart data is incomplete.", 422)
    rows = len(chart.nodes) if chart.kind == "diagram" else len(chart.labels)
    row_height = 100 if chart.kind == "diagram" else max(70, len(chart.series) * 26 + 12)
    height = max(650, 260 + rows * row_height) if chart.kind in {"bar", "diagram"} else 900
    plot_height = height
    notes = [line for note in chart.notes for line in textwrap.wrap(note, 100)]
    height += len(notes) * 29 + (40 if notes else 0)
    width = 1600
    if width * height > 16_000_000:
        raise IngestionError(
            "export_limit",
            "This chart exceeds 16 million pixels. Use the complete spreadsheet export.",
            422,
        )
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT_PATH), 24)
    heading = ImageFont.truetype(str(FONT_PATH), 28)
    font.set_variation_by_axes([500])
    heading.set_variation_by_axes([650])

    def text(
        position: tuple[float, float], value: str, *, large: bool = False, fill: str = "#23483d"
    ) -> None:
        if any(char != "\n" and ord(char) not in GLYPHS for char in value):
            raise IngestionError(
                "export_text",
                "The image font cannot display every character in this result. Use CSV or Excel.",
                422,
            )
        draw.multiline_text(position, value, font=heading if large else font, fill=fill, spacing=4)

    title_lines = textwrap.wrap(chart.title, 85)
    text((45, 25), "\n".join(title_lines[:2]) + ("…" if len(title_lines) > 2 else ""), large=True)
    text(
        (45, 110),
        "ExecPlus | Approximate geometry. Exact values and source evidence are embedded.",
    )
    if chart.kind == "diagram":
        groups = [node for node in chart.nodes if node.get("kind") == "group"]
        root = next(
            (node for node in chart.nodes if node.get("kind") == "dataset"), {"label": "This file"}
        )
        y: float = 190
        for group in groups:
            members = [
                node
                for node in chart.nodes
                if node.get("kind") == "field"
                and any(
                    edge.get("source") == group["id"] and edge.get("target") == node["id"]
                    for edge in chart.edges
                )
            ]
            center = y + max(0, len(members) - 1) * row_height / 2
            text((45, center), str(root["label"]))
            text((350, center - 24), str(group["label"]))
            draw.line((170, center + 12, 700, center + 12), fill="#90aaa0", width=2)
            for index, node in enumerate(members):
                target = y + index * row_height
                draw.line(
                    (700, center + 12, 700, target + 12, 820, target + 12), fill="#90aaa0", width=2
                )
                draw.ellipse((814, target + 6, 826, target + 18), fill=COLORS[0])
                text((845, target), "\n".join(textwrap.wrap(str(node["label"]), 50)))
            y += max(1, len(members)) * row_height + 35
        text(
            (45, plot_height - 55),
            "Lines show field membership, not causality, joins or measured relationships.",
        )
    else:

        def axis_label(value: Decimal) -> str:
            if value and (value.adjusted() > 12 or value.adjusted() < -6):
                return "≈" + format(value, ".5E")
            raw = format(value, "f")
            raw = raw.rstrip("0").rstrip(".") if "." in raw else raw
            return raw if len(raw) <= 18 else "≈" + format(value, ".5E")

        values = [number(value) for series in chart.series for value in series.values]
        real = [value for value in values if value is not None]
        if not real:
            raise IngestionError(
                "export_chart", "No measured values are available for this chart.", 422
            )
        low, high = min(Decimal(0), *real), max(Decimal(0), *real)
        if low == high:
            high = low + 1

        def scale(value: Decimal, start: float, end: float) -> float:
            with localcontext() as context:
                context.prec = max(60, len(low.as_tuple().digits), len(high.as_tuple().digits)) + 20
                return start + float((value - low) / (high - low)) * (end - start)

        if chart.kind == "bar":
            left, right = 400, 1120
            zero = scale(Decimal(0), left, right)
            draw.line((zero, 180, zero, plot_height - 80), fill="#72877b", width=2)
            text((left, 150), axis_label(low))
            text((right - 80, 150), axis_label(high))
            for index, label in enumerate(chart.labels):
                y = 195 + index * row_height
                text((45, y), "\n".join(textwrap.wrap(label, 25)))
                for series_index, series in enumerate(chart.series):
                    value = number(series.values[index])
                    position = y + series_index * 26
                    if value is None:
                        text((1140, position), f"{series.name}: Missing")
                        continue
                    end = scale(value, left, right)
                    draw.line(
                        (zero, position + 12, end, position + 12),
                        fill=COLORS[series_index],
                        width=6,
                    )
                    draw.ellipse(
                        (end - 4, position + 8, end + 4, position + 16), fill=COLORS[series_index]
                    )
                    text(
                        (1140, position),
                        str(series.values[index])
                        if len(str(series.values[index])) <= 28
                        else str(series.values[index])[:24] + "…",
                    )
        else:
            left, right, top, bottom = 300, 1450, 210, 690
            draw.rectangle((left, top, right, bottom), outline="#d4dfd8", width=2)
            for step in range(5):
                y = top + step * (bottom - top) / 4
                draw.line((left, y, right, y), fill="#e5ece7")
            text((45, top), axis_label(high))
            text((45, bottom - 20), axis_label(low))
            x_values = [number(label) for label in chart.labels] if chart.kind == "scatter" else []
            x_real = [value for value in x_values if value is not None]
            x_low = min(x_real) if x_real else Decimal(0)
            x_high = max(x_real) if x_real else Decimal(1)
            if x_high == x_low:
                x_high = x_low + 1
            for series_index, series in enumerate(chart.series):
                previous = None
                for index, raw in enumerate(series.values):
                    value = number(raw)
                    if value is None:
                        previous = None
                        continue
                    x = left + index * (right - left) / max(1, len(chart.labels) - 1)
                    if x_values:
                        with localcontext() as context:
                            context.prec = 380
                            x = left + float((x_real[index] - x_low) / (x_high - x_low)) * (
                                right - left
                            )
                    y = scale(value, bottom, top)
                    if previous and chart.kind == "line":
                        draw.line((*previous, x, y), fill=COLORS[series_index], width=3)
                    draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=COLORS[series_index])
                    previous = (x, y)
                text((150 + series_index * 330, 780), series.name, fill=COLORS[series_index])
            text((left, bottom + 20), axis_label(x_low) if x_values else chart.labels[0])
            text((right - 200, bottom + 20), axis_label(x_high) if x_values else chart.labels[-1])
        text(
            (45, plot_height - 40),
            (
                f"{chart.x_label} | {chart.y_label} | All {len(chart.labels)} returned "
                f"positions included; missing values stay missing."
            ),
        )
    for index, note in enumerate(notes):
        text((45, plot_height + index * 29), note)
    info = PngImagePlugin.PngInfo()
    info.add_itxt("ExecPlus evidence", json.dumps(evidence, ensure_ascii=False, default=str))
    info.add_itxt("ExecPlus chart", json.dumps(asdict(chart), ensure_ascii=False))
    output = BytesIO()
    image.save(output, format="PNG", pnginfo=info)
    encoded = output.getvalue()
    if len(encoded) > MAX_EXPORT_BYTES:
        raise IngestionError("export_limit", "This image exceeds 16 MiB.", 422)
    return encoded
