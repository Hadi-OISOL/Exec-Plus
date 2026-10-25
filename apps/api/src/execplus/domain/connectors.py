"""Use case: Turns records from an external platform into a table ready to become an upload.

What it does: Flattens nested records, converts provider dates and writes bounded CSV bytes.
"""

import csv
import json
import re
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from typing import Any, BinaryIO
from uuid import UUID

from execplus.domain.google_oauth import MAX_CELLS, MAX_COLUMNS, MAX_ROWS
from execplus.domain.ingestion import IngestionError
from execplus.domain.upload_sessions import safe_label

XERO_DATE = re.compile(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/")
MAX_DEPTH = 3
MAX_IMPORT_BYTES = 20 * 1024 * 1024
PROVIDER_ID = re.compile(r"[a-z][a-z0-9_]{1,39}")
KNOWN_PLATFORMS = (
    ("google_sheets", "Google Sheets"),
    ("quickbooks", "QuickBooks Online"),
    ("xero", "Xero"),
    ("zoho_books", "Zoho Books"),
    ("odoo", "Odoo"),
    ("postgresql", "PostgreSQL database"),
    ("mysql", "MySQL or MariaDB database"),
    ("sqlserver", "Microsoft SQL Server database"),
    ("bigquery", "Google BigQuery"),
)


def source_too_large() -> IngestionError:
    return IngestionError(
        "source_too_large", "That source exceeds the import size limits. Choose a smaller one.", 413
    )


class RecordBuffer(list[dict[str, Any]]):
    def __init__(self) -> None:
        super().__init__()
        self.byte_count = 0
        self.cell_count = 0
        self.columns: set[str] = set()

    def append(self, record: dict[str, Any]) -> None:
        if not isinstance(record, dict):
            raise IngestionError(
                "connector_unexpected_response", "The platform sent an unexpected reply.", 502
            )
        if len(self) >= MAX_ROWS + 1 or len(record) > MAX_COLUMNS:
            raise source_too_large()
        size = 0
        try:
            for chunk in json.JSONEncoder(default=str, ensure_ascii=False).iterencode(record):
                size += len(chunk.encode("utf-8"))
                if self.byte_count + size > MAX_IMPORT_BYTES:
                    raise source_too_large()
        except RecursionError:
            raise source_too_large() from None
        columns = set(flatten(record))
        cells = len(columns)
        if len(self.columns | columns) > MAX_COLUMNS:
            raise source_too_large()
        if cells > MAX_COLUMNS or self.cell_count + cells > MAX_CELLS:
            raise source_too_large()
        self.byte_count += size
        self.cell_count += cells
        self.columns.update(columns)
        super().append(record)

    def extend(self, records: Iterable[dict[str, Any]]) -> None:
        for record in records:
            self.append(record)


@dataclass(frozen=True)
class Source:
    id: str
    label: str
    container: bool = False
    rows: int | None = None


def valid_provider(value: str) -> str:
    if not PROVIDER_ID.fullmatch(value):
        raise IngestionError("unknown_connector", "That data platform is not available.", 404)
    return value


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        match = XERO_DATE.fullmatch(value)
        if match:
            moment = datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
            return (
                moment.date().isoformat()
                if moment.time().isoformat() == "00:00:00"
                else moment.isoformat()
            )
        return value
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return json.dumps(value, default=str, ensure_ascii=False)


def structured_lists(record: dict[str, Any], prefix: str = "", depth: int = 0) -> set[str]:
    names: set[str] = set()
    for key, value in record.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict) and depth < MAX_DEPTH:
            names |= structured_lists(value, f"{name}_", depth + 1)
        elif isinstance(value, list) and any(isinstance(item, dict | list) for item in value):
            names.add(name)
    return names


def flatten(
    record: dict[str, Any],
    prefix: str = "",
    depth: int = 0,
    counted: frozenset[str] = frozenset(),
    *,
    origins: dict[str, tuple[str, ...]] | None = None,
    path: tuple[str, ...] = (),
) -> dict[str, str]:
    origins = {} if origins is None else origins
    result: dict[str, str] = {}

    def put(name: str, value: str, origin: tuple[str, ...]) -> None:
        if name in origins and origins[name] != origin:
            raise IngestionError(
                "ambiguous_source_columns",
                "This source has fields that become the same column name. Rename them first.",
                422,
            )
        origins[name] = origin
        result[name] = value

    for key, value in record.items():
        name = f"{prefix}{key}"
        origin = (*path, key)
        if isinstance(value, dict):
            if depth >= MAX_DEPTH:
                put(name, scalar(value), ("value", *origin))
            else:
                result.update(
                    flatten(value, f"{name}_", depth + 1, counted, origins=origins, path=origin)
                )
        elif isinstance(value, list):
            if name in counted or any(isinstance(item, dict | list) for item in value):
                put(f"{name}_count", str(len(value)), ("count", *origin))
            else:
                put(name, "; ".join(scalar(item) for item in value), ("value", *origin))
        else:
            put(name, scalar(value), ("value", *origin))
    return result


