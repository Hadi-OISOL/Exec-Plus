"""Use case: Defines price-free local product allowances.

What it does: Validates versioned limits and periods without subscriptions,
invented prices or changes to independent global safety limits.
"""

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from execplus.domain.ingestion import IngestionError

STOCK = frozenset({"seats", "datasets", "file_bytes", "storage_bytes", "saved_studies"})
OPERATIONS = frozenset({"processing", "exports", "forecasts", "model_attempts"})
LIMITS = STOCK | OPERATIONS
DEMO = {
    "seats": 5,
    "datasets": 10,
    "file_bytes": 20 * 1024 * 1024,
    "storage_bytes": 200 * 1024 * 1024,
    "saved_studies": 100,
    "processing": 10000,
    "exports": 100,
    "forecasts": 100,
    "model_attempts": 500,
}
CATALOG = {
    "demo": {"name": "Demo", "limits": DEMO},
    "starter": {
        "name": "Starter",
        "limits": {
            **DEMO,
            "seats": 10,
            "datasets": 50,
            "storage_bytes": 1024**3,
            "saved_studies": 500,
            "processing": 50000,
            "exports": 500,
            "forecasts": 500,
            "model_attempts": 2000,
        },
    },
    "growth": {
        "name": "Growth",
        "limits": {
            **DEMO,
            "seats": 30,
            "datasets": 200,
            "storage_bytes": 5 * 1024**3,
            "saved_studies": 2000,
            "processing": 200000,
            "exports": 2000,
            "forecasts": 2000,
            "model_attempts": 10000,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "limits": {
            **DEMO,
            "seats": 100,
            "datasets": 1000,
            "storage_bytes": 20 * 1024**3,
            "saved_studies": 10000,
            "processing": 1000000,
            "exports": 10000,
            "forecasts": 10000,
            "model_attempts": 50000,
        },
    },
}


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False
        ).encode()
    ).hexdigest()


def checked_limits(value: Any) -> dict[str, int | None]:
    if not isinstance(value, dict) or set(value) != LIMITS:
        raise IngestionError("plan_limits", "Declare every supported local allowance.", 422)
    if any(
        item is not None and (type(item) is not int or not 0 <= item <= 10**12)
        for item in value.values()
    ):
        raise IngestionError("plan_limits", "Use nonnegative whole limits or unlimited.", 422)
    return dict(value)


def checked_key(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", value):
        raise IngestionError("plan_key", "Use a short lowercase plan identifier.", 422)
    return value


def checked_period(start: datetime, end: datetime) -> None:
    if (
        any(
            not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None
            for v in (start, end)
        )
        or not 0 < (end - start).total_seconds() <= 366 * 86400
    ):
        raise IngestionError("plan_period", "Use an explicit time window of at most 366 days.", 422)


def require_active(assignment: dict[str, Any] | None, now: datetime) -> None:
    if assignment and not assignment["starts_at"] <= now < assignment["ends_at"]:
        raise IngestionError(
            "plan_expired",
            "This workspace allowance is not active. Ask an administrator to review it.",
            429,
        )


def require_capacity(
    assignment: dict[str, Any] | None, kind: str, used: int, amount: int = 1
) -> None:
    if kind not in LIMITS or type(amount) is not int or amount < 0:
        raise ValueError("Use a registered nonnegative allowance quantity")
    limit = assignment["limits"][kind] if assignment else None
    if limit is not None and used + amount > limit:
        raise IngestionError(
            "plan_limit",
            "This workspace has reached its local allowance. Ask an administrator to review it.",
            429,
        )
