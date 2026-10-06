"""Use case: Defines revocable internal staff access and private customer support records.

What it does: Bounds public support conversations and validates explicit state changes.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from execplus.domain.ingestion import IngestionError

STAFF_ROLES = frozenset({"admin", "support"})
SUPPORT_STATUSES = frozenset(
    {"open", "triaged", "in_progress", "waiting_on_customer", "escalated", "resolved"}
)
SUPPORT_FEATURES = frozenset(
    {
        "upload",
        "profile",
        "dashboard",
        "question",
        "knowledge",
        "report",
        "onboarding",
        "forecast",
        "refresh",
        "account",
        "other",
    }
)
SUPPORT_CATEGORIES = frozenset(
    {"question", "problem", "incorrect", "slow", "missing_feature", "other"}
)
MAX_SUPPORT_EVENTS = 200
JOB_FAILURE_CODES = frozenset(
    {
        "cancelled",
        "source_changed",
        "unauthorized",
        "timeout",
        "queue_expired",
        "interrupted_before_start",
        "interrupted",
        "lease_lost",
        "job_budget",
        "execution_failed",
    }
)


@dataclass(frozen=True)
class StaffGrant:
    user_id: UUID
    role: str
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class StaffAudit:
    id: UUID
    actor_id: UUID | None
    action: str
    origin: str
    outcome: str
    created_at: datetime
    workspace_id: UUID | None = None
    resource_id: UUID | None = None


@dataclass(frozen=True)
class SupportTicket:
    id: UUID
    workspace_id: UUID
    requester_id: UUID
    subject: str
    description: str
    feature: str
    category: str
    status: str
    priority: str
    version: int
    created_at: datetime
    updated_at: datetime
    assignee_id: UUID | None = None
    feedback_id: UUID | None = None
    job_id: UUID | None = None
    resolved_at: datetime | None = None


@dataclass(frozen=True)
class SupportEvent:
    id: UUID
    workspace_id: UUID
    ticket_id: UUID
    sequence: int
    actor_id: UUID
    actor_role: str
    kind: str
    body: str
    status: str
    priority: str
    assignee_id: UUID | None
    created_at: datetime


def support_text(value: str, limit: int, *, optional: bool = False) -> str:
    if not isinstance(value, str):
        raise IngestionError("invalid_support", "Use plain text for the support request.", 422)
    result = value.strip()
    if (
        len(result) > limit
        or (not optional and not result)
        or any(ord(character) < 32 and character not in "\n\t" for character in result)
    ):
        raise IngestionError("invalid_support", "Use bounded text without control characters.", 422)
    return result


def support_transition(current: str, target: str, *, reopen: bool = False) -> None:
    if target not in SUPPORT_STATUSES:
        raise IngestionError("invalid_support_status", "Choose a supported support status.", 422)
    if reopen:
        valid = current == "resolved" and target == "open"
    else:
        valid = current != "resolved" and current != target
    if not valid:
        raise IngestionError(
            "invalid_support_transition",
            "Use an available status change or explicitly reopen.",
            409,
        )
