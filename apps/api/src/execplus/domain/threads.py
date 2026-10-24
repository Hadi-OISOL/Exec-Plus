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
    first_metric: str | None = None
    first_aggregation: str | None = None
    first_grouping: tuple[str, ...] = ()

    @property
    def display_title(self) -> str:
        if self.thread.title:
            return chat_title(self.thread.title)
        return context_title(
            self.first_question,
            self.first_metric,
            self.first_aggregation,
            self.first_grouping,
            self.dataset_name,
        )


def chat_title(text: str | None, limit: int = 80) -> str:
    words = " ".join((text or "").split())
    if not words:
        return "New chat"
    return words if len(words) <= limit else words[: limit - 1].rstrip() + "…"


_SUBJECTS = {
    "sum": "Total {}",
    "avg": "Average {}",
    "min": "Lowest {}",
    "max": "Highest {}",
    "count": "Count of {}",
}
TITLE_LIMIT = 60


def _words(name: str) -> str:
    return " ".join(name.replace("_", " ").replace(":", " ").split())


def context_title(
    question: str | None,
    metric: str | None,
    aggregation: str | None,
    grouping: tuple[str, ...],
    dataset_name: str,
) -> str:
    """A stable title built only from the owner's first turn and its executed plan."""
    subject = None
    if aggregation == "rows":
        subject = "Records"
    elif metric and aggregation in _SUBJECTS:
        name = _words(metric)
        subject = _SUBJECTS[aggregation].format(name) if name not in {"", "*"} else "Record count"
    if subject:
        if grouping:
            subject += " by " + " and ".join(_words(item) for item in grouping[:2])
        subject = subject[0].upper() + subject[1:]
        titled = f"{subject} — {_words(dataset_name)}" if dataset_name.strip() else subject
        return chat_title(titled if len(titled) <= TITLE_LIMIT else subject, TITLE_LIMIT)
    words = " ".join((question or "").split()).split(" ")
    return chat_title(" ".join(words[:7]) + ("…" if len(words) > 7 else ""), TITLE_LIMIT)


def valid_chat_title(text: str) -> str:
    title = " ".join(text.split())
    if not 0 < len(title) <= 120 or any(ord(char) < 32 for char in text if char not in "\t\n"):
        raise ValueError("Use a chat name between 1 and 120 characters.")
    return title
