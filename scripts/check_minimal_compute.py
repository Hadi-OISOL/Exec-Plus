"""Use case: Rehearses exact concurrent computation in the clean production image.

What it does: Checks isolated broker results without optional data libraries or services.
"""

import asyncio
import importlib
import importlib.util
from decimal import Decimal
from uuid import UUID, uuid4

from execplus.application.services.compute import ComputeBroker, ComputeEngine
from execplus.domain.compute import ComputeCapabilities, ComputeOperation, QueryBudget
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import AggregationKind, MetricRequest, dataset_view, plan_query
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor


async def run(index: int) -> UUID:
    value = Decimal(index) / 1000
    table = TableData(("amount",), tuple((str(value),) for _ in range(1200)))
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
    return result.query_id


async def main() -> None:
    for name in ("numpy", "pandas", "pyarrow"):
        if importlib.util.find_spec(name) is not None:
            raise RuntimeError("Run this check in the minimal production image")
    for module in ("execplus.main", "execplus.manage"):
        importlib.import_module(module)
    identifiers = await asyncio.gather(*(run(index) for index in range(1, 9)))
    if len(set(identifiers)) != 8:
        raise RuntimeError("Concurrent executions did not retain distinct identifiers")
    print("Clean runtime imports and 8/8 isolated exact computations passed.")


if __name__ == "__main__":
    asyncio.run(main())
