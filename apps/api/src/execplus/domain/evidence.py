"""Use case: Encodes exact execution evidence for durable replay and display.

What it does: Preserves scalar types, immutable sources and result checksums without float coercion.
"""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

from execplus.domain.models import QueryPlan, QueryResult, Scalar


def scalar_record(value: Scalar) -> dict[str, object]:
    kind = type(value).__name__
    encoded: object = value
    if isinstance(value, Decimal):
        encoded = str(value)
    elif isinstance(value, date | datetime):
        encoded = value.isoformat()
    return {"type": kind, "value": encoded}


def scalar_from_record(record: dict[str, object]) -> Scalar:
    kind, value = record["type"], record["value"]
    if kind == "Decimal":
        return Decimal(str(value))
    if kind == "date":
        return date.fromisoformat(str(value))
    if kind == "datetime":
        return datetime.fromisoformat(str(value))
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise ValueError("Invalid scalar evidence")


def result_evidence(result: QueryResult) -> dict[str, object]:
    body = {
        "columns": list(result.columns),
        "rows": [[scalar_record(value) for value in row] for row in result.rows],
        "records_analyzed": result.records_analyzed,
    }
    checksum = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {**body, "checksum": checksum}


def receipt(
    plan: QueryPlan,
    sources: tuple[dict[str, str], ...],
    result: QueryResult | None,
    *,
    row_query: bool = False,
) -> dict[str, object]:
    evidence = result_evidence(result) if result is not None else {}
    body: dict[str, object] = {
        "version": "execution-v1",
        "sources": list(sources),
        "parameters": [scalar_record(value) for value in plan.params],
        "outcome": "executed" if result is not None else "failed",
        "result_checksum": evidence.get("checksum"),
        "answer": None if row_query else evidence,
    }
    if result is not None and result.matched_records is not None:
        body["matched_records"] = result.matched_records
    return body
