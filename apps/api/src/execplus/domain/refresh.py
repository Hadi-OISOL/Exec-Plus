"""Use case: Defines validated file refresh and descriptive monitoring contracts.

What it does: Makes update semantics, completeness, exact comparisons and alert decisions explicit.
"""

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from io import StringIO
from typing import Any, NoReturn
from uuid import UUID

from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import TableData


@dataclass(frozen=True)
class RefreshFeed:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    owner_id: UUID
    version: int
    source: dict[str, Any]
    interval_hours: int
    freshness_hours: int
    enabled: bool
    next_due: datetime
    last_checked_at: datetime | None
    state: str
    created_at: datetime


@dataclass(frozen=True)
class RefreshCandidate:
    id: UUID
    workspace_id: UUID
    feed_id: UUID
    request_id: UUID
    signature: str
    base_version: int
    created_by: UUID
    status: str
    details: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class Monitor:
    id: UUID
    workspace_id: UUID
    feed_id: UUID
    owner_id: UUID
    name: str
    method: dict[str, Any]
    relevance: int
    enabled: bool
    created_at: datetime


@dataclass(frozen=True)
class Observation:
    id: UUID
    workspace_id: UUID
    monitor_id: UUID
    source_version: int
    source: dict[str, Any]
    status: str
    attempts: int
    claimed_at: datetime | None
    claim_id: UUID | None
    evidence: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class AlertRule:
    id: UUID
    workspace_id: UUID
    monitor_id: UUID
    owner_id: UUID
    operator: str
    threshold: str
    cooldown_minutes: int
    enabled: bool
    last_delivered_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class AlertEvent:
    id: UUID
    workspace_id: UUID
    rule_id: UUID
    observation_id: UUID
    status: str
    read_at: datetime | None
    created_at: datetime


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def fail(code: str, message: str, status: int = 422) -> NoReturn:
    raise IngestionError(code, message, status)


def source_dates(
    as_of: datetime, start: date | None, end: date | None, now: datetime
) -> dict[str, Any]:
    if as_of.tzinfo is None or as_of > now + timedelta(minutes=5):
        fail(
            "invalid_freshness", "Source time must include a timezone and cannot be in the future."
        )
    if (start is None) != (end is None) or (start and end and (start > end or end > as_of.date())):
        fail("invalid_coverage", "Declare both complete-coverage dates, ending by the source date.")
    return dict(
        as_of=as_of.isoformat(),
        coverage_start=str(start) if start else None,
        coverage_end=str(end) if end else None,
    )


def stale(source: dict[str, Any], hours: int, now: datetime) -> bool:
    return now - datetime.fromisoformat(source["as_of"]) > timedelta(hours=hours)


def combine(
    previous: TableData, incoming: TableData, mode: str, keys: list[str], duplicates: str
) -> tuple[TableData, dict[str, int]]:
    if mode not in {"replace", "append", "merge"} or duplicates not in {
        "keep_all",
        "reject",
        "ignore_exact",
    }:
        fail(
            "invalid_update", "Choose replacement, append or merge and an explicit duplicate rule."
        )
    if (
        len(keys) > 4
        or len(set(keys)) != len(keys)
        or any(key not in incoming.headers for key in keys)
    ):
        fail("invalid_keys", "Choose up to four distinct existing key columns.")
    if mode == "replace":
        if keys or duplicates != "keep_all":
            fail(
                "invalid_update",
                "Replacement preserves every row; keyed rules apply to append/merge.",
            )
        return incoming, dict(inserted=len(incoming.rows), updated=0, ignored=0)
    if previous.headers != incoming.headers:
        fail(
            "schema_incompatible",
            "Append/merge requires the same ordered columns. Use reviewed replacement.",
        )
    if mode == "append" and duplicates == "keep_all" and not keys:
        return TableData(previous.headers, previous.rows + incoming.rows), dict(
            inserted=len(incoming.rows), updated=0, ignored=0
        )
    if not keys or duplicates == "keep_all":
        fail(
            "keys_required", "Keyed append/merge needs keys and reject or ignore-exact duplicates."
        )
    positions = [incoming.headers.index(key) for key in keys]

    def key_for(row: tuple[str, ...]) -> tuple[str, ...]:
        key = tuple(row[pos].strip() for pos in positions)
        if not all(key):
            fail("empty_key", "Refresh keys cannot be empty.")
        return key

    rows = list(previous.rows)
    index: dict[tuple[str, ...], int] = {}
    for pos, row in enumerate(rows):
        key = key_for(row)
        if key in index:
            fail("duplicate_base_key", "The active snapshot has duplicate keys; review it first.")
        index[key] = pos
    seen: dict[tuple[str, ...], tuple[str, ...]] = {}
    stats = dict(inserted=0, updated=0, ignored=0)
    for row in incoming.rows:
        key = key_for(row)
        if key in seen:
            if duplicates == "ignore_exact" and seen[key] == row:
                stats["ignored"] += 1
                continue
            fail("duplicate_input_key", "The input has duplicate or conflicting keys.")
        seen[key] = row
        if key not in index:
            index[key] = len(rows)
            rows.append(row)
            stats["inserted"] += 1
        elif mode == "merge" and rows[index[key]] != row:
            rows[index[key]] = row
            stats["updated"] += 1
        elif duplicates == "ignore_exact" and rows[index[key]] == row:
            stats["ignored"] += 1
        else:
            fail("duplicate_key", "An incoming key already exists; choose merge for changes.")
    return TableData(previous.headers, tuple(rows)), stats


