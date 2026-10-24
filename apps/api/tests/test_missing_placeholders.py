"""Use case: Verifies N/A-style placeholders read as missing (profile-v4) and is-missing filters.

What it does: Checks exact aggregates against independent pandas results, the honest error
for genuine bad values, unchanged profile-v3 behavior, SQL validation, planning and replay.
"""

import io
import json
from decimal import Decimal
from uuid import UUID, uuid4

import pandas as pd
import pytest
from sqlalchemy import update

from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.domain.errors import QueryDataError, UnsafeQueryError
from execplus.domain.intent import route_response
from execplus.domain.models import QuestionKind, VerifiedMetricAnswer, WorkspaceScope
from execplus.domain.offline_planner import offline_plan
from execplus.domain.profiling import (
    CURRENT_ALGORITHM,
    PROFILE_V3,
    TableData,
    profile_for,
)
from execplus.domain.semantics import (
    RECORD_COUNT,
    AggregationKind,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    dataset_view,
    plan_query,
)
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from execplus.infrastructure.query.validation import validated_query
from test_harness_context_integration import Planner
from test_workspace_integration import dataset, identity, upload, workspace

PLACEHOLDERS = ["N/A", "n/a", " NA ", "N.A.", "null", "NULL", "none", "#N/A", "—"]
HEADERS = ("Date", "Store", "Category", "Sales Amount", "Units")


def messy_rows(bad=None):
    rows = []
    for index in range(40):
        amount = f"{100 + index * 7}.{index % 10}5"
        if index % 4 == 3:
            amount = PLACEHOLDERS[index // 4 % len(PLACEHOLDERS)]
        if index == 10:
            amount = ""
        if bad is not None and index == 23:
            amount = bad
        category = "None" if index % 5 == 0 else "Food"
        rows.append(
            (f"2025-01-{index % 28 + 1:02d}", f"S{index % 3}", category, amount, str(index % 6))
        )
    return rows


def table(rows):
    return TableData(HEADERS, tuple(rows))


def csv_bytes(rows):
    return "\n".join([",".join(HEADERS), *(",".join(row) for row in rows)]).encode() + b"\n"


def frame(rows):
    na = {value.strip().casefold() for value in PLACEHOLDERS} | {""}
    data = pd.read_csv(io.BytesIO(csv_bytes(rows)), dtype=str, keep_default_na=False)
    data["Sales Amount"] = data["Sales Amount"].map(
        lambda value: None if value.strip().casefold() in na else Decimal(value.strip())
    )
    return data


def column(profile, name):
    return next(item for item in profile["columns"] if item["name"] == name)


async def run(rows, request, algorithm=CURRENT_ALGORITHM):
    did = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({did}))
    data = table(rows)
    view = dataset_view(profile_for(data, algorithm))
    plan = plan_query(scope, did, view, request, row_limit=1000)
    return await DuckDBQueryExecutor(5, 64).execute(plan, scope, data, view)


def test_profile_v4_reads_placeholders_as_missing_and_records_how_many():
    rows = messy_rows()
    current = profile_for(table(rows), CURRENT_ALGORITHM)
    amount = column(current, "Sales Amount")
    expected = sum(1 for index in range(40) if index % 4 == 3)
    assert CURRENT_ALGORITHM == "profile-v4"
    assert amount["type"] == "decimal" and amount["role"] == "metric"
    assert amount["missing_placeholders"] == expected
    assert amount["missing"] == expected + 1 and amount["type_conflicts"] == 0
    category = column(current, "Category")
    assert "missing_placeholders" not in category and category["missing"] == 0
    assert category["distinct_count"] == 2


def test_profile_v3_is_unchanged_for_the_same_file():
    rows = messy_rows()
    old = profile_for(table(rows), PROFILE_V3)
    amount = column(old, "Sales Amount")
    assert old["algorithm"] == PROFILE_V3
    assert "missing_placeholders" not in amount
    assert amount["missing"] == 1 and amount["type_conflicts"] == 10


