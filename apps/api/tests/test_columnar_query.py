"""Use case: Proves Parquet-backed queries return exactly what the in-memory path returns.

What it does: Runs the same governed plans against a legacy snapshot and a profile-v5
typed-Parquet snapshot, plus a 200,000-row exact check and conversion-error refusal.
"""

import csv
import random
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from execplus.application.services.compute import ComputeBroker, ComputeEngine
from execplus.domain.columnar import ColumnarManifest, ColumnarTable
from execplus.domain.compute import (
    ColumnarBudget,
    ComputeCapabilities,
    ComputeOperation,
    QueryBudget,
)
from execplus.domain.errors import QueryDataError, UnsafeQueryError
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import PROFILE_V5, TableData, profile_for
from execplus.domain.semantics import (
    AggregationKind,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    RowExtremum,
    RowRequest,
    dataset_view,
    plan_query,
    plan_rows,
)
from execplus.infrastructure.columnar.converter import DuckDBColumnarConverter
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor

HEADERS = ("region", "sale_date", "revenue", "units", "seen at", "score")


def generated_rows(count, seed=7):
    generator = random.Random(seed)
    regions = ["North", "South", "East", "West", " Central "]
    rows = []
    for index in range(count):
        cents = generator.randint(-50_000, 5_000_000)
        rows.append(
            (
                regions[index % len(regions)],
                f"2024-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
                f"{cents // 100}.{abs(cents) % 100:02d}" if cents >= 0 else f"-{-cents / 100:.2f}",
                str(generator.randint(0, 40)) if index % 17 else "",
                f"2024-01-{index % 28 + 1:02d}T{index % 24:02d}:15:00Z",
                "N/A" if index % 11 == 0 else f"{generator.randint(0, 9)}.5",
            )
        )
    return rows


def columnar_snapshot(tmp_path, headers, rows):
    source = tmp_path / "source.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    work = tmp_path / "work"
    work.mkdir()
    conversion = DuckDBColumnarConverter(memory_limit_mb=512, threads=2).convert(
        source, "csv", work
    )
    manifest = ColumnarManifest(
        "key", conversion.sha256, conversion.size, conversion.rows, conversion.errors
    )
    legacy = TableData(tuple(headers), tuple(tuple(row) for row in rows))
    table = ColumnarTable(
        conversion.headers, manifest, lambda: conversion.parquet, lambda: legacy
    )
    return table, dataset_view(conversion.profile), legacy, conversion


def requests():
    north = MetricFilter("region", FilterOperator.EQ, "North")
    return [
        MetricRequest("revenue", AggregationKind.SUM),
        MetricRequest("revenue", AggregationKind.AVG),
        MetricRequest("revenue", AggregationKind.SUM, group_by=("region",)),
        MetricRequest("revenue", AggregationKind.SUM, group_by=("region",), order="desc", limit=3),
        MetricRequest("revenue", AggregationKind.AVG, group_by=("region",), order="asc", limit=2),
        MetricRequest("units", AggregationKind.MAX, filters=(north,)),
        MetricRequest("revenue", AggregationKind.SUM, group_by=("sale_date",), period="month"),
        MetricRequest("revenue", AggregationKind.SUM, group_by=("seen at",), period="day"),
        MetricRequest("score", AggregationKind.AVG),
        MetricRequest("units", AggregationKind.COUNT),
    ]


@pytest.mark.asyncio
async def test_parquet_queries_match_in_memory_results(tmp_path):
    rows = generated_rows(5_000)
    table, view, legacy, _ = columnar_snapshot(tmp_path, HEADERS, rows)
    legacy_view = dataset_view(profile_for(legacy, PROFILE_V5))
    assert legacy_view == view
    dataset_id = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset_id}))
    executor = DuckDBQueryExecutor(30, 256)
    for request in requests():
        plan = plan_query(scope, dataset_id, view, request, row_limit=1000)
        expected = await executor.execute(plan, scope, legacy, view)
        actual = await executor.execute(plan, scope, table, view)
        assert actual == expected, request
    row_plan = plan_rows(
        scope,
        dataset_id,
        view,
        RowRequest(extremum=RowExtremum("revenue", "max")),
        row_limit=10,
    )
    assert await executor.execute(row_plan, scope, table, view) == await executor.execute(
        row_plan, scope, legacy, view
    )


@pytest.mark.asyncio
async def test_two_hundred_thousand_rows_sum_exactly_through_the_broker(tmp_path):
    rows = generated_rows(200_000, seed=11)
    table, view, _, conversion = columnar_snapshot(tmp_path, HEADERS, rows)
    assert conversion.rows == 200_000
    dataset_id = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset_id}))
    budget = QueryBudget(timeout_seconds=30, memory_limit_mb=256)
    broker = ComputeBroker(
        {
            "duckdb": ComputeEngine(
                ComputeCapabilities("duckdb", frozenset(ComputeOperation), budget),
                DuckDBQueryExecutor(30, 256, budget=budget, columnar=ColumnarBudget()),
            )
        },
        "duckdb",
    )
    plan = plan_query(
        scope,
        dataset_id,
        view,
        MetricRequest("revenue", AggregationKind.SUM, group_by=("region",)),
        row_limit=100,
    )
    result = await broker.execute(plan, scope, table, view)
    expected: dict[str, Decimal] = {}
    for row in rows:
        expected[row[0].strip()] = expected.get(row[0].strip(), Decimal(0)) + Decimal(row[2])
    assert {name: value for name, value in result.rows} == expected
    assert result.records_analyzed == 200_000


@pytest.mark.asyncio
async def test_row_budget_and_conversion_errors_refuse_queries(tmp_path):
    rows = [("1", "a"), ("2", "b"), ("x", "c")]
    table, view, _, conversion = columnar_snapshot(tmp_path, ("amount", "note"), rows)
    assert "amount" in conversion.errors
    dataset_id = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset_id}))
    plan = plan_query(
        scope, dataset_id, view, MetricRequest("amount", AggregationKind.SUM), row_limit=10
    )
    with pytest.raises(QueryDataError, match='Column "amount", data row 3'):
        await DuckDBQueryExecutor(5, 64).execute(plan, scope, table, view)
    count = plan_query(
        scope, dataset_id, view, MetricRequest("note", AggregationKind.COUNT), row_limit=10
    )
    assert (await DuckDBQueryExecutor(5, 64).execute(count, scope, table, view)).rows == ((3,),)
    small = DuckDBQueryExecutor(5, 64, columnar=ColumnarBudget(input_rows=2))
    with pytest.raises(UnsafeQueryError, match="input row budget"):
        await small.execute(count, scope, table, view)
    tampered = replace(table.manifest, rows=4)
    lazy = ColumnarTable(table.headers, tampered, table.parquet_path, lambda: TableData(("a",), ()))
    with pytest.raises(Exception, match="integrity"):
        _ = lazy.rows
