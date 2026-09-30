"""Use case: Defines multi-turn conversation state using structured references.

What it does: Records each turn's question and a reference to its executed query
or explanation, never raw prior prompt text, so later turns are resolved from
structured facts rather than a growing transcript.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Thread:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    upload_id: UUID
    owner_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ThreadTurn:
    id: UUID
    thread_id: UUID
    question: str
    kind: str
    query_id: UUID | None
    message: str | None
    created_at: datetime
    model_route: str | None = None
    request_id: UUID | None = None
    status: str = "complete"
    evidence: dict[str, object] = field(default_factory=dict)
