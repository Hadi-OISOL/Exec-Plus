"""Use case: Publishes actual execution activity without coupling use cases to a worker.

What it does: Carries an optional request-local progress port through existing trusted operations.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from execplus.application.ports import ExecutionProgress
from execplus.domain.analysis_plan import AnalysisPlan
from execplus.domain.jobs import EventStatus, JobStage

_current: ContextVar[ExecutionProgress | None] = ContextVar("execution_progress", default=None)


@contextmanager
def execution_progress(sink: ExecutionProgress) -> Iterator[None]:
    token = _current.set(sink)
    try:
        yield
    finally:
        _current.reset(token)


async def activity(stage: JobStage, status: EventStatus) -> None:
    sink = _current.get()
    if sink is not None:
        await sink.emit(stage, status)


async def planned(plan: AnalysisPlan) -> None:
    sink = _current.get()
    if sink is not None:
        await sink.planned(plan)


async def model_call() -> None:
    sink = _current.get()
    if sink is not None:
        await sink.model_call()


async def provider_attempt() -> None:
    sink = _current.get()
    if sink is not None:
        await sink.provider_attempt()
