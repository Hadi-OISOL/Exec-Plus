"""Use case: Brokers authorized analytical execution through registered engines.

What it does: Applies snapshot/result budgets while preserving the QueryExecutor contract.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from execplus.application.ports import QueryExecutor
from execplus.domain.compute import ComputeCapabilities, ComputeOperation
from execplus.domain.errors import AuthorizationError, UnsafeQueryError
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
        return self._result(plan, await self._engine.executor.execute(plan, scope, table, view))

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
        return self._result(
            plan,
            await self._engine.executor.execute_join(
                plan, scope, join_path, left_table, left_view, right_table, right_view
            ),
        )
