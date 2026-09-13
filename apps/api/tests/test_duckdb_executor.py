"""Use case: Verifies DuckDB executes planned queries within safety limits.

What it does: Proves aggregate correctness, row limits, timeout handling, and
that filter values are always treated as literal bound data.
"""

import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from execplus.domain.errors import AuthorizationError, UnsafeQueryError
from execplus.domain.join_paths import JoinPath, combine, plan_join_query
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import (
    AggregationKind,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    dataset_view,
    plan_query,
)
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor


def table():
    return TableData(
        ("region", "sale_date", "revenue"),
        (
            ("North", "2026-01-01", "100"),
            ("North", "2026-01-02", "50"),
            ("South", "2026-01-01", "200"),
        ),
    )


def view():
    return dataset_view(
        {
            "columns": [
                {"name": "region", "type": "text", "role": "dimension"},
                {"name": "sale_date", "type": "date", "role": "dimension"},
                {"name": "revenue", "type": "decimal", "role": "metric"},
            ]
        }
    )


def scope(dataset_id):
    return WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({dataset_id}))


@pytest.mark.asyncio
async def test_execute_computes_ungrouped_sum():
    dataset_id = uuid4()
    scope_ = scope(dataset_id)
    plan = plan_query(
        scope_, dataset_id, view(), MetricRequest("revenue", AggregationKind.SUM), row_limit=100
    )
    executor = DuckDBQueryExecutor(timeout_seconds=5, memory_limit_mb=64)
    result = await executor.execute(plan, scope_, table(), view())
    assert result.columns == ("__value",)
    assert result.rows == ((350.0,),)
    assert result.records_analyzed == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("aggregation", "expected"),
    [
        (AggregationKind.SUM, {("North", 150.0), ("South", 200.0)}),
        (AggregationKind.AVG, {("North", 75.0), ("South", 200.0)}),
        (AggregationKind.COUNT, {("North", 2.0), ("South", 1.0)}),
        (AggregationKind.MIN, {("North", 50.0), ("South", 200.0)}),
        (AggregationKind.MAX, {("North", 100.0), ("South", 200.0)}),
    ],
)
async def test_execute_computes_grouped_aggregations(aggregation, expected):
    dataset_id = uuid4()
    scope_ = scope(dataset_id)
    request = MetricRequest("revenue", aggregation, group_by=("region",))
    plan = plan_query(scope_, dataset_id, view(), request, row_limit=100)
    executor = DuckDBQueryExecutor(timeout_seconds=5, memory_limit_mb=64)
    result = await executor.execute(plan, scope_, table(), view())
    assert result.columns == ("region", "__value")
    assert {(row[0], float(row[1])) for row in result.rows} == expected


@pytest.mark.asyncio
async def test_execute_enforces_row_limit():
    dataset_id = uuid4()
    scope_ = scope(dataset_id)
    request = MetricRequest("revenue", AggregationKind.SUM, group_by=("region",))
    plan = plan_query(scope_, dataset_id, view(), request, row_limit=1)
    executor = DuckDBQueryExecutor(timeout_seconds=5, memory_limit_mb=64)
    result = await executor.execute(plan, scope_, table(), view())
    assert len(result.rows) == 1


@pytest.mark.asyncio
async def test_execute_treats_filter_value_as_literal_data_not_sql():
    dataset_id = uuid4()
    scope_ = scope(dataset_id)
    request = MetricRequest(
        "revenue",
        AggregationKind.SUM,
        filters=(MetricFilter("region", FilterOperator.EQ, "'; DROP TABLE dataset; --"),),
    )
    plan = plan_query(scope_, dataset_id, view(), request, row_limit=100)
    executor = DuckDBQueryExecutor(timeout_seconds=5, memory_limit_mb=64)
    result = await executor.execute(plan, scope_, table(), view())
    assert result.rows == ((None,),)
    assert result.records_analyzed == 3

    unfiltered = plan_query(
        scope_, dataset_id, view(), MetricRequest("revenue", AggregationKind.SUM), row_limit=100
    )
    still_intact = await executor.execute(unfiltered, scope_, table(), view())
    assert still_intact.rows == ((350.0,),)


