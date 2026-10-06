"""Use case: Rehearses exact concurrent computation in the clean production image.

What it does: Checks isolated broker and calendar forecasts without optional data libraries.
"""

import asyncio
import importlib
import importlib.util
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from execplus.application.services.compute import ComputeBroker, ComputeEngine
from execplus.domain.compute import ComputeCapabilities, ComputeOperation, QueryBudget
from execplus.domain.forecast_series import series_plan, series_values
from execplus.domain.forecasting import ForecastPoint, ForecastRequest, compare_forecast, forecast
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import (
    AggregationKind,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    dataset_view,
    plan_query,
)
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor


async def run(index: int) -> tuple[UUID, ...]:
    value = Decimal(index) / 1000
    start = date(2020, 1, 1)
    end = start + timedelta(days=1199)
    table = TableData(
        ("date", "amount"),
        tuple(((start + timedelta(days=offset)).isoformat(), str(value)) for offset in range(1200)),
    )
    view = dataset_view(profile(table))
    dataset_id = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset_id}))
    budget = QueryBudget(memory_limit_mb=64)
    executor = DuckDBQueryExecutor(15, 64, budget=budget)
    broker = ComputeBroker(
        {
            "duckdb": ComputeEngine(
                ComputeCapabilities("duckdb", frozenset(ComputeOperation), budget), executor
            )
        },
        "duckdb",
    )
    plan = plan_query(
        scope, dataset_id, view, MetricRequest("amount", AggregationKind.SUM), row_limit=10
    )
    result = await broker.execute(plan, scope, table, view)
    if result.rows != ((value * 1200,),):
        raise RuntimeError("A minimal-runtime exact query failed")
    request = MetricRequest(
        "amount",
        AggregationKind.SUM,
        ("date",),
        (
            MetricFilter("date", FilterOperator.GTE, start.isoformat()),
            MetricFilter("date", FilterOperator.LTE, end.isoformat()),
        ),
    )
    results = []
    for kind in ("value", "present", "samples"):
        calendar = series_plan(scope, dataset_id, view, request, "daily", kind)
        results.append(await broker.execute(calendar, scope, table, view))
    points = tuple(
        ForecastPoint(period, actual)
        for period, actual in series_values(
            results,
            {
                "frequency": "daily",
                "coverage_start": start.isoformat(),
                "coverage_end": end.isoformat(),
                "coverage_confirmed": True,
            },
        )
    )
    forecasted = forecast(points, ForecastRequest("daily", 30, 7)).to_record()
    if (
        len(points) != 1200
        or any(point.actual != value for point in points)
        or Decimal(forecasted["accuracy"]["mae"]) != 0
        or any(Decimal(row["estimate"]) != value for row in forecasted["predictions"])
        or compare_forecast(forecasted, ())["pending_count"] != 30
    ):
        raise RuntimeError("A minimal-runtime calendar forecast failed")
    return (result.query_id, *(item.query_id for item in results))


async def main() -> None:
    for name in ("numpy", "pandas", "pyarrow"):
        if importlib.util.find_spec(name) is not None:
            raise RuntimeError("Run this check in the minimal production image")
    for module in ("execplus.main", "execplus.manage"):
        importlib.import_module(module)
    groups = await asyncio.gather(*(run(index) for index in range(1, 9)))
    if len({identifier for group in groups for identifier in group}) != 32:
        raise RuntimeError("Concurrent executions did not retain distinct identifiers")
    print("Clean imports and 8/8 isolated exact computations and calendar forecasts passed.")


if __name__ == "__main__":
    asyncio.run(main())