@pytest.mark.asyncio
async def test_sum_avg_and_grouped_totals_skip_placeholders_exactly_like_pandas():
    rows = messy_rows()
    data = frame(rows)
    values = [value for value in data["Sales Amount"] if value is not None]
    total = await run(rows, MetricRequest("Sales Amount", AggregationKind.SUM))
    assert Decimal(total.rows[0][0]) == sum(values, Decimal(0))
    average = await run(rows, MetricRequest("Sales Amount", AggregationKind.AVG))
    assert Decimal(average.rows[0][0]) == (sum(values, Decimal(0)) / len(values)).quantize(
        Decimal("1e-12")
    )
    grouped = await run(rows, MetricRequest("Sales Amount", AggregationKind.SUM, ("Store",)))
    expected = {
        store: sum((v for v in group if v is not None), Decimal(0))
        for store, group in data.groupby("Store")["Sales Amount"]
    }
    assert {row[0]: Decimal(row[1]) for row in grouped.rows} == expected


@pytest.mark.asyncio
async def test_missing_and_present_filters_count_exactly_like_pandas():
    rows = messy_rows()
    data = frame(rows)
    missing = await run(
        rows,
        MetricRequest(
            RECORD_COUNT,
            AggregationKind.COUNT,
            filters=(MetricFilter("Sales Amount", FilterOperator.IS_MISSING, None),),
        ),
    )
    present = await run(
        rows,
        MetricRequest(
            RECORD_COUNT,
            AggregationKind.COUNT,
            filters=(MetricFilter("Sales Amount", FilterOperator.NOT_MISSING, None),),
        ),
    )
    assert missing.rows[0][0] == int(data["Sales Amount"].isna().sum()) == 11
    assert present.rows[0][0] == int(data["Sales Amount"].notna().sum()) == 29


@pytest.mark.asyncio
async def test_a_genuine_bad_value_still_reports_its_cell():
    with pytest.raises(QueryDataError, match='"Sales Amount", data row 24'):
        await run(messy_rows("abc"), MetricRequest("Sales Amount", AggregationKind.SUM))


@pytest.mark.asyncio
async def test_profile_v3_view_still_refuses_placeholders():
    with pytest.raises(QueryDataError, match='"Sales Amount", data row 4'):
        await run(messy_rows(), MetricRequest("Sales Amount", AggregationKind.SUM), PROFILE_V3)


def test_validator_accepts_only_field_null_checks():
    base = 'SELECT COUNT(*) FROM "dataset" WHERE {} LIMIT 1'
    validated_query(base.format('"a" IS NULL'), {"dataset"}, 0)
    validated_query(base.format('"a" IS NOT NULL'), {"dataset"}, 0)
    for unsafe in ('NOT ("a" = ?)', '"a" IS TRUE', 'NOT "a" IS NULL AND NOT ("a" < ?)'):
        params = unsafe.count("?")
        with pytest.raises(UnsafeQueryError):
            validated_query(base.format(unsafe), {"dataset"}, params)


def test_plans_parse_missing_operators_and_reject_values():
    view = dataset_view(profile_for(table(messy_rows()), CURRENT_ALGORITHM))

    def plan(value):
        filters = [{"column": "Sales Amount", "operator": "is_missing", "value": value}]
        body = {"metric": "*", "aggregation": "count", "filters": filters}
        return route_response(json.dumps({"kind": "numerical", "plan": body}), view)

    routed = plan(None)
    assert routed.request is not None
    assert routed.request.filters == (
        MetricFilter("Sales Amount", FilterOperator.IS_MISSING, None),
    )
    assert plan(5).kind == QuestionKind.UNSUPPORTED


def test_offline_planner_answers_missing_value_questions():
    view = dataset_view(profile_for(table(messy_rows()), CURRENT_ALGORITHM))
    counted = offline_plan("How many rows have missing sales?", view)
    assert counted is not None and counted.request is not None
    assert counted.request.metric == RECORD_COUNT
    assert counted.request.filters == (
        MetricFilter("Sales Amount", FilterOperator.IS_MISSING, None),
    )
    listed = offline_plan("Rows with missing sales", view)
    assert listed is not None and listed.kind == QuestionKind.ROWS
    assert offline_plan("How many rows have missing sales by store?", view) is None


