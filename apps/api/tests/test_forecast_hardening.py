"""Use case: Independently guards forecast publication, replay identity and reader cleanup.

What it does: Exercises real snapshot evidence under tampering, revocation and cancellation.
"""

import asyncio
import threading
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from execplus.domain.forecast_series import series_values
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryResult
from execplus.infrastructure.persistence import schema as s
from test_forecast_integration import create, daily, request
from test_studies import add_member, prepare
from test_understanding import confirm, context
from test_workspace_integration import dataset, upload


def calendar_evidence():
    periods = (date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3))
    results = [
        QueryResult(
            uuid4(),
            ("__forecast_period", "__value"),
            tuple((period, value) for period in periods),
            3,
        )
        for value in (Decimal("0.123456789012345678901234567890"), 1, 1)
    ]
    raw = dict(
        coverage_confirmed=True,
        coverage_start="2024-01-01",
        coverage_end="2024-01-03",
        frequency="daily",
    )
    return results, raw


@pytest.mark.parametrize("index", [0, 1, 2])
def test_calendar_evidence_rejects_duplicate_periods_in_each_receipt(index):
    results, raw = calendar_evidence()
    result = results[index]
    results[index] = replace(result, rows=(*result.rows, result.rows[0]))
    with pytest.raises(IngestionError, match="duplicate periods"):
        series_values(results, raw, allow_missing=True)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_calendar_evidence_requires_matching_value_and_coverage_periods(index):
    results, raw = calendar_evidence()
    results[index] = replace(results[index], rows=results[index].rows[:-1])
    with pytest.raises(IngestionError, match="inconsistent periods"):
        series_values(results, raw, allow_missing=True)


@pytest.mark.parametrize("index,value", [(1, True), (2, True), (1, -1), (2, 0), (2, "1")])
def test_calendar_evidence_rejects_malformed_record_counts(index, value):
    results, raw = calendar_evidence()
    result = results[index]
    results[index] = replace(result, rows=((result.rows[0][0], value), *result.rows[1:]))
    with pytest.raises(IngestionError, match="invalid record counts"):
        series_values(results, raw)


@pytest.mark.parametrize("value", [None, True, 1.2, "1.2", Decimal("NaN"), Decimal("Infinity")])
def test_calendar_evidence_rejects_missing_or_inexact_aggregate_values(value):
    results, raw = calendar_evidence()
    result = results[0]
    results[0] = replace(result, rows=((result.rows[0][0], value), *result.rows[1:]))
    with pytest.raises(IngestionError, match="finite numbers"):
        series_values(results, raw, allow_missing=True)


@pytest.mark.parametrize(
    "period", [date(2024, 1, 4), datetime(2024, 1, 1, 12), "2024-01-01"]
)
def test_calendar_evidence_rejects_unrequested_or_noncalendar_periods(period):
    results, raw = calendar_evidence()
    results = [replace(result, rows=((period, result.rows[0][1]),)) for result in results]
    with pytest.raises(IngestionError):
        series_values(results, raw, allow_missing=True)


def test_calendar_evidence_rejects_malformed_shape_without_unpacking_error():
    results, raw = calendar_evidence()
    results[0] = replace(results[0], rows=((date(2024, 1, 1),),))
    with pytest.raises(IngestionError, match="malformed"):
        series_values(results, raw)


def test_calendar_evidence_preserves_exact_values_and_explicit_pending_gaps():
    results, raw = calendar_evidence()
    results = [replace(result, rows=result.rows[:-1]) for result in results]
    assert series_values(results, raw, allow_missing=True) == (
        (date(2024, 1, 1), Decimal("0.123456789012345678901234567890")),
        (date(2024, 1, 2), Decimal("0.123456789012345678901234567890")),
    )
    with pytest.raises(IngestionError, match="Some complete periods have no records"):
        series_values(results, raw)
    empty = [replace(result, rows=()) for result in results]
    assert series_values(empty, raw, allow_missing=True) == ()


def test_calendar_evidence_rejects_partially_missing_measures():
    results, raw = calendar_evidence()
    results[1] = replace(results[1], rows=((date(2024, 1, 1), 0), *results[1].rows[1:]))
    with pytest.raises(IngestionError, match="Resolve missing measure values"):
        series_values(results, raw, allow_missing=True)


def another_source(env, headers, wid):
    did = dataset(env, headers, wid)
    uid = upload(env, headers, wid, did, daily()).json()["id"]
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    meaning = context(env, headers, root)
    meaning["definition"]["domain"] = "sales"
    for column in meaning["definition"]["columns"]:
        if column["role"] == "metric":
            column["unit"] = "PKR"
    assert confirm(env, headers, root, meaning).status_code == 201
    return did, uid, root


