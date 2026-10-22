"""Use case: Verifies hourly date-time sources become calendar fields in profile-v3 only.

What it does: Checks detection, explicit time-zone handling, exact DuckDB daily/weekly
aggregates against independent pandas/Decimal results, routing, forecasts and old replay.
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pandas as pd
import pytest
from sqlalchemy import update

from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.domain.intent import route_response, with_time_grain
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import (
    ALGORITHM,
    CURRENT_ALGORITHM,
    PROFILE_V2,
    TableData,
    parse_datetime,
    profile_for,
)
from execplus.domain.semantics import (
    AggregationKind,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    dataset_view,
    plan_query,
)
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from test_harness_context_integration import Planner
from test_workspace_integration import dataset, identity, upload, workspace

START = datetime(2025, 1, 1)


def hourly_rows(hours=24 * 10):
    rows = []
    for index in range(hours):
        moment = START + timedelta(hours=index)
        sensor = "S1" if index % 2 else "S2"
        temperature = Decimal(20) + Decimal(index % 7) / 4 + Decimal(index // 24) / 10
        rows.append((moment.strftime("%Y-%m-%d %H:%M:%S"), sensor, str(temperature)))
    return rows


def iot_table(rows=None):
    return TableData(("timestamp", "sensor", "temperature"), tuple(rows or hourly_rows()))


def iot_csv(rows=None):
    lines = ["timestamp,sensor,temperature", *(",".join(row) for row in rows or hourly_rows())]
    return ("\n".join(lines) + "\n").encode()


def column(result, name):
    return next(item for item in result["columns"] if item["name"] == name)


def test_profile_v3_detects_space_and_iso_date_times_while_v1_v2_stay_frozen():
    table = iot_table()
    current = column(profile_for(table, CURRENT_ALGORITHM), "timestamp")
    assert CURRENT_ALGORITHM == "profile-v3"
    assert current["type"] == "date" and current["datetime"] is True
    assert current["timezone"] == "as_given" and current["role"] == "dimension"
    assert {"date", "datetime"} <= set(current["semantic_tags"])
    assert (current["date_min"], current["date_max"]) == ("2025-01-01", "2025-01-10")
    assert current["invalid_dates"] == current["type_conflicts"] == 0
    for old in (ALGORITHM, PROFILE_V2):
        frozen = column(profile_for(table, old), "timestamp")
        assert frozen["type"] == "text" and "datetime" not in frozen
        assert profile_for(table, old)["algorithm"] == old


@pytest.mark.parametrize(
    ("value", "expected", "aware"),
    [
        ("2025-01-01 13:00:00", datetime(2025, 1, 1, 13), False),
        ("2025-01-01T13:00", datetime(2025, 1, 1, 13), False),
        ("2025-01-01T13:00:00.250", datetime(2025, 1, 1, 13, 0, 0, 250000), False),
        ("2025-01-01T13:00:00Z", datetime(2025, 1, 1, 13), True),
        ("2025-01-01T03:00:00+05:00", datetime(2024, 12, 31, 22), True),
        ("2025-01-01", datetime(2025, 1, 1), False),
    ],
)
def test_date_times_parse_with_explicit_utc_conversion(value, expected, aware):
    assert parse_datetime(value) == (expected, aware)


@pytest.mark.parametrize(
    "values",
    [
        ("2025-01-01 13:00:00", "2025-01-01T14:00:00Z"),
        ("2025-01-01 13:00:00", "yesterday"),
        ("2025-01-01 25:00:00", "2025-01-01 13:00:00"),
        ("2025-01-01", "2025-01-02"),
        ("01/02/2025 13:00", "01/03/2025 13:00"),
    ],
)
def test_mixed_invalid_or_date_only_columns_are_not_reinterpreted(values):
    table = TableData(("reading_time", "value"), tuple((item, "1") for item in values))
    current = column(profile_for(table, CURRENT_ALGORITHM), "reading_time")
    assert "datetime" not in current
    assert current["type"] in {"text", "date"}


def test_aware_values_are_bucketed_on_their_utc_calendar_day():
    table = TableData(
        ("observed_at", "value"),
        (("2025-01-01T03:00:00+05:00", "1"), ("2025-01-01T13:00:00+05:00", "2")),
    )
    current = column(profile_for(table, CURRENT_ALGORITHM), "observed_at")
    assert current["timezone"] == "UTC"
    assert (current["date_min"], current["date_max"]) == ("2024-12-31", "2025-01-01")


def independent(rows, frequency):
    frame = pd.DataFrame(rows, columns=["timestamp", "sensor", "temperature"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame["temperature"] = frame["temperature"].map(Decimal)
    period = frame["timestamp"].dt.to_period("W-SUN" if frequency == "week" else "D")
    totals = {}
    for key, values in frame.groupby(period)["temperature"]:
        values = list(values)
        totals[key.start_time.date()] = (sum(values, Decimal(0)), len(values))
    return totals


async def run(table, request):
    did = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({did}))
    view = dataset_view(profile_for(table, CURRENT_ALGORITHM))
    plan = plan_query(scope, did, view, request, row_limit=1000)
    return await DuckDBQueryExecutor(5, 64).execute(plan, scope, table, view)


@pytest.mark.asyncio
@pytest.mark.parametrize("frequency", ["day", "week"])
@pytest.mark.parametrize("aggregation", [AggregationKind.AVG, AggregationKind.SUM])
async def test_daily_and_weekly_aggregates_over_hourly_data_are_exact(frequency, aggregation):
    rows = hourly_rows()
    request = MetricRequest("temperature", aggregation, ("timestamp",), period=frequency)
    result = await run(iot_table(rows), request)
    expected = independent(rows, frequency)
    assert [row[0] for row in result.rows] == sorted(expected)
    for period, value in result.rows:
        total, count = expected[period]
        exact = total / count if aggregation == AggregationKind.AVG else total
        assert isinstance(period, date) and Decimal(value) == exact.quantize(Decimal("1e-12"))


@pytest.mark.asyncio
async def test_a_date_filter_matches_every_hour_of_that_day():
    rows = hourly_rows()
    filtered = MetricRequest(
        "temperature",
        AggregationKind.COUNT,
        filters=(MetricFilter("timestamp", FilterOperator.LTE, "2025-01-02"),),
    )
    assert (await run(iot_table(rows), filtered)).rows[0][0] == 48
    grouped = await run(
        iot_table(rows), MetricRequest("temperature", AggregationKind.MAX, ("timestamp",))
    )
    assert grouped.rows[0][0] == datetime(2025, 1, 1, 0)


def test_daily_trend_question_buckets_a_date_time_column_by_day():
    view = dataset_view(profile_for(iot_table(), CURRENT_ALGORITHM))
    plan = {
        "kind": "numerical",
        "plan": {
            "metric": "temperature",
            "aggregation": "avg",
            "group_by": ["timestamp"],
            "filters": [],
            "order": "asc",
        },
    }
    routed = with_time_grain(
        "Show daily average temperature trend", route_response(json.dumps(plan), view), view
    )
    assert routed.request.period == "day" and routed.request.order is None
    planned = route_response(json.dumps({**plan, "plan": {**plan["plan"], "period": "day"}}), view)
    assert planned.request is not None and planned.request.period == "day"


def thread_setup(env, content, *plans):
    headers, actor = identity(env, f"iot-{uuid4().hex}@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    response = upload(env, headers, wid, did, content, "iot.csv", "text/csv")
    assert response.status_code == 201, response.text
    router = IntentRouterService(
        Planner(*plans), env.runtime.analytics, context_enabled=True, orchestration_enabled=True
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    return headers, actor, UUID(wid), UUID(did), UUID(response.json()["id"]), threads


DAILY_AVG = {
    "kind": "numerical",
    "plan": {
        "metric": "temperature",
        "aggregation": "avg",
        "group_by": ["timestamp"],
        "filters": [],
        "period": "day",
    },
}


@pytest.mark.asyncio
async def test_new_iot_upload_answers_daily_average_trend_exactly_with_replay(integration):
    rows = hourly_rows()
    headers, actor, wid, did, uid, threads = thread_setup(integration, iot_csv(rows), DAILY_AVG)
    path = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/profile"
    profiled = integration.client.get(path, headers=headers).json()
    assert profiled["algorithm"] == CURRENT_ALGORITHM
    assert column(profiled["profile"], "timestamp")["datetime"] is True
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Show daily average temperature trend")
    assert turn.status == "complete"
    result, lineage = answer
    expected = independent(rows, "day")
    assert [row[0] for row in result.rows] == sorted(expected)
    for period, value in result.rows:
        total, count = expected[period]
        assert Decimal(value) == (total / count).quantize(Decimal("1e-12"))
    replayed, _ = await integration.runtime.analytics.replay(actor, wid, lineage.query_id)
    assert replayed.rows == result.rows


@pytest.mark.asyncio
async def test_old_profile_v2_upload_stays_text_and_replays_unchanged(integration):
    rows = hourly_rows(48)
    by_text = {
        "kind": "numerical",
        "plan": {
            "metric": "temperature",
            "aggregation": "sum",
            "group_by": ["sensor"],
            "filters": [],
        },
    }
    headers, actor, wid, did, uid, threads = thread_setup(integration, iot_csv(rows), by_text)
    table = iot_table(rows)
    legacy = profile_for(table, PROFILE_V2)
    with integration.engine.begin() as connection:
        connection.execute(
            update(s.revisions)
            .where(s.revisions.c.upload_id == uid)
            .values(algorithm=PROFILE_V2, profile=legacy)
        )
    path = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/profile"
    profiled = integration.client.get(path, headers=headers).json()
    assert profiled["algorithm"] == PROFILE_V2
    assert column(profiled["profile"], "timestamp")["type"] == "text"
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Total temperature by sensor")
    assert turn.status == "complete"
    result, lineage = answer
    sums = {}
    for _, sensor, value in rows:
        sums[sensor] = sums.get(sensor, Decimal(0)) + Decimal(value)
    assert {row[0]: Decimal(row[1]) for row in result.rows} == sums
    replayed, _ = await integration.runtime.analytics.replay(actor, wid, lineage.query_id)
    assert replayed.rows == result.rows


def test_daily_forecast_runs_on_an_hourly_date_time_column(integration):
    from test_forecast_integration import create
    from test_studies import prepare

    env = integration
    rows = hourly_rows(24 * 40)
    owner, _, _, _, _, root = prepare(env, iot_csv(rows))
    options = env.client.get(root + "/forecasts/options", headers=owner).json()
    assert "timestamp" in options["date_columns"]
    result = create(
        env,
        owner,
        root,
        time_column="timestamp",
        metric="temperature",
        aggregation="avg",
        coverage_start="2025-01-01",
        coverage_end="2025-02-09",
    )
    assert result.status_code == 201, result.text
    history = result.json()["result"]["history"]
    expected = independent(rows, "day")
    assert len(history) == 40
    for point in history:
        total, count = expected[date.fromisoformat(point["period"])]
        assert Decimal(point["actual"]) == (total / count).quantize(Decimal("1e-12"))
