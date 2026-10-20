"""Use case: Checks redacted incident collection, lifecycle and outage recovery.

What it does: Verifies fixed metadata, bounded nonblocking queues and safe optimistic
updates before exercising durable SQL collection and staff-only HTTP access.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from execplus.application.services.incidents import IncidentService
from execplus.domain.incidents import IncidentOccurrence, observe, transition
from execplus.domain.ingestion import IngestionError


def occurrence(code="http_failed", **changes):
    return IncidentOccurrence(
        **{
            "source_kind": "http",
            "source_id": uuid4(),
            "occurred_at": datetime.now(timezone.utc),
            "code": code,
            **changes,
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"code": "private-question-or-token"},
        {"source_kind": "user@example.test"},
        {"count": 0},
        {"count": True},
        {"count": 1_000_001},
        {"occurred_at": datetime(2026, 1, 1)},
        {"source_id": "secret"},
    ],
)
def test_occurrence_rejects_unbounded_or_untrusted_metadata(changes):
    with pytest.raises(ValueError):
        occurrence(**changes)


def test_repeated_incident_counts_exactly_and_new_failure_reopens_resolution():
    event = occurrence()
    first = observe(None, event)
    acknowledged = transition(first, 1, "acknowledged", event.occurred_at)
    assert acknowledged.status == "acknowledged" and acknowledged.version == 2
    repeated = observe(
        acknowledged, occurrence(occurred_at=event.occurred_at + timedelta(seconds=1))
    )
    assert repeated.occurrences == 2 and repeated.status == "acknowledged"
    resolved = transition(repeated, 3, "resolved", event.occurred_at)
    reopened = observe(resolved, occurrence(count=3))
    assert reopened.status == "open" and reopened.occurrences == 5
    assert reopened.acknowledged_at is None and reopened.resolved_at is None
    with pytest.raises(IngestionError, match="changed"):
        transition(reopened, 1, "resolved", event.occurred_at)
    with pytest.raises(IngestionError):
        transition(reopened, reopened.version, "deleted", event.occurred_at)


class MemoryStore:
    def __init__(self):
        self.calls = []
        self.fail = False
        self.capacity = False

    def collect(self, values, now, observations=None):
        self.calls.append(values)
        if self.fail:
            raise RuntimeError("secret-token-private-user-data")
        return {"accepted": len(values), "capacity_limited": int(self.capacity)}


def test_request_queue_never_calls_storage_and_outage_retry_retains_occurrences(caplog):
    async def run():
        store = MemoryStore()
        service = IncidentService(store, queue_limit=2)
        for _ in range(5):
            service.record_http_failure()
        assert not store.calls and len(service.pending) == 2 and service.dropped == 3
        original = tuple(service.pending)
        store.fail = True
        assert not await service.collect_once()
        assert tuple(service.pending) == original and service.dropped == 3
        assert service.outages == 1 and service.last_failure is not None
        store.fail = False
        assert await service.collect_once()
        recovered = store.calls[-1]
        assert recovered[:2] == original
        assert {item.code: item.count for item in recovered[2:]} == {
            "queue_overflow": 3,
            "collector_recovered": 1,
        }
        assert not service.pending and service.dropped == service.outages == 0
        assert service.last_success is not None
        store.capacity = True
        assert await service.collect_once()
        assert service.health()["capacity_limited"] is True

    asyncio.run(run())
    assert "incident_collector_unavailable" in caplog.text
    assert "secret-token" not in caplog.text and "RuntimeError" not in caplog.text


def test_collector_polls_and_stops_without_waiting_for_full_interval():
    async def run():
        store = MemoryStore()
        service = IncidentService(store, interval=60)
        task = asyncio.create_task(service.run())
        for _ in range(100):
            if service.last_success:
                break
            await asyncio.sleep(0.001)
        assert store.calls and service.running
        service.stop.set()
        await asyncio.wait_for(task, timeout=1)
        assert not service.running

    asyncio.run(run())


def test_staff_admin_lifecycle_is_private_versioned_and_revocable(integration):
    from sqlalchemy import select

    from execplus.infrastructure.persistence import schema as s
    from test_operations import setup

    env = integration
    owner, _, _, staff, _, admin, administrator = setup(env)
    store = env.runtime.incidents.store
    event = occurrence()
    store.collect((event,), event.occurred_at)
    for headers in ({}, owner, staff):
        assert env.client.get("/admin/incidents", headers=headers).status_code in {401, 403}
    response = env.client.get("/admin/incidents", headers=admin)
    assert response.status_code == 200, response.text
    item = response.json()["incidents"][0]
    assert item["title"] == "A server request failed" and item["occurrences"] == 1
    path = f"/admin/incidents/{item['id']}"
    ack = env.client.patch(
        path, headers=admin, json={"expected_version": 1, "status": "acknowledged"}
    )
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged"
    assert (
        env.client.patch(
            path, headers=admin, json={"expected_version": 1, "status": "resolved"}
        ).status_code
        == 409
    )
    assert (
        env.client.patch(
            path, headers=admin, json={"expected_version": 2, "status": "resolved"}
        ).status_code
        == 200
    )
    assert not env.client.get("/admin/incidents", headers=admin).json()["incidents"]
    store.collect((occurrence(),), datetime.now(timezone.utc))
    reopened = env.client.get("/admin/incidents", headers=admin).json()["incidents"][0]
    assert reopened["status"] == "open" and reopened["occurrences"] == 2
    env.runtime.operations.change_staff(administrator.email, None)
    assert env.client.get("/admin/incidents", headers=admin).status_code == 403
    assert (
        env.client.patch(
            path, headers=admin, json={"expected_version": 4, "status": "resolved"}
        ).status_code
        == 403
    )
    with env.engine.connect() as conn:
        audits = conn.execute(select(s.staff_audit)).mappings().all()
    assert any(
        row["action"] == "incident.acknowledged" and row["outcome"] == "success" for row in audits
    )
    assert any(row["action"] == "incident.updated" and row["outcome"] == "denied" for row in audits)


def test_durable_failures_are_polled_once_without_reading_private_payloads(integration):
    from sqlalchemy import insert, select, update

    from execplus.infrastructure.persistence import schema as s
    from test_conversation_jobs import prepared, submit
    from test_phase3_integration import CapturingEmail, analysis, setup

    env = integration
    owner, _, _, path, _ = prepared(env)
    job = submit(env, owner, path, question="Private question must never be stored in incidents")
    timestamp = datetime.now(timezone.utc)
    with env.engine.begin() as conn:
        conn.execute(
            update(s.jobs)
            .where(s.jobs.c.id == job["id"])
            .values(status="failed", failure_code="secret-private-diagnostic", updated_at=timestamp)
        )
    report_owner, actor, wid, _, _, root = setup(env)
    saved, _ = analysis(env, report_owner, root)
    mail = CapturingEmail()
    mail.fail = True
    env.runtime.reports.email = mail
    assert (
        env.client.post(
            f"/workspaces/{wid}/report-schedules",
            headers=report_owner,
            json={"item_id": saved["id"], "interval_hours": 1},
        ).status_code
        == 201
    )
    assert (
        asyncio.run(env.runtime.reports.deliver_due(timestamp + timedelta(hours=2)))["failed"] == 1
    )
    with env.engine.begin() as conn:
        conn.execute(
            insert(s.audit_events).values(
                id=uuid4(),
                workspace_id=wid,
                actor_id=actor.id,
                action="refresh.activation_failed",
                resource_type="refresh_candidate",
                resource_id=uuid4(),
                created_at=timestamp,
            )
        )
    store = env.runtime.incidents.store
    assert store.collect((), timestamp)["accepted"] == 3
    assert store.collect((), timestamp)["accepted"] == 0
    with env.engine.connect() as conn:
        rows = conn.execute(select(s.incidents)).mappings().all()
        keys = conn.execute(select(s.incident_occurrences)).mappings().all()
    assert {row["code"] for row in rows} == {"job_failed", "report_failed", "refresh_failed"}
    assert all(row["occurrences"] == 1 for row in rows)
    assert "secret" not in str(rows) + str(keys)
    assert "Private question" not in str(rows) + str(keys)


def test_concurrent_collectors_deduplicate_and_retention_is_bounded(integration, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import select, update

    from execplus.infrastructure.persistence import incidents as module
    from execplus.infrastructure.persistence import schema as s

    env = integration
    store = env.runtime.incidents.store
    events = (occurrence(), occurrence())
    timestamp = datetime.now(timezone.utc)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: store.collect(events, timestamp), range(2)))
    assert sum(result["accepted"] for result in results) == 2
    with env.engine.connect() as conn:
        assert conn.execute(select(s.incidents.c.occurrences)).scalar_one() == 2
    monkeypatch.setattr(module, "MAX_OCCURRENCES", 2)
    assert store.collect((occurrence(),), timestamp)["capacity_limited"] == 1
    with env.engine.begin() as conn:
        conn.execute(
            update(s.incident_occurrences).values(occurred_at=timestamp - timedelta(days=31))
        )
        conn.execute(
            update(s.incidents).values(
                status="resolved",
                last_seen=timestamp - timedelta(days=31),
                resolved_at=timestamp - timedelta(days=31),
            )
        )
    assert store.collect((occurrence(),), timestamp)["accepted"] == 1
    with env.engine.connect() as conn:
        assert len(conn.execute(select(s.incident_occurrences)).all()) == 1
        rows = conn.execute(select(s.incidents)).mappings().all()
    assert len(rows) == 1 and rows[0]["occurrences"] == 1


def test_http_errors_are_queued_without_request_details_or_response_delay(integration):
    from fastapi.responses import JSONResponse
    from sqlalchemy import select

    from execplus.infrastructure.persistence import schema as s

    env = integration

    @env.client.app.get("/test-private-incident")
    def fail():
        return JSONResponse(status_code=503, content={"error": "Temporary failure"})

    response = env.client.get(
        "/test-private-incident?token=PRIVATE_SENTINEL", headers={"X-Private": "PRIVATE_HEADER"}
    )
    assert response.status_code == 503 and response.headers["cache-control"] == "no-store"
    assert len(env.runtime.incidents.pending) == 1
    env.client.portal.call(env.runtime.incidents.collect_once)
    with env.engine.connect() as conn:
        rows = conn.execute(select(s.incidents)).mappings().all()
        keys = conn.execute(select(s.incident_occurrences)).mappings().all()
    assert rows[0]["code"] == "http_failed"
    assert "PRIVATE" not in str(rows) + str(keys)


def test_incident_evidence_refuses_destructive_downgrade(integration):
    from alembic import command

    env = integration
    env.runtime.incidents.store.collect((occurrence(),), datetime.now(timezone.utc))
    with (
        pytest.raises(RuntimeError, match=r"Preserve (internal incident|operational metrics)"),
        env.engine.begin() as conn,
    ):
        env.config.attributes["connection"] = conn
        command.downgrade(env.config, "0019")


def test_real_locked_database_is_bounded_and_retained_queue_recovers(integration, caplog):
    from time import monotonic

    from sqlalchemy import select, text

    from execplus.infrastructure.persistence import schema as s

    env = integration
    service = IncidentService(env.runtime.incidents.store)
    service.record_http_failure()
    with env.engine.begin() as blocker:
        blocker.execute(text("SELECT pg_advisory_xact_lock(619832043)"))
        started = monotonic()
        assert not asyncio.run(service.collect_once())
        assert 0.8 <= monotonic() - started < 4
        assert len(service.pending) == 1
    assert asyncio.run(service.collect_once())
    with env.engine.connect() as connection:
        rows = connection.execute(select(s.incidents)).mappings().all()
    assert {row["code"] for row in rows} == {"http_failed", "collector_recovered"}
    assert "LockNotAvailable" not in caplog.text and "619832043" not in caplog.text


def test_cancelled_collection_drains_real_sql_before_returning(integration):
    from time import monotonic

    from sqlalchemy import text

    env = integration
    service = IncidentService(env.runtime.incidents.store)
    service.record_http_failure()

    async def cancel():
        task = asyncio.create_task(service.collect_once())
        await asyncio.sleep(0.1)
        task.cancel()
        await asyncio.sleep(0.1)
        assert not task.done()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(service.pending) == 1

    with env.engine.begin() as blocker:
        blocker.execute(text("SELECT pg_advisory_xact_lock(619832043)"))
        started = monotonic()
        asyncio.run(cancel())
        assert monotonic() - started < 4
    assert asyncio.run(service.collect_once())


def test_real_connection_outage_reports_fixed_failure_then_recovers(integration, caplog):
    from sqlalchemy import create_engine

    from execplus.infrastructure.persistence.incidents import SQLIncidentStore

    env = integration
    unavailable = create_engine(
        env.engine.url.set(host="127.0.0.1", port=1),
        connect_args={"connect_timeout": 1},
        pool_timeout=1,
    )
    service = IncidentService(SQLIncidentStore(unavailable))
    service.record_http_failure()
    assert not asyncio.run(service.collect_once())
    assert service.last_failure is not None and len(service.pending) == 1
    unavailable.dispose()
    service.store = env.runtime.incidents.store
    assert asyncio.run(service.collect_once())
    assert service.last_success is not None and not service.pending
    assert "password" not in caplog.text and "OperationalError" not in caplog.text


def test_large_fixed_batch_is_complete_and_old_occurrences_are_not_retained(integration):
    from sqlalchemy import select

    from execplus.infrastructure.persistence import schema as s

    env = integration
    now = datetime.now(timezone.utc)
    events = tuple(occurrence() for _ in range(500))
    result = env.runtime.incidents.store.collect(
        (*events, occurrence(occurred_at=now - timedelta(days=31))), now
    )
    assert result == {"accepted": 500, "capacity_limited": 0}
    with env.engine.connect() as conn:
        assert len(conn.execute(select(s.incident_occurrences)).all()) == 500
        assert conn.execute(select(s.incidents.c.occurrences)).scalar_one() == 500
