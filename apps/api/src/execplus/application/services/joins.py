"""Use case: Declares cross-dataset join paths and executes queries across them.

What it does: Authorizes both datasets in a declared join, reconstructs each
snapshot, and runs a validated two-table aggregate through the same execution
and lineage-recording path every other query uses.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID, uuid4

from execplus.application.ports import FileParser, ObjectStorage, QueryExecutor, WorkspaceRepository
from execplus.application.services.lineage import persist_query_execution
from execplus.domain.ingestion import AuditEvent, IngestionError, Membership, Upload, User
from execplus.domain.join_paths import JoinPath, combine, plan_join_query
from execplus.domain.models import CalculationLineage, QueryResult, WorkspaceScope
from execplus.domain.profiling import TableData, reconstruct
from execplus.domain.semantics import DatasetView, MetricRequest, dataset_view

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


class JoinService:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        storage: ObjectStorage,
        parser: FileParser,
        executor: QueryExecutor,
        row_limit: int = 10_000,
    ) -> None:
        self.uow = unit_of_work
        self.storage = storage
        self.parser = parser
        self.executor = executor
        self.row_limit = row_limit

    def _authorize(self, repo: WorkspaceRepository, actor: User, workspace_id: UUID) -> Membership:
        return repo.membership(workspace_id, actor.id)

    def _snapshot(self, repo: WorkspaceRepository, upload: Upload) -> tuple[TableData, DatasetView]:
        revision = repo.active_revision(upload.workspace_id, upload.dataset_id, upload.id)
        if revision is None:
            raise IngestionError("not_found", "This upload has not been profiled yet.", 404)
        content = BytesIO(self.storage.read(upload))
        self.parser.parse(content, upload.filename, upload.content_type)
        table = self.parser.read_table(content, upload.format)
        table = reconstruct(table, revision)
        return table, dataset_view(revision.profile)

    async def create_join_path(
        self,
        actor: User,
        workspace_id: UUID,
        left_dataset_id: UUID,
        left_column: str,
        right_dataset_id: UUID,
        right_column: str,
    ) -> JoinPath:
        now = datetime.now(timezone.utc)
        join_path = JoinPath(
            uuid4(),
            workspace_id,
            left_dataset_id,
            left_column,
            right_dataset_id,
            right_column,
            actor.id,
            now,
        )
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            repo.dataset(workspace_id, left_dataset_id)
            repo.dataset(workspace_id, right_dataset_id)
            repo.add(join_path)
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    "join_path.created",
                    "join_path",
                    join_path.id,
                    now,
                )
            )
        return join_path

    async def list_join_paths(self, actor: User, workspace_id: UUID) -> tuple[JoinPath, ...]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            return repo.join_paths(workspace_id)

    async def run_join_query(
        self,
        actor: User,
        workspace_id: UUID,
        join_path_id: UUID,
        left_upload_id: UUID,
        right_upload_id: UUID,
        request: MetricRequest,
    ) -> tuple[QueryResult, CalculationLineage]:
        with self.uow() as repo:
            member = self._authorize(repo, actor, workspace_id)
            join_path = repo.join_path(workspace_id, join_path_id)
            left_dataset = repo.dataset(workspace_id, join_path.left_dataset_id)
            right_dataset = repo.dataset(workspace_id, join_path.right_dataset_id)
            left_upload = repo.upload(workspace_id, join_path.left_dataset_id, left_upload_id)
            right_upload = repo.upload(workspace_id, join_path.right_dataset_id, right_upload_id)
            left_table, left_view = self._snapshot(repo, left_upload)
            right_table, right_view = self._snapshot(repo, right_upload)

        scope = WorkspaceScope(
            workspace_id,
            actor.id,
            frozenset({member.role}),
            frozenset({join_path.left_dataset_id, join_path.right_dataset_id}),
        )
        combined = combine(left_view, right_view, join_path)
        plan = plan_join_query(scope, join_path, combined, request, row_limit=self.row_limit)
        result = await self.executor.execute_join(
            plan, scope, join_path, left_table, left_view, right_table, right_view
        )
        lineage = CalculationLineage(
            query_id=plan.query_id,
            workspace_id=workspace_id,
            dataset_id=join_path.left_dataset_id,
            dataset_name=f"{left_dataset.name} ⋈ {right_dataset.name}",
            records_analyzed=result.records_analyzed,
            metric=request.metric,
            aggregation=request.aggregation.value,
            grouping=request.group_by,
            filters=tuple(
                f"{clause.column} {clause.operator.value} {clause.value!r}"
                for clause in request.filters
            ),
            sql=plan.sql,
        )
        persist_query_execution(self.uow, actor, lineage)
        return result, lineage
