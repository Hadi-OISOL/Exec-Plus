"""Use case: Verifies exact local alert rules, bounded buffering and redacted correlation.

What it does: Exercises completed-minute windows, real SQL retry/concurrency, staff
permissions, failed request classification and preservation of operational evidence.
"""

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from execplus.application.services.incidents import IncidentService
from execplus.domain.ingestion import IngestionError
from execplus.domain.operational_metrics import (
    AlertPolicy,
    ObservationBatch,
    RequestObservation,
    assess,
)

NOW = datetime(2026, 10, 17, 12, 0, 20, tzinfo=timezone.utc)


def observed(**changes):
    return RequestObservation(
        **dict(
            minute=NOW.replace(minute=59, hour=11, second=0),
            category="exports",
            requests=40,
            rejected=4,
            failed=3,
            response_start_ms=1000,
            maximum_response_start_ms=80,
            **changes,
        )
    )


def test_exact_threshold_boundary_excludes_current_and_outside_minutes():
    policy = AlertPolicy(
        "exports",
        enabled=True,
        window_minutes=2,
        minimum_requests=40,
        minimum_failures=3,
        failure_basis_points=750,
    )
    current = replace(observed(), minute=NOW.replace(second=0), requests=100, failed=90)
    old = replace(current, minute=NOW.replace(minute=57, hour=11, second=0))
    value = assess(policy, (observed(), current, old), NOW)
    assert value["state"] == "alert"
    assert value["requests"] == 40 and value["rejected"] == 4 and value["successful"] == 33
    assert value["failure_rate"] == {
        "numerator": "3",
        "denominator": "40",
        "percent_display": "7.50",
    }
    assert value["mean_response_start_ms"] == "25.000" and value["maximum_response_start_ms"] == 80
    assert (
        assess(replace(policy, failure_basis_points=751), (observed(),), NOW)["state"]
        == "below_threshold"
    )
    assert (
        assess(replace(policy, minimum_failures=4), (observed(),), NOW)["state"]
        == "below_threshold"
    )
    assert (
        assess(replace(policy, minimum_requests=41), (observed(),), NOW)["state"]
        == "insufficient_data"
    )
    empty = assess(policy, (), NOW)
    assert (
        empty["state"] == "insufficient_data" and empty["failure_rate"]["percent_display"] is None
    )
    assert assess(replace(policy, enabled=False), (observed(),), NOW)["state"] == "disabled"


@pytest.mark.parametrize(
    "change",
    [
        {"category": "PRIVATE_FILE"},
        {"enabled": 1},
        {"window_minutes": 0},
        {"window_minutes": 61},
        {"minimum_requests": True},
        {"minimum_failures": 0},
        {"failure_basis_points": 10001},
    ],
)
def test_alert_settings_reject_unknown_or_unbounded_values(change):
    with pytest.raises(IngestionError):
        AlertPolicy(**{"category": "exports", **change})


@pytest.mark.parametrize(
    "change",
    [
        {"requests": 0},
        {"requests": True},
        {"failed": 41},
        {"rejected": -1},
        {"category": "SECRET"},
        {"minute": NOW},
        {"minute": datetime(2026, 10, 17)},
        {"maximum_response_start_ms": 1001},
    ],
)
def test_observations_reject_untrusted_metadata(change):
    with pytest.raises(ValueError):
        replace(observed(), **change)


def test_bounded_buffer_keeps_stable_retry_batch_and_surfaces_overflow(monkeypatch):
    from execplus.application.services import incidents as module

    class Store:
        def __init__(self):
            self.fail = True
            self.batches = []

        def collect(self, values, now, batch):
            self.batches.append(batch)
            if self.fail:
                raise RuntimeError("PRIVATE")
            return {"capacity_limited": 0, "metrics_accepted": 1, "metrics_expired": 0}

    async def run():
        monkeypatch.setattr(module, "MAX_PENDING_BUCKETS", 2)
        store = Store()
        service = IncidentService(store)
        for status in (200, 403, 503):
            service.record_request("exports", status, 10, now=NOW)
        service.record_request("analysis", 200, 1, now=NOW)
        service.record_request("other", 200, 1, now=NOW)
        assert service.health()["metric_dropped_or_expired_requests"] == 1 and not store.batches
        assert not await service.collect_once()
        original = service.observation_batch
        assert original.observations[0].requests == 3
        assert original.observations[0].failed == original.observations[0].rejected == 1
        service.record_request("exports", 200, 1, now=NOW)
        store.fail = False
        assert await service.collect_once()
        assert store.batches[0] is store.batches[1] is original
        assert service.observation_batch is None and len(service.observations) == 1
        assert await service.collect_once()
        assert store.batches[2].id != original.id
        assert service.health()["metric_dropped_or_expired_requests"] == 1

    asyncio.run(run())


