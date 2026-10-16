"""Use case: Keeps object reads outside workspace locks without stale-policy publication.

What it does: Mutates access during real source reads and verifies the final locked
check rejects the old snapshot for planning, calculation and saved replay.
"""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_dataset_access import fixture, query


@pytest.mark.parametrize("operation", ["description", "query", "retained", "replay", "recheck"])
def test_object_reads_release_workspace_lock_and_recheck_policy_epoch(
    integration, monkeypatch, operation
):
    env = integration
    _, owner, member, actor, wid, did, uid, root, _, raw = fixture(env)
    original = query(env, member, root).json()
    query_id = UUID(original["lineage"]["query_id"])
    with env.engine.connect() as connection:
        receipt = connection.execute(
            select(s.query_executions.c.receipt).where(s.query_executions.c.id == query_id)
        ).scalar_one()
    source = receipt["sources"][0]
    analytics = env.runtime.analytics
    read = analytics.storage.read
    changed = False

    def change_during_read(upload):
        nonlocal changed
        content = read(upload)
        if not changed:
            changed = True
            with env.engine.begin() as connection:
                connection.execute(
                    select(s.workspaces.c.id)
                    .where(s.workspaces.c.id == UUID(wid))
                    .with_for_update(nowait=True)
                ).scalar_one()
            env.runtime.access_policies.save(owner, UUID(wid), UUID(did), 1, True, raw["grants"])
        return content

    monkeypatch.setattr(analytics.storage, "read", change_during_read)
    with pytest.raises((IngestionError, ClarificationRequiredError)):
        if operation == "description":
            analytics.descriptive_snapshot(actor, UUID(wid), UUID(did), UUID(uid))
        elif operation == "query":
            analytics._context(actor, UUID(wid), UUID(did), UUID(uid))
        elif operation == "retained":
            analytics.context_at(actor, UUID(wid), source)
        elif operation == "replay":
            asyncio.run(analytics.replay(actor, UUID(wid), query_id))
        else:
            analytics.recheck_description(actor, UUID(wid), UUID(did), UUID(uid), (source,))
    assert changed
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions.c.id)).all() == [(query_id,)]
        assert connection.execute(
            select(s.query_executions.c.receipt).where(s.query_executions.c.id == query_id)
        ).scalar_one() == receipt
