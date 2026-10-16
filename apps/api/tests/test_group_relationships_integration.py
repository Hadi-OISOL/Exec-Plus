"""Use case: Verifies private grouped comparisons against retained real-service evidence.

What it does: Exercises exact replay, tampering, changing sources, authorization and cleanup.
"""

import asyncio
import threading
from copy import deepcopy
from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy import delete, select

from execplus.application.services import patterns as pattern_module
from execplus.domain.decision_analysis import checksum
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_patterns_integration import discover as ordinary_discover
from test_patterns_integration import reopen, service
from test_refresh import setup as refresh_setup
from test_studies import add_member, prepare
from test_understanding import confirm, context
from test_workspace_integration import upload


def sample():
    return (
        "group,amount,reading\n"
        + "".join(f"A,{i}.001,{100 + i}.003\n" for i in range(20))
        + "".join(f"B,{100 + i}.001,{i}.003\n" for i in range(20))
    ).encode()


def discover(env, actor, wid, did, uid):
    return asyncio.run(
        service(env).discover(
            actor, UUID(wid), UUID(did), UUID(uid), ("amount", "reading"), group_by="group"
        )
    )


def test_new_group_comparison_keeps_typed_receipt_private_and_old_pattern_unchanged(integration):
    env = integration
    headers, actor, wid, did, uid, root = prepare(env, sample())
    before = context(env, headers, root)
    old = ordinary_discover(env, actor, wid, did, uid)
    evidence = discover(env, actor, wid, did, uid)
    assert evidence["version"] == "group-relationship-evidence-v1"
    assert evidence["request"]["version"] == "group-relationship-request-v1"
    assert evidence["result"]["version"] == "group-relationship-comparison-v1"
    assert evidence["result"]["pooled"]["support"] == 40
    assert evidence["result"]["comparisons"]["pearson"]["reversal_groups"] == ["A", "B"]
    assert reopen(env, actor, wid, evidence) == evidence
    assert reopen(env, actor, wid, old) == old
    assert old["version"] == "pattern-evidence-v1"
    receipt_url = f"/workspaces/{wid}/queries/{evidence['query_id']}"
    response = env.client.get(receipt_url, headers=headers)
    assert response.status_code == 200
    with service(env).uow() as repo:
        record = repo.query_execution(UUID(wid), UUID(evidence["query_id"]))
    assert record.receipt["answer"]["rows"][0] == [
        {"type": "Decimal", "value": "0.001000000000"},
        {"type": "Decimal", "value": "100.003000000000"},
        {"type": "str", "value": "A"},
    ]
    member, other = add_member(env, headers, wid, "admin")
    assert env.client.post(receipt_url + "/replay", headers=headers).status_code == 200
    assert env.client.post(receipt_url + "/replay", headers=member).status_code == 404
    assert env.client.get(receipt_url, headers=member).status_code == 404
    with pytest.raises(IngestionError) as failure:
        reopen(env, other, wid, evidence)
    assert failure.value.status == 404
    assert context(env, headers, root) == before
    with env.engine.connect() as connection:
        records = connection.execute(select(s.query_executions)).mappings().all()
    assert len(records) == 2 and all(record["aggregation"] == "analysis" for record in records)


@pytest.mark.parametrize(
    "mutation", ["result", "request", "group_by", "fields", "source", "engine", "wrapper"]
)
def test_group_comparison_tampering_is_rejected_even_with_new_checksum(integration, mutation):
    env = integration
    _, actor, wid, did, uid, _ = prepare(env, sample())
    changed = deepcopy(discover(env, actor, wid, did, uid))
    if mutation == "result":
        changed["result"]["pooled"]["statistics"]["pearson"] = "0.123456"
        changed["result_checksum"] = checksum(changed["result"])
    elif mutation in {"request", "group_by", "fields"}:
        if mutation == "request":
            changed["request"]["units"]["amount"] = "different unit"
        elif mutation == "group_by":
            changed["request"]["group_by"] = "amount"
        else:
            changed["request"]["columns"].reverse()
        changed["request_checksum"] = checksum(changed["request"])
    elif mutation == "source":
        changed["sources"][0]["source_checksum"] = "a" * 64
    elif mutation == "wrapper":
        changed["version"] = "pattern-evidence-v1"
    else:
        changed["engine_version"] = "different-engine"
    with pytest.raises(IngestionError):
        reopen(env, actor, wid, changed)


def test_new_meaning_preserves_old_grouped_and_ordinary_historical_answers(integration):
    env = integration
    headers, actor, wid, did, uid, root = prepare(env, sample())
    evidence = discover(env, actor, wid, did, uid)
    meaning = context(env, headers, root)
    meaning["definition"]["description"] = "More detailed fictional observation meaning"
    assert confirm(env, headers, root, meaning).status_code == 201
    assert reopen(env, actor, wid, evidence) == evidence
    newer = discover(env, actor, wid, did, uid)
    assert newer["sources"] != evidence["sources"]
    assert newer["result"] == evidence["result"]


@pytest.mark.parametrize("mutation", ["meaning", "bytes", "membership"])
def test_changed_source_or_authorization_cannot_publish_group_comparison(
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
                Bucket=env.bucket, Key=stored.storage_key, Body=b"changed-private-test-data"
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


def test_reopen_refuses_changed_group_source_bytes(integration):
    env = integration
    _, actor, wid, did, uid, _ = prepare(env, sample())
    evidence = discover(env, actor, wid, did, uid)
    with service(env).uow() as repo:
        stored = repo.upload(UUID(wid), UUID(did), UUID(uid))
    env.runtime.analytics.storage.client.put_object(
        Bucket=env.bucket, Key=stored.storage_key, Body=b"changed-private-test-data"
    )
    with pytest.raises(IngestionError):
        reopen(env, actor, wid, evidence)


def test_replaced_refresh_source_blocks_new_comparison_but_old_reopen_remains(integration):
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


def test_group_statistics_cancellation_waits_for_worker_cleanup(integration, monkeypatch):
    env = integration
    _, actor, wid, did, uid, _ = prepare(env, sample())
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    calculate = pattern_module.group_relationship_result

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=5)
        try:
            return calculate(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(pattern_module, "group_relationship_result", blocked)

    async def run():
        task = asyncio.create_task(
            service(env).discover(
                actor, UUID(wid), UUID(did), UUID(uid), ("amount", "reading"), group_by="group"
            )
        )
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not finished.is_set() and not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(run())


def test_cancelled_group_projection_records_private_failed_receipt(integration, monkeypatch):
    env = integration
    _, actor, wid, did, uid, _ = prepare(env, sample())

    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(env.runtime.analytics.executor, "execute", cancelled)
    with pytest.raises(asyncio.CancelledError):
        discover(env, actor, wid, did, uid)
    with env.engine.connect() as connection:
        records = connection.execute(select(s.query_executions)).mappings().all()
    assert len(records) == 1
    assert records[0]["aggregation"] == "analysis"
    assert records[0]["receipt"]["outcome"] == "failed"