def test_real_metrics_deduplicate_concurrent_retry_and_preserve_exact_counts(integration):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import select

    from execplus.infrastructure.persistence import schema as s

    env = integration
    stamp = datetime.now(timezone.utc)
    value = replace(
        observed(), minute=(stamp - timedelta(minutes=1)).replace(second=0, microsecond=0)
    )
    batch = ObservationBatch(uuid4(), stamp, (value,))
    with ThreadPoolExecutor(2) as pool:
        result = list(
            pool.map(lambda _: env.runtime.incidents.store.collect((), stamp, batch), range(2))
        )
    assert all(item["metrics_accepted"] for item in result)
    with env.engine.connect() as conn:
        stored = conn.execute(select(s.request_metrics)).mappings().one()
        assert (
            stored["requests"] == 40
            and stored["failed"] == 3
            and stored["response_start_ms"] == 1000
        )
        assert len(conn.execute(select(s.request_metric_batches)).all()) == 1


def test_metrics_capacity_does_not_block_incidents_and_old_retry_never_recounts(
    integration, monkeypatch
):
    from sqlalchemy import select

    from execplus.infrastructure.persistence import incidents as module
    from execplus.infrastructure.persistence import schema as s
    from test_incidents import occurrence

    env = integration
    stamp = datetime.now(timezone.utc)
    value = replace(
        observed(), minute=(stamp - timedelta(minutes=1)).replace(second=0, microsecond=0)
    )
    batch = ObservationBatch(uuid4(), stamp, (value,))
    monkeypatch.setattr(module, "MAX_METRIC_BATCHES", 0)
    result = env.runtime.incidents.store.collect((occurrence(),), stamp, batch)
    assert (
        result["accepted"] == 1
        and result["metrics_capacity_limited"] == 1
        and result["metrics_accepted"] == 0
    )
    monkeypatch.setattr(module, "MAX_METRIC_BATCHES", 1)
    assert env.runtime.incidents.store.collect((), stamp, batch)["metrics_accepted"] == 1
    old = env.runtime.incidents.store.collect((), stamp + timedelta(days=3), batch)
    assert old["metrics_expired"] == 40
    with env.engine.connect() as conn:
        assert not conn.execute(select(s.request_metrics)).all()
        assert not conn.execute(select(s.request_metric_batches)).all()


