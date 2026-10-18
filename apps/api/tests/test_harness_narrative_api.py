"""Exercise configured harness behavior through real thread/job API serialization."""

import asyncio
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from execplus.bootstrap import build_runtime
from execplus.config import Settings
from execplus.infrastructure.persistence import schema as tables
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from execplus.presentation.routes.threads import get_thread_service
from test_analytics_integration import uploaded_dataset
from test_conversation_jobs import job_path, submit
from test_harness_context import query
from test_harness_context_integration import Planner
from test_thread_narrative_integration import SelectionModel
from test_workspace_integration import identity, workspace


def configured(env, *plans, enabled=True, selection=None):
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=os.environ["EXECPLUS_TEST_DATABASE_URL"],
        object_store_endpoint=os.environ["EXECPLUS_TEST_OBJECT_STORE_ENDPOINT"],
        object_store_bucket=env.bucket,
        agent_context_enabled=enabled,
        agent_orchestration_enabled=enabled,
        agent_synthesis_enabled=enabled,
    )
    wired = build_runtime(settings)
    wired.engine.dispose()
    planner = Planner(*plans)
    wired.intent_router.analytics = env.runtime.analytics
    wired.intent_router.model = planner
    wired.intent_router.documents = None
    wired.threads.uow = SQLUnitOfWork(env.engine)
    wired.jobs.uow = SQLUnitOfWork(env.engine)
    assert wired.threads.intent_router is wired.intent_router
    assert wired.jobs.threads is wired.threads
    assert wired.intent_router.context_enabled is enabled
    assert wired.intent_router.orchestration_enabled is enabled
    assert wired.jobs.budget.max_queries == (2 if enabled else 1)
    if enabled:
        assert wired.threads.response_synthesis is not None
        wired.threads.response_synthesis.model = selection or SelectionModel()
    else:
        assert wired.threads.response_synthesis is None
    env.client.app.dependency_overrides[get_thread_service] = lambda: wired.threads
    env.runtime.jobs = wired.jobs
    headers, actor = identity(env, "narrative-api@example.test")
    wid = workspace(env, headers)
    did, uid = uploaded_dataset(env, headers, wid)
    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/threads",
        headers=headers,
    )
    assert response.status_code == 201, response.text
    tid = response.json()["id"]
    return headers, actor, wid, did, uid, f"/workspaces/{wid}/threads/{tid}", wired, planner


def compound():
    return {"kind": "compound", "steps": [query(), query("count", metric="*")]}


def check_compound(body):
    assert body["kind"] == "mixed"
    assert body["data"]["value"] == "350.000000000000"
    assert body["additional_data"][0]["value"] == 3
    first = body["data"]["lineage"]["query_id"]
    second = body["additional_data"][0]["lineage"]["query_id"]
    assert first != second
    refs = {ref for segment in body["narrative"]["segments"] for ref in segment["evidence_ids"]}
    assert refs == {first, second}
    assert body["narrative"]["mode"] == "selected"


