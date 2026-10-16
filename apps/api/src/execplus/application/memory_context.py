"""Use case: Tracks the personal-memory revision used by one private conversation.

What it does: Carries only a revision reference to publication checks, never remembered text.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from execplus.domain.agent_memory import AgentMemory


@dataclass
class MemoryUse:
    reference: dict[str, Any] | None = None


_current: ContextVar[MemoryUse | None] = ContextVar("agent_memory_use", default=None)


@contextmanager
def capture_memory() -> Iterator[MemoryUse]:
    usage = MemoryUse()
    token = _current.set(usage)
    try:
        yield usage
    finally:
        _current.reset(token)


def remember_usage(memory: AgentMemory | None) -> None:
    usage = _current.get()
    if usage is not None and memory is not None and memory.context():
        usage.reference = memory.reference()
