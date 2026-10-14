"""Use case: Closes the gap between pattern computation and conversation publication.

What it does: Checks refresh, meaning and cancellation races preserve private evidence safely.
"""

import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from execplus.infrastructure.persistence import schema as s
from test_conversation_jobs import job_path, process, submit
from test_pattern_conversations import setup
from test_patterns_integration import sample
from test_refresh import setup as refresh_setup
from test_understanding import confirm, context
from test_workspace_integration import upload


def test_legacy_pattern_publish_failure_closes_turn_without_exposing_unpublished_answer(
    integration, monkeypatch
):
    env = integration
    owner, _, root, path = setup(env)
    router = env.runtime.intent_router
    original = router.ask

    def change_meaning():
        meaning = context(env, owner, root)
        meaning["definition"]["description"] = "Changed just before publication"
        assert confirm(env, owner, root, meaning).status_code == 201

    async def changed_after_calculation(*args, **kwargs):
        answer = await original(*args, **kwargs)
        await asyncio.to_thread(change_meaning)
        return answer

    monkeypatch.setattr(router, "ask", changed_after_calculation)
    response = env.client.post(
        path + "/ask",
        headers=owner,
        json={"question": "Find patterns", "request_id": str(uuid4())},
    )
    assert response.status_code == 409, response.text
    with env.engine.connect() as connection:
        turn = connection.execute(select(s.thread_turns)).mappings().one()
        queries = connection.execute(select(s.query_executions)).mappings().all()
    assert turn["status"] == "failed"
    assert turn["query_id"] is None and turn["evidence"] == {}
    assert len(queries) == 1 and queries[0]["aggregation"] == "analysis"
    assert queries[0]["receipt"]["outcome"] == "executed"
    assert env.client.get(path + f"/turns/{turn['id']}/answer", headers=owner).json() is None


def test_accepted_refresh_change_at_publication_gets_source_changed_status(
    integration, monkeypatch
):
    env = integration
    owner, _, wid, did, uid, _, feed = refresh_setup(env, sample())
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}"
    replacement = upload(env, owner, wid, did, sample()).json()["id"]
    job = submit(env, owner, path, "Find patterns")
    original = env.runtime.jobs._finish

    def replaced_before_publication(*args, **kwargs):
        with env.runtime.refresh.uow() as repo:
            current = repo.refresh_feed(UUID(wid), UUID(feed["id"]))
            repo.set_refresh_feed(
                replace(current, source={**current.source, "upload_id": replacement})
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(env.runtime.jobs, "_finish", replaced_before_publication)
    assert process(env) == {"processed": 1}
    body = env.client.get(job_path(job), headers=owner).json()
    assert body["status"] == "failed" and body["failure_code"] == "source_changed", body
    answer = env.client.get(job_path(job) + "/result", headers=owner).json()
    assert answer["answer"] is None
    with env.engine.connect() as connection:
        turn = connection.execute(select(s.thread_turns)).mappings().one()
    assert turn["query_id"] is None and turn["evidence"] == {}


@pytest.mark.asyncio
async def test_pattern_cancellation_wins_after_calculation_and_keeps_private_receipt(
    integration, monkeypatch
):
    env = integration
    owner, wid, _, path = setup(env)
    job = submit(env, owner, path, "Find patterns")
    original = env.runtime.jobs._finish

    def cancelled_before_publication(*args, **kwargs):
        actor = env.runtime.identity.authenticate(owner["Authorization"].removeprefix("Bearer "))
        env.runtime.jobs.cancel(actor, UUID(wid), UUID(job["id"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(env.runtime.jobs, "_finish", cancelled_before_publication)
    await env.runtime.jobs.process()
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "cancelled"
    assert env.client.get(job_path(job) + "/result", headers=owner).json()["answer"] is None
    with env.engine.connect() as connection:
        turn = connection.execute(select(s.thread_turns)).mappings().one()
        query = connection.execute(select(s.query_executions)).mappings().one()
    assert turn["evidence"] == {} and turn["query_id"] is None
    assert query["aggregation"] == "analysis" and query["receipt"]["outcome"] == "executed"
