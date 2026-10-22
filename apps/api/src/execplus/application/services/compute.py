"""Use case: Brokers authorized analytical execution through registered engines.

What it does: Applies snapshot/result and concurrency budgets while preserving the
QueryExecutor contract.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

from execplus.application.ports import QueryExecutor
from execplus.domain.compute import ComputeCapabilities, ComputeOperation
from execplus.domain.errors import AuthorizationError, QueryCapacityError, UnsafeQueryError
from execplus.domain.join_paths import JoinPath
from execplus.domain.models import QueryPlan, QueryResult, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView


@dataclass(frozen=True, slots=True)
class ComputeEngine:
    capabilities: ComputeCapabilities
    executor: QueryExecutor


class ComputeBroker:
    def __init__(self, engines: Mapping[str, ComputeEngine], selected_engine: str) -> None:
        if selected_engine not in engines:
            raise ValueError("The selected compute engine is not registered")
        self._engine = engines[selected_engine]
        if self._engine.capabilities.engine_id != selected_engine:
            raise ValueError("The registered compute engine identifier does not match")
        self._running = 0
        self._workspace_running: dict[UUID, int] = {}

    @property
    def capabilities(self) -> ComputeCapabilities:
        return self._engine.capabilities

    def _authorize(self, plan: QueryPlan, scope: WorkspaceScope) -> None:
        if plan.workspace_id != scope.workspace_id or not scope.permits_dataset(plan.dataset_id):
            raise AuthorizationError("The query does not belong to the authorized workspace")

    def _validate(self, operation: ComputeOperation, *tables: TableData) -> None:
        if operation not in self.capabilities.operations:
            raise UnsafeQueryError("The configured engine does not support this operation")
        budget = self.capabilities.budget
        if sum(len(table.rows) for table in tables) > budget.input_rows:
            raise UnsafeQueryError("The query exceeds the input row budget")
        if sum(len(table.headers) * len(table.rows) for table in tables) > budget.input_cells:
            raise UnsafeQueryError("The query exceeds the input cell budget")

    def _saturated(self, workspace_id: UUID) -> bool:
        budget = self.capabilities.budget
        return (
            self._running >= budget.concurrent_queries
            or self._workspace_running.get(workspace_id, 0) >= budget.workspace_concurrent_queries
        )

    @asynccontextmanager
    async def _slot(self, workspace_id: UUID) -> AsyncIterator[None]:
        deadline = time.monotonic() + self.capabilities.budget.queue_seconds
        while self._saturated(workspace_id):
            if time.monotonic() >= deadline:
                raise QueryCapacityError(
                    "The query service is at its concurrent query limit; try again shortly"
                )
            await asyncio.sleep(0.01)
        self._running += 1
        self._workspace_running[workspace_id] = self._workspace_running.get(workspace_id, 0) + 1
        try:
            yield
        finally:
            self._running -= 1
            remaining = self._workspace_running[workspace_id] - 1
            if remaining:
                self._workspace_running[workspace_id] = remaining
            else:
                del self._workspace_running[workspace_id]

    def _result(self, plan: QueryPlan, result: QueryResult) -> QueryResult:
        if result.query_id != plan.query_id:
            raise UnsafeQueryError("The engine returned a result for a different execution")
        if len(result.rows) > self.capabilities.budget.result_rows:
            raise UnsafeQueryError("The result exceeds the row budget")
        if any(len(row) != len(result.columns) for row in result.rows):
            raise UnsafeQueryError("The engine returned an inconsistent result shape")
        return result

    async def execute(
        self, plan: QueryPlan, scope: WorkspaceScope, table: TableData, view: DatasetView
    ) -> QueryResult:
        self._authorize(plan, scope)
        self._validate(ComputeOperation.SNAPSHOT_QUERY, table)
        async with self._slot(scope.workspace_id):
            result = await self._engine.executor.execute(plan, scope, table, view)
        return self._result(plan, result)

    async def execute_join(
        self,
        plan: QueryPlan,
        scope: WorkspaceScope,
        join_path: JoinPath,
        left_table: TableData,
        left_view: DatasetView,
        right_table: TableData,
        right_view: DatasetView,
    ) -> QueryResult:
        self._authorize(plan, scope)
        if (
            join_path.workspace_id != scope.workspace_id
            or plan.dataset_id != join_path.left_dataset_id
            or not scope.permits_dataset(join_path.left_dataset_id)
            or not scope.permits_dataset(join_path.right_dataset_id)
        ):
            raise AuthorizationError("Both joined datasets must belong to the authorized workspace")
        self._validate(ComputeOperation.DECLARED_JOIN, left_table, right_table)
        async with self._slot(scope.workspace_id):
            result = await self._engine.executor.execute_join(
                plan, scope, join_path, left_table, left_view, right_table, right_view
            )
        return self._result(plan, result)
