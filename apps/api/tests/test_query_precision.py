"""Use case: Reproduces wide spreadsheet query failures without retaining user data.

What it does: Verifies exact adaptive decimals, query column scope, actionable errors and replay.
"""

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from execplus.domain.errors import QueryDataError, UnsafeQueryError
from execplus.domain.join_paths import JoinPath, combine, plan_join_query
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import (
    AggregationKind,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    RowRequest,
    dataset_view,
    plan_query,
    plan_rows,
)
from execplus.domain.studies import count_plan
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from test_conversational_explorer import ScriptedModel, prepare
from test_duckdb_executor import scope


async def execute(table, request):
    did = uuid4()
    authorized = scope(did)
    view = dataset_view(profile(table))
    plan = plan_query(authorized, did, view, request, row_limit=100)
    return await DuckDBQueryExecutor(5, 64).execute(plan, authorized, table, view)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("0.1", "0.2", "0.300000000000"),
        ("0.0000000000001", "0.0000000000002", "0.0000000000003"),
        ("0.000000000000000000000000001", "1.5", "1.500000000000000000000000001"),
        ("1e-38", "2e-38", "3e-38"),
        ("0.1000000000000000000000000000000000000000000", "0.2", "0.300000000000"),
        ("-1e-27", "2e-27", "1e-27"),
    ],
)
async def test_decimal_sum_is_exact_without_rounding_or_float_conversion(first, second, expected):
    data = TableData(("amount",), ((first,), (second,)))
    result = await execute(data, MetricRequest("amount", AggregationKind.SUM))
    assert result.rows == ((Decimal(expected),),)
    assert isinstance(result.rows[0][0], Decimal)
    assert result.rows[0][0].as_tuple() == Decimal(expected).as_tuple()


@pytest.mark.asyncio
async def test_unused_conflicting_columns_do_not_block_valid_totals():
    data = TableData(
        ("amount", "other", "event_date"),
        (("0.1", "1", "2026-01-01"), ("0.2", "2", "2026-01-02"), ("0.3", "private", "bad")),
    )
    result = await execute(data, MetricRequest("amount", AggregationKind.SUM))
    assert result.rows == ((Decimal("0.6"),),)
    assert result.records_analyzed == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [(), (("1",), ("2",), ("PrivateCell",))])
async def test_sample_count_preserves_source_rows_without_requiring_any_column(rows):
    data = TableData(("amount",), rows)
    view = dataset_view(profile(TableData(("amount",), (("1",),))))
    did = uuid4()
    authorized = scope(did)
    plan = count_plan(
        authorized, did, view, MetricRequest("amount", AggregationKind.SUM), present_only=False
    )
    result = await DuckDBQueryExecutor(5, 64).execute(plan, authorized, data, view)
    assert result.rows == ((len(rows),),)
    assert result.records_analyzed == len(rows)


@pytest.mark.asyncio
async def test_projection_cannot_make_a_nonexistent_source_column_queryable():
    data = TableData(("amount",), (("1",),))
    view = dataset_view(profile(data))
    did = uuid4()
    authorized = scope(did)
    plan = plan_query(
        authorized, did, view, MetricRequest("amount", AggregationKind.SUM), row_limit=10
    )
    with pytest.raises(UnsafeQueryError, match="unavailable source column"):
        await DuckDBQueryExecutor(5, 64).execute(
            replace(plan, sql='SELECT "__row" FROM "dataset" LIMIT 10'), authorized, data, view
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", ["metric", "filter", "group", "rows"])
async def test_every_referenced_column_is_still_checked_without_exposing_values(reference):
    data = TableData(("amount", "other"), (("0.1", "1"), ("0.2", "2"), ("0.3", "PrivateCell")))
    metadata = profile(data)
    if reference == "group":
        metadata["columns"][1]["role"] = "dimension"
    view = dataset_view(metadata)
    did = uuid4()
    authorized = scope(did)
    request = MetricRequest(
        "other" if reference == "metric" else "amount",
        AggregationKind.SUM,
        group_by=("other",) if reference == "group" else (),
        filters=(MetricFilter("other", FilterOperator.EQ, 1),) if reference == "filter" else (),
    )
    plan = (
        plan_rows(authorized, did, view, RowRequest(), row_limit=100)
        if reference == "rows"
        else plan_query(authorized, did, view, request, row_limit=100)
    )
    with pytest.raises(QueryDataError, match='Column "other", data row 3') as error:
        await DuckDBQueryExecutor(5, 64).execute(plan, authorized, data, view)
    assert "PrivateCell" not in str(error.value)


@pytest.mark.asyncio
async def test_selected_records_keep_matching_counts_and_exact_decimal_filter():
    data = TableData(
        ("amount", "other"),
        (("1e-27", "1"), ("2e-27", "2"), ("3e-27", "PrivateCell")),
    )
    did = uuid4()
    authorized = scope(did)
    view = dataset_view(profile(data))
    plan = plan_rows(
        authorized,
        did,
        view,
        RowRequest((MetricFilter("amount", FilterOperator.GTE, "2e-27"),), ("amount",)),
        row_limit=1,
    )
    result = await DuckDBQueryExecutor(5, 64).execute(plan, authorized, data, view)
    assert result.matched_records == 2 and result.records_analyzed == 3
    assert result.rows == ((Decimal("2e-27"),),)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "values",
    [
        ("1e-39", "2e-39"),
        ("100000000000", "1e-28"),
        ("9223372036854775808", "1"),
        ("0.1", "0.2", "NaN"),
        ("0.1", "0.2", "Infinity"),
    ],
)
async def test_unrepresentable_values_fail_explicitly_without_truncation(values):
    with pytest.raises(QueryDataError, match='Column "amount", data row'):
        await execute(
            TableData(("amount",), tuple((value,) for value in values)),
            MetricRequest("amount", AggregationKind.SUM),
        )


