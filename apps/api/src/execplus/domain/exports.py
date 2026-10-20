"""Use case: Describes exact portable results and trusted export figures.

What it does: Keeps original scalar types, source-backed report text and bounded
chart specifications separate from file libraries and user-supplied markup.
"""

import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from execplus.domain.ingestion import IngestionError
from execplus.domain.models import Scalar
from execplus.domain.pdf_exports import PdfDocument, validate_report_time

MAX_EXPORT_CELLS = 200_000
MAX_EXPORT_BYTES = 16 * 1024 * 1024
MAX_EXPORT_CHARACTERS = 2_000_000


@dataclass(frozen=True, slots=True)
class ExportTable:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Scalar, ...], ...]


@dataclass(frozen=True, slots=True)
class ExportSeries:
    name: str
    values: tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class ExportChart:
    kind: str
    title: str
    x_label: str = ""
    y_label: str = ""
    labels: tuple[str, ...] = ()
    series: tuple[ExportSeries, ...] = ()
    nodes: tuple[dict[str, Any], ...] = ()
    edges: tuple[dict[str, Any], ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExportContent:
    document: PdfDocument
    tables: tuple[ExportTable, ...]
    charts: tuple[ExportChart, ...] = ()


@dataclass(frozen=True, slots=True)
class ExportDownload:
    filename: str
    content: bytes
    media_type: str


def exact_text(value: Scalar) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value.isoformat() if isinstance(value, date | datetime) else str(value)


def cell_type(value: Scalar) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, Decimal):
        return "decimal"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    return "string"


def validate_export(content: ExportContent) -> None:
    validate_report_time(content.document.generated_at)
    cells = 0
    characters = len(json.dumps(asdict(content.document), default=str, ensure_ascii=False))
    for table in content.tables:
        if not table.columns or len(table.columns) > 100:
            raise IngestionError("export_limit", "A result export supports up to 100 columns.", 422)
        cells += len(table.columns) * (len(table.rows) + 1)
        for row in (table.columns, *table.rows):
            if len(row) != len(table.columns):
                raise IngestionError("export_integrity", "The returned table is inconsistent.", 409)
            for value in row:
                if (isinstance(value, float) and not math.isfinite(value)) or (
                    isinstance(value, Decimal) and not value.is_finite()
                ):
                    raise IngestionError(
                        "export_integrity", "Non-finite values cannot be exported as numbers.", 409
                    )
                text = exact_text(value)
                try:
                    text.encode("utf-8")
                except UnicodeEncodeError as error:
                    raise IngestionError(
                        "export_text", "This text contains an invalid Unicode sequence.", 422
                    ) from error
                characters += len(text)
    if cells > MAX_EXPORT_CELLS or characters > MAX_EXPORT_CHARACTERS:
        raise IngestionError(
            "export_limit",
            "This result exceeds the 200,000-cell or two-million-character export limit.",
            422,
        )
