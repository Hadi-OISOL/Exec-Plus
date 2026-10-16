"""Use case: Attributes provider calls to one authorized workspace operation.

What it does: Carries only identifiers and a fixed operation code, rejects confused
nested scopes, and restores the previous context after cancellation or failure.
"""

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import signature
from typing import ParamSpec, TypeVar
from uuid import UUID, uuid4

from execplus.domain.ingestion import IngestionError, User
from execplus.domain.usage_metering import UsageAttribution

_current: ContextVar[UsageAttribution | None] = ContextVar("usage_attribution", default=None)
P = ParamSpec("P")
R = TypeVar("R")


@contextmanager
def usage_scope(attribution: UsageAttribution) -> Iterator[UsageAttribution]:
    previous = _current.get()
    if previous is not None:
        if (
            previous.workspace_id != attribution.workspace_id
            or previous.actor_id != attribution.actor_id
        ):
            raise IngestionError("usage_attribution", "Model usage has conflicting ownership.", 409)
        yield previous
        return
    token = _current.set(attribution)
    try:
        yield attribution
    finally:
        _current.reset(token)


def current_usage(*, required: bool = True) -> UsageAttribution | None:
    attribution = _current.get()
    if required and attribution is None:
        raise IngestionError(
            "usage_attribution", "Model usage requires an authorized operation.", 503
        )
    return attribution


def attributed_operation(
    operation: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorate(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        parameters = signature(function)

        @wraps(function)
        async def call(*args: P.args, **kwargs: P.kwargs) -> R:
            arguments = parameters.bind(*args, **kwargs).arguments
            actor = arguments.get("actor")
            workspace_id = arguments.get("workspace_id", arguments.get("wid"))
            turn = arguments.get("turn")
            if not isinstance(actor, User) or not isinstance(workspace_id, UUID):
                raise IngestionError(
                    "usage_attribution", "Model usage requires an authorized operation.", 503
                )
            attribution = UsageAttribution(
                workspace_id,
                actor.id,
                turn.id if turn is not None else uuid4(),
                operation,
            )
            with usage_scope(attribution):
                return await function(*args, **kwargs)

        return call

    return decorate