def test_forecast_replay_rejects_receipts_swapped_from_equal_valued_other_dataset(integration):
    env = integration
    headers, _, wid, did, _, root = prepare(env, daily())
    original = create(env, headers, root).json()
    _, _, other = another_source(env, headers, wid)
    substituted = create(env, headers, other).json()
    assert original["result"] == substituted["result"]
    evidence = deepcopy(original["evidence"])
    evidence["query_ids"] = substituted["evidence"]["query_ids"]
    with env.engine.begin() as connection:
        connection.execute(
            update(s.forecast_runs)
            .where(s.forecast_runs.c.id == UUID(original["id"]))
            .values(evidence=evidence)
        )
    result = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/forecasts/{original['id']}", headers=headers
    )
    assert result.status_code == 409, result.text
    assert result.json()["error"]["code"] == "lineage_mismatch"


@pytest.mark.parametrize("replacement", ["empty", "extra", "duplicate", "reordered"])
def test_forecast_replay_requires_exact_ordered_distinct_receipt_triplet(
    integration, replacement
):
    env = integration
    headers, _, wid, did, _, root = prepare(env, daily())
    original = create(env, headers, root).json()
    evidence = deepcopy(original["evidence"])
    keys = evidence["query_ids"]
    evidence["query_ids"] = {
        "empty": [],
        "extra": [*keys, keys[0]],
        "duplicate": [keys[0], keys[1], keys[1]],
        "reordered": [keys[0], keys[2], keys[1]],
    }[replacement]
    with env.engine.begin() as connection:
        connection.execute(
            update(s.forecast_runs)
            .where(s.forecast_runs.c.id == UUID(original["id"]))
            .values(evidence=evidence)
        )
    response = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/forecasts/{original['id']}", headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "lineage_mismatch"


def test_comparison_replay_rejects_other_forecast_filter_with_equal_values(integration):
    env = integration

    def cities(count):
        source = daily(count)
        return source + source.split(b"\n", 1)[1].replace(b"Karachi", b"Lahore")

    headers, _, wid, did, uid, root = prepare(env, cities(40))
    original = create(
        env, headers, root, filters=[dict(column="city", operator="eq", value="Karachi")]
    ).json()
    other = create(
        env, headers, root, filters=[dict(column="city", operator="eq", value="Lahore")]
    ).json()
    assert original["result"] == other["result"]
    next_uid = upload(env, headers, wid, did, cities(43)).json()["id"]
    next_root = root.replace(uid, next_uid)
    assert (
        confirm(
            env,
            headers,
            next_root,
            context(env, headers, next_root),
            original["evidence"]["definition"],
        ).status_code
        == 201
    )
    source = request(env, headers, next_root)
    raw = dict(
        upload_id=next_uid,
        revision_id=source["revision_id"],
        understanding_id=source["understanding_id"],
        coverage_start="2024-02-10",
        coverage_end="2024-02-12",
        coverage_confirmed=True,
    )
    path = f"/workspaces/{wid}/datasets/{did}/forecasts"
    comparisons = []
    for saved in (original, other):
        response = env.client.post(path + f"/{saved['id']}/compare", headers=headers, json=raw)
        assert response.status_code == 201
        comparisons.append(response.json())
    assert comparisons[0]["result"] == comparisons[1]["result"]
    with env.engine.begin() as connection:
        connection.execute(
            update(s.forecast_comparisons)
            .where(s.forecast_comparisons.c.id == UUID(comparisons[0]["id"]))
            .values(evidence=comparisons[1]["evidence"])
        )
    response = env.client.get(
        path + f"/{original['id']}/comparisons/{comparisons[0]['id']}", headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "lineage_mismatch"


def test_comparison_changed_meaning_stops_before_actual_queries(integration, monkeypatch):
    env = integration
    headers, _, wid, did, uid, root = prepare(env, daily())
    original = create(env, headers, root).json()
    changed = context(env, headers, root)
    changed["definition"]["columns"][1]["unit"] = "USD"
    assert confirm(env, headers, root, changed).status_code == 201
    source = request(env, headers, root)
    execute = env.runtime.analytics.executor.execute
    calls = []

    async def counted(plan, *args, **kwargs):
        calls.append(str(plan.query_id))
        return await execute(plan, *args, **kwargs)

    monkeypatch.setattr(env.runtime.analytics.executor, "execute", counted)
    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/forecasts/{original['id']}/compare",
        headers=headers,
        json=dict(
            upload_id=uid,
            revision_id=source["revision_id"],
            understanding_id=source["understanding_id"],
            coverage_start="2024-02-10",
            coverage_end="2024-02-12",
            coverage_confirmed=True,
        ),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "forecast_definition_changed"
    assert calls == original["evidence"]["query_ids"]


@pytest.mark.parametrize(
    "field,value", [("method_version", "forecast-v999"), ("method", "different_method")]
)
def test_forecast_replay_rejects_unbound_method_metadata(integration, field, value):
    env = integration
    headers, _, wid, did, _, root = prepare(env, daily())
    original = create(env, headers, root).json()
    with env.engine.begin() as connection:
        connection.execute(
            update(s.forecast_runs)
            .where(s.forecast_runs.c.id == UUID(original["id"]))
            .values(**{field: value})
        )
    response = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/forecasts/{original['id']}", headers=headers
    )
    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_forecast_replay_source_reads_and_parsing_stay_off_event_loop(
    integration, monkeypatch
):
    env = integration
    headers, actor, wid, did, _, root = prepare(env, daily())
    original = create(env, headers, root).json()
    thread_id = threading.get_ident()
    calls = []
    storage = env.runtime.analytics.storage
    parser = env.runtime.analytics.parser
    read, read_table = storage.read, parser.read_table

    def checked_read(*args, **kwargs):
        calls.append(("read", threading.get_ident()))
        return read(*args, **kwargs)

    def checked_table(*args, **kwargs):
        calls.append(("parse", threading.get_ident()))
        return read_table(*args, **kwargs)

    monkeypatch.setattr(storage, "read", checked_read)
    monkeypatch.setattr(parser, "read_table", checked_table)
    result = await env.runtime.forecasts.open(actor, UUID(wid), UUID(did), UUID(original["id"]))
    assert str(result.id) == original["id"]
    assert {kind for kind, _ in calls} == {"read", "parse"}
    assert all(current != thread_id for _, current in calls)


