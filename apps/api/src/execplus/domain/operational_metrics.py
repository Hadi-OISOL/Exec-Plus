"""Use case: Defines bounded redacted request observations and local alert rules.

What it does: Counts actual outcomes, evaluates exact threshold ratios over complete
minutes, and distinguishes insufficient evidence from a below-threshold result.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID

from execplus.domain.ingestion import IngestionError

CATEGORIES = {
    "ingestion": "File ingestion",
    "exports": "Result exports",
    "analysis": "Analysis requests",
    "queue": "Job submission",
    "other": "Other application requests",
}
METRIC_RETENTION_DAYS = 2
MAX_METRIC_BATCHES = 50_000
MAX_PENDING_BUCKETS = 256


@dataclass(frozen=True)
class RequestObservation:
    minute: datetime
    category: str
    requests: int
    rejected: int
    failed: int
    response_start_ms: int
    maximum_response_start_ms: int

    def __post_init__(self) -> None:
        counts = (
            self.requests,
            self.rejected,
            self.failed,
            self.response_start_ms,
            self.maximum_response_start_ms,
        )
        if (
            self.category not in CATEGORIES
            or self.minute.tzinfo is None
            or self.minute.second
            or self.minute.microsecond
            or any(type(value) is not int or value < 0 for value in counts)
            or not 1 <= self.requests <= 1_000_000_000
            or self.failed + self.rejected > self.requests
            or self.maximum_response_start_ms > self.response_start_ms
            or self.response_start_ms > 1_000_000_000_000_000
        ):
            raise ValueError("Invalid bounded request observation")


@dataclass(frozen=True)
class ObservationBatch:
    id: UUID
    created_at: datetime
    observations: tuple[RequestObservation, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.id, UUID)
            or self.created_at.tzinfo is None
            or not 1 <= len(self.observations) <= MAX_PENDING_BUCKETS
            or len({(item.minute, item.category) for item in self.observations})
            != len(self.observations)
        ):
            raise ValueError("Invalid bounded observation batch")


@dataclass(frozen=True)
class AlertPolicy:
    category: str
    version: int = 0
    enabled: bool = False
    window_minutes: int = 15
    minimum_requests: int = 20
    minimum_failures: int = 3
    failure_basis_points: int = 500
    updated_at: datetime | None = None
    updated_by: UUID | None = None

    def __post_init__(self) -> None:
        integer_fields = (
            self.version,
            self.window_minutes,
            self.minimum_requests,
            self.minimum_failures,
            self.failure_basis_points,
        )
        if (
            self.category not in CATEGORIES
            or type(self.enabled) is not bool
            or any(type(value) is not int for value in integer_fields)
            or self.version < 0
            or not 1 <= self.window_minutes <= 60
            or not 1 <= self.minimum_requests <= 1_000_000
            or not 1 <= self.minimum_failures <= 1_000_000
            or not 0 <= self.failure_basis_points <= 10_000
        ):
            raise IngestionError("invalid_alert_policy", "Choose valid alert thresholds.", 422)


def assess(
    policy: AlertPolicy, observations: tuple[RequestObservation, ...], now: datetime
) -> dict[str, Any]:
    end = now.replace(second=0, microsecond=0)
    start = end - timedelta(minutes=policy.window_minutes)
    selected = tuple(
        value
        for value in observations
        if value.category == policy.category and start <= value.minute < end
    )
    total = sum(value.requests for value in selected)
    failed = sum(value.failed for value in selected)
    rejected = sum(value.rejected for value in selected)
    elapsed = sum(value.response_start_ms for value in selected)
    if not policy.enabled:
        state = "disabled"
    elif total < policy.minimum_requests:
        state = "insufficient_data"
    elif (
        failed >= policy.minimum_failures and failed * 10_000 >= policy.failure_basis_points * total
    ):
        state = "alert"
    else:
        state = "below_threshold"
    with localcontext() as context:
        context.prec = 40
        rate = format(Decimal(failed * 100) / total, ".2f") if total else None
        average = format(Decimal(elapsed) / total, ".3f") if total else None
    return dict(
        category=policy.category,
        title=CATEGORIES[policy.category],
        policy=asdict(policy),
        state=state,
        window_start=start,
        window_end=end,
        requests=total,
        failed=failed,
        rejected=rejected,
        successful=total - failed - rejected,
        failure_rate=dict(numerator=str(failed), denominator=str(total), percent_display=rate),
        mean_response_start_ms=average,
        maximum_response_start_ms=max(
            (value.maximum_response_start_ms for value in selected), default=None
        ),
    )
