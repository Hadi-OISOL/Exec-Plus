"""Use case: Orchestrates authorized, verified metric queries against a dataset snapshot.

What it does: Reconstructs an authorized revision, plans and executes read-only
queries, records each query in the audit trail, and derives a deterministic
dashboard summary from the dataset's profile.
"""

import asyncio
import hashlib
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from io import BytesIO
from typing import cast
from uuid import UUID, uuid4

from execplus.application.ports import FileParser, ObjectStorage, QueryExecutor, WorkspaceRepository
from execplus.application.progress import activity
from execplus.application.services.answers import AnswerAssembler
from execplus.application.services.lineage import persist_query_execution
from execplus.application.services.understanding import current_meaning
from execplus.domain.dashboard_templates import TEMPLATES, DashboardTemplate, applicable_templates
from execplus.domain.errors import ClarificationRequiredError, UnsupportedQuestionError
from execplus.domain.evidence import receipt, result_evidence, scalar_from_record
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import AuditEvent, IngestionError, Membership, Upload, User
from execplus.domain.jobs import EventStatus, JobStage
from execplus.domain.kpi_library import KpiMatch, compatible_kpis, kpi_by_id
from execplus.domain.models import (
    CalculationLineage,
    QueryPlan,
    QueryResult,
    VerifiedMetricAnswer,
    WorkspaceScope,
)
from execplus.domain.profiling import Revision, TableData, reconstruct
from execplus.domain.semantics import (
    VALUE_ALIAS,
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
from execplus.domain.understanding import apply_definition, governed_request, preferred_aggregation

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

    def _revision_snapshot(
        self, upload: Upload, revision: Revision
    ) -> tuple[TableData, DatasetView]:
        content = BytesIO(self.storage.read(upload))
        self.parser.parse(
            content, upload.filename, upload.content_type, stored_format=upload.format
        )
        table = self.parser.read_table(content, upload.format)
        table = reconstruct(table, revision)
        if revision.source_checksum != upload.checksum:
            raise IngestionError("lineage_mismatch", "The source integrity check failed.", 409)
        source = {
            "dataset_id": str(upload.dataset_id),
            "upload_id": str(upload.id),
            "revision_id": str(revision.id),
            "source_checksum": upload.checksum,
            "output_checksum": revision.output_checksum,
        }
        view = replace(dataset_view(revision.profile), sources=(source,))
        return table, view

    def _snapshot(self, repo: WorkspaceRepository, upload: Upload) -> tuple[TableData, DatasetView]:
        revision = repo.active_revision(upload.workspace_id, upload.dataset_id, upload.id)
        if revision is None:
            raise IngestionError("not_found", "This upload has not been profiled yet.", 404)
        table, view = self._revision_snapshot(upload, revision)
        return table, current_meaning(repo, revision, view)

    def describe(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        source: dict[str, str] | None = None,
    ) -> DescriptionContext:
        context, _, _ = self.descriptive_snapshot(
            actor, workspace_id, dataset_id, upload_id, source
        )
        return context

    def descriptive_snapshot(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        source: dict[str, str] | None = None,
    ) -> tuple[DescriptionContext, TableData, WorkspaceScope]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            dataset = repo.dataset(workspace_id, dataset_id)
            upload = repo.upload(workspace_id, dataset_id, upload_id)
            revision = (
                repo.revision(workspace_id, dataset_id, upload_id, UUID(source["revision_id"]))
                if source
                else repo.active_revision(workspace_id, dataset_id, upload_id)
            )
            if revision is None:
                raise IngestionError("not_found", "Profile this upload first.", 404)
            table, view = self._revision_snapshot(upload, revision)
            saved = (
                repo.understanding(workspace_id, dataset_id, UUID(source["understanding_id"]))
                if source and source.get("understanding_id")
                else None
                if source
                else repo.latest_understanding(workspace_id, dataset_id)
            )
            state = "inferred"
            definition = None
            if saved:
                state = saved.state if saved.revision_id == revision.id else "needs_review"
                definition = saved.definition if state in {"inferred", "confirmed"} else None
                view = replace(
                    view, sources=({**view.sources[0], "understanding_id": str(saved.id)},)
                )
                if state == "confirmed":
                    view = apply_definition(view, saved.definition)
            if source and view.sources != (source,):
                raise IngestionError("lineage_mismatch", "The explanation source changed.", 409)
            member = self._authorize(repo, actor, workspace_id)
            context = DescriptionContext(dataset.name, revision.profile, view, definition, state)
            scope = WorkspaceScope(
                workspace_id, actor.id, frozenset({member.role}), frozenset({dataset_id})
            )
            return context, table, scope

    def _current_description_source(
        self,
        repo: WorkspaceRepository,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
    ) -> tuple[Upload, tuple[dict[str, str], ...]]:
        self._authorize(repo, actor, workspace_id)
        repo.dataset(workspace_id, dataset_id)
        upload = repo.upload(workspace_id, dataset_id, upload_id)
        revision = repo.active_revision(workspace_id, dataset_id, upload_id)
        if revision is None:
            raise IngestionError("not_found", "Profile this upload first.", 404)
        if revision.source_checksum != upload.checksum:
            raise IngestionError("lineage_mismatch", "The source integrity check failed.", 409)
        saved = repo.latest_understanding(workspace_id, dataset_id)
        source = {
            "dataset_id": str(dataset_id),
            "upload_id": str(upload_id),
            "revision_id": str(revision.id),
            "source_checksum": upload.checksum,
            "output_checksum": revision.output_checksum,
        }
        if saved:
            source["understanding_id"] = str(saved.id)
        return upload, (source,)

    def recheck_description(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        expected_sources: tuple[dict[str, str], ...],
    ) -> None:
        message = "The file or its meaning changed. Reload the discovery."
        with self.uow() as repo:
            upload, before = self._current_description_source(
                repo, actor, workspace_id, dataset_id, upload_id
            )
            if before != expected_sources:
                raise ClarificationRequiredError(message)
            content = self.storage.read(upload)
            if hashlib.sha256(content).hexdigest() != upload.checksum:
                raise IngestionError("lineage_mismatch", "The source integrity check failed.", 409)
            _, after = self._current_description_source(
                repo, actor, workspace_id, dataset_id, upload_id
            )
            if after != expected_sources:
                raise ClarificationRequiredError(message)

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

    def context_at(
        self, actor: User, workspace_id: UUID, source: dict[str, str]
    ) -> tuple[str, WorkspaceScope, TableData, DatasetView]:
        with self.uow() as repo:
            member = self._authorize(repo, actor, workspace_id)
            did, uid = UUID(source["dataset_id"]), UUID(source["upload_id"])
            dataset = repo.dataset(workspace_id, did)
            upload = repo.upload(workspace_id, did, uid)
            revision = repo.revision(workspace_id, did, uid, UUID(source["revision_id"]))
            meaning = repo.understanding(workspace_id, did, UUID(source["understanding_id"]))
            if (
                meaning.revision_id != revision.id
                or meaning.state != "confirmed"
                or source["source_checksum"] != upload.checksum
                or revision.source_checksum != upload.checksum
                or source["output_checksum"] != revision.output_checksum
            ):
                raise IngestionError(
                    "lineage_mismatch", "The retained source failed verification.", 409
                )
            content = BytesIO(self.storage.read(upload))
            self.parser.parse(
                content, upload.filename, upload.content_type, stored_format=upload.format
            )
            table = reconstruct(self.parser.read_table(content, upload.format), revision)
            frozen_source = {
                key: source[key]
                for key in (
                    "dataset_id",
                    "upload_id",
                    "revision_id",
                    "source_checksum",
                    "output_checksum",
                    "understanding_id",
                )
            }
            view = apply_definition(
                replace(dataset_view(revision.profile), sources=(frozen_source,)),
                meaning.definition,
            )
            self._authorize(repo, actor, workspace_id)
        return (
            dataset.name,
            WorkspaceScope(workspace_id, actor.id, frozenset({member.role}), frozenset({did})),
            table,
            view,
        )

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
        request = governed_request(view, table, request)
        plan = plan_query(scope, dataset_id, view, request, row_limit=self.row_limit)
        lineage = CalculationLineage(
            query_id=plan.query_id,
            workspace_id=scope.workspace_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            records_analyzed=len(table.rows),
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
        with self.uow() as repo:
            self._authorize(repo, actor, scope.workspace_id)
        await activity(JobStage.QUERY, EventStatus.STARTED)
        try:
            result = await self.executor.execute(plan, scope, table, view)
        except (Exception, asyncio.CancelledError):
            self._persist(actor, replace(lineage, receipt=receipt(plan, view.sources, None)))
            await activity(JobStage.QUERY, EventStatus.FAILED)
            raise
        lineage = replace(
            lineage,
            receipt=receipt(plan, view.sources, result, row_query=lineage.aggregation == "rows"),
        )
        self._persist(actor, lineage)
        await activity(JobStage.QUERY, EventStatus.COMPLETED)
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
        model_route: str | None = None,
    ) -> tuple[QueryResult, CalculationLineage]:
        plan = plan_rows(scope, dataset_id, view, request, row_limit=limit)
        lineage = CalculationLineage(
            query_id=plan.query_id,
            workspace_id=scope.workspace_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            records_analyzed=len(table.rows),
            metric="(all columns)",
            aggregation="rows",
            grouping=(),
            filters=tuple(
                f"{clause.column} {clause.operator.value} {clause.value!r}"
                for clause in request.filters
            ),
            sql=plan.sql,
            model_route=model_route,
        )
        with self.uow() as repo:
            self._authorize(repo, actor, scope.workspace_id)
        await activity(JobStage.QUERY, EventStatus.STARTED)
        try:
            result = await self.executor.execute(plan, scope, table, view)
        except (Exception, asyncio.CancelledError):
            self._persist(actor, replace(lineage, receipt=receipt(plan, view.sources, None)))
            await activity(JobStage.QUERY, EventStatus.FAILED)
            raise
        lineage = replace(
            lineage,
            receipt=receipt(plan, view.sources, result, row_query=lineage.aggregation == "rows"),
        )
        self._persist(actor, lineage)
        await activity(JobStage.QUERY, EventStatus.COMPLETED)
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
        expected_sources: tuple[dict[str, str], ...] | None = None,
    ) -> tuple[QueryResult, CalculationLineage]:
        dataset_name, scope, table, view = self._context(actor, workspace_id, dataset_id, upload_id)
        if expected_sources is not None and view.sources != expected_sources:
            raise ClarificationRequiredError(
                "The data or business definition changed while planning. "
                "Ask again with the current revision."
            )
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
        expected_sources: tuple[dict[str, str], ...] | None = None,
    ) -> VerifiedMetricAnswer:
        if request.group_by:
            raise UnsupportedQuestionError("A single verified answer cannot include grouping")
        result, lineage = await self.run_query(
            actor, workspace_id, dataset_id, upload_id, request, model_route, expected_sources
        )
        if not result.rows or result.rows[0][0] is None:
            raise UnsupportedQuestionError("No matching numeric values were found for this request")
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
        if not result.rows or result.rows[0][0] is None:
            raise UnsupportedQuestionError("No matching numeric values were found for this request")
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
            request = MetricRequest(
                metric=metric, aggregation=preferred_aggregation(view, metric), filters=filters
            )
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
                aggregation=preferred_aggregation(view, primary_metric[0]),
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
                aggregation=preferred_aggregation(view, primary_metric[0]),
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

    async def query_records(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        request: RowRequest,
        limit: int,
        model_route: str,
        expected_sources: tuple[dict[str, str], ...] | None = None,
    ) -> tuple[QueryResult, CalculationLineage]:
        dataset_name, scope, table, view = self._context(actor, workspace_id, dataset_id, upload_id)
        if expected_sources is not None and view.sources != expected_sources:
            raise ClarificationRequiredError(
                "The data or business definition changed while planning. "
                "Ask again with the current revision."
            )
        return await self._execute_rows(
            actor,
            dataset_id,
            dataset_name,
            scope,
            table,
            view,
            request,
            min(limit, self.row_limit),
            model_route,
        )

    async def replay(
        self, actor: User, workspace_id: UUID, query_id: UUID
    ) -> tuple[QueryResult, CalculationLineage]:
        lineage = await self.get_lineage(actor, workspace_id, query_id)
        evidence = lineage.receipt
        if evidence.get("version") != "execution-v1" or evidence.get("outcome") != "executed":
            raise IngestionError(
                "replay_unavailable",
                "This historical query has no complete execution receipt.",
                409,
            )
        sources = cast(list[dict[str, str]], evidence["sources"])
        tables: list[TableData] = []
        views: list[DatasetView] = []
        with self.uow() as repo:
            member = self._authorize(repo, actor, workspace_id)
            for source in sources:
                upload = repo.upload(
                    workspace_id, UUID(source["dataset_id"]), UUID(source["upload_id"])
                )
                revision = repo.revision(
                    workspace_id, upload.dataset_id, upload.id, UUID(source["revision_id"])
                )
                if (
                    upload.checksum != source["source_checksum"]
                    or revision.output_checksum != source["output_checksum"]
                ):
                    raise IngestionError(
                        "lineage_mismatch", "The snapshot no longer matches its receipt.", 409
                    )
                content = BytesIO(self.storage.read(upload))
                self.parser.parse(
                    content, upload.filename, upload.content_type, stored_format=upload.format
                )
                tables.append(reconstruct(self.parser.read_table(content, upload.format), revision))
                view = dataset_view(revision.profile)
                if source.get("understanding_id"):
                    meaning = repo.understanding(
                        workspace_id, upload.dataset_id, UUID(source["understanding_id"])
                    )
                    if meaning.revision_id != revision.id or meaning.state != "confirmed":
                        raise IngestionError(
                            "lineage_mismatch",
                            "The definition does not match the recorded revision.",
                            409,
                        )
                    view = apply_definition(view, meaning.definition)
                views.append(view)
        scope = WorkspaceScope(
            workspace_id,
            actor.id,
            frozenset({member.role}),
            frozenset(UUID(source["dataset_id"]) for source in sources),
        )
        parameters = cast(list[dict[str, object]], evidence["parameters"])
        plan = QueryPlan(
            query_id,
            workspace_id,
            lineage.dataset_id,
            "Replay verified query",
            lineage.sql,
            tuple(scalar_from_record(value) for value in parameters),
        )
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
        if len(tables) == 1:
            result = await self.executor.execute(plan, scope, tables[0], views[0])
        elif len(tables) == 2 and "join_path_id" in evidence:
            with self.uow() as repo:
                path = repo.join_path(workspace_id, UUID(str(evidence["join_path_id"])))
            result = await self.executor.execute_join(
                plan, scope, path, tables[0], views[0], tables[1], views[1]
            )
        else:
            raise IngestionError("replay_unavailable", "Unsupported snapshot receipt.", 409)
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
        if result_evidence(result)["checksum"] != evidence["result_checksum"]:
            raise IngestionError(
                "lineage_mismatch", "The replay did not reproduce the recorded answer.", 409
            )
        if "matched_records" in evidence and evidence["matched_records"] != result.matched_records:
            raise IngestionError("lineage_mismatch", "The matching record count changed.", 409)
        return result, lineage

    async def record_narrative(
        self,
        actor: User,
        workspace_id: UUID,
        evidence_ids: tuple[str, ...],
        text: str,
        model_route: str,
    ) -> None:
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            self._authorize(repo, actor, workspace_id)
            executions = [repo.query_execution(workspace_id, UUID(key)) for key in evidence_ids]
            execution = executions[0]
            updated = dict(execution.receipt)
            narratives = updated.get("narratives", [])
            assert isinstance(narratives, list)
            updated["narratives"] = [
                *narratives,
                {
                    "id": str(uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "actor_id": str(actor.id),
                    "evidence_ids": list(evidence_ids),
                    "text": text,
                    "model_route": model_route,
                },
            ]
            repo.set_query_receipt(workspace_id, execution.id, updated)
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    "summary.generated",
                    "query",
                    execution.id,
                    datetime.now(timezone.utc),
                )
            )