def test_bootstrap_flags_direct_api_and_historical_compound_narrative(integration):
    env = integration
    headers, _, _, _, _, path, _, planner = configured(env, compound())
    request_id = str(uuid4())
    response = env.client.post(
        path + "/ask",
        headers=headers,
        json={
            "question": "total revenue and count records",
            "request_id": request_id,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    check_compound(body["answer"])
    assert "narrative" not in body["turn"]
    historical = env.client.get(path + f"/turns/{body['turn']['id']}/answer", headers=headers)
    assert historical.status_code == 200 and historical.json() == body["answer"]
    repeated = env.client.post(
        path + "/ask",
        headers=headers,
        json={
            "question": "total revenue and count records",
            "request_id": request_id,
        },
    )
    assert repeated.status_code == 200 and repeated.json()["answer"] == body["answer"]
    assert len(planner.requests) == 1
    listed = env.client.get(path, headers=headers).json()
    assert "narrative" not in listed["turns"][0]


def test_bootstrap_flags_durable_worker_result_and_historical_narrative(integration):
    env = integration
    headers, _, _, _, _, path, _, planner = configured(env, compound())
    job = submit(env, headers, path, "total revenue and count records")
    assert asyncio.run(env.runtime.jobs.process()) == {"processed": 1}
    result = env.client.get(job_path(job) + "/result", headers=headers)
    assert result.status_code == 200, result.text
    body = result.json()
    check_compound(body["answer"])
    historical = env.client.get(path + f"/turns/{body['turn']['id']}/answer", headers=headers)
    assert historical.status_code == 200 and historical.json() == body["answer"]
    assert env.client.get(job_path(job), headers=headers).json()["status"] == "succeeded"
    assert len(planner.requests) == 1


def test_default_bootstrap_preserves_legacy_api_without_narrative(integration):
    env = integration
    headers, _, _, _, _, path, _, _ = configured(env, query(), enabled=False)
    job = submit(env, headers, path, "total revenue")
    assert asyncio.run(env.runtime.jobs.process()) == {"processed": 1}
    result = env.client.get(job_path(job) + "/result", headers=headers)
    assert result.status_code == 200
    body = result.json()
    assert body["answer"]["value"] == "350.000000000000"
    assert "narrative" not in body["answer"]
    historical = env.client.get(path + f"/turns/{body['turn']['id']}/answer", headers=headers)
    assert historical.status_code == 200 and "narrative" not in historical.json()


@pytest.mark.asyncio
async def test_worker_cancellation_during_synthesis_has_no_api_narrative(integration):
    env = integration
    selection = SelectionModel(block=True)
    headers, _, _, _, _, path, _, _ = configured(env, query(), selection=selection)
    job = submit(env, headers, path, "total revenue")
    worker = asyncio.create_task(env.runtime.jobs.process())
    await asyncio.wait_for(selection.entered.wait(), 10)
    response = env.client.post(job_path(job) + "/cancel", headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "cancelling"
    await asyncio.wait_for(worker, 10)
    assert selection.cancelled
    assert env.client.get(job_path(job), headers=headers).json()["status"] == "cancelled"
    result = env.client.get(job_path(job) + "/result", headers=headers)
    assert result.status_code == 200 and result.json()["answer"] is None
    assert result.json()["turn"]["query_id"] is None


@pytest.mark.parametrize("change", ["source", "membership"])
def test_worker_source_or_access_changes_during_synthesis_never_publish(integration, change):
    env = integration
    selection = SelectionModel()
    headers, actor, wid, did, uid, path, _, _ = configured(env, query(), selection=selection)

    def mutate():
        if change == "source":
            revision = env.runtime.service.profile_upload(actor, UUID(wid), UUID(did), UUID(uid))
            env.runtime.service.clean(
                actor,
                UUID(wid),
                UUID(did),
                UUID(uid),
                revision.id,
                {
                    "trim": True,
                    "drop_duplicates": False,
                    "drop_missing": False,
                    "mapping": {},
                },
                apply=True,
            )
        else:
            with env.engine.begin() as connection:
                connection.execute(
                    delete(tables.memberships).where(
                        tables.memberships.c.workspace_id == UUID(wid),
                        tables.memberships.c.user_id == actor.id,
                    )
                )

    selection.callback = mutate
    job = submit(env, headers, path, "total revenue")
    assert asyncio.run(env.runtime.jobs.process()) == {"processed": 1}
    with env.engine.connect() as connection:
        turn = (
            connection.execute(
                select(tables.thread_turns).where(
                    tables.thread_turns.c.id == UUID(job["turn_id"]),
                )
            )
            .mappings()
            .one()
        )
        assert turn["status"] == "failed" and turn["query_id"] is None
        assert "narrative" not in turn["evidence"]
    result = env.client.get(job_path(job) + "/result", headers=headers)
    if change == "membership":
        assert result.status_code == 404
    else:
        assert result.status_code == 200 and result.json()["answer"] is None


def test_narrative_keeps_immutable_usd_definition_after_current_currency_changes(integration):
    from test_understanding import confirm, context

    env = integration
    headers, _, wid, did, uid, path, _, _ = configured(env, query(), query())
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    current = context(env, headers, root)
    definition = current["definition"]
    field = next(item for item in definition["columns"] if item["name"] == "revenue")
    field.update(currency="USD", unit="")
    confirmed = confirm(env, headers, root, current, definition)
    assert confirmed.status_code == 201, confirmed.text
    first = env.client.post(path + "/ask", headers=headers, json={"question": "total revenue"})
    assert first.status_code == 200, first.text
    first_body = first.json()
    old_text = " ".join(
        segment["text"] for segment in first_body["answer"]["narrative"]["segments"]
    )
    assert "350.000000000000 USD" in old_text and "EUR" not in old_text
    current = context(env, headers, root)
    definition = current["definition"]
    next(item for item in definition["columns"] if item["name"] == "revenue")["currency"] = "EUR"
    changed = confirm(env, headers, root, current, definition)
    assert changed.status_code == 201, changed.text
    historical = env.client.get(
        path + f"/turns/{first_body['turn']['id']}/answer",
        headers=headers,
    )
    assert historical.status_code == 200, historical.text
    assert historical.json()["narrative"] == first_body["answer"]["narrative"]
    second = env.client.post(path + "/ask", headers=headers, json={"question": "total revenue"})
    assert second.status_code == 200, second.text
    new_text = " ".join(
        segment["text"] for segment in second.json()["answer"]["narrative"]["segments"]
    )
    assert "350.000000000000 EUR" in new_text and "USD" not in new_text
