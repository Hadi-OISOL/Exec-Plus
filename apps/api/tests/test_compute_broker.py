"""Use case: Verifies the bounded compute boundary without changing exact answers.

What it does: Exercises authorization, engine selection, limits, cancellation and result contracts.
"""

import asyncio
import time
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from execplus.application.services.compute import ComputeBroker, ComputeEngine
from execplus.domain.compute import ComputeCapabilities, ComputeOperation, QueryBudget
from execplus.domain.errors import AuthorizationError, QueryCapacityError, UnsafeQueryError
from execplus.domain.join_paths import JoinPath, combine, plan_join_query
from execplus.domain.models import QueryResult, WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import (
    AggregationKind,
    MetricRequest,
    RowRequest,
    dataset_view,
    plan_query,
    plan_rows,
)
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor


def fixture():
    table = TableData(("amount", "city"), (("0.1", "Karachi"), ("0.2", "Attock")))
    view = dataset_view(profile(table))
    dataset_id = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset_id}))
    plan = plan_query(
        scope, dataset_id, view, MetricRequest("amount", AggregationKind.SUM), row_limit=100
    )
    return plan, scope, table, view


def broker(budget=None, executor=None, operations=None):
    budget = budget or QueryBudget(timeout_seconds=5, memory_limit_mb=64)
    executor = executor or DuckDBQueryExecutor(5, 64, budget=budget)
    return ComputeBroker(
        {
            "duckdb": ComputeEngine(
                ComputeCapabilities(
                    "duckdb",
                    frozenset(ComputeOperation) if operations is None else operations,
                    budget,
                ),
                executor,
            )
        },
        "duckdb",
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": 0},
        {"timeout_seconds": 301},
        {"threads": 0},
        {"threads": 9},
        {"threads": True},
        {"input_rows": 200_001},
        {"input_cells": 2_000_001},
        {"result_rows": 100_001},
        {"memory_limit_mb": -1},
        {"concurrent_queries": 0},
        {"concurrent_queries": 65},
        {"concurrent_queries": 2, "workspace_concurrent_queries": 3},
        {"queue_seconds": -1},
        {"queue_seconds": float("inf")},
    ],
)
def test_invalid_budgets_refuse_startup(changes):
    with pytest.raises(ValueError):
        QueryBudget(**changes)


def test_unregistered_compute_or_remote_address_cannot_be_selected():
    with pytest.raises(ValueError, match="not registered"):
        ComputeBroker({}, "http://untrusted.example/execute")


@pytest.mark.asyncio
async def test_broker_preserves_exact_values_and_receipt_query_identity():
    plan, scope, table, view = fixture()
    result = await broker().execute(plan, scope, table, view)
    assert result.rows == ((Decimal("0.300000000000"),),)
    assert result.query_id == plan.query_id
    assert result.records_analyzed == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("restriction", ["workspace", "dataset", "capability", "rows", "cells"])
async def test_rejected_work_does_not_reach_the_engine(restriction):
    class Unreachable:
        async def execute(self, *args):
            pytest.fail("Rejected work reached the engine")

    plan, scope, table, view = fixture()
    budget = QueryBudget()
    operations = frozenset(ComputeOperation)
    if restriction == "workspace":
        plan = replace(plan, workspace_id=uuid4())
    elif restriction == "dataset":
        scope = replace(scope, allowed_dataset_ids=frozenset())
    elif restriction == "capability":
        operations = frozenset()
    elif restriction == "rows":
        budget = replace(budget, input_rows=1)
    else:
        budget = replace(budget, input_cells=3)
    with pytest.raises((UnsafeQueryError, AuthorizationError)):
        await broker(budget, Unreachable(), operations).execute(plan, scope, table, view)


@pytest.mark.asyncio
@pytest.mark.parametrize("violation", ["foreign_result", "shape", "rows"])
async def test_broker_rejects_invalid_engine_results(violation):
    plan, scope, table, view = fixture()

    class InvalidEngine:
        async def execute(self, *args):
            return QueryResult(
                uuid4() if violation == "foreign_result" else plan.query_id,
                ("value",),
                ((1, 2),) if violation == "shape" else ((1,), (2,)),
                2,
            )

    with pytest.raises(UnsafeQueryError):
        await broker(QueryBudget(result_rows=1), InvalidEngine()).execute(plan, scope, table, view)


@pytest.mark.asyncio
async def test_duckdb_enforces_fetch_and_input_limits_even_without_broker():
    plan, scope, table, view = fixture()
    rows = plan_rows(scope, plan.dataset_id, view, RowRequest(), row_limit=100)
    with pytest.raises(UnsafeQueryError, match="result exceeds"):
        await DuckDBQueryExecutor(5, 64, budget=QueryBudget(result_rows=1)).execute(
            rows, scope, table, view
        )
    with pytest.raises(UnsafeQueryError, match="input cell"):
        await DuckDBQueryExecutor(5, 64, budget=QueryBudget(input_cells=3)).execute(
            plan, scope, table, view
        )


@pytest.mark.asyncio
async def test_broker_cancellation_interrupts_and_joins_executor_before_return():
    started = asyncio.Event()
    finished = []
    loop = asyncio.get_running_loop()

    class SlowExecutor(DuckDBQueryExecutor):
        def _load(self, connection, table, view, table_name="dataset"):
            loop.call_soon_threadsafe(started.set)
            time.sleep(0.05)
            try:
                super()._load(connection, table, view, table_name)
            finally:
                finished.append(True)

    plan, scope, table, view = fixture()
    compute = broker(executor=SlowExecutor(5, 64))
    task = asyncio.create_task(compute.execute(plan, scope, table, view))
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished == [True]
    assert (await broker().execute(plan, scope, table, view)).rows == ((Decimal("0.3"),),)