def test_staff_threshold_settings_are_versioned_private_and_audited(integration):
    from sqlalchemy import select

    from execplus.infrastructure.persistence import schema as s
    from test_operations import setup

    env = integration
    owner, _, _, staff, _, admin, administrator = setup(env)
    path = "/admin/incidents/thresholds/exports"
    body = dict(
        expected_version=0,
        enabled=True,
        window_minutes=5,
        minimum_requests=20,
        minimum_failures=2,
        failure_basis_points=1000,
    )
    for headers in ({}, owner, staff):
        assert env.client.put(path, headers=headers, json=body).status_code in {401, 403}
    saved = env.client.put(path, headers=admin, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    assert env.client.put(path, headers=admin, json=body).status_code == 409
    report = env.client.get("/admin/incidents", headers=admin).json()
    target = next(value for value in report["metrics"] if value["category"] == "exports")
    assert target["policy"]["version"] == 1 and target["state"] == "insufficient_data"
    body["expected_version"] = 1
    body["enabled"] = False
    assert env.client.put(path, headers=admin, json=body).json()["version"] == 2
    env.runtime.operations.change_staff(administrator.email, None)
    assert env.client.put(path, headers=admin, json=body).status_code == 403
    with env.engine.connect() as conn:
        actions = conn.execute(select(s.staff_audit.c.action, s.staff_audit.c.outcome)).all()
    assert ("incident_threshold.exports.changed", "success") in actions
    assert ("incident_threshold.changed", "denied") in actions


def test_unhandled_failure_is_redacted_correlated_and_counted_once(integration, caplog):
    from sqlalchemy import select

    from execplus.infrastructure.persistence import schema as s
    from test_operations import setup

    env = integration
    _, _, _, _, _, admin, _ = setup(env)

    @env.client.app.post("/synthetic-result/export.xlsx")
    def failing_export():
        raise ValueError("PRIVATE_PASSWORD PRIVATE_FILE PRIVATE_QUERY")

    supplied_id = str(uuid4())
    response = env.client.post(
        "/synthetic-result/export.xlsx?secret=PRIVATE_QUERY",
        headers={
            "X-Request-ID": supplied_id,
            "Origin": env.client.app.state.web_origin,
        },
    )
    assert response.status_code == 500 and "PRIVATE" not in response.text
    assert response.headers["x-request-id"] != supplied_id
    correlation = UUID(response.headers["x-request-id"])
    assert response.headers["access-control-allow-origin"] == env.client.app.state.web_origin
    assert len(env.runtime.incidents.pending) == 1
    assert env.runtime.incidents.pending[0].source_id == correlation
    assert env.runtime.incidents.pending[0].code == "export_failed"
    assert (
        str(correlation) in caplog.text
        and "PRIVATE" not in caplog.text
        and "ValueError" not in caplog.text
    )
    env.client.portal.call(env.runtime.incidents.collect_once)
    with env.engine.connect() as conn:
        event = (
            conn.execute(select(s.incidents).where(s.incidents.c.code == "export_failed"))
            .mappings()
            .one()
        )
        metric = (
            conn.execute(select(s.request_metrics).where(s.request_metrics.c.category == "exports"))
            .mappings()
            .one()
        )
    assert metric["requests"] == metric["failed"] == 1
    path = f"/admin/incidents/{event['id']}/references"
    references = env.client.get(path, headers=admin)
    assert references.status_code == 200 and references.json()["references"][0]["source_id"] == str(
        correlation
    )
    assert env.client.get(path).status_code == 401
    assert "PRIVATE" not in references.text


def test_metric_history_refuses_destructive_downgrade(integration):
    from alembic import command

    env = integration
    stamp = datetime.now(timezone.utc)
    value = replace(observed(), minute=stamp.replace(second=0, microsecond=0))
    env.runtime.incidents.store.collect((), stamp, ObservationBatch(uuid4(), stamp, (value,)))
    with (
        pytest.raises(RuntimeError, match="Preserve operational metrics"),
        env.engine.begin() as conn,
    ):
        env.config.attributes["connection"] = conn
        command.downgrade(env.config, "0026")


def test_committed_metrics_retry_after_lost_response_does_not_double_count(integration):
    from sqlalchemy import select

    from execplus.infrastructure.persistence import schema as s

    real = integration.runtime.incidents.store

    class LostResponse:
        first = True

        def collect(self, values, now, batch):
            result = real.collect(values, now, batch)
            if self.first:
                self.first = False
                raise RuntimeError("Synthetic commit response lost")
            return result

    service = IncidentService(LostResponse())
    service.record_request("exports", 503, 21)
    assert not asyncio.run(service.collect_once())
    retained = service.observation_batch.id
    assert asyncio.run(service.collect_once())
    assert service.observation_batch is None
    with integration.engine.connect() as conn:
        row = (
            conn.execute(select(s.request_metrics).where(s.request_metrics.c.category == "exports"))
            .mappings()
            .one()
        )
        assert row["requests"] == row["failed"] == 1 and row["response_start_ms"] == 21
        assert conn.execute(select(s.request_metric_batches.c.id)).scalar_one() == retained


def test_request_categories_exclude_polling_and_never_inspect_content():
    from types import SimpleNamespace

    from starlette.requests import Request

    from execplus.presentation.request_observation import category_for

    def category(method, template, tags=()):
        return category_for(
            Request(
                {
                    "type": "http",
                    "method": method,
                    "path": "/PRIVATE_DATA",
                    "query_string": b"PRIVATE_TOKEN",
                    "headers": [],
                    "route": SimpleNamespace(path=template, tags=tags),
                }
            )
        )

    assert category("GET", "/health/ready") is None
    assert category("GET", "/admin/incidents") is None
    assert category("OPTIONS", "/workspaces") is None
    assert category("POST", "/workspaces/{wid}/samples/{id}") == "ingestion"
    assert category("POST", "/workspaces/{wid}/datasets/{did}/uploads") == "ingestion"
    assert category("POST", "/datasets/{did}/google-sheets/import", ("google",)) == "ingestion"
    assert category("POST", "/datasets/{did}/connectors/{provider}/import", ("connectors",)) == (
        "ingestion"
    )
    assert category("POST", "/connectors/{provider}/connect", ("connectors",)) == "other"
    assert category("POST", "/workspaces/{wid}/threads/{tid}/jobs") == "queue"
    assert category("GET", "/workspaces/{wid}/saved/{id}/export.xlsx") == "exports"
    assert category("POST", "/workspaces/{wid}/anomalies", ("decision analysis",)) == "analysis"
    assert category("GET", "/workspaces") == "other"


def test_job_acceptance_correlates_only_opaque_ids(integration, caplog):
    import json
    import logging

    from test_conversation_jobs import prepared

    env = integration
    owner, _, _, path, _ = prepared(env)
    with caplog.at_level(logging.INFO, logger="execplus.requests"):
        response = env.client.post(
            path + "/jobs",
            headers=owner,
            json={"question": "PRIVATE_QUESTION_SENTINEL", "request_id": str(uuid4())},
        )
    assert response.status_code == 202, response.text
    records = [json.loads(row.message) for row in caplog.records if row.name == "execplus.requests"]
    assert records == [
        {
            "event": "job_accepted",
            "job_id": response.json()["id"],
            "request_id": response.headers["x-request-id"],
        }
    ]
    assert "PRIVATE_QUESTION_SENTINEL" not in caplog.text


def test_collector_overflow_and_recovery_retries_keep_original_occurrence_ids(integration):
    from sqlalchemy import select

    from execplus.infrastructure.persistence import schema as s

    real = integration.runtime.incidents.store

    class Interrupted:
        calls = 0

        def collect(self, values, now, batch):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Synthetic connection loss")
            result = real.collect(values, now, batch)
            if self.calls == 2:
                raise RuntimeError("Synthetic acknowledgement loss")
            return result

    service = IncidentService(Interrupted(), queue_limit=1)
    for _ in range(4):
        service.record_http_failure()
    assert not asyncio.run(service.collect_once())
    assert not asyncio.run(service.collect_once())
    assert asyncio.run(service.collect_once())
    assert asyncio.run(service.collect_once())
    assert service.outages == service.dropped == 0
    with integration.engine.connect() as conn:
        counts = dict(conn.execute(select(s.incidents.c.code, s.incidents.c.occurrences)).all())
    assert counts == {"http_failed": 1, "queue_overflow": 3, "collector_recovered": 2}


@pytest.mark.parametrize("retry_batch", [False, True])
def test_clean_shutdown_flushes_metrics_without_pending_failed_requests(retry_batch):
    from types import SimpleNamespace

    from execplus.config import Settings
    from execplus.main import create_app

    class Store:
        def __init__(self):
            self.batches = []

        def collect(self, values, now, batch):
            self.batches.append(batch)
            return {"capacity_limited": 0, "metrics_accepted": 1}

    async def run():
        store = Store()
        service = IncidentService(store)
        # Hold background polling so the final request reaches the shutdown path.
        service.run = service.stop.wait
        webhook_stop = asyncio.Event()
        runtime = SimpleNamespace(
            incidents=service,
            webhooks=SimpleNamespace(stop=webhook_stop, run=webhook_stop.wait),
        )
        app = create_app(Settings(_env_file=None, environment="test"), runtime)
        original = None
        async with app.router.lifespan_context(app):
            service.record_request("exports", 200, 17)
            if retry_batch:
                original = ObservationBatch(
                    uuid4(), datetime.now(timezone.utc), tuple(service.observations.values())
                )
                service.observation_batch = original
                service.observations.clear()
            assert not store.batches and not service.pending
        assert len(store.batches) == 1
        assert store.batches[0].observations[0].requests == 1
        assert store.batches[0].observations[0].response_start_ms == 17
        if original:
            assert store.batches[0] is original
        assert service.observation_batch is None and not service.observations

    asyncio.run(run())
