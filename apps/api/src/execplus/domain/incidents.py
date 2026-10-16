"""Use case: Describes redacted internal incidents and safe operational occurrences.

What it does: Restricts persisted diagnostics to fixed codes, opaque occurrence IDs,
counts and timestamps, with explicit optimistic acknowledgement and resolution.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID, uuid4

from execplus.domain.ingestion import IngestionError

INCIDENT_CODES = {
    "http_failed": ("api", "A server request failed", "error"),
    "job_failed": ("jobs", "An analysis job failed", "error"),
    "job_timeout": ("jobs", "An analysis job exceeded its time limit", "warning"),
    "job_interrupted": ("jobs", "An analysis job was interrupted", "error"),
    "job_expired": ("jobs", "A queued analysis expired", "warning"),
    "refresh_failed": ("refresh", "A staged refresh could not activate", "error"),
    "report_failed": ("reports", "A scheduled report failed", "error"),
    "queue_overflow": ("collector", "The request-error queue overflowed", "warning"),
    "collector_recovered": ("collector", "Incident storage recovered after an outage", "warning"),
    "retention_capacity": (
        "collector",
        "Incident deduplication storage reached its bound",
        "error",
    ),
}
SOURCE_KINDS = frozenset({"http", "job", "refresh", "report", "collector"})
INCIDENT_STATES = frozenset({"open", "acknowledged", "resolved"})
RETENTION_DAYS = 30
MAX_OCCURRENCES = 100_000
COLLECT_BATCH = 500


@dataclass(frozen=True)
class IncidentOccurrence:
    source_kind: str
    source_id: UUID
    occurred_at: datetime
    code: str
    count: int = 1

    def __post_init__(self) -> None:
        if (
            self.source_kind not in SOURCE_KINDS
            or self.code not in INCIDENT_CODES
            or not isinstance(self.source_id, UUID)
            or self.occurred_at.tzinfo is None
            or type(self.count) is not int
            or not 1 <= self.count <= 1_000_000
        ):
            raise ValueError("Invalid redacted incident occurrence")


@dataclass(frozen=True)
class Incident:
    id: UUID
    code: str
    component: str
    severity: str
    status: str
    version: int
    occurrences: int
    first_seen: datetime
    last_seen: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    def public(self) -> dict[str, object]:
        return {**self.__dict__, "title": INCIDENT_CODES[self.code][1]}


def observe(previous: Incident | None, occurrence: IncidentOccurrence) -> Incident:
    if previous is None:
        component, _, severity = INCIDENT_CODES[occurrence.code]
        return Incident(
            uuid4(),
            occurrence.code,
            component,
            severity,
            "open",
            1,
            occurrence.count,
            occurrence.occurred_at,
            occurrence.occurred_at,
        )
    return replace(
        previous,
        version=previous.version + 1,
        occurrences=previous.occurrences + occurrence.count,
        first_seen=min(previous.first_seen, occurrence.occurred_at),
        last_seen=max(previous.last_seen, occurrence.occurred_at),
        status="open" if previous.status == "resolved" else previous.status,
        acknowledged_at=None if previous.status == "resolved" else previous.acknowledged_at,
        resolved_at=None,
    )


def transition(value: Incident, expected: int, status: str, now: datetime) -> Incident:
    if expected != value.version:
        raise IngestionError("incident_conflict", "This incident changed. Reload it first.", 409)
    if status not in {"acknowledged", "resolved"} or value.status == "resolved":
        raise IngestionError("incident_transition", "Choose an open incident to update.", 422)
    if status == value.status:
        raise IngestionError("incident_transition", "This incident is already acknowledged.", 422)
    return replace(
        value,
        status=status,
        version=value.version + 1,
        acknowledged_at=now if status == "acknowledged" else value.acknowledged_at,
        resolved_at=now if status == "resolved" else None,
    )