@pytest.mark.asyncio
async def test_join_preserves_high_precision_keys_and_ignores_unused_conflicts():
    left = TableData(
        ("key", "amount", "bad"),
        (("1e-27", "0.1", "1"), ("2e-27", "0.2", "2"), ("1e-27", "0.3", "private")),
    )
    right = TableData(("key", "region"), (("1e-27", "North"), ("2e-27", "South")))
    left_view, right_view = dataset_view(profile(left)), dataset_view(profile(right))
    lid, rid = uuid4(), uuid4()
    authorized = WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({lid, rid}))
    path = JoinPath(
        uuid4(),
        authorized.workspace_id,
        lid,
        "key",
        rid,
        "key",
        authorized.actor_id,
        datetime.now(timezone.utc),
    )
    plan = plan_join_query(
        authorized,
        path,
        combine(left_view, right_view, path),
        MetricRequest("amount", AggregationKind.SUM, ("region",)),
        row_limit=100,
    )
    result = await DuckDBQueryExecutor(5, 64).execute_join(
        plan, authorized, path, left, left_view, right, right_view
    )
    assert set(result.rows) == {("North", Decimal("0.4")), ("South", Decimal("0.2"))}


def test_wide_file_chat_dashboard_and_replay_use_exact_source_values(integration):
    env = integration
    model = ScriptedModel(
        {"kind": "numerical", "plan": {"metric": "fsd_chiniot_erp_value", "aggregation": "sum"}}
    )
    content = b"fsd_chiniot_erp_value,other_value\n10,0.000000000000000000000000001\n20,1.5\n"
    owner, wid, root = prepare(env, model, content=content)
    dashboard = env.client.post(root + "/dashboard", headers=owner, json={})
    assert dashboard.status_code == 200, dashboard.text
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    response = env.client.post(
        f"/workspaces/{wid}/threads/{tid}/ask",
        headers=owner,
        json={"question": "What is the total fsd_chiniot_erp_value?"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["turn"]["status"] == "complete"
    assert response.json()["answer"]["value"] == 30
    exact = env.client.post(
        root + "/query", headers=owner, json={"metric": "other_value", "aggregation": "sum"}
    )
    assert exact.status_code == 200, exact.text
    assert exact.json()["rows"] == [["1.500000000000000000000000001"]]
    qid = exact.json()["lineage"]["query_id"]
    replay = env.client.post(f"/workspaces/{wid}/queries/{qid}/replay", headers=owner)
    assert replay.status_code == 200, replay.text
    assert replay.json()["rows"] == exact.json()["rows"]


def test_chat_data_error_identifies_location_without_private_cell_and_reopens(integration):
    env = integration
    model = ScriptedModel({"kind": "numerical", "plan": {"metric": "amount", "aggregation": "sum"}})
    owner, wid, root = prepare(env, model, content=b"amount\n0.1\n0.2\nPrivateCell\n")
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}"
    response = env.client.post(path + "/ask", headers=owner, json={"question": "Total amount?"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["turn"]["status"] == "failed" and body["answer"] is None
    assert 'Column "amount", data row 3' in body["turn"]["message"]
    assert "PrivateCell" not in response.text
    reopened = env.client.get(path, headers=owner)
    assert reopened.json()["turns"][0]["message"] == body["turn"]["message"]
