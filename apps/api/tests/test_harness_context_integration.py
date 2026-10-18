"""Use case: Exercises compound receipts and contextual follow-ups with real isolated storage.

What it does: Uses fake planning only; arithmetic, replay and authorization are actual services.
"""

import json
from uuid import UUID

import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.conversation import EvidenceAnswer
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.domain.errors import QueryDataError
from execplus.domain.ingestion import IngestionError
from test_analytics_integration import uploaded_dataset
from test_harness_context import query
from test_workspace_integration import identity, workspace


class Planner:
    def __init__(self, *plans):
        self.plans = list(plans)
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        return ModelResponse(json.dumps(self.plans.pop(0)), "fake", "fake")


def setup(env, *plans, context=True, orchestration=True):
    headers, actor = identity(env, "harness@example.test")
    wid = workspace(env, headers)
    did, uid = uploaded_dataset(env, headers, wid)
    model = Planner(*plans)
    router = IntentRouterService(
        model,
        env.runtime.analytics,
        context_enabled=context,
        orchestration_enabled=orchestration,
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    return actor, UUID(wid), UUID(did), UUID(uid), model, threads


@pytest.mark.asyncio
async def test_compound_executes_two_exact_scopes_and_reopens_each_receipt(integration):
    compound = {"kind": "compound", "steps": [query(), query("count", metric="*")]}
    actor, wid, did, uid, model, threads = setup(integration, compound)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue and count records")
    assert turn.status == "complete"
    assert isinstance(answer, EvidenceAnswer)
    assert str(answer.data.value) == "350.000000000000"
    assert answer.additional_data[0].value == 3
    assert len(turn.evidence["data_steps"]) == 1
    assert str(turn.query_id) != turn.evidence["data_steps"][0]["query_id"]
    restored = await threads.resolve(actor, wid, thread.id, turn.id)
    assert isinstance(restored, EvidenceAnswer)
    assert restored.data.value == answer.data.value
    assert restored.additional_data[0].value == 3
    assert len(model.requests) == 1
    prompt = model.requests[0].messages[0].content
    assert '"kind":"compound"' in prompt


@pytest.mark.asyncio
async def test_explain_and_causal_followups_reuse_verified_values_without_model_or_calculation(
    integration,
):
    actor, wid, did, uid, model, threads = setup(integration, query())
    thread = await threads.start_thread(actor, wid, did, uid)
    first, first_turn = await threads.ask(actor, wid, thread.id, "total revenue")
    explanation, turn = await threads.ask(actor, wid, thread.id, "Explain that simply")
    assert turn.status == "complete"
    assert isinstance(explanation, EvidenceAnswer)
    assert explanation.data.value == first.value
    assert turn.query_id == first_turn.query_id
    causal, turn = await threads.ask(actor, wid, thread.id, "Why might that be?")
    assert isinstance(causal, EvidenceAnswer)
    assert causal.data.value == first.value
    assert "do not establish why" in causal.limitations[0]
    assert len(model.requests) == 1


@pytest.mark.asyncio
async def test_elliptical_filter_gets_verified_result_and_previous_typed_scope(integration):
    followup = query(filters=[{"column": "region", "operator": "ieq", "value": "South"}])
    actor, wid, did, uid, model, threads = setup(integration, query(), followup)
    thread = await threads.start_thread(actor, wid, did, uid)
    _, first = await threads.ask(actor, wid, thread.id, "total revenue")
    answer, turn = await threads.ask(actor, wid, thread.id, "Show me only the South region")
    assert turn.status == "complete"
    assert str(answer.value) == "200.000000000000"
    prompt = model.requests[-1].messages[-1].content
    assert "Previous verified results" in prompt
    assert str(first.query_id) in prompt
    assert "350.000000000000" in prompt
    assert "Previous turn: sum of revenue" in prompt


@pytest.mark.asyncio
async def test_new_explicit_task_does_not_receive_old_result_packet(integration):
    actor, wid, did, uid, model, threads = setup(integration, query(), query("avg"))
    thread = await threads.start_thread(actor, wid, did, uid)
    await threads.ask(actor, wid, thread.id, "total revenue")
    answer, turn = await threads.ask(actor, wid, thread.id, "average revenue")
    assert turn.status == "complete"
    assert answer.lineage.aggregation == "avg"
    prompt = model.requests[-1].messages[-1].content
    assert "Previous verified results" not in prompt
    assert "Previous turn:" not in prompt


@pytest.mark.asyncio
async def test_silent_omission_of_second_requested_calculation_clarifies(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue and average revenue")
    assert answer is None
    assert turn.kind == "ambiguous"
    assert turn.query_id is None


@pytest.mark.asyncio
async def test_step_two_failure_does_not_publish_a_partial_compound_result(
    integration, monkeypatch
):
    compound = {"kind": "compound", "steps": [query(), query("count", metric="*")]}
    actor, wid, did, uid, _, threads = setup(integration, compound)
    execute = threads.intent_router._execute_data
    calls = []

    async def fail_second(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise QueryDataError("The second calculation failed.")
        return await execute(*args, **kwargs)

    monkeypatch.setattr(threads.intent_router, "_execute_data", fail_second)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue and count records")
    assert len(calls) == 2
    assert answer is None
    assert turn.status == "failed"
    assert turn.query_id is None
    assert not turn.evidence.get("data_steps")


@pytest.mark.asyncio
async def test_compound_is_unavailable_when_orchestration_flag_is_off(integration):
    compound = {"kind": "compound", "steps": [query(), query("count", metric="*")]}
    actor, wid, did, uid, _, threads = setup(integration, compound, orchestration=False)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue and count records")
    assert answer is None
    assert turn.kind == "unsupported"
    assert turn.query_id is None


@pytest.mark.asyncio
async def test_compound_context_and_history_remain_private_to_owner(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    thread = await threads.start_thread(actor, wid, did, uid)
    _, turn = await threads.ask(actor, wid, thread.id, "total revenue")
    _, stranger = identity(integration, "stranger@example.test")
    with pytest.raises(IngestionError):
        await threads.resolve(stranger, wid, thread.id, turn.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["membership", "source"])
@pytest.mark.parametrize("when", ["between_steps", "before_publish"])
async def test_compound_races_withhold_results_and_preserve_receipts(
    integration, monkeypatch, change, when
):
    from sqlalchemy import delete, select

    from execplus.infrastructure.persistence import schema as tables

    compound = {"kind": "compound", "steps": [query(), query("count", metric="*")]}
    actor, wid, did, uid, _, threads = setup(integration, compound)
    thread = await threads.start_thread(actor, wid, did, uid)
    calls = []

    def mutate():
        if change == "membership":
            with integration.runtime.engine.begin() as connection:
                connection.execute(
                    delete(tables.memberships).where(
                        tables.memberships.c.workspace_id == wid,
                        tables.memberships.c.user_id == actor.id,
                    )
                )
        else:
            profile = integration.runtime.service.profile_upload(actor, wid, did, uid)
            integration.runtime.service.clean(
                actor,
                wid,
                did,
                uid,
                profile.id,
                {"trim": True, "drop_duplicates": False, "drop_missing": False, "mapping": {}},
                apply=True,
            )

    if when == "between_steps":
        execute = threads.intent_router._execute_data

        async def mutate_after_first(*args, **kwargs):
            answer = await execute(*args, **kwargs)
            calls.append(True)
            if len(calls) == 1:
                mutate()
            return answer

        monkeypatch.setattr(threads.intent_router, "_execute_data", mutate_after_first)
    else:
        publish = threads.publish

        def mutate_before_publish(*args, **kwargs):
            mutate()
            return publish(*args, **kwargs)

        monkeypatch.setattr(threads, "publish", mutate_before_publish)

    if change == "source" and when == "between_steps":
        answer, turn = await threads.ask(actor, wid, thread.id, "total revenue and count records")
        assert answer is None and turn.kind == "ambiguous"
        assert turn.query_id is None and not turn.evidence.get("data_steps")
    else:
        with pytest.raises(IngestionError):
            await threads.ask(actor, wid, thread.id, "total revenue and count records")
    with threads.uow() as repo:
        recorded = repo.thread_turns(wid, thread.id)[-1]
        assert recorded.query_id is None
        assert not recorded.evidence.get("data_steps")
        assert recorded.status == "failed" or recorded.kind == "ambiguous"
    with integration.runtime.engine.connect() as connection:
        retained = connection.execute(
            select(tables.query_executions.c.id).where(
                tables.query_executions.c.workspace_id == wid,
            )
        ).all()
        assert len(retained) >= 1


@pytest.mark.asyncio
async def test_followup_cannot_silently_remove_previous_filter(integration):
    first = query(filters=[{"column": "region", "operator": "eq", "value": "North"}])
    actor, wid, did, uid, _, threads = setup(integration, first, query(group_by=["sale_date"]))
    thread = await threads.start_thread(actor, wid, did, uid)
    await threads.ask(actor, wid, thread.id, "total revenue for North region")
    answer, turn = await threads.ask(actor, wid, thread.id, "and by sale date?")
    assert answer is None
    assert turn.kind == "ambiguous"
    assert "earlier condition" in turn.message
    assert turn.query_id is None


@pytest.mark.asyncio
async def test_new_orientation_ends_verified_result_context(integration):
    actor, wid, did, uid, model, threads = setup(integration, query())
    thread = await threads.start_thread(actor, wid, did, uid)
    await threads.ask(actor, wid, thread.id, "total revenue")
    await threads.ask(actor, wid, thread.id, "Explain what this file is about")
    answer, _ = await threads.ask(actor, wid, thread.id, "Explain that simply")
    assert not isinstance(answer, EvidenceAnswer)
    assert len(model.requests) == 1


@pytest.mark.asyncio
async def test_memory_edit_invalidates_followup_without_changing_historical_receipt(integration):
    from dataclasses import replace
    from datetime import datetime, timezone

    actor, wid, did, uid, model, threads = setup(integration, query())
    thread = await threads.start_thread(actor, wid, did, uid)
    first, first_turn = await threads.ask(actor, wid, thread.id, "total revenue")
    assert first_turn.evidence["context_memory"]["version"] == 0
    with threads.uow() as repo:
        memory = repo.agent_memory(wid, actor.id)
        repo.save_agent_memory(
            replace(
                memory,
                version=1,
                role="Reader",
                focus="Revenue",
                updated_at=datetime.now(timezone.utc),
            )
        )
    answer, turn = await threads.ask(actor, wid, thread.id, "Explain that simply")
    assert answer is None and turn.kind == "ambiguous"
    assert "memory changed" in turn.message
    restored = await threads.resolve(actor, wid, thread.id, first_turn.id)
    assert restored.value == first.value
    assert len(model.requests) == 1
