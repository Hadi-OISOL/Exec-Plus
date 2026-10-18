"""Verify saved conversational presentation against authorized immutable receipts."""

import asyncio
import json
from dataclasses import replace

import pytest
from sqlalchemy import delete

from execplus.application.contracts import ModelResponse
from execplus.application.services.response_synthesis import ResponseSynthesisService
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as tables
from test_harness_context import query
from test_harness_context_integration import setup


class SelectionModel:
    def __init__(self, callback=None, block=False):
        self.callback = callback
        self.block = block
        self.entered = asyncio.Event()
        self.cancelled = False
        self.calls = 0

    async def complete(self, request):
        self.calls += 1
        self.entered.set()
        if self.callback:
            self.callback()
        if self.block:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        choices = json.loads(request.messages[-1].content)["statements"]
        return ModelResponse(
            json.dumps(
                {
                    "selections": [
                        {"id": item["id"], "variant": min(1, len(item["variants"]) - 1)}
                        for item in choices
                    ]
                }
            ),
            "selection",
            "fake",
        )


@pytest.mark.asyncio
async def test_thread_saves_selected_narrative_reopens_and_rejects_tampering(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    selection = SelectionModel()
    threads.response_synthesis = ResponseSynthesisService(selection)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue")
    assert turn.status == "complete"
    assert turn.evidence["narrative_diagnostics"] == {
        "mode": "selected",
        "reason": "selected",
        "model_route": "fake:selection",
    }
    saved = await threads.validated_narrative(actor, wid, thread.id, turn.id, answer)
    assert saved == turn.evidence["narrative"]
    reopened = await threads.resolve(actor, wid, thread.id, turn.id)
    assert await threads.validated_narrative(actor, wid, thread.id, turn.id, reopened) == saved
    assert selection.calls == 1
    with threads.uow() as repo:
        narrative = dict(saved)
        narrative["segments"] = [dict(item) for item in saved["segments"]]
        narrative["segments"][0]["text"] = "The revenue is 999999 USD."
        repo.update_thread_turn(
            wid, replace(turn, evidence={**turn.evidence, "narrative": narrative})
        )
    with pytest.raises(IngestionError, match="does not match"):
        await threads.validated_narrative(actor, wid, thread.id, turn.id)


@pytest.mark.asyncio
async def test_disabled_synthesis_model_still_saves_verified_fallback(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    threads.response_synthesis = ResponseSynthesisService(None)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue")
    narrative = await threads.validated_narrative(actor, wid, thread.id, turn.id, answer)
    assert narrative["mode"] == "fallback"
    assert turn.evidence["narrative_diagnostics"]["reason"] == "disabled"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["source", "membership", "memory"])
async def test_changes_during_synthesis_withhold_narrative_and_answer(integration, change):
    from datetime import datetime, timezone

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
                {
                    "trim": True,
                    "drop_duplicates": False,
                    "drop_missing": False,
                    "mapping": {},
                },
                apply=True,
            )
        elif change == "membership":
            with integration.runtime.engine.begin() as connection:
                connection.execute(
                    delete(tables.memberships).where(
                        tables.memberships.c.workspace_id == wid,
                        tables.memberships.c.user_id == actor.id,
                    )
                )
        else:
            with threads.uow() as repo:
                memory = repo.agent_memory(wid, actor.id)
                repo.save_agent_memory(
                    replace(
                        memory,
                        version=1,
                        role="Reader",
                        updated_at=datetime.now(timezone.utc),
                    )
                )

    threads.response_synthesis = ResponseSynthesisService(SelectionModel(mutate))
    thread = await threads.start_thread(actor, wid, did, uid)
    with pytest.raises(IngestionError):
        await threads.ask(actor, wid, thread.id, "total revenue")
    with threads.uow() as repo:
        turn = repo.thread_turns(wid, thread.id)[-1]
        assert turn.status == "failed" and turn.query_id is None
        assert not turn.evidence.get("narrative")


@pytest.mark.asyncio
async def test_historical_narrative_stays_readable_after_new_revision(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    threads.response_synthesis = ResponseSynthesisService(None)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue")
    revision = integration.runtime.service.profile_upload(actor, wid, did, uid)
    integration.runtime.service.clean(
        actor,
        wid,
        did,
        uid,
        revision.id,
        {
            "trim": True,
            "drop_duplicates": False,
            "drop_missing": False,
            "mapping": {},
        },
        apply=True,
    )
    reopened = await threads.resolve(actor, wid, thread.id, turn.id)
    assert reopened.value == answer.value
    narrative = await threads.validated_narrative(actor, wid, thread.id, turn.id, reopened)
    assert narrative == turn.evidence["narrative"]


@pytest.mark.asyncio
async def test_cancellation_during_synthesis_leaves_no_published_narrative(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    selection = SelectionModel(block=True)
    threads.response_synthesis = ResponseSynthesisService(selection)
    thread = await threads.start_thread(actor, wid, did, uid)
    task = asyncio.create_task(threads.ask(actor, wid, thread.id, "total revenue"))
    await asyncio.wait_for(selection.entered.wait(), timeout=10)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert selection.cancelled
    with threads.uow() as repo:
        turn = repo.thread_turns(wid, thread.id)[-1]
        assert turn.status == "failed" and turn.query_id is None
        assert not turn.evidence.get("narrative")


@pytest.mark.asyncio
async def test_saved_narrative_is_not_returned_after_access_revocation(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    threads.response_synthesis = ResponseSynthesisService(None)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue")
    with integration.runtime.engine.begin() as connection:
        connection.execute(
            delete(tables.memberships).where(
                tables.memberships.c.workspace_id == wid,
                tables.memberships.c.user_id == actor.id,
            )
        )
    with pytest.raises(IngestionError):
        await threads.validated_narrative(actor, wid, thread.id, turn.id, answer)


@pytest.mark.asyncio
async def test_timed_out_synthesis_returns_validated_fallback(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    selection = SelectionModel(block=True)
    threads.response_synthesis = ResponseSynthesisService(selection, timeout=0.001)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "total revenue")
    assert turn.status == "complete"
    narrative = await threads.validated_narrative(actor, wid, thread.id, turn.id, answer)
    assert narrative["mode"] == "fallback"
    assert turn.evidence["narrative_diagnostics"]["reason"] == "timeout"
    assert selection.cancelled
