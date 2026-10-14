"""Use case: Verifies private measured patterns against real metadata and object storage.

What it does: Checks exact replay, source changes, ownership, tampering and cancellation.
"""

import asyncio
import threading
from copy import deepcopy
from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy import delete, select

from execplus.application.services import patterns as pattern_module
from execplus.application.services.patterns import PatternService
from execplus.domain.decision_analysis import checksum
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics
from test_refresh import setup as refresh_setup
from test_studies import add_member, prepare
from test_understanding import confirm, context
from test_workspace_integration import upload


def sample():
    return (
        "group,amount,reading,condition\n"
        + "".join(
            f"{'A' if i < 20 else 'B'},{i + 1},{2 * (i + 1)},{'Dry' if i < 20 else 'Wet'}\n"
            for i in range(40)
        )
    ).encode()


def service(env):
    return PatternService(
        env.runtime.analytics.uow, env.runtime.analytics, ScipyPatternStatistics()
    )


def discover(env, actor, wid, did, uid, columns=()):
    return asyncio.run(service(env).discover(actor, UUID(wid), UUID(did), UUID(uid), columns))


def reopen(env, actor, wid, evidence):
    return asyncio.run(service(env).reopen(actor, UUID(wid), evidence))


def test_all_patterns_replay_private_receipt_and_denied_other_members(integration):
    env = integration
    headers, actor, wid, did, uid, root = prepare(env, sample())
    evidence = discover(env, actor, wid, did, uid)
    assert {item["type"] for item in evidence["result"]["findings"]} == {
        "numeric_relationship",
        "group_difference",
        "category_association",
    }
    assert evidence["result"]["coverage"]["filtered_rows"] == 40
    assert reopen(env, actor, wid, evidence) == evidence
    receipt_url = f"/workspaces/{wid}/queries/{evidence['query_id']}"
    assert env.client.post(receipt_url + "/replay", headers=headers).status_code == 200
    member, other = add_member(env, headers, wid, "admin")
    assert env.client.post(receipt_url + "/replay", headers=member).status_code == 404
    assert env.client.get(receipt_url, headers=member).status_code == 404
    with pytest.raises(IngestionError) as failure:
        reopen(env, other, wid, evidence)
    assert failure.value.status == 404
    assert (
        context(env, headers, root)["history"][-1]["id"]
        == evidence["sources"][0]["understanding_id"]
    )


@pytest.mark.parametrize("mutation", ["result", "request", "source", "engine"])
def test_saved_pattern_tampering_is_detected_even_after_checksum_recalculation(
    integration, mutation
):
    env = integration
    _, actor, wid, did, uid, _ = prepare(env, sample())
    evidence = discover(env, actor, wid, did, uid)
    changed = deepcopy(evidence)
    if mutation == "result":
        changed["result"]["findings"][0]["score"] = "0.123456"
        changed["result_checksum"] = checksum(changed["result"])
    elif mutation == "request":
        changed["request"]["units"]["amount"] = "different units"
        changed["request_checksum"] = checksum(changed["request"])
    elif mutation == "source":
        changed["sources"][0]["source_checksum"] = "a" * 64
    else:
        changed["engine_version"] = "different-library-version"
    with pytest.raises(IngestionError):
        reopen(env, actor, wid, changed)


def test_historical_pattern_survives_new_confirmed_meaning_without_rewriting(integration):
    env = integration
    headers, actor, wid, did, uid, root = prepare(env, sample())
    evidence = discover(env, actor, wid, did, uid)
    meaning = context(env, headers, root)
    meaning["definition"]["description"] = "Changed description for the next analysis"
    assert confirm(env, headers, root, meaning).status_code == 201
    assert reopen(env, actor, wid, evidence) == evidence
    newer = discover(env, actor, wid, did, uid)
    assert newer["sources"] != evidence["sources"]


@pytest.mark.parametrize("mutation", ["meaning", "bytes", "membership"])
def test_no_pattern_publication_after_source_or_authorization_changes(
    integration, monkeypatch, mutation
):
    env = integration
    headers, actor, wid, did, uid, root = prepare(env, sample())
    analytics = env.runtime.analytics
    execute = analytics.executor.execute
    current = context(env, headers, root)
    with analytics.uow() as repo:
        stored = repo.upload(UUID(wid), UUID(did), UUID(uid))

    async def changed(*args, **kwargs):
        result = await execute(*args, **kwargs)
        if mutation == "meaning":
            assert confirm(env, headers, root, current).status_code == 201
        elif mutation == "bytes":
            analytics.storage.client.put_object(
                Bucket=env.bucket, Key=stored.storage_key, Body=b"private-broken-data"
            )
        else:
            with env.engine.begin() as connection:
                connection.execute(
                    delete(s.memberships).where(s.memberships.c.workspace_id == UUID(wid))
                )
        return result

    monkeypatch.setattr(analytics.executor, "execute", changed)
    with pytest.raises((IngestionError, ClarificationRequiredError)):
        discover(env, actor, wid, did, uid)


def test_reopen_rejects_changed_source_bytes(integration):
    env = integration
    _, actor, wid, did, uid, _ = prepare(env, sample())
    evidence = discover(env, actor, wid, did, uid)
    with env.runtime.analytics.uow() as repo:
        stored = repo.upload(UUID(wid), UUID(did), UUID(uid))
    env.runtime.analytics.storage.client.put_object(
        Bucket=env.bucket, Key=stored.storage_key, Body=b"changed-private-data"
    )
    with pytest.raises(IngestionError):
        reopen(env, actor, wid, evidence)


def test_refresh_source_replacement_blocks_new_old_file_scan_but_keeps_history(integration):
    env = integration
    headers, actor, wid, did, uid, _, feed = refresh_setup(env, sample())
    evidence = discover(env, actor, wid, did, uid)
    replacement = upload(env, headers, wid, did, sample()).json()["id"]
    with env.runtime.refresh.uow() as repo:
        current = repo.refresh_feed(UUID(wid), UUID(feed["id"]))
        repo.set_refresh_feed(replace(current, source={**current.source, "upload_id": replacement}))
    with pytest.raises(ClarificationRequiredError, match="current accepted"):
        discover(env, actor, wid, did, uid)
    assert reopen(env, actor, wid, evidence) == evidence


def test_cancelled_projection_records_failed_private_receipt(integration, monkeypatch):
    env = integration
    _, actor, wid, did, uid, _ = prepare(env, sample())

    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(env.runtime.analytics.executor, "execute", cancelled)
    with pytest.raises(asyncio.CancelledError):
        discover(env, actor, wid, did, uid)
    with env.engine.connect() as connection:
        receipts = connection.execute(select(s.query_executions)).mappings().all()
    assert len(receipts) == 1
    assert receipts[0]["aggregation"] == "analysis"
    assert receipts[0]["receipt"]["outcome"] == "failed"


def test_cancellation_awaits_statistics_thread_cleanup(integration, monkeypatch):
    env = integration
    _, actor, wid, did, uid, _ = prepare(env, sample())
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    calculate = pattern_module.pattern_result

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=5)
        try:
            return calculate(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(pattern_module, "pattern_result", blocked)

    async def run():
        task = asyncio.create_task(service(env).discover(actor, UUID(wid), UUID(did), UUID(uid)))
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not finished.is_set() and not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(run())