@pytest.mark.asyncio
async def test_join_broker_keeps_exact_aggregation_scope_and_combined_budget():
    plan, scope, table, view = fixture()
    right_id = uuid4()
    scope = replace(scope, allowed_dataset_ids=scope.allowed_dataset_ids | {right_id})
    right = TableData(("branch", "region"), (("Karachi", "South"), ("Attock", "North")))
    right_view = dataset_view(profile(right))
    path = JoinPath(
        uuid4(),
        scope.workspace_id,
        plan.dataset_id,
        "city",
        right_id,
        "branch",
        scope.actor_id,
        datetime.now(timezone.utc),
    )
    joined = plan_join_query(
        scope,
        path,
        combine(view, right_view, path),
        MetricRequest("amount", AggregationKind.SUM, group_by=("region",)),
        row_limit=100,
    )
    result = await broker().execute_join(joined, scope, path, table, view, right, right_view)
    assert set(result.rows) == {("South", Decimal("0.1")), ("North", Decimal("0.2"))}
    assert result.records_analyzed == 4
    with pytest.raises(UnsafeQueryError, match="input row budget"):
        await broker(QueryBudget(input_rows=3)).execute_join(
            joined, scope, path, table, view, right, right_view
        )
    with pytest.raises(AuthorizationError):
        await broker().execute_join(
            joined,
            replace(scope, allowed_dataset_ids=frozenset({plan.dataset_id})),
            path,
            table,
            view,
            right,
            right_view,
        )
    with pytest.raises(AuthorizationError):
        await broker().execute_join(
            replace(joined, dataset_id=right_id),
            scope,
            path,
            table,
            view,
            right,
            right_view,
        )


class HeldEngine:
    def __init__(self):
        self.release = asyncio.Event()
        self.entered = 0

    async def execute(self, plan, scope, table, view):
        self.entered += 1
        await self.release.wait()
        return QueryResult(plan.query_id, ("__value",), ((Decimal("0.3"),),), len(table.rows))


@pytest.mark.asyncio
async def test_global_concurrency_limit_refuses_before_reaching_the_engine():
    plan, scope, table, view = fixture()
    engine = HeldEngine()
    compute = broker(
        QueryBudget(concurrent_queries=1, workspace_concurrent_queries=1, queue_seconds=0), engine
    )
    held = asyncio.create_task(compute.execute(plan, scope, table, view))
    while engine.entered == 0:
        await asyncio.sleep(0)
    other = replace(scope, workspace_id=uuid4())
    with pytest.raises(QueryCapacityError, match="concurrent query limit"):
        await compute.execute(replace(plan, workspace_id=other.workspace_id), other, table, view)
    assert engine.entered == 1
    engine.release.set()
    assert (await held).rows == ((Decimal("0.3"),),)
    assert (await compute.execute(plan, scope, table, view)).rows == ((Decimal("0.3"),),)
    assert compute._running == 0 and compute._workspace_running == {}


@pytest.mark.asyncio
async def test_workspace_limit_isolates_one_tenant_from_another():
    plan, scope, table, view = fixture()
    engine = HeldEngine()
    compute = broker(
        QueryBudget(concurrent_queries=2, workspace_concurrent_queries=1, queue_seconds=0), engine
    )
    held = asyncio.create_task(compute.execute(plan, scope, table, view))
    while engine.entered == 0:
        await asyncio.sleep(0)
    with pytest.raises(QueryCapacityError):
        await compute.execute(plan, scope, table, view)
    other = replace(scope, workspace_id=uuid4(), allowed_dataset_ids=scope.allowed_dataset_ids)
    second = asyncio.create_task(
        compute.execute(replace(plan, workspace_id=other.workspace_id), other, table, view)
    )
    while engine.entered < 2:
        await asyncio.sleep(0)
    engine.release.set()
    assert len({(await held).query_id, (await second).query_id}) == 1


@pytest.mark.asyncio
async def test_queued_query_waits_for_a_slot_then_runs_exactly():
    plan, scope, table, view = fixture()
    engine = HeldEngine()
    compute = broker(
        QueryBudget(concurrent_queries=1, workspace_concurrent_queries=1, queue_seconds=5), engine
    )
    held = asyncio.create_task(compute.execute(plan, scope, table, view))
    while engine.entered == 0:
        await asyncio.sleep(0)
    queued = asyncio.create_task(compute.execute(plan, scope, table, view))
    await asyncio.sleep(0.05)
    assert engine.entered == 1 and not queued.done()
    engine.release.set()
    assert (await held).rows == (await queued).rows == ((Decimal("0.3"),),)
    assert engine.entered == 2


@pytest.mark.asyncio
async def test_slot_is_released_when_the_engine_fails_or_is_cancelled():
    plan, scope, table, view = fixture()

    class Failing:
        async def execute(self, *args):
            raise UnsafeQueryError("engine failed")

    compute = broker(
        QueryBudget(concurrent_queries=1, workspace_concurrent_queries=1, queue_seconds=0),
        Failing(),
    )
    for _ in range(3):
        with pytest.raises(UnsafeQueryError, match="engine failed"):
            await compute.execute(plan, scope, table, view)
    assert compute._running == 0 and compute._workspace_running == {}
    engine = HeldEngine()
    compute = broker(
        QueryBudget(concurrent_queries=1, workspace_concurrent_queries=1, queue_seconds=0), engine
    )
    task = asyncio.create_task(compute.execute(plan, scope, table, view))
    while engine.entered == 0:
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert compute._running == 0 and compute._workspace_running == {}
