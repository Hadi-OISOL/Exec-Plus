"""Use case: Gives explicit local operation retries stable opaque identifiers.

What it does: Carries no payload or credentials and never changes authorization.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID, uuid4, uuid5

from execplus.application.usage_context import current_usage
from execplus.domain.ingestion import IngestionError

_request: ContextVar[UUID | None] = ContextVar("plan_request_id", default=None)


@contextmanager
def plan_request_context(raw: str | None) -> Iterator[None]:
    try:
        value = UUID(raw) if raw is not None else None
    except (ValueError, TypeError, AttributeError):
        raise IngestionError(
            "idempotency_key", "Use an opaque UUID Idempotency-Key.", 422
        ) from None
    token = _request.set(value)
    try:
        yield
    finally:
        _request.reset(token)


def operation_id(kind: str, fallback: UUID | None = None, *, derived: str = "") -> UUID:
    explicit = _request.get()
    current = current_usage(required=False)
    parent = explicit or (current.operation_id if current else None)
    if parent:
        return uuid5(parent, kind + (":" + derived if derived else ""))
    return fallback or uuid4()
