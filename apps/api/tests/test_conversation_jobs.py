"""Use case: Verifies durable conversations against real PostgreSQL and object storage.

What it does: Covers privacy, idempotency, fencing, cancellation, recovery and compatibility.
"""

import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update

from execplus.application.job_worker import work
from execplus.application.services.jobs import JobService
from execplus.infrastructure.persistence import schema as s
from execplus.presentation.routes.threads import get_thread_service
from test_conversational_explorer import ScriptedModel
from test_unified_conversation import MIXED, NUMERICAL, ask, document, setup
from test_workspace_integration import accept, identity, invite, workspace


def prepared(env, *responses, primary=None):
    owner, wid, root, path, model = setup(env, *(responses or (NUMERICAL,)), primary=primary)
    env.runtime.jobs.threads = env.client.app.dependency_overrides[get_thread_service]()
    return owner, wid, root, path, model


def submit(env, owner, path, question="What is total revenue?", request_id=None):
    response = env.client.post(
        path + "/jobs",
        headers=owner,
        json={"question": question, "request_id": request_id or str(uuid4())},
    )
    assert response.status_code == 202, response.text
    return response.json()


def job_path(job):
    return f"/workspaces/{job['workspace_id']}/jobs/{job['id']}"


def process(env):
    return asyncio.run(env.runtime.jobs.process())


