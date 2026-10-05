"""Use case: Stops superseded discovery requests when their browser disconnects.

What it does: Exercises ASGI disconnect messages, completed work and task cleanup
without extra queries.
"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.requests import Request

from execplus.application.services.discovery import DiscoveryBrief
from execplus.presentation.routes import analytics


class IncomingMessages:
    def __init__(self):
        self.messages = asyncio.Queue()
        self.receives = 0
        self.request = Request(
            {"type": "http", "method": "GET", "path": "/discovery", "headers": []},
            self.receive,
        )

    async def receive(self):
        self.receives += 1
        return await self.messages.get()


async def call_route(request):
    return await analytics.discovery(
        uuid4(), uuid4(), uuid4(), SimpleNamespace(), SimpleNamespace(), request
    )


@pytest.mark.asyncio
async def test_already_disconnected_request_never_starts_discovery(monkeypatch):
    incoming = IncomingMessages()
    await incoming.messages.put({"type": "http.disconnect"})

    async def unexpected(*args):
        pytest.fail("Disconnected request must not begin snapshot work")

    monkeypatch.setattr(analytics, "discover", unexpected)
    response = await call_route(incoming.request)
    assert response.status_code == 499
    assert response.body == b""


@pytest.mark.asyncio
async def test_asgi_disconnect_cancels_inflight_work_and_prevents_later_queries(monkeypatch):
    incoming = IncomingMessages()
    first_finished = asyncio.Event()
    cancellation_received = asyncio.Event()
    released = asyncio.Event()
    executed = []

    async def controlled_discovery(*args):
        executed.append("completed_receipt")
        first_finished.set()
        try:
            await asyncio.Event().wait()
            executed.append("must_not_execute")
        except asyncio.CancelledError:
            cancellation_received.set()
            raise
        finally:
            released.set()

    monkeypatch.setattr(analytics, "_DISCONNECT_POLL_SECONDS", 0.001)
    monkeypatch.setattr(analytics, "discover", controlled_discovery)
    running = asyncio.create_task(call_route(incoming.request))
    await asyncio.wait_for(first_finished.wait(), timeout=1)
    await incoming.messages.put({"type": "http.disconnect"})
    response = await asyncio.wait_for(running, timeout=1)
    assert response.status_code == 499
    assert cancellation_received.is_set() and released.is_set()
    assert executed == ["completed_receipt"]
    receives = incoming.receives
    await asyncio.sleep(0.01)
    assert incoming.receives == receives


@pytest.mark.asyncio
async def test_complete_discovery_stops_the_disconnect_watcher(monkeypatch):
    incoming = IncomingMessages()

    async def finished(*args):
        return DiscoveryBrief({"version": "discovery-v1"}, ())

    monkeypatch.setattr(analytics, "_DISCONNECT_POLL_SECONDS", 0.001)
    monkeypatch.setattr(analytics, "discover", finished)
    result = await call_route(incoming.request)
    assert result == {"version": "discovery-v1", "findings": []}
    receives = incoming.receives
    await asyncio.sleep(0.01)
    assert incoming.receives == receives


@pytest.mark.asyncio
async def test_completed_result_wins_when_disconnect_finishes_in_same_tick(monkeypatch):
    incoming = IncomingMessages()

    async def finished(*args):
        return DiscoveryBrief({"retained": "completed_evidence"}, ())

    async def disconnected(*args):
        return None

    monkeypatch.setattr(analytics, "discover", finished)
    monkeypatch.setattr(analytics, "_wait_for_disconnect", disconnected)
    result = await call_route(incoming.request)
    assert result == {"retained": "completed_evidence", "findings": []}


@pytest.mark.asyncio
async def test_application_failure_is_preserved_and_watcher_is_cleaned_up(monkeypatch):
    incoming = IncomingMessages()

    async def failed(*args):
        raise ValueError("Application failure")

    monkeypatch.setattr(analytics, "_DISCONNECT_POLL_SECONDS", 0.001)
    monkeypatch.setattr(analytics, "discover", failed)
    with pytest.raises(ValueError, match="Application failure"):
        await call_route(incoming.request)
    receives = incoming.receives
    await asyncio.sleep(0.01)
    assert incoming.receives == receives


@pytest.mark.asyncio
async def test_outer_request_cancellation_joins_computation_and_watcher(monkeypatch):
    incoming = IncomingMessages()
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def running(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    monkeypatch.setattr(analytics, "_DISCONNECT_POLL_SECONDS", 0.001)
    monkeypatch.setattr(analytics, "discover", running)
    request = asyncio.create_task(call_route(incoming.request))
    await asyncio.wait_for(started.wait(), timeout=1)
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    assert cleaned.is_set()
    receives = incoming.receives
    await asyncio.sleep(0.01)
    assert incoming.receives == receives