def csv_bytes(table: TableData) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(table.headers)
    writer.writerows(table.rows)
    return output.getvalue().encode("utf-8")


def periods(
    source: dict[str, Any], date_column: str | None
) -> tuple[list[dict[str, str]], list[str]]:
    if not date_column:
        return [], []
    month = datetime.fromisoformat(source["as_of"]).date().replace(day=1)
    last = (month - timedelta(days=1)).replace(day=1)
    before = (last - timedelta(days=1)).replace(day=1)
    windows = [dict(start=str(last), end=str(month)), dict(start=str(before), end=str(last))]
    complete = (
        source.get("coverage_start")
        and source.get("coverage_end")
        and source["coverage_start"] <= str(before)
        and source["coverage_end"] >= str(month - timedelta(days=1))
    )
    return windows, [] if complete else ["incomplete_periods"]


def decimal_value(raw: object) -> Decimal:
    if isinstance(raw, bool) or raw is None or len(str(raw)) > 100:
        fail("invalid_threshold", "Use a finite decimal with at most 38 digits.")
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        fail("invalid_threshold", "Use a finite decimal threshold.")
        raise AssertionError from None
    if (
        not value.is_finite()
        or len(value.as_tuple().digits) > 38
        or abs(int(value.as_tuple().exponent)) > 38
    ):
        fail("invalid_threshold", "Use a finite decimal with at most 38 digits and scale.")
    return value


def difference(current: object, previous: object) -> dict[str, str | None]:
    with localcontext() as ctx:
        ctx.prec = 80
        now, before = decimal_value(current), decimal_value(previous)
        delta = now - before
        percent = delta / abs(before) * 100 if before else None
        return dict(delta=str(delta), percent_change=str(percent) if percent is not None else None)


def drivers(
    current: list[list[Any]], previous: list[list[Any]], expected: str
) -> list[dict[str, Any]]:
    with localcontext() as ctx:
        ctx.prec = 80
        left = {
            json.dumps(row[:-1], sort_keys=True): (row[:-1], decimal_value(row[-1] or 0))
            for row in current
        }
        right = {
            json.dumps(row[:-1], sort_keys=True): (row[:-1], decimal_value(row[-1] or 0))
            for row in previous
        }
        values: list[dict[str, Any]] = []
        for key in left.keys() | right.keys():
            label = (left.get(key) or right[key])[0]
            delta = left.get(key, ([], Decimal(0)))[1] - right.get(key, ([], Decimal(0)))[1]
            values.append(dict(segment=label, delta=str(delta)))
        if sum((Decimal(item["delta"]) for item in values), Decimal(0)) != Decimal(expected):
            fail(
                "driver_mismatch",
                "Segment contributions did not reconcile to the executed total.",
                409,
            )
        values.sort(key=lambda item: (-abs(Decimal(item["delta"])), str(item["segment"])))
        if len(values) > 10:
            rest = sum((Decimal(item["delta"]) for item in values[10:]), Decimal(0))
            values = [*values[:10], dict(segment=["Remaining segments"], delta=str(rest))]
        return values


def breached(value: object, operator: str, threshold: str) -> bool:
    a, b = decimal_value(value), decimal_value(threshold)
    if operator not in {"gt", "gte", "lt", "lte"}:
        fail("invalid_operator", "Choose gt, gte, lt or lte.")
    return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[operator]