@pytest.mark.asyncio
async def test_cancelled_forecast_waits_for_reader_and_does_not_start_queries(
    integration, monkeypatch
):
    env = integration
    headers, actor, wid, did, uid, root = prepare(env, daily())
    body = request(env, headers, root)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    storage = env.runtime.analytics.storage
    original = storage.read
    queries = []
    execute = env.runtime.analytics.executor.execute

    def blocked_read(*args, **kwargs):
        started.set()
        try:
            assert release.wait(5)
            return original(*args, **kwargs)
        finally:
            finished.set()

    async def counted(*args, **kwargs):
        queries.append(True)
        return await execute(*args, **kwargs)

    monkeypatch.setattr(storage, "read", blocked_read)
    monkeypatch.setattr(env.runtime.analytics.executor, "execute", counted)
    task = asyncio.create_task(
        env.runtime.forecasts.create(actor, UUID(wid), UUID(did), UUID(uid), body)
    )
    try:
        assert await asyncio.to_thread(started.wait, 3)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done() and not finished.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set() and queries == []
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    with env.engine.connect() as connection:
        assert connection.execute(select(s.forecast_runs.c.id)).all() == []


@pytest.mark.asyncio
async def test_forecast_revocation_after_query_blocks_publication(integration, monkeypatch):
    env = integration
    headers, _, wid, did, uid, root = prepare(env, daily())
    member, actor = add_member(env, headers, wid)
    body = request(env, member, root)
    execute = env.runtime.analytics.executor.execute
    count = 0

    async def revoke_after_execute(*args, **kwargs):
        nonlocal count
        result = await execute(*args, **kwargs)
        count += 1
        if count == 1:
            response = env.client.delete(f"/workspaces/{wid}/members/{actor.id}", headers=headers)
            assert response.status_code == 204
        return result

    monkeypatch.setattr(env.runtime.analytics.executor, "execute", revoke_after_execute)
    with pytest.raises(IngestionError) as error:
        await env.runtime.forecasts.create(actor, UUID(wid), UUID(did), UUID(uid), body)
    assert error.value.status == 404
    with env.engine.connect() as connection:
        assert connection.execute(select(s.forecast_runs.c.id)).all() == []


@pytest.mark.asyncio
async def test_forecast_source_tamper_during_queries_blocks_publication(integration, monkeypatch):
    env = integration
    headers, actor, wid, did, uid, root = prepare(env, daily())
    body = request(env, headers, root)
    storage = env.runtime.analytics.storage
    with env.runtime.service.uow() as repo:
        original = repo.upload(UUID(wid), UUID(did), UUID(uid))
    content = storage.read(original)
    execute = env.runtime.analytics.executor.execute
    count = 0

    async def tamper_after_execute(*args, **kwargs):
        nonlocal count
        result = await execute(*args, **kwargs)
        count += 1
        if count == 1:
            storage.client.put_object(
                Bucket=env.bucket, Key=original.storage_key, Body=content + b"\n"
            )
        return result

    monkeypatch.setattr(env.runtime.analytics.executor, "execute", tamper_after_execute)
    with pytest.raises(IngestionError):
        await env.runtime.forecasts.create(actor, UUID(wid), UUID(did), UUID(uid), body)
    with env.engine.connect() as connection:
        assert connection.execute(select(s.forecast_runs.c.id)).all() == []
