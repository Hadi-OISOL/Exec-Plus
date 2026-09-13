"""Use case: Orchestrates authorized, verified metric queries against a dataset snapshot.

What it does: Reconstructs an authorized revision, plans and executes read-only
queries, records each query in the audit trail, and derives a deterministic
dashboard summary from the dataset's profile.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

from execplus.application.ports import FileParser, ObjectStorage, QueryExecutor, WorkspaceRepository
from execplus.application.services.answers import AnswerAssembler
from execplus.application.services.lineage import persist_query_execution
from execplus.domain.dashboard_templates import TEMPLATES, DashboardTemplate, applicable_templates
from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.ingestion import IngestionError, Membership, Upload, User
from execplus.domain.kpi_library import KpiMatch, compatible_kpis, kpi_by_id
from execplus.domain.models import (
    CalculationLineage,
    QueryResult,
    VerifiedMetricAnswer,
    WorkspaceScope,
)
from execplus.domain.profiling import TableData, reconstruct
from execplus.domain.semantics import (
    VALUE_ALIAS,
    AggregationKind,
    DatasetView,
    MetricFilter,
    MetricRequest,
    RowRequest,
    dataset_view,
    plan_query,
    plan_rows,
    recommend_breakdown_dimension,
    recommend_metrics,
    recommend_trend_dimension,
)
from execplus.domain.suggestions import suggested_questions

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


@dataclass(frozen=True, slots=True)
class DashboardCard:
    metric: str
    result: QueryResult
    lineage: CalculationLineage
    kpi: KpiMatch | None = None


@dataclass(frozen=True, slots=True)
class DashboardBreakdown:
    metric: str
    dimension: str
    result: QueryResult
    lineage: CalculationLineage


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    cards: tuple[DashboardCard, ...]
    trend: DashboardBreakdown | None
    breakdown: DashboardBreakdown | None


class AnalyticsService:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        storage: ObjectStorage,
        parser: FileParser,
        executor: QueryExecutor,
        assembler: AnswerAssembler,
        row_limit: int = 10_000,
    ) -> None:
        self.uow = unit_of_work
        self.storage = storage
        self.parser = parser
        self.executor = executor
        self.assembler = assembler
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

    def _context(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[str, WorkspaceScope, TableData, DatasetView]:
        with self.uow() as repo:
            member = self._authorize(repo, actor, workspace_id)
            dataset = repo.dataset(workspace_id, dataset_id)
            upload = repo.upload(workspace_id, dataset_id, upload_id)
            table, view = self._snapshot(repo, upload)
        scope = WorkspaceScope(
            workspace_id, actor.id, frozenset({member.role}), frozenset({dataset_id})
        )
        return dataset.name, scope, table, view

    def _persist(self, actor: User, lineage: CalculationLineage) -> None:
        persist_query_execution(self.uow, actor, lineage)

    async def _execute(
        self,
        actor: User,
        dataset_id: UUID,
        dataset_name: str,
        scope: WorkspaceScope,
        table: TableData,
        view: DatasetView,
        request: MetricRequest,
        model_route: str | None = None,
    ) -> tuple[QueryResult, CalculationLineage]:
        plan = plan_query(scope, dataset_id, view, request, row_limit=self.row_limit)
        result = await self.executor.execute(plan, scope, table, view)
        lineage = CalculationLineage(
            query_id=plan.query_id,
            workspace_id=scope.workspace_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            records_analyzed=result.records_analyzed,
            metric=request.metric,
            aggregation=request.aggregation.value,
            grouping=request.group_by,
            filters=tuple(
                f"{clause.column} {clause.operator.value} {clause.value!r}"
                for clause in request.filters
            ),
            sql=plan.sql,
            model_route=model_route,
        )
        self._persist(actor, lineage)
        return result, lineage

    async def _execute_rows(
        self,
        actor: User,
        dataset_id: UUID,
        dataset_name: str,
        scope: WorkspaceScope,
        table: TableData,
        view: DatasetView,
        request: RowRequest,
        limit: int,
    ) -> tuple[QueryResult, CalculationLineage]:
        plan = plan_rows(scope, dataset_id, view, request, row_limit=limit)
        result = await self.executor.execute(plan, scope, table, view)
        lineage = CalculationLineage(
            query_id=plan.query_id,
            workspace_id=scope.workspace_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            records_analyzed=result.records_analyzed,
            metric="(all columns)",
            aggregation="rows",
            grouping=(),
            filters=tuple(
                f"{clause.column} {clause.operator.value} {clause.value!r}"
                for clause in request.filters
            ),
            sql=plan.sql,
        )
        self._persist(actor, lineage)
        return result, lineage

    async def get_lineage(
        self, actor: User, workspace_id: UUID, query_id: UUID
    ) -> CalculationLineage:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            execution = repo.query_execution(workspace_id, query_id)
        return execution.lineage()

    async def get_view(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> DatasetView:
        _, _, _, view = self._context(actor, workspace_id, dataset_id, upload_id)
        return view

    async def suggested_questions(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[str, ...]:
        view = await self.get_view(actor, workspace_id, dataset_id, upload_id)
        return suggested_questions(view)

    async def run_query(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        request: MetricRequest,
        model_route: str | None = None,
    ) -> tuple[QueryResult, CalculationLineage]:
        dataset_name, scope, table, view = self._context(actor, workspace_id, dataset_id, upload_id)
        return await self._execute(
            actor, dataset_id, dataset_name, scope, table, view, request, model_route
        )

    async def answer_metric(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        request: MetricRequest,
        model_route: str | None = None,
    ) -> VerifiedMetricAnswer:
        if request.group_by:
            raise UnsupportedQuestionError("A single verified answer cannot include grouping")
        result, lineage = await self.run_query(
            actor, workspace_id, dataset_id, upload_id, request, model_route
        )
        return self.assembler.assemble_metric(
            label=request.metric, column=VALUE_ALIAS, result=result, lineage=lineage
        )

    async def list_kpis(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[KpiMatch, ...]:
        _, _, _, view = self._context(actor, workspace_id, dataset_id, upload_id)
        return compatible_kpis(view)

    async def compute_kpi(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID, kpi_id: str
    ) -> VerifiedMetricAnswer:
        definition = kpi_by_id(kpi_id)
        if definition is None:
            raise UnsupportedQuestionError(f"{kpi_id!r} is not a recognized KPI")
        dataset_name, scope, table, view = self._context(actor, workspace_id, dataset_id, upload_id)
        matches = {match.definition.id: match for match in compatible_kpis(view)}
        match = matches.get(kpi_id)
        if match is None:
            raise UnsupportedQuestionError(
                f"{definition.name!r} is not supported by this dataset's profile"
            )
        request = MetricRequest(metric=match.column, aggregation=definition.aggregation)
        result, lineage = await self._execute(
            actor, dataset_id, dataset_name, scope, table, view, request
        )
        return self.assembler.assemble_metric(
            label=definition.name, column=VALUE_ALIAS, result=result, lineage=lineage
        )

    async def list_dashboard_templates(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[DashboardTemplate, ...]:
        view = await self.get_view(actor, workspace_id, dataset_id, upload_id)
        return applicable_templates(view)

    async def dashboard_summary(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        filters: tuple[MetricFilter, ...] = (),
        template_id: str | None = None,
    ) -> DashboardSummary:
        dataset_name, scope, table, view = self._context(actor, workspace_id, dataset_id, upload_id)

        if template_id is not None:
            return await self._template_dashboard(
                actor, dataset_id, dataset_name, scope, table, view, filters, template_id
            )

        # Dashboard recommendations are KPI-aware: a curated KPI match takes the
        # card slot for its column, labeled and explained by the KPI library;
        # any remaining numeric column recommended by the profile alone still
        # gets a plain card so nothing numeric is silently hidden. The same
        # filters are applied to every card, trend, and breakdown query so the
        # whole dashboard reflects one consistent, user-chosen slice of data.
        cards: list[DashboardCard] = []
        covered_columns: set[str] = set()
        for match in compatible_kpis(view):
            if match.column in covered_columns or len(cards) >= 6:
                continue
            request = MetricRequest(
                metric=match.column, aggregation=match.definition.aggregation, filters=filters
            )
            result, lineage = await self._execute(
                actor, dataset_id, dataset_name, scope, table, view, request
            )
            cards.append(DashboardCard(match.column, result, lineage, match))
            covered_columns.add(match.column)
        for metric in recommend_metrics(view):
            if metric in covered_columns or len(cards) >= 6:
                continue
            request = MetricRequest(metric=metric, aggregation=AggregationKind.SUM, filters=filters)
            result, lineage = await self._execute(
                actor, dataset_id, dataset_name, scope, table, view, request
            )
            cards.append(DashboardCard(metric, result, lineage))
            covered_columns.add(metric)

        primary_metric = recommend_metrics(view, limit=1)
        trend = None
        trend_dimension = recommend_trend_dimension(view)
        if primary_metric and trend_dimension:
            request = MetricRequest(
                metric=primary_metric[0],
                aggregation=AggregationKind.SUM,
                group_by=(trend_dimension,),
                filters=filters,
            )
            result, lineage = await self._execute(
                actor, dataset_id, dataset_name, scope, table, view, request
            )
            trend = DashboardBreakdown(primary_metric[0], trend_dimension, result, lineage)

        breakdown = None
        breakdown_dimension = recommend_breakdown_dimension(view)
        if primary_metric and breakdown_dimension:
            request = MetricRequest(
                metric=primary_metric[0],
                aggregation=AggregationKind.SUM,
                group_by=(breakdown_dimension,),
                filters=filters,
            )
            result, lineage = await self._execute(
                actor, dataset_id, dataset_name, scope, table, view, request
            )
            breakdown = DashboardBreakdown(primary_metric[0], breakdown_dimension, result, lineage)

        return DashboardSummary(tuple(cards), trend, breakdown)

    async def _template_dashboard(
        self,
        actor: User,
        dataset_id: UUID,
        dataset_name: str,
        scope: WorkspaceScope,
        table: TableData,
        view: DatasetView,
        filters: tuple[MetricFilter, ...],
        template_id: str,
    ) -> DashboardSummary:
        template = next((item for item in TEMPLATES if item.id == template_id), None)
        if template is None:
            raise UnsupportedQuestionError(
                f"{template_id!r} is not a recognized dashboard template"
            )
        matches = {match.definition.id: match for match in compatible_kpis(view)}
        for kpi_id in template.card_kpi_ids:
            if kpi_id not in matches:
                raise UnsupportedQuestionError(
                    f"{template.name!r} is not supported by this dataset's profile"
                )

        cards: list[DashboardCard] = []
        for kpi_id in template.card_kpi_ids:
            match = matches[kpi_id]
            request = MetricRequest(
                metric=match.column, aggregation=match.definition.aggregation, filters=filters
            )
            result, lineage = await self._execute(
                actor, dataset_id, dataset_name, scope, table, view, request
            )
            cards.append(DashboardCard(match.column, result, lineage, match))

        trend = await self._template_breakdown(
            actor,
            dataset_id,
            dataset_name,
            scope,
            table,
            view,
            filters,
            matches,
            template.trend_kpi_id,
            recommend_trend_dimension,
        )
        breakdown = await self._template_breakdown(
            actor,
            dataset_id,
            dataset_name,
            scope,
            table,
            view,
            filters,
            matches,
            template.breakdown_kpi_id,
            recommend_breakdown_dimension,
        )
        return DashboardSummary(tuple(cards), trend, breakdown)

    async def _template_breakdown(
        self,
        actor: User,
        dataset_id: UUID,
        dataset_name: str,
        scope: WorkspaceScope,
        table: TableData,
        view: DatasetView,
        filters: tuple[MetricFilter, ...],
        matches: dict[str, KpiMatch],
        kpi_id: str | None,
        recommend_dimension: Callable[[DatasetView], str | None],
    ) -> DashboardBreakdown | None:
        if kpi_id is None:
            return None
        match = matches.get(kpi_id)
        dimension = recommend_dimension(view)
        if match is None or dimension is None:
            return None
        request = MetricRequest(
            metric=match.column,
            aggregation=match.definition.aggregation,
            group_by=(dimension,),
            filters=filters,
        )
        result, lineage = await self._execute(
            actor, dataset_id, dataset_name, scope, table, view, request
        )
        return DashboardBreakdown(match.column, dimension, result, lineage)

    async def drill_down(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        filters: tuple[MetricFilter, ...],
        limit: int = 100,
    ) -> tuple[QueryResult, CalculationLineage]:
        dataset_name, scope, table, view = self._context(actor, workspace_id, dataset_id, upload_id)
        request = RowRequest(filters=filters)
        bounded_limit = min(limit, self.row_limit)
        return await self._execute_rows(
            actor, dataset_id, dataset_name, scope, table, view, request, bounded_limit
        )
