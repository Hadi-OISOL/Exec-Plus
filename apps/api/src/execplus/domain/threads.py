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
    title: str | None = None
    hidden_at: datetime | None = None


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
    job_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ThreadSummary:
    thread: Thread
    first_question: str | None
    last_activity: datetime
    turn_count: int
    dataset_name: str
    filename: str

    @property
    def display_title(self) -> str:
        return chat_title(self.thread.title or self.first_question)


def chat_title(text: str | None) -> str:
    words = " ".join((text or "").split())
    if not words:
        return "New chat"
    return words if len(words) <= 80 else words[:79].rstrip() + "…"


def valid_chat_title(text: str) -> str:
    title = " ".join(text.split())
    if not 0 < len(title) <= 120 or any(ord(char) < 32 for char in text if char not in "\t\n"):
        raise ValueError("Use a chat name between 1 and 120 characters.")
    return title