def test_job_submission_is_durable_retry_safe_and_reuses_exact_receipt(integration):
    env = integration
    owner, _, _, path, model = prepared(env)
    rid = str(uuid4())
    job = submit(env, owner, path, request_id=rid)
    assert job["status"] == "queued" and model.requests == []
    assert submit(env, owner, path, request_id=rid)["id"] == job["id"]
    assert env.client.get(job_path(job) + "/result", headers=owner).status_code == 409
    conflicting = env.client.post(
        path + "/jobs", headers=owner, json={"question": "A different question", "request_id": rid}
    )
    assert conflicting.status_code == 409
    assert process(env) == {"processed": 1}
    result = env.client.get(job_path(job) + "/result", headers=owner)
    assert result.status_code == 200, result.text
    assert result.json()["answer"]["value"] == "8.050000000000"
    assert result.json()["turn"]["job_id"] == job["id"]
    assert env.client.get(path, headers=owner).json()["turns"][0]["job_id"] == job["id"]
    assert submit(env, owner, path, request_id=rid)["status"] == "succeeded"
    assert len(model.requests) == 1
    activity = env.client.get(job_path(job) + "/events", headers=owner).json()
    events = activity["events"]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert any(
        event["stage"] == "executing_query" and event["status"] == "completed" for event in events
    )
    assert events[-1]["stage"] == "finished"
    assert "revenue" not in json.dumps(events) and "8.05" not in json.dumps(events)
    assert (
        env.client.get(
            job_path(job) + f"/events?after={activity['next_sequence']}", headers=owner
        ).json()["events"]
        == []
    )
    with env.engine.connect() as connection:
        saved = (
            connection.execute(select(s.jobs).where(s.jobs.c.id == UUID(job["id"])))
            .mappings()
            .one()
        )
        plan = saved["plan"]
        encoded = json.dumps(
            plan["value"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        assert hashlib.sha256(encoded).hexdigest() == plan["checksum"]
        assert [step["operation"] for step in plan["value"]["steps"]] == [
            "query",
            "assemble_evidence",
        ]
        assert connection.execute(select(s.query_executions.c.id)).all() == [
            (UUID(result.json()["turn"]["query_id"]),)
        ]


def test_old_synchronous_turn_cannot_be_reexecuted_as_a_new_job(integration):
    env = integration
    owner, _, _, path, model = prepared(env)
    rid = str(uuid4())
    original = ask(env, owner, path, "What is total revenue?", rid)
    assert original.status_code == 200
    attempted = env.client.post(
        path + "/jobs",
        headers=owner,
        json={"question": "What is total revenue?", "request_id": rid},
    )
    assert attempted.status_code == 409
    assert len(model.requests) == 1 and original.json()["turn"]["job_id"] is None


def test_jobs_events_results_and_cancellation_are_owner_private(integration):
    env = integration
    owner, wid, _, path, _ = prepared(env)
    member, member_user = identity(env, "job-member@example.test")
    accept(env, member, wid, invite(env, owner, wid, member_user.email).json()["id"])
    outsider, _ = identity(env, "job-outsider@example.test")
    other_wid = workspace(env, outsider)
    job = submit(env, owner, path)
    for headers in (member, outsider):
        for suffix in ("", "/events", "/result"):
            assert env.client.get(job_path(job) + suffix, headers=headers).status_code == 404
        assert env.client.post(job_path(job) + "/cancel", headers=headers).status_code == 404
    assert (
        env.client.get(f"/workspaces/{other_wid}/jobs/{job['id']}", headers=outsider).status_code
        == 404
    )
    assert (
        env.client.post(
            path + "/jobs", headers=member, json={"question": "total", "request_id": str(uuid4())}
        ).status_code
        == 404
    )


def test_cancel_queued_job_never_calls_model_and_remains_visible_after_reload(integration):
    env = integration
    owner, _, _, path, model = prepared(env)
    job = submit(env, owner, path)
    cancelled = env.client.post(job_path(job) + "/cancel", headers=owner)
    assert cancelled.json()["status"] == "cancelled"
    assert process(env) == {"processed": 0}
    result = env.client.get(job_path(job) + "/result", headers=owner).json()
    assert result["answer"] is None and result["turn"]["status"] == "failed"
    assert "cancelled" in result["turn"]["message"]
    assert model.requests == []
    assert env.client.post(job_path(job) + "/cancel", headers=owner).json()["status"] == "cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["model", "query", "retrieval"])
async def test_cancel_active_work_interrupts_real_operation_and_retains_failed_query_receipt(
    integration, monkeypatch, stage
):
    env = integration
    entered = asyncio.Event()

    class HangingModel(ScriptedModel):
        async def complete(self, request):
            entered.set()
            await asyncio.Event().wait()

    owner, _, root, path, _model = prepared(
        env,
        MIXED if stage == "retrieval" else NUMERICAL,
        primary=HangingModel() if stage == "model" else None,
    )
    if stage == "query":

        async def hanging_query(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(env.runtime.analytics.executor, "execute", hanging_query)
    elif stage == "retrieval":
        document(env, owner, root)

        async def hanging_search(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(env.runtime.knowledge, "search", hanging_search)
    job = submit(env, owner, path)
    worker = asyncio.create_task(env.runtime.jobs.process())
    await asyncio.wait_for(entered.wait(), 10)
    assert (
        env.client.post(job_path(job) + "/cancel", headers=owner).json()["status"] == "cancelling"
    )
    await asyncio.wait_for(worker, 10)
    status = env.client.get(job_path(job), headers=owner).json()
    assert status["status"] == "cancelled"
    assert env.client.get(job_path(job) + "/result", headers=owner).json()["answer"] is None
    with env.engine.connect() as connection:
        receipts = connection.execute(select(s.query_executions.c.receipt)).scalars().all()
    if stage == "query":
        assert len(receipts) == 1 and receipts[0]["outcome"] == "failed"
    if stage == "retrieval":
        assert len(receipts) == 1 and receipts[0]["outcome"] == "executed"


def test_cancellation_after_success_preserves_the_completed_answer(integration):
    env = integration
    owner, _, _, path, _ = prepared(env)
    job = submit(env, owner, path)
    process(env)
    assert env.client.post(job_path(job) + "/cancel", headers=owner).json()["status"] == "succeeded"
    assert (
        env.client.get(job_path(job) + "/result", headers=owner).json()["answer"]["value"]
        == "8.050000000000"
    )


def test_workspace_concurrency_is_global_across_independent_workers(integration):
    env = integration
    owner, wid, root, path, _ = prepared(env)
    jobs = [submit(env, owner, path)]
    for _ in range(2):
        tid = env.client.post(root + "/threads", headers=owner).json()["id"]
        jobs.append(submit(env, owner, f"/workspaces/{wid}/threads/{tid}"))
    workers = [
        JobService(env.runtime.jobs.uow, env.runtime.jobs.threads, workspace_limit=1)
        for _ in range(3)
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        leases = list(pool.map(lambda worker: worker.claim_next(), workers))
    assert sum(lease is not None for lease in leases) == 1
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.job_attempts.c.id)).all()) == 1


def test_queued_source_change_or_revocation_prevents_any_model_input(integration):
    env = integration
    owner, wid, root, path, model = prepared(env)
    job = submit(env, owner, path)
    original = env.client.get(root + "/profile", headers=owner).json()
    changed = env.client.post(
        root + "/cleaning/apply",
        headers=owner,
        json={"expected_revision_id": original["id"], "trim": True},
    )
    assert changed.status_code == 201
    process(env)
    assert env.client.get(job_path(job), headers=owner).json()["failure_code"] == "source_changed"
    assert model.requests == []
    other_tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    revoked = submit(env, owner, f"/workspaces/{wid}/threads/{other_tid}")
    with env.engine.begin() as connection:
        connection.execute(delete(s.memberships).where(s.memberships.c.workspace_id == UUID(wid)))
    process(env)
    assert env.client.get(job_path(revoked), headers=owner).status_code == 404
    with env.engine.connect() as connection:
        assert (
            connection.execute(
                select(s.jobs.c.status).where(s.jobs.c.id == UUID(revoked["id"]))
            ).scalar_one()
            == "failed"
        )
    assert model.requests == []


def test_expired_running_lease_is_not_reexecuted_and_stale_worker_cannot_publish(integration):
    env = integration
    owner, _, _, path, model = prepared(env)
    job = submit(env, owner, path)
    lease = env.runtime.jobs.claim_next()
    assert lease is not None
    with env.engine.begin() as connection:
        connection.execute(
            update(s.jobs)
            .where(s.jobs.c.id == lease.job_id)
            .values(
                status="running", lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
            )
        )
    polled = env.client.get(job_path(job), headers=owner)
    assert polled.json()["status"] == "expired"
    assert env.runtime.jobs.heartbeat(lease) == "lease_lost"
    asyncio.run(env.runtime.jobs.run(lease))
    assert model.requests == []
    assert env.client.get(job_path(job) + "/result", headers=owner).json()["answer"] is None


def test_claimed_only_recovery_is_bounded_and_old_attempt_is_fenced(integration):
    env = integration
    owner, _, _, path, model = prepared(env)
    job = submit(env, owner, path)
    leases = []
    for _ in range(3):
        lease = env.runtime.jobs.claim_next()
        assert lease is not None
        leases.append(lease)
        with env.engine.begin() as connection:
            connection.execute(
                update(s.jobs)
                .where(s.jobs.c.id == lease.job_id)
                .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
            )
    assert env.runtime.jobs.claim_next() is None
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "expired"
    for lease in leases:
        asyncio.run(env.runtime.jobs.run(lease))
    assert model.requests == []
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.job_attempts.c.id)).all()) == 3


