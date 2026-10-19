"""Use case: Turns records from an external platform into a table ready to become an upload.

What it does: Flattens nested records, converts provider dates and writes bounded CSV bytes.
"""

import csv
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO
from typing import Any
from uuid import UUID

from execplus.domain.google_oauth import MAX_CELLS, MAX_COLUMNS, MAX_ROWS
from execplus.domain.ingestion import IngestionError

XERO_DATE = re.compile(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/")
MAX_DEPTH = 3
PROVIDER_ID = re.compile(r"[a-z][a-z0-9_]{1,39}")


@dataclass(frozen=True)
class Source:
    id: str
    label: str
    container: bool = False


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
) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in record.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            if depth >= MAX_DEPTH:
                result[name] = scalar(value)
            else:
                result.update(flatten(value, f"{name}_", depth + 1, counted))
        elif isinstance(value, list):
            if name in counted or any(isinstance(item, dict | list) for item in value):
                result[f"{name}_count"] = str(len(value))
            else:
                result[name] = "; ".join(scalar(item) for item in value)
        else:
            result[name] = scalar(value)
    return result


def records_to_csv(records: list[dict[str, Any]]) -> bytes:
    counted = frozenset(name for record in records for name in structured_lists(record))
    rows = [flatten(record, counted=counted) for record in records]
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
            "That source is larger than ExecPlus can import. Choose a smaller one.",
            413,
        )
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(name, "") for name in columns])
    return output.getvalue().encode("utf-8")


def connector_filename(platform: str, account: str, source: str) -> str:
    parts = [part for part in (platform, account, source) if part]
    label = re.sub(r"[\\/\x00-\x1f]", " ", " - ".join(parts))
    label = " ".join(label.split())[:96] or "Imported data"
    return f"{label}.csv"
