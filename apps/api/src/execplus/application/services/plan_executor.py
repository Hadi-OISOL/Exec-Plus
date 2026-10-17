"""Use case: Admits governed compute through the shared query execution port.

What it does: Counts each source-bound operation once, preserving SQL validation,
exact calculations, private source checks and the separate financial ledger.
"""

from execplus.application.plan_context import operation_id
from execplus.application.ports import QueryExecutor
from execplus.application.services.dataset_access import dataset_access
from execplus.application.services.plans import UnitOfWork, now
from execplus.domain.evidence import scalar_record
from execplus.domain.ingestion import IngestionError
from execplus.domain.join_paths import JoinPath
from execplus.domain.models import QueryPlan, QueryResult, WorkspaceScope
from execplus.domain.plans import fingerprint
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView


class PlanAwareExecutor:
    def __init__(self, executor: QueryExecutor, uow: UnitOfWork) -> None:
        self.executor: QueryExecutor = (
            executor.executor if isinstance(executor, PlanAwareExecutor) else executor
        )
        self.uow = uow

    def _admit(
        self, plan: QueryPlan, scope: WorkspaceScope, views: tuple[DatasetView, ...]
    ) -> None:
        if plan.workspace_id != scope.workspace_id or not scope.permits_dataset(plan.dataset_id):
            raise IngestionError("not_found", "The query source is unavailable.", 404)
        sources = [source for view in views for source in view.sources]
        digest = fingerprint(
            {
                "dataset": plan.dataset_id,
                "sql": plan.sql,
                "parameters": plan.params,
                "sources": sources,
            }
        )
        identifier = operation_id("processing", plan.query_id, derived=digest)
        with self.uow() as repo:
            repo.workspace(scope.workspace_id, lock=True)
            actor = repo.user(scope.actor_id)
            repo.membership(scope.workspace_id, actor.id)
            for did in scope.allowed_dataset_ids:
                dataset_access(repo, actor, scope.workspace_id, did)
            try:
                saved = repo.query_execution(scope.workspace_id, plan.query_id)
            except IngestionError as error:
                if error.status != 404:
                    raise
            else:
                if (
                    saved.sql == plan.sql
                    and saved.dataset_id == plan.dataset_id
                    and saved.receipt.get("sources") == sources
                    and saved.receipt.get("parameters")
                    == [scalar_record(item) for item in plan.params]
                    and saved.receipt.get("outcome") == "executed"
                ):
                    return
                raise IngestionError(
                    "plan_request_conflict",
                    "The saved execution does not match this operation.",
                    409,
                )
            # New operations are serialized; receipt replay remains readable at the cap.
            repo.admit_plan_operation(
                scope.workspace_id, actor.id, "processing", identifier, digest, now()
            )

    async def execute(
        self, plan: QueryPlan, scope: WorkspaceScope, table: TableData, view: DatasetView
    ) -> QueryResult:
        self._admit(plan, scope, (view,))
        return await self.executor.execute(plan, scope, table, view)

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
        self._admit(plan, scope, (left_view, right_view))
        return await self.executor.execute_join(
            plan, scope, join_path, left_table, left_view, right_table, right_view
        )