@pytest.mark.asyncio
async def test_worker_shutdown_finishes_active_attempt_without_claiming_next_job(integration):
    env = integration
    entered = asyncio.Event()

    class HangingModel(ScriptedModel):
        async def complete(self, request):
            self.requests.append(request)
            entered.set()
            await asyncio.Event().wait()

    owner, wid, root, path, model = prepared(env, primary=HangingModel())
    first = submit(env, owner, path)
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    second = submit(env, owner, f"/workspaces/{wid}/threads/{tid}")
    stop = asyncio.Event()
    worker = asyncio.create_task(work(env.runtime.jobs, stop, watch=True, concurrency=1))
    await asyncio.wait_for(entered.wait(), 10)
    stop.set()
    await asyncio.wait_for(worker, 10)
    assert env.client.get(job_path(first), headers=owner).json()["status"] == "failed"
    assert env.client.get(job_path(second), headers=owner).json()["status"] == "queued"
    assert len(model.requests) == 1


def test_stalled_queue_expires_on_owner_poll_without_worker(integration):
    env = integration
    owner, _, _, path, model = prepared(env)
    job = submit(env, owner, path)
    with env.engine.begin() as connection:
        connection.execute(
            update(s.jobs)
            .where(s.jobs.c.id == UUID(job["id"]))
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "expired"
    assert model.requests == []


@pytest.mark.asyncio
async def test_completed_query_cannot_publish_after_cancellation_wins(integration, monkeypatch):
    env = integration
    owner, _, _, path, _ = prepared(env)
    job = submit(env, owner, path)
    original = env.runtime.jobs._finish

    def cancellation_wins(*args, **kwargs):
        actor = env.runtime.identity.authenticate(owner["Authorization"].removeprefix("Bearer "))
        env.runtime.jobs.cancel(actor, UUID(job["workspace_id"]), UUID(job["id"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(env.runtime.jobs, "_finish", cancellation_wins)
    await env.runtime.jobs.process()
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "cancelled"
    assert env.client.get(job_path(job) + "/result", headers=owner).json()["answer"] is None
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(s.query_executions.c.receipt)).scalar_one()["outcome"]
            == "executed"
        )


@pytest.mark.asyncio
async def test_expired_lease_blocks_real_late_completion_and_duplicate_receipt(
    integration, monkeypatch
):
    env = integration
    owner, _, _, path, model = prepared(env)
    job = submit(env, owner, path)
    original = env.runtime.jobs._finish

    def lease_lost(*args, **kwargs):
        with env.engine.begin() as connection:
            connection.execute(
                update(s.jobs)
                .where(s.jobs.c.id == UUID(job["id"]))
                .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(env.runtime.jobs, "_finish", lease_lost)
    await env.runtime.jobs.process()
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "expired"
    assert env.client.get(job_path(job) + "/result", headers=owner).json()["answer"] is None
    assert len(model.requests) == 1
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.query_executions.c.id)).all()) == 1