def records_to_csv(records: list[dict[str, Any]]) -> bytes:
    if len(records) > MAX_ROWS:
        raise source_too_large()
    checked = RecordBuffer()
    checked.extend(records)
    counted = frozenset(name for record in records for name in structured_lists(record))
    origins: dict[str, tuple[str, ...]] = {}
    rows = [flatten(record, counted=counted, origins=origins) for record in records]
    if not rows:
        raise IngestionError("empty_source", "That source has no records to import.", 422)
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in row:
            if name not in seen:
                seen.add(name)
                columns.append(name)
    if len(rows) > MAX_ROWS or len(columns) > MAX_COLUMNS or len(rows) * len(columns) > MAX_CELLS:
        raise IngestionError(
            "source_too_large",
            "That source is larger than Syntelio can import. Choose a smaller one.",
            413,
        )
    output = BytesIO()

    def write_row(values: list[str]) -> None:
        line = StringIO()
        csv.writer(line, lineterminator="\n").writerow(values)
        content = line.getvalue().encode("utf-8")
        if output.tell() + len(content) > MAX_IMPORT_BYTES:
            raise source_too_large()
        output.write(content)

    write_row(columns)
    for row in rows:
        write_row([row.get(name, "") for name in columns])
    return output.getvalue()


def _portable(value: Any) -> str:
    if isinstance(value, bytes | bytearray | memoryview):
        raise IngestionError(
            "connector_binary_value", "Leave binary columns out of the import.", 422
        )
    return scalar(value)


def row_limit_exceeded() -> IngestionError:
    return IngestionError(
        "source_too_large",
        "That source exceeds the import row limit. Choose a smaller source.",
        413,
    )


def write_rows_csv(
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    target: BinaryIO,
    *,
    max_rows: int,
    max_bytes: int,
) -> int:
    names = list(columns)
    if not names or any(not name for name in names):
        raise IngestionError("unnamed_source_columns", "Give every column a name.", 422)
    if len(set(names)) != len(names):
        raise IngestionError(
            "ambiguous_source_columns", "Two columns have the same name. Rename one.", 422
        )
    if len(names) > MAX_COLUMNS:
        raise source_too_large()
    encoder = json.JSONEncoder(default=_portable, ensure_ascii=False)
    with tempfile.TemporaryFile() as spool:
        count, nested, counted = 0, False, set[str]()
        for row in rows:
            count += 1
            if count > max_rows:
                raise row_limit_exceeded()
            record = dict(zip(names, row, strict=True))
            if any(isinstance(value, dict | list) for value in record.values()):
                nested = True
                counted |= structured_lists(record)
            spool.write(encoder.encode(list(record.values())).encode("utf-8") + b"\n")
            if spool.tell() > 4 * max_bytes:
                raise source_too_large()
        if not count:
            raise IngestionError("empty_source", "That source has no records to import.", 422)

        def records() -> Iterable[dict[str, str]]:
            spool.seek(0)
            origins: dict[str, tuple[str, ...]] = {}
            for line in spool:
                yield flatten(
                    dict(zip(names, json.loads(line), strict=True)),
                    counted=frozenset(counted),
                    origins=origins,
                )

        header = names
        if nested:
            seen: dict[str, None] = {}
            for flat in records():
                seen.update(dict.fromkeys(flat))
                if len(seen) > MAX_COLUMNS:
                    raise source_too_large()
            header = list(seen)
        start = target.tell()

        def write(values: list[str]) -> None:
            line = StringIO()
            csv.writer(line, lineterminator="\n").writerow(values)
            content = line.getvalue().encode("utf-8")
            if target.tell() - start + len(content) > max_bytes:
                raise source_too_large()
            target.write(content)

        write(header)
        for flat in records():
            write([flat.get(name, "") for name in header])
    return count


def connector_filename(platform: str, account: str, source: str) -> str:
    parts = [part for part in (platform, account, source) if part]
    return f"{safe_label(' - '.join(parts), 96, 'Imported data')}.csv"


def unconfigured_platforms(configured: Iterable[str]) -> list[dict[str, Any]]:
    present = set(configured)
    return [
        dict(
            id=platform,
            label=label,
            kind="unavailable",
            description="Not set up on this server. An administrator must add its settings.",
            fields=[],
            connected=False,
            account="",
            configured=False,
        )
        for platform, label in KNOWN_PLATFORMS
        if platform not in present
    ]
