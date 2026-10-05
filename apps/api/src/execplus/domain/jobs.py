"""Use case: Defines bounded durable work and truthful execution activity.

What it does: Validates job states, budgets and lease ownership without infrastructure dependencies.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from execplus.domain.ingestion import IngestionError


class JobState(str, Enum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "expired"})
ACTIVE_STATES = frozenset({"claimed", "running", "cancelling"})


class JobStage(str, Enum):
    QUEUED = "queued"
    AUTHORIZING = "authorizing"
    SOURCE = "checking_source"
    PLANNING = "planning"
    VALIDATING = "validating_plan"
    QUERY = "executing_query"
    RETRIEVAL = "retrieving_documents"
    VERIFYING = "verifying_evidence"
    FINISHED = "finished"


class EventStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ResourceBudget:
    wall_seconds: int = 100
    input_bytes: int = 20 * 1024 * 1024
    max_steps: int = 4
    max_model_calls: int = 3
    max_provider_attempts: int = 7
    max_queries: int = 1
    max_retrievals: int = 1

    def __post_init__(self) -> None:
        bounds = (
            (self.wall_seconds, 1, 120),
            (self.input_bytes, 1, 20 * 1024 * 1024),
            (self.max_steps, 1, 4),
            (self.max_model_calls, 0, 3),
            (self.max_provider_attempts, 0, 7),
            (self.max_queries, 0, 1),
            (self.max_retrievals, 0, 1),
        )
        if any(type(value) is not int or not low <= value <= high for value, low, high in bounds):
            raise IngestionError("invalid_job_budget", "The work exceeds supported limits.", 422)


@dataclass(frozen=True)
class Job:
    id: UUID
    workspace_id: UUID
    thread_id: UUID
    turn_id: UUID
    owner_id: UUID
    request_id: UUID
    payload_hash: str
    status: str
    priority: int
    attempts: int
    max_attempts: int
    budget: dict[str, Any]
    sources: list[dict[str, str]]
    plan: dict[str, Any]
    result_refs: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    lease_id: UUID | None = None
    lease_expires_at: datetime | None = None
    cancel_requested: bool = False
    failure_code: str | None = None
    current_stage: str | None = None
    event_sequence: int = 0


@dataclass(frozen=True)
class JobAttempt:
    id: UUID
    workspace_id: UUID
    job_id: UUID
    number: int
    status: str
    started_at: datetime
    heartbeat_at: datetime
    lease_expires_at: datetime
    finished_at: datetime | None = None
    failure_code: str | None = None


@dataclass(frozen=True)
class JobLease:
    workspace_id: UUID
    job_id: UUID
    attempt_id: UUID
    expires_at: datetime


@dataclass(frozen=True)
class JobEvent:
    id: UUID
    workspace_id: UUID
    job_id: UUID
    sequence: int
    stage: str
    status: str
    created_at: datetime


def transition(job: Job, state: JobState) -> None:
    allowed = {
        "queued": {"claimed", "cancelled", "expired", "failed"},
        "claimed": {"running", "queued", "cancelling", "cancelled", "expired", "failed"},
        "running": {"cancelling", "succeeded", "failed", "cancelled", "expired"},
        "cancelling": {"cancelled", "failed", "expired"},
    }
    if state.value not in allowed.get(job.status, set()):
        raise IngestionError("job_conflict", "This work has already changed state.", 409)


def owns_lease(job: Job, lease: JobLease, now: datetime) -> bool:
    return (
        job.workspace_id == lease.workspace_id
        and job.id == lease.job_id
        and job.lease_id == lease.attempt_id
        and job.status in ACTIVE_STATES
        and job.lease_expires_at is not None
        and job.lease_expires_at > now
    )