@pytest.mark.asyncio
async def test_source_deletion_during_work_prevents_result_publication(integration, monkeypatch):
    env = integration
    owner, wid, root, path, _ = prepared(env)
    job = submit(env, owner, path)
    original = env.runtime.jobs._source_check
    calls = 0

    async def deleting_source(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            storage = env.runtime.service.storage
            with env.runtime.jobs.uow() as repo:
                stored = repo.upload(UUID(wid), UUID(root.split("/")[4]), UUID(root.split("/")[6]))
            storage.delete(stored)
        await original(*args, **kwargs)

    monkeypatch.setattr(env.runtime.jobs, "_source_check", deleting_source)
    await env.runtime.jobs.process()
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "failed"
    assert env.client.get(job_path(job) + "/result", headers=owner).json()["answer"] is None


@pytest.mark.asyncio
async def test_real_model_http_retry_budget_is_checked_before_each_outgoing_attempt(
    integration, monkeypatch
):
    import httpx

    from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel

    env = integration
    owner, _, _, path, _ = prepared(env)
    actual = OpenAICompatibleLanguageModel(
        "https://provider.example.test",
        "",
        "small",
        "large",
        "test",
        max_attempts=10,
        retry_backoff_seconds=0,
    )
    env.runtime.jobs.threads.intent_router.model = actual
    calls = []

    async def retryable(client, url, **kwargs):
        calls.append(url)
        return httpx.Response(503, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", retryable)
    job = submit(env, owner, path)
    await env.runtime.jobs.process()
    assert len(calls) == 7
    state = env.client.get(job_path(job), headers=owner).json()
    assert state["status"] == "failed" and state["failure_code"] == "job_budget"


@pytest.mark.asyncio
async def test_model_retry_rechecks_cancellation_before_another_http_attempt(
    integration, monkeypatch
):
    import httpx

    from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel

    env = integration
    owner, _, _, path, _ = prepared(env)
    actual = OpenAICompatibleLanguageModel(
        "https://provider.example.test",
        "",
        "small",
        "large",
        "test",
        max_attempts=3,
        retry_backoff_seconds=0,
    )
    env.runtime.jobs.threads.intent_router.model = actual
    job = submit(env, owner, path)
    actor = env.runtime.identity.authenticate(owner["Authorization"].removeprefix("Bearer "))
    calls = []

    async def cancelled(client, url, **kwargs):
        calls.append(url)
        env.runtime.jobs.cancel(actor, UUID(job["workspace_id"]), UUID(job["id"]))
        return httpx.Response(503, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", cancelled)
    await env.runtime.jobs.process()
    assert len(calls) == 1
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "cancelled"


def test_polling_does_not_disable_safe_claimed_attempt_recovery(integration):
    env = integration
    owner, _, _, path, model = prepared(env)
    job = submit(env, owner, path)
    first = env.runtime.jobs.claim_next()
    with env.engine.begin() as connection:
        connection.execute(
            update(s.jobs)
            .where(s.jobs.c.id == UUID(job["id"]))
            .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "queued"
    second = env.runtime.jobs.claim_next()
    assert second is not None and second.attempt_id != first.attempt_id
    assert env.runtime.jobs.heartbeat(first) == "lease_lost"
    asyncio.run(env.runtime.jobs.run(second))
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "succeeded"
    assert len(model.requests) == 1


def test_final_publication_rechecks_elapsed_time_even_when_lease_is_fresh(integration, monkeypatch):
    env = integration
    owner, _, _, path, _ = prepared(env)
    job = submit(env, owner, path)
    original = env.runtime.jobs._finish

    def late_finish(lease, *args, **kwargs):
        with env.engine.begin() as connection:
            connection.execute(
                update(s.job_attempts)
                .where(s.job_attempts.c.id == lease.attempt_id)
                .values(started_at=datetime.now(timezone.utc) - timedelta(seconds=110))
            )
        return original(lease, *args, **kwargs)

    monkeypatch.setattr(env.runtime.jobs, "_finish", late_finish)
    process(env)
    state = env.client.get(job_path(job), headers=owner).json()
    assert state["status"] == "failed" and state["failure_code"] == "timeout"
    assert env.client.get(job_path(job) + "/result", headers=owner).json()["answer"] is None
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(s.query_executions.c.receipt)).scalar_one()["outcome"]
            == "executed"
        )
