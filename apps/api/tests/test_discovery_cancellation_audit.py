"""Use case: Preserves query evidence when a browser abandons automatic discovery.

What it does: Checks cancellation stops later queries and records the interrupted execution.
"""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select

from execplus.application.services.discovery import discover
from execplus.infrastructure.persistence import schema as s
from test_discovery import setup


@pytest.mark.parametrize("cancel_at", [1, 7])
def test_abandoned_discovery_retains_failed_receipt_and_stops(integration, monkeypatch, cancel_at):
    env = integration
    headers, wid, root, _ = setup(env)
    service = env.runtime.analytics
    actor = env.runtime.identity.authenticate(headers["Authorization"].removeprefix("Bearer "))
    original = service.executor.execute
    calls = 0

    async def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == cancel_at:
            raise asyncio.CancelledError
        return await original(*args, **kwargs)

    monkeypatch.setattr(service.executor, "execute", interrupted)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            discover(service, actor, UUID(wid), UUID(root.split("/")[4]), UUID(root.split("/")[6]))
        )
    assert calls == cancel_at
    with env.engine.connect() as connection:
        receipts = list(connection.execute(select(s.query_executions.c.receipt)).scalars())
        failed_events = connection.execute(
            select(s.audit_events).where(s.audit_events.c.action == "query.failed")
        ).all()
    assert len(receipts) == cancel_at
    failed = [item for item in receipts if item["outcome"] == "failed"]
    assert len(failed) == len(failed_events) == 1
    assert failed[0]["answer"] == {}
    assert failed[0]["sources"][0]["upload_id"] == root.split("/")[6]
