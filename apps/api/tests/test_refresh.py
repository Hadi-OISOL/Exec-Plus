"""Use case: Verifies staged refresh and monitoring against real PostgreSQL and retained objects.

What it does: Covers exact evidence, scheduled activation, failures, permissions and alert delivery.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import TableData
from execplus.domain.refresh import combine, decimal_value, difference, drivers, periods
from execplus.infrastructure.persistence import schema as s
from test_studies import add_member, prepare
from test_understanding import confirm, context
from test_workspace_integration import identity, workspace


def setup(env, content=b"city,amount\nKarachi,0.10\nLahore,0.20\n", **config):
    headers, actor, wid, did, uid, root = prepare(env, content)
    meaning = context(env, headers, root)
    body = dict(
        upload_id=uid,
        revision_id=meaning["revision_id"],
        understanding_id=meaning["history"][-1]["id"],
        expected_version=0,
        as_of=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        interval_hours=1,
        freshness_hours=48,
        enabled=True,
        **config,
    )
    path = f"/workspaces/{wid}/datasets/{did}"
    response = env.client.put(path + "/refresh", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return headers, actor, wid, did, uid, path, response.json()


def stage(env, headers, path, content=b"city,amount\nKarachi,0.30\nLahore,0.20\n", **kwargs):
    current = env.client.get(path + "/refresh", headers=headers).json()["feed"]
    options = (
        dict(
            request_id=str(uuid4()),
            expected_version=current["version"],
            mode="replace",
            keys=[],
            duplicates="keep_all",
            as_of=datetime.now(timezone.utc).isoformat(),
        )
        | kwargs
    )
    return env.client.post(
        path + "/refresh/candidates",
        headers=headers,
        data={"options": json.dumps(options)},
        files={"file": ("refresh.csv", content, "text/csv")},
    )


def activate(env, headers, wid, candidate):
    return env.client.post(
        f"/workspaces/{wid}/refresh-candidates/{candidate['id']}/activate", headers=headers
    )


def monitor(env, headers, path, **kwargs):
    body = (
        dict(
            name="Revenue watch",
            method=dict(kind="metric", column="amount", aggregation="sum"),
            relevance=4,
            segment="city",
        )
        | kwargs
    )
    response = env.client.post(path + "/monitors", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def process(env, headers, path):
    response = env.client.post(path + "/observations/process", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def observations(env, headers, path):
    response = env.client.get(path + "/observations", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_replace_replay_drivers_and_active_catalog(integration):
    env = integration
    h, _, wid, _did, uid, path, _feed = setup(env)
    monitor(env, h, path)
    assert process(env, h, path)["complete"] == 1
    before = observations(env, h, path)[0]
    assert Decimal(before["finding"]["value"]) == Decimal("0.30")
    candidate = stage(env, h, path).json()
    assert candidate["status"] == "queued", candidate
    assert env.client.get(path + "/refresh", headers=h).json()["feed"]["source"]["upload_id"] == uid
    catalog = env.client.get(f"/workspaces/{wid}/catalog", headers=h).json()
    assert str(uid) in json.dumps(catalog)
    assert activate(env, h, wid, candidate).json()["status"] == "activated"
    assert activate(env, h, wid, candidate).json()["status"] == "activated"
    assert process(env, h, path)["complete"] == 1
    after = observations(env, h, path)[0]
    assert Decimal(after["finding"]["delta"]) == Decimal("0.20")
    assert sum(Decimal(d["delta"]) for d in after["finding"]["drivers"]) == Decimal("0.20")
    assert after["finding"]["sample_count"] == 2
    reopened = env.client.get(
        f"/workspaces/{wid}/observations/{before['observation']['id']}", headers=h
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["finding"]["value"] == before["finding"]["value"]
    assert "historical_snapshot" in reopened.json()["finding"]["limitations"]
    receipts = reopened.json()["results"]
    assert all(
        value["lineage"]["receipt"]["sources"][0]["understanding_id"] for value in receipts.values()
    )
    uploads = env.client.get(path + "/uploads", headers=h).json()
    assert uploads[0]["id"] == candidate["details"]["output_upload_id"]


@pytest.mark.parametrize("content", [b"wrong\n", b"city,amount\nK,1\nL,2\nM,wrong\n", b"\xff\x00"])
def test_invalid_candidates_preserve_active_source(integration, content):
    env = integration
    h, _, wid, _, uid, path, feed = setup(env)
    response = stage(env, h, path, content)
    assert response.status_code == 201, response.text
    candidate = response.json()
    assert candidate["status"] == "failed"
    assert activate(env, h, wid, candidate).status_code == 409
    assert env.client.get(path + "/refresh", headers=h).json()["feed"]["source"] == feed["source"]
    assert env.client.get(path + f"/uploads/{uid}/understanding", headers=h).status_code == 200


def test_schema_review_definition_invalidation_and_conflict(integration):
    env = integration
    h, _, wid, _, _, path, _feed = setup(env)
    monitor(env, h, path)
    candidate = stage(env, h, path, b"region,total\nK,4\n").json()
    assert candidate["status"] == "needs_review"
    assert activate(env, h, wid, candidate).status_code == 409
    definition = candidate["details"]["definition"]
    definition["columns"][1]["unit"] = "PKR"
    reviewed = env.client.post(
        f"/workspaces/{wid}/refresh-candidates/{candidate['id']}/review",
        headers=h,
        json=dict(definition=definition),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert activate(env, h, wid, candidate).json()["status"] == "activated"
    result = process(env, h, path)
    assert result["failed"] == 1
    latest = observations(env, h, path)[0]
    assert latest["observation"]["evidence"]["failure_code"] == "definition_changed"
    assert latest["finding"] is None


def test_candidate_idempotency_and_concurrent_activation(integration):
    env = integration
    h, actor, wid, _, _, path, _ = setup(env)
    now = datetime.now(timezone.utc).isoformat()
    request_id = str(uuid4())
    one = stage(env, h, path, request_id=request_id, as_of=now)
    two = stage(env, h, path, request_id=request_id, as_of=now)
    assert one.json()["id"] == two.json()["id"]
    assert (
        stage(env, h, path, b"city,amount\nK,3\n", request_id=request_id, as_of=now).status_code
        == 409
    )
    cid = UUID(one.json()["id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(
            pool.map(lambda _: env.runtime.refresh.activate(actor, UUID(wid), cid), range(2))
        )
    assert all(v.status == "activated" for v in values)
    assert env.client.get(path + "/refresh", headers=h).json()["feed"]["version"] == 2


@pytest.mark.parametrize(
    "mode,duplicates,expected",
    [("append", "ignore_exact", "0.60"), ("merge", "ignore_exact", "0.80")],
)
def test_keyed_updates_retain_delta_and_full_snapshot(integration, mode, duplicates, expected):
    env = integration
    h, _, wid, _, _, path, _ = setup(env)
    monitor(env, h, path, segment=None)
    content = (
        b"city,amount\nKarachi,0.10\nMultan,0.30\nMultan,0.30\n"
        if mode == "append"
        else b"city,amount\nKarachi,0.30\nMultan,0.30\nMultan,0.30\n"
    )
    candidate = stage(env, h, path, content, mode=mode, duplicates=duplicates, keys=["city"]).json()
    assert candidate["status"] == "queued", candidate
    assert candidate["details"]["input_upload_id"] != candidate["details"]["output_upload_id"]
    assert candidate["details"]["stats"]["ignored"] >= 1
    activate(env, h, wid, candidate)
    process(env, h, path)
    assert Decimal(observations(env, h, path)[0]["finding"]["value"]) == Decimal(expected)


def test_schedule_waiting_then_activation_and_revocation(integration):
    env = integration
    h, _, wid, _, _, path, feed = setup(env)
    due = datetime.fromisoformat(feed["next_due"].replace("Z", "+00:00"))
    assert env.runtime.refresh.process_due(due)["waiting"] == 1
    assert env.runtime.refresh.process_due(due)["waiting"] == 0
    candidate = stage(env, h, path).json()
    assert env.runtime.refresh.process_due(due + timedelta(hours=1))["activated"] == 1
    assert env.runtime.refresh.process_due(due + timedelta(hours=1))["activated"] == 0
    assert activate(env, h, wid, candidate).json()["status"] == "activated"


def test_permissions_private_alerts_and_foreign_resources(integration):
    env = integration
    h, _, wid, _, _, path, _ = setup(env)
    member, _ = add_member(env, h, wid)
    outsider, _ = identity(env, f"outside-{uuid4().hex}@example.test")
    foreign = workspace(env, outsider)
    candidate = stage(env, h, path).json()
    mid = monitor(env, h, path)["id"]
    assert stage(env, member, path).status_code == 403
    assert activate(env, member, wid, candidate).status_code == 403
    assert env.client.get(path + "/refresh", headers=outsider).status_code in {403, 404}
    assert (
        env.client.post(
            f"/workspaces/{foreign}/refresh-candidates/{candidate['id']}/activate", headers=outsider
        ).status_code
        == 404
    )
    alert = env.client.post(
        f"/workspaces/{wid}/monitors/{mid}/alerts",
        headers=member,
        json=dict(operator="gt", threshold="0.1", cooldown_minutes=1),
    ).json()
    assert env.client.get(path + "/monitors", headers=h).json()["monitors"][0]["rules"] == []
    assert (
        env.client.delete(f"/workspaces/{wid}/alerts/{alert['id']}", headers=h).status_code == 404
    )
    assert (
        env.client.delete(f"/workspaces/{wid}/alerts/{alert['id']}", headers=member).status_code
        == 204
    )


def test_alert_threshold_cooldown_duplicate_read_and_unsubscribe(integration):
    env = integration
    h, _, wid, _, _, path, _ = setup(env)
    mid = monitor(env, h, path)["id"]
    rule = env.client.post(
        f"/workspaces/{wid}/monitors/{mid}/alerts",
        headers=h,
        json=dict(operator="gte", threshold="0.5", cooldown_minutes=60),
    ).json()
    process(env, h, path)
    for amount in ("0.30", "0.40"):
        candidate = stage(
            env, h, path, f"city,amount\nKarachi,{amount}\nLahore,0.20\n".encode()
        ).json()
        activate(env, h, wid, candidate)
        assert process(env, h, path)["complete"] == 1
        assert process(env, h, path)["complete"] == 0
    deliveries = env.client.get(path + "/monitors", headers=h).json()["monitors"][0]["deliveries"]
    assert sorted(d["status"] for d in deliveries) == ["delivered", "suppressed_cooldown"]
    eid = next(d["id"] for d in deliveries if d["status"] == "delivered")
    assert (
        env.client.post(f"/workspaces/{wid}/alert-events/{eid}/read", headers=h).status_code == 204
    )
    assert env.client.delete(f"/workspaces/{wid}/alerts/{rule['id']}", headers=h).status_code == 204
    candidate = stage(env, h, path).json()
    activate(env, h, wid, candidate)
    process(env, h, path)
    assert (
        len(env.client.get(path + "/monitors", headers=h).json()["monitors"][0]["deliveries"]) == 2
    )


def test_monthly_complete_and_incomplete_periods(integration):
    env = integration
    as_of = datetime(2026, 9, 15, tzinfo=timezone.utc)
    h, _, wid, _, _, path, feed = setup(
        env, b"date,city,amount\n2026-07-01,K,0.10\n2026-08-01,K,0.30\n2026-09-01,K,99\n"
    )
    with env.runtime.refresh.uow() as repo:
        current = repo.refresh_feed(UUID(wid), UUID(feed["id"]))
        repo.set_refresh_feed(
            replace(
                current,
                source={
                    **current.source,
                    "as_of": as_of.isoformat(),
                    "coverage_start": "2026-07-01",
                    "coverage_end": "2026-08-31",
                },
            )
        )
    monitor(env, h, path, date_column="date")
    assert asyncio.run(env.runtime.monitoring.process(as_of))["complete"] == 1
    first = observations(env, h, path)[0]
    assert Decimal(first["finding"]["value"]) == Decimal("0.30")
    assert Decimal(first["finding"]["delta"]) == Decimal("0.20")
    assert "incomplete_periods" not in first["finding"]["limitations"]
    assert first["observation"]["evidence"]["periods"][0] == dict(
        start="2026-08-01", end="2026-09-01"
    )
    assert periods({"as_of": as_of.isoformat()}, "date")[1] == ["incomplete_periods"]


def test_retry_delivery_failure_and_stale_claim(integration, monkeypatch):
    env = integration
    h, _, wid, _, _, path, _ = setup(env)
    mid = monitor(env, h, path)["id"]
    env.client.post(
        f"/workspaces/{wid}/monitors/{mid}/alerts",
        headers=h,
        json=dict(operator="gt", threshold="0.1", cooldown_minutes=1),
    )
    process(env, h, path)
    candidate = stage(env, h, path).json()
    activate(env, h, wid, candidate)
    original = env.runtime.monitoring._deliver

    def broken(*args):
        original(*args)
        raise RuntimeError("Simulated database delivery failure")

    monkeypatch.setattr(env.runtime.monitoring, "_deliver", broken)
    assert process(env, h, path)["failed"] == 1
    assert env.client.get(path + "/monitors", headers=h).json()["monitors"][0]["deliveries"] == []
    monkeypatch.setattr(env.runtime.monitoring, "_deliver", original)
    assert process(env, h, path)["complete"] == 1
    assert process(env, h, path)["complete"] == 0
    assert (
        len(env.client.get(path + "/monitors", headers=h).json()["monitors"][0]["deliveries"]) == 1
    )
    candidate = stage(env, h, path).json()
    activate(env, h, wid, candidate)
    with env.engine.begin() as connection:
        connection.execute(
            update(s.observations)
            .where(s.observations.c.status == "pending")
            .values(
                status="running",
                claimed_at=datetime.now(timezone.utc) - timedelta(minutes=11),
                claim_id=uuid4(),
                attempts=1,
            )
        )
    assert process(env, h, path)["complete"] == 1


@pytest.mark.parametrize(
    "mode,keys,duplicates,rows,code",
    [
        ("merge", [], "ignore_exact", (("K", "2"),), "keys_required"),
        ("append", ["city"], "reject", (("K", "1"),), "duplicate_key"),
        ("merge", ["city"], "ignore_exact", (("K", "2"), ("K", "3")), "duplicate_input_key"),
        ("merge", ["city"], "reject", (("", "1"),), "empty_key"),
    ],
)
def test_explicit_key_policies(mode, keys, duplicates, rows, code):
    with pytest.raises(IngestionError) as error:
        combine(
            TableData(("city", "amount"), (("K", "1"),)),
            TableData(("city", "amount"), rows),
            mode,
            keys,
            duplicates,
        )
    assert error.value.code == code


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "1e999", "abc", True, None])
def test_threshold_validation(raw):
    with pytest.raises(IngestionError):
        decimal_value(raw)


def test_exact_delta_and_reconciled_driver_math():
    assert difference("0.30", "0.10")["delta"] == "0.20"
    assert difference("10", "0")["percent_change"] is None
    assert drivers([["new", "0.30"]], [["old", "0.10"]], "0.20") == [
        dict(segment=["new"], delta="0.30"),
        dict(segment=["old"], delta="-0.10"),
    ]
    with pytest.raises(IngestionError):
        drivers([["x", "1"]], [], "2")


@pytest.mark.parametrize("storage_error", [RuntimeError, IngestionError])
def test_storage_failure_is_recorded_and_does_not_replace_source(
    integration, monkeypatch, storage_error
):
    env = integration
    h, _, _, _, _, path, feed = setup(env)

    original_put = env.runtime.service.storage.put

    def unavailable(*args):
        original_put(*args)
        if storage_error is IngestionError:
            raise IngestionError("storage_unavailable", "private storage diagnostic", 503)
        raise RuntimeError("private storage diagnostic")

    monkeypatch.setattr(env.runtime.service.storage, "put", unavailable)
    response = stage(env, h, path)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "failed"
    assert "private storage diagnostic" not in response.text
    assert (
        len(env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket)["Contents"]) == 1
    )
    assert env.client.get(path + "/refresh", headers=h).json()["feed"]["source"] == feed["source"]


@pytest.mark.parametrize("limitation", ["stale", "incomplete", "missing"])
def test_alerts_block_unreliable_evidence(integration, limitation):
    env = integration
    content = b"date,city,amount\n2026-07-01,K,0.10\n2026-08-01,L,0.20\n"
    h, _, wid, _, _, path, _ = setup(env, content)
    mid = monitor(env, h, path, date_column="date" if limitation == "incomplete" else None)["id"]
    env.client.post(
        f"/workspaces/{wid}/monitors/{mid}/alerts",
        headers=h,
        json=dict(operator="gt", threshold="0", cooldown_minutes=1),
    )
    process(env, h, path)
    if limitation == "missing":
        content = b"date,city,amount\n2026-07-01,K,0.10\n2026-08-01,L,0.20\n2026-08-02,M,\n"
    candidate = stage(env, h, path, content).json()
    assert activate(env, h, wid, candidate).json()["status"] == "activated"
    now = datetime.now(timezone.utc) + (timedelta(days=3) if limitation == "stale" else timedelta())
    assert asyncio.run(env.runtime.monitoring.process(now))["complete"] == 1
    deliveries = env.client.get(path + "/monitors", headers=h).json()["monitors"][0]["deliveries"]
    assert [d["status"] for d in deliveries] == [
        "blocked_stale" if limitation == "stale" else "blocked_coverage"
    ]


def test_revoked_subscriber_and_monitor_owner_are_rechecked(integration):
    env = integration
    h, _, wid, _, _, path, _ = setup(env)
    member, actor = add_member(env, h, wid)
    mid = monitor(env, h, path)["id"]
    env.client.post(
        f"/workspaces/{wid}/monitors/{mid}/alerts",
        headers=member,
        json=dict(operator="gt", threshold="0", cooldown_minutes=1),
    )
    process(env, h, path)
    candidate = stage(env, h, path).json()
    activate(env, h, wid, candidate)
    assert env.client.delete(f"/workspaces/{wid}/members/{actor.id}", headers=h).status_code == 204
    assert process(env, h, path)["complete"] == 1
    with env.engine.connect() as connection:
        assert connection.execute(select(s.alert_events.c.status)).scalars().all() == [
            "unauthorized"
        ]
    assert env.client.get(path + "/observations", headers=member).status_code in {403, 404}


def test_changed_preparation_blocks_activation_and_old_evidence_still_replays(integration):
    env = integration
    h, _, wid, _, uid, path, feed = setup(env)
    monitor(env, h, path)
    process(env, h, path)
    candidate = stage(env, h, path).json()
    with env.runtime.refresh.uow() as repo:
        latest = repo.latest_understanding(UUID(wid), UUID(feed["dataset_id"]))
        repo.add(replace(latest, id=uuid4(), version=latest.version + 1, state="rejected"))
    assert activate(env, h, wid, candidate).json()["status"] == "conflict"
    assert env.client.get(path + "/refresh", headers=h).json()["feed"]["source"]["upload_id"] == uid
    reopened = observations(env, h, path)[0]
    assert Decimal(reopened["finding"]["value"]) == Decimal("0.30")
    assert "current_definition_needs_review" in reopened["finding"]["limitations"]


def test_missing_object_fails_replay_instead_of_returning_cached_finding(integration):
    env = integration
    h, _, wid, did, uid, path, _ = setup(env)
    monitor(env, h, path)
    process(env, h, path)
    oid = observations(env, h, path)[0]["observation"]["id"]
    with env.runtime.refresh.uow() as repo:
        upload = repo.upload(UUID(wid), UUID(did), UUID(uid))
    env.runtime.service.storage.delete(upload)
    response = env.client.get(f"/workspaces/{wid}/observations/{oid}", headers=h)
    assert response.status_code in {409, 503, 404}


def test_schema_same_meaning_edit_requires_rebase(integration):
    env = integration
    h, _, _, _, uid, path, _ = setup(env)
    root = path + f"/uploads/{uid}"
    meaning = context(env, h, root)
    meaning["definition"]["columns"][1]["unit"] = "USD"
    assert confirm(env, h, root, meaning).status_code == 201
    assert stage(env, h, path).status_code == 409
    assert env.client.get(path + "/refresh", headers=h).json()["definition_state"] == "needs_review"


def test_activation_transaction_failure_rolls_back_meaning_and_jobs(integration, monkeypatch):
    import execplus.application.services.refresh as service_module

    env = integration
    h, actor, wid, _, _, path, feed = setup(env)
    candidate = stage(env, h, path).json()

    def broken(*args):
        raise RuntimeError("Simulated enqueue failure")

    monkeypatch.setattr(service_module, "enqueue", broken)
    with pytest.raises(RuntimeError):
        env.runtime.refresh.activate(actor, UUID(wid), UUID(candidate["id"]))
    state = env.client.get(path + "/refresh", headers=h).json()
    assert state["feed"] == feed
    assert state["candidates"][0]["status"] == "queued"
    assert state["definition_state"] == "confirmed"


def test_staged_cleaning_cannot_bypass_candidate_review(integration):
    env = integration
    h, _, wid, did, _, path, feed = setup(env)
    candidate = stage(env, h, path).json()
    with env.runtime.refresh.uow() as repo:
        uid = UUID(candidate["details"]["output_upload_id"])
        rev = repo.active_revision(UUID(wid), UUID(did), uid)
        changed = replace(rev, id=uuid4(), parent_id=rev.id)
        repo.add(changed)
        repo.set_active_revision(changed)
    assert activate(env, h, wid, candidate).status_code == 409
    assert env.client.get(path + "/refresh", headers=h).json()["feed"] == feed


def test_monitor_limit_and_disabled_monitor_delivery(integration):
    env = integration
    h, _, wid, _, _, path, _ = setup(env)
    for i in range(6):
        monitor(env, h, path, name=f"Monitor {i}")
    response = env.client.post(
        path + "/monitors",
        headers=h,
        json=dict(name="Seventh", method=dict(kind="metric", column="amount", aggregation="sum")),
    )
    assert response.status_code == 409
    rows = env.client.get(path + "/monitors", headers=h).json()["monitors"]
    mid = rows[0]["monitor"]["id"]
    assert env.client.delete(f"/workspaces/{wid}/monitors/{mid}", headers=h).status_code == 204
    monitor(env, h, path, name="Replacement monitor")
    assert process(env, h, path) == dict(complete=6, failed=1, skipped=0)


def test_access_revoked_between_replays_blocks_final_response(integration, monkeypatch):
    env = integration
    h, _, wid, _, _, path, _ = setup(env)
    member, actor = add_member(env, h, wid)
    monitor(env, h, path)
    process(env, h, path)
    oid = observations(env, h, path)[0]["observation"]["id"]
    original = env.runtime.analytics.replay

    async def revoke(*args):
        result = await original(*args)
        with env.engine.begin() as connection:
            connection.execute(
                s.memberships.delete().where(
                    s.memberships.c.workspace_id == UUID(wid), s.memberships.c.user_id == actor.id
                )
            )
        return result

    monkeypatch.setattr(env.runtime.analytics, "replay", revoke)
    response = env.client.get(f"/workspaces/{wid}/observations/{oid}", headers=member)
    assert response.status_code in {403, 404}
    assert "0.300000000000" not in response.text


def test_worker_rechecks_config_owner_and_candidate_creator(integration):
    env = integration
    h, actor, wid, _, _, path, feed = setup(env)
    admin, _ = add_member(env, h, wid, role="admin")
    candidate = stage(env, h, path).json()
    with env.engine.begin() as connection:
        connection.execute(
            s.memberships.delete().where(
                s.memberships.c.workspace_id == UUID(wid), s.memberships.c.user_id == actor.id
            )
        )
    due = datetime.fromisoformat(feed["next_due"].replace("Z", "+00:00"))
    assert env.runtime.refresh.process_due(due)["failed"] == 1
    assert activate(env, admin, wid, candidate).status_code in {403, 404}
    state = env.client.get(path + "/refresh", headers=admin).json()
    assert state["feed"]["enabled"] is False
    assert state["feed"]["source"] == feed["source"]


def test_manual_processing_scopes_before_the_worker_batch_limit(integration):
    env = integration
    other, _, wid, _, _, path, _ = setup(env)
    mid = monitor(env, other, path)["id"]
    with env.runtime.monitoring.uow() as repo:
        base = repo.observations(UUID(wid), UUID(mid))[0]
        for version in range(2, 103):
            repo.add(replace(base, id=uuid4(), source_version=version))
    h, _, _, _, _, selected, _ = setup(env)
    monitor(env, h, selected)
    assert process(env, h, selected)["complete"] == 1
    with env.runtime.monitoring.uow() as repo:
        assert all(o.status == "pending" for o in repo.observations(UUID(wid), UUID(mid)))


def test_segment_truncation_cannot_be_mistaken_for_complete_drivers(integration):
    env = integration
    h, _, _, _, _, path, _ = setup(env)
    monitor(env, h, path)
    env.runtime.analytics.row_limit = 1
    assert process(env, h, path)["failed"] == 1
    value = observations(env, h, path)[0]
    assert value["finding"] is None
    assert value["observation"]["evidence"]["failure_code"] == "monitor_too_many_groups"


def test_monthly_monitor_reserves_filter_slots_for_period_bounds(integration):
    env = integration
    h, _, _, _, _, path, _ = setup(env, b"date,city,amount\n2026-07-01,K,0.10\n2026-08-01,L,0.20\n")
    response = env.client.post(
        path + "/monitors",
        headers=h,
        json=dict(
            name="Too many filters",
            date_column="date",
            method=dict(
                kind="metric",
                column="amount",
                aggregation="sum",
                filters=[
                    dict(column="city", operator="ne", value=f"excluded{i}") for i in range(19)
                ],
            ),
        ),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_period"
