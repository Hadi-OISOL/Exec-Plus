"""An optional narrative deadline preserves exact answers, never permission/source races."""

import asyncio

import pytest
from sqlalchemy import delete

from execplus.application.services.response_synthesis import ResponseSynthesisService
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as tables
from test_harness_context import query
from test_harness_context_integration import setup
from test_thread_narrative_integration import SelectionModel


def expire_optional_stage(monkeypatch, selection):
    original = asyncio.wait_for

    async def shortened(awaitable, timeout):
        if getattr(getattr(awaitable, "cr_code", None), "co_name", None) == "_narrative":
            task = asyncio.create_task(awaitable)
            await original(selection.entered.wait(), 5)
            return await original(task, 0.001)
        return await original(awaitable, timeout)

    monkeypatch.setattr(asyncio, "wait_for", shortened)


@pytest.mark.asyncio
async def test_outer_narrative_deadline_retains_exact_answer_and_immutable_reopening(
    integration, monkeypatch
):
    actor, wid, did, uid, _, threads = setup(integration, query())
    selection = SelectionModel(block=True)
    threads.response_synthesis = ResponseSynthesisService(selection)
    expire_optional_stage(monkeypatch, selection)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue")
    assert selection.cancelled and turn.status == "complete"
    assert str(answer.value) == "350.000000000000"
    assert "narrative" not in turn.evidence
    assert turn.evidence["narrative_sources"] == answer.lineage.receipt["sources"]
    assert turn.evidence["narrative_diagnostics"] == {
        "mode": "fallback",
        "reason": "turn_deadline",
        "model_route": "deterministic:structured-answer",
    }
    reopened = await threads.resolve(actor, wid, thread.id, turn.id)
    assert reopened.value == answer.value
    assert await threads.validated_narrative(actor, wid, thread.id, turn.id, reopened) is None


@pytest.mark.parametrize("change", ["source", "membership"])
@pytest.mark.asyncio
async def test_deadline_fallback_still_denies_changed_source_or_membership(
    integration, monkeypatch, change
):
    actor, wid, did, uid, _, threads = setup(integration, query())

    def mutate():
        if change == "source":
            revision = integration.runtime.service.profile_upload(actor, wid, did, uid)
            integration.runtime.service.clean(
                actor,
                wid,
                did,
                uid,
                revision.id,
                {"trim": True, "drop_duplicates": False, "drop_missing": False, "mapping": {}},
                apply=True,
            )
        else:
            with integration.engine.begin() as connection:
                connection.execute(
                    delete(tables.memberships).where(
                        tables.memberships.c.workspace_id == wid,
                        tables.memberships.c.user_id == actor.id,
                    )
                )

    selection = SelectionModel(callback=mutate, block=True)
    threads.response_synthesis = ResponseSynthesisService(selection)
    expire_optional_stage(monkeypatch, selection)
    thread = await threads.start_thread(actor, wid, did, uid)
    with pytest.raises(IngestionError):
        await threads.ask(actor, wid, thread.id, "total revenue")
    assert selection.cancelled


@pytest.mark.asyncio
async def test_external_cancellation_is_not_optional_timeout(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    selection = SelectionModel(block=True)
    threads.response_synthesis = ResponseSynthesisService(selection)
    thread = await threads.start_thread(actor, wid, did, uid)
    task = asyncio.create_task(threads.ask(actor, wid, thread.id, "total revenue"))
    await asyncio.wait_for(selection.entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert selection.cancelled