@pytest.mark.asyncio
async def test_execute_raises_on_timeout():
    class SlowExecutor(DuckDBQueryExecutor):
        def _load(self, connection, data, semantic_view):
            super()._load(connection, data, semantic_view)
            time.sleep(0.2)

    dataset_id = uuid4()
    scope_ = scope(dataset_id)
    plan = plan_query(
        scope_, dataset_id, view(), MetricRequest("revenue", AggregationKind.SUM), row_limit=100
    )
    executor = SlowExecutor(timeout_seconds=0.01, memory_limit_mb=64)
    with pytest.raises(UnsafeQueryError, match="time limit"):
        await executor.execute(plan, scope_, table(), view())


def sales_table():
    return TableData(
        ("sku", "revenue"),
        (("A1", "100"), ("A1", "50"), ("B2", "200")),
    )


def sales_view():
    return dataset_view(
        {
            "columns": [
                {"name": "sku", "type": "text", "role": "dimension"},
                {"name": "revenue", "type": "decimal", "role": "metric"},
            ]
        }
    )


def products_table():
    return TableData(("sku", "category"), (("A1", "Widgets"), ("B2", "Gadgets")))


def products_view():
    return dataset_view(
        {
            "columns": [
                {"name": "sku", "type": "text", "role": "dimension"},
                {"name": "category", "type": "text", "role": "dimension"},
            ]
        }
    )


@pytest.mark.asyncio
async def test_execute_join_computes_aggregate_across_two_datasets():
    left_id, right_id = uuid4(), uuid4()
    path = JoinPath(
        uuid4(), uuid4(), left_id, "sku", right_id, "sku", uuid4(), datetime.now(timezone.utc)
    )
    combined = combine(sales_view(), products_view(), path)
    scope_ = WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({left_id, right_id}))
    request = MetricRequest(
        metric="revenue", aggregation=AggregationKind.SUM, group_by=("category",)
    )
    plan = plan_join_query(scope_, path, combined, request, row_limit=100)

    executor = DuckDBQueryExecutor(timeout_seconds=5, memory_limit_mb=64)
    result = await executor.execute_join(
        plan, scope_, path, sales_table(), sales_view(), products_table(), products_view()
    )
    assert result.columns == ("category", "__value")
    assert {(row[0], float(row[1])) for row in result.rows} == {
        ("Widgets", 150.0),
        ("Gadgets", 200.0),
    }
    assert result.records_analyzed == 3 + 2


@pytest.mark.asyncio
async def test_execute_join_rejects_dataset_outside_scope():
    # The plan is built with a fully-authorized scope (plan_join_query has its own,
    # already-tested authorization check); this proves the executor independently
    # re-checks authorization too, as defense in depth, using a narrower scope.
    left_id, right_id = uuid4(), uuid4()
    path = JoinPath(
        uuid4(), uuid4(), left_id, "sku", right_id, "sku", uuid4(), datetime.now(timezone.utc)
    )
    combined = combine(sales_view(), products_view(), path)
    authorized_scope = WorkspaceScope(
        uuid4(), uuid4(), frozenset({"member"}), frozenset({left_id, right_id})
    )
    request = MetricRequest(metric="revenue", aggregation=AggregationKind.SUM)
    plan = plan_join_query(authorized_scope, path, combined, request, row_limit=100)

    narrow_scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({left_id}))
    executor = DuckDBQueryExecutor(timeout_seconds=5, memory_limit_mb=64)
    with pytest.raises(AuthorizationError):
        await executor.execute_join(
            plan, narrow_scope, path, sales_table(), sales_view(), products_table(), products_view()
        )