BY_STORE = {
    "kind": "numerical",
    "plan": {"metric": "Sales Amount", "aggregation": "sum", "group_by": ["Store"]},
}
MISSING = {
    "kind": "numerical",
    "plan": {
        "metric": "*",
        "aggregation": "count",
        "filters": [{"column": "Sales Amount", "operator": "is_missing", "value": None}],
    },
}


def thread_setup(env, content, *plans):
    headers, actor = identity(env, f"messy-{uuid4().hex}@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    response = upload(env, headers, wid, did, content, "messy_store_sales.csv", "text/csv")
    assert response.status_code == 201, response.text
    router = IntentRouterService(
        Planner(*plans), env.runtime.analytics, context_enabled=True, orchestration_enabled=True
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    return headers, actor, UUID(wid), UUID(did), UUID(response.json()["id"]), threads


@pytest.mark.asyncio
async def test_live_messy_file_questions_answer_exactly_and_replay(integration):
    rows = messy_rows()
    data = frame(rows)
    headers, actor, wid, did, uid, threads = thread_setup(
        integration, csv_bytes(rows), BY_STORE, MISSING
    )
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    profiled = integration.client.get(root + "/profile", headers=headers).json()
    assert profiled["algorithm"] == CURRENT_ALGORITHM
    assert column(profiled["profile"], "Sales Amount")["missing_placeholders"] == 10
    quality = integration.client.get(root + "/quality", headers=headers)
    assert quality.status_code == 200, quality.text
    findings = {(item["code"], item["column"]): item for item in quality.json()["findings"]}
    assert findings[("missing_placeholders", "Sales Amount")]["count"] == 10
    thread = await threads.start_thread(actor, wid, did, uid)
    values = [value for value in data["Sales Amount"] if value is not None]
    expected_store = {
        store: sum((v for v in group if v is not None), Decimal(0))
        for store, group in data.groupby("Store")["Sales Amount"]
    }
    answers = []
    for question in (
        "What is the total sales amount?",
        "Sales by store",
        "How many rows have missing sales?",
    ):
        answer, turn = await threads.ask(actor, wid, thread.id, question)
        assert turn.status == "complete", question
        if isinstance(answer, VerifiedMetricAnswer):
            answers.append(([[answer.value]], answer.lineage))
        else:
            answers.append((answer[0].rows, answer[1]))
    (total, _), (by_store, _), (missing, _) = answers
    assert Decimal(total[0][0]) == sum(values, Decimal(0))
    assert {row[0]: Decimal(row[1]) for row in by_store} == expected_store
    assert int(missing[0][0]) == int(data["Sales Amount"].isna().sum())
    for rows, lineage in answers:
        replayed, _ = await integration.runtime.analytics.replay(actor, wid, lineage.query_id)
        assert [list(row) for row in replayed.rows] == [list(row) for row in rows]


@pytest.mark.asyncio
async def test_old_profile_v3_upload_replays_unchanged(integration):
    rows = [row for row in messy_rows() if row[3].strip() and row[3] not in PLACEHOLDERS]
    _, actor, wid, did, uid, threads = thread_setup(integration, csv_bytes(rows), BY_STORE)
    legacy = profile_for(table(rows), PROFILE_V3)
    with integration.engine.begin() as connection:
        connection.execute(
            update(s.revisions)
            .where(s.revisions.c.upload_id == uid)
            .values(algorithm=PROFILE_V3, profile=legacy)
        )
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Sales by store")
    assert turn.status == "complete"
    result, lineage = answer
    data = frame(rows)
    assert {row[0]: Decimal(row[1]) for row in result.rows} == {
        store: sum(group, Decimal(0)) for store, group in data.groupby("Store")["Sales Amount"]
    }
    replayed, _ = await integration.runtime.analytics.replay(actor, wid, lineage.query_id)
    assert replayed.rows == result.rows
