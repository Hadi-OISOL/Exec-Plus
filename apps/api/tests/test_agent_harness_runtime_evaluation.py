"""Measured disposable-API checks for the staged conversation harness.

These use scripted planner replies to measure application behavior, not language quality.
They intentionally fail on the unchanged baseline where the staged flags/contracts do not exist.
"""

from uuid import UUID

from sqlalchemy import select

from execplus.application.contracts import KnowledgeChunk
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.infrastructure.knowledge import ReferenceHybridRanker
from execplus.infrastructure.persistence import schema as s
from execplus.presentation.routes.analytics import get_intent_router_service
from execplus.presentation.routes.threads import get_thread_service
from test_conversational_explorer import ScriptedModel, prepare
from test_dataset_guidance import ask


def staged(env, *responses, context=False, orchestration=False):
    model = ScriptedModel(*responses)
    owner, wid, root = prepare(
        env,
        model,
        content=(
            b"order_id,region,sales,discount\n"
            b"A1,West,10.00,5\nA2,West,10.00,\nA3,East,7.00,0\nA4,East,,10\n"
        ),
    )
    router = IntentRouterService(
        model,
        env.runtime.analytics,
        context_enabled=context,
        orchestration_enabled=orchestration,
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    env.client.app.dependency_overrides[get_intent_router_service] = lambda: router
    env.client.app.dependency_overrides[get_thread_service] = lambda: threads
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    return owner, wid, f"/workspaces/{wid}/threads/{tid}", model


def test_actual_compound_executes_two_exact_queries_and_reopens_both(integration):
    plan = {
        "kind": "compound",
        "steps": [
            {"kind": "numerical", "plan": {"metric": "sales", "aggregation": "sum"}},
            {"kind": "numerical", "plan": {"metric": "*", "aggregation": "count"}},
        ],
    }
    owner, wid, path, model = staged(integration, plan, orchestration=True)
    response = ask(integration, owner, path, "Give me sales and count the orders.")
    assert response["turn"]["status"] == "complete"
    assert response["answer"]["data"]["value"] == 27
    assert response["answer"]["additional_data"][0]["value"] == 4
    turn_id = response["turn"]["id"]
    reopened = integration.client.get(path + f"/turns/{turn_id}/answer", headers=owner)
    assert reopened.status_code == 200 and reopened.json() == response["answer"]
    with integration.engine.connect() as connection:
        receipts = connection.execute(
            select(s.query_executions.c.actor_id, s.query_executions.c.receipt).where(
                s.query_executions.c.workspace_id == UUID(wid)
            )
        ).all()
    assert len(receipts) == 2
    assert all(receipt[1]["sources"] == response["answer"]["sources"] for receipt in receipts)
    assert len(model.requests) == 1


def test_actual_result_followup_reuses_verified_receipt_without_second_model_call(integration):
    plan = {"kind": "numerical", "plan": {"metric": "sales", "aggregation": "sum"}}
    owner, wid, path, model = staged(integration, plan, context=True)
    first = ask(integration, owner, path, "What are total sales?")
    assert first["answer"]["value"] == 27
    second = ask(integration, owner, path, "Explain that simply")
    assert second["turn"]["status"] == "complete"
    assert second["answer"]["data"]["value"] == first["answer"]["value"]
    assert (
        second["answer"]["data"]["lineage"]["query_id"]
        == first["answer"]["lineage"]["query_id"]
    )
    assert len(model.requests) == 1
    with integration.engine.connect() as connection:
        assert len(
            connection.execute(
                select(s.query_executions.c.id).where(
                    s.query_executions.c.workspace_id == UUID(wid)
                )
            ).all()
        ) == 1


def test_actual_synonym_expansion_finds_authorized_candidate_without_renaming_fields():
    from uuid import uuid4

    wid, did = uuid4(), uuid4()
    personnel = KnowledgeChunk(uuid4(), wid, did, "Personnel handbook", {"name": "policy"})
    unrelated = KnowledgeChunk(uuid4(), wid, did, "Warehouse stock", {"name": "stock"})
    assert ReferenceHybridRanker().rank("employees", (personnel, unrelated), 3) == ()
    hits = ReferenceHybridRanker(expand_terms=True).rank("employees", (personnel, unrelated), 3)
    assert [hit.chunk.chunk_id for hit in hits] == [personnel.chunk_id]
