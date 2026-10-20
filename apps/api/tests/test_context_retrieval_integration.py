"""Use case: Reuses older authorized results with real synthetic storage.

What it does: Checks source/memory freshness, ownership and visible evidence links.
"""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from execplus.domain.ingestion import IngestionError
from test_harness_context import query
from test_harness_context_integration import setup
from test_workspace_integration import identity


@pytest.mark.asyncio
async def test_explicit_older_result_selected_and_linked(integration):
    actor, wid, did, uid, model, threads = setup(
        integration, query(), *(query("count", metric="*") for _ in range(7)), query()
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    _, first = await threads.ask(actor, wid, thread.id, "total revenue")
    for _ in range(7):
        await threads.ask(actor, wid, thread.id, "count records")
    _, recalled = await threads.ask(actor, wid, thread.id, "Explain earlier total revenue result")
    assert recalled.status == "complete"
    assert recalled.evidence["context_reference"]["turn_id"] == str(first.id)
    assert recalled.evidence["context_reference"]["query_ids"] == [str(first.query_id)]
    assert str(first.query_id) in model.requests[-1].messages[-1].content


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["memory", "source", "legacy"])
async def test_older_result_rejects_stale_or_unverifiable_context(integration, change):
    actor, wid, did, uid, model, threads = setup(integration, query(), query("count", metric="*"))
    thread = await threads.start_thread(actor, wid, did, uid)
    _, first = await threads.ask(actor, wid, thread.id, "total revenue")
    await threads.ask(actor, wid, thread.id, "count records")
    if change == "memory":
        with threads.uow() as repo:
            memory = repo.agent_memory(wid, actor.id)
            repo.save_agent_memory(
                replace(memory, version=1, role="Reader", updated_at=datetime.now(timezone.utc))
            )
    elif change == "legacy":
        with threads.uow() as repo:
            repo.update_thread_turn(
                wid,
                replace(
                    first,
                    evidence={k: v for k, v in first.evidence.items() if k != "context_memory"},
                ),
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
    answer, recalled = await threads.ask(
        actor, wid, thread.id, "Explain earlier total revenue result"
    )
    assert answer is None and recalled.kind == "ambiguous"
    assert "context_reference" not in recalled.evidence
    assert len(model.requests) == 2


@pytest.mark.asyncio
async def test_older_result_remains_private(integration):
    actor, wid, did, uid, _, threads = setup(integration, query())
    thread = await threads.start_thread(actor, wid, did, uid)
    await threads.ask(actor, wid, thread.id, "total revenue")
    _, stranger = identity(integration, "recall-stranger@example.test")
    with pytest.raises(IngestionError):
        await threads.ask(stranger, wid, thread.id, "Explain earlier total revenue result")


@pytest.mark.asyncio
async def test_ambiguous_older_result_clarifies_without_provider(integration):
    actor, wid, did, uid, model, threads = setup(integration, query(), query("avg"))
    thread = await threads.start_thread(actor, wid, did, uid)
    await threads.ask(actor, wid, thread.id, "total revenue")
    await threads.ask(actor, wid, thread.id, "average revenue")
    answer, recalled = await threads.ask(actor, wid, thread.id, "Explain earlier revenue result")
    assert answer is None and recalled.kind == "ambiguous"
    assert len(model.requests) == 2
