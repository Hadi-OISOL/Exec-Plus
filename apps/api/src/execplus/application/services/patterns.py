"""Use case: Runs private measured pattern scans inside existing conversations.

What it does: Binds one complete projection to source receipts and replays statistical output.
"""

import asyncio
from dataclasses import replace
from typing import Any
from uuid import UUID

from execplus.application.ports import PatternStatistics
from execplus.application.progress import activity
from execplus.application.services.analytics import AnalyticsService, UnitOfWork
from execplus.application.services.dataset_access import authorize_sources, dataset_access
from execplus.application.services.forecasts import read_complete
from execplus.application.validated_tables import sampled_table
from execplus.domain import sampling
from execplus.domain.cohort_comparison import (
    EVIDENCE_VERSION as COHORT_EVIDENCE_VERSION,
)
from execplus.domain.cohort_comparison import (
    VERSION as COHORT_VERSION,
)
from execplus.domain.cohort_comparison import (
    cohort_plan,
    cohort_request,
    cohort_result,
)
from execplus.domain.columnar import ColumnarTable
from execplus.domain.decision_analysis import checksum
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.evidence import receipt
from execplus.domain.group_relationships import EVIDENCE_VERSION as GROUP_EVIDENCE_VERSION
from execplus.domain.group_relationships import VERSION as GROUP_VERSION
from execplus.domain.group_relationships import (
    group_relationship_plan,
    group_relationship_request,
    group_relationship_result,
)
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.jobs import EventStatus, JobStage
from execplus.domain.models import CalculationLineage, QueryPlan, QueryResult, WorkspaceScope
from execplus.domain.patterns import (
    MAX_ROWS,
    REQUEST_VERSION,
    VERSION,
    pattern_plan,
    pattern_request,
    pattern_result,
)
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView

EVIDENCE_VERSION = "pattern-evidence-v1"


def with_sample(table: TableData, request: dict[str, Any]) -> dict[str, Any]:
    """Big Parquet snapshots scan a disclosed fixed-seed sample of row-level evidence."""
    if isinstance(table, ColumnarTable) and table.row_count > MAX_ROWS:
        return {
            **request,
            "sample": dict(spec=sampling.spec(MAX_ROWS), source_rows=table.row_count),
        }
    return request


def sampled_input(
    table: TableData, view: DatasetView, request: dict[str, Any]
) -> tuple[TableData, DatasetView]:
    sample = request.get("sample")
    if not sample:
        return table, view
    return sampled_table(table, sample["spec"]), sampled_view(view, request)


def sampled_view(view: DatasetView, request: dict[str, Any]) -> DatasetView:
    sample = request.get("sample")
    if not sample:
        return view
    return replace(
        view, sources=tuple({**source, "sample": sample["spec"]} for source in view.sources)
    )


def needs_totals(request: dict[str, Any]) -> bool:
    return (
        bool(request.get("sample"))
        and request.get("version") == REQUEST_VERSION
        and bool(request["categories"])
    )


class PatternService:
    def __init__(
        self, uow: UnitOfWork, analytics: AnalyticsService, statistics: PatternStatistics
    ) -> None:
        self.uow, self.analytics, self.statistics = uow, analytics, statistics

    def _current(self, actor: User, wid: UUID, did: UUID, uid: UUID) -> None:
        with self.uow() as repo:
            dataset_access(repo, actor, wid, did)
            repo.upload(wid, did, uid)
            if any(
                str(feed.source["upload_id"]) != str(uid) for feed in repo.refresh_feeds(wid, did)
            ):
                raise ClarificationRequiredError(
                    "Use the current accepted file before finding new patterns."
                )

    def _result(
        self,
        value: QueryResult,
        request: dict[str, Any],
        *,
        grouped: bool,
        totals: QueryResult | None = None,
    ) -> dict[str, Any]:
        if request.get("version") == "cohort-comparison-request-v1":
            return self._disclosed(
                cohort_result(value, request, self.statistics.engine_version), value, request
            )
        if grouped:
            return self._disclosed(
                group_relationship_result(
                    value, request, self.statistics.engine_version, self.statistics.correlations
                ),
                value,
                request,
            )
        return pattern_result(
            value,
            request,
            self.statistics.engine_version,
            self.statistics.correlations,
            self.statistics.categorical_association,
            totals,
        )

    @staticmethod
    def _disclosed(
        result: dict[str, Any], value: QueryResult, request: dict[str, Any]
    ) -> dict[str, Any]:
        sample = request.get("sample")
        if not sample:
            return result
        return {
            **result,
            "coverage": {
                **result["coverage"],
                "source_rows": sample["source_rows"],
                "sample": dict(spec=sample["spec"], sampled_rows=value.records_analyzed),
            },
            "limitations": [
                sampling.label(value.records_analyzed, sample["source_rows"])
                + " Every figure in this comparison uses only the sampled rows.",
                *result["limitations"],
            ],
        }

    async def _run(
        self,
        actor: User,
        plan: QueryPlan,
        lineage: CalculationLineage,
        scope: WorkspaceScope,
        table: TableData,
        view: DatasetView,
    ) -> QueryResult:
        await activity(JobStage.QUERY, EventStatus.STARTED)
        try:
            value = await self.analytics.executor.execute(plan, scope, table, view)
        except (Exception, asyncio.CancelledError):
            self.analytics._persist(
                actor, replace(lineage, receipt=receipt(plan, view.sources, None))
            )
            await activity(JobStage.QUERY, EventStatus.FAILED)
            raise
        self.analytics._persist(actor, replace(lineage, receipt=receipt(plan, view.sources, value)))
        await activity(JobStage.QUERY, EventStatus.COMPLETED)
        return value

    async def discover(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        uid: UUID,
        columns: tuple[str, ...] = (),
        *,
        group_by: str | None = None,
        target: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        self._current(actor, wid, did, uid)
        context, table, scope = await read_complete(
            lambda: self.analytics.descriptive_snapshot(actor, wid, did, uid)
        )
        grouped = group_by is not None
        request = with_sample(
            table,
            cohort_request(context, table, target[0], target[1], columns)
            if target is not None
            else group_relationship_request(context, table, columns, group_by)
            if group_by is not None
            else pattern_request(context, table, columns),
        )
        view = context.view
        run_table, run_view = sampled_input(table, view, request)
        plan = (
            cohort_plan
            if target is not None
            else group_relationship_plan
            if grouped
            else pattern_plan
        )(scope, did, view, request)
        lineage = CalculationLineage(
            plan.query_id,
            wid,
            did,
            context.name,
            run_table.row_count,
            "Selected pattern fields",
            "analysis",
            (),
            (),
            plan.sql,
            "deterministic:"
            + (COHORT_VERSION if target is not None else GROUP_VERSION if grouped else VERSION),
        )
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, view.sources)
        )
        self._current(actor, wid, did, uid)
        value = await self._run(actor, plan, lineage, scope, run_table, run_view)
        totals = None
        totals_plan = None
        if needs_totals(request):
            totals_plan = pattern_plan(scope, did, view, request, totals=True)
            totals = await self._run(
                actor,
                totals_plan,
                replace(
                    lineage,
                    query_id=totals_plan.query_id,
                    records_analyzed=table.row_count,
                    sql=totals_plan.sql,
                ),
                scope,
                table,
                view,
            )
        result = await read_complete(
            lambda: self._result(value, request, grouped=grouped, totals=totals)
        )
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, view.sources)
        )
        self._current(actor, wid, did, uid)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            authorize_sources(repo, actor, wid, view.sources, did)
        return dict(
            version=COHORT_EVIDENCE_VERSION
            if target is not None
            else GROUP_EVIDENCE_VERSION
            if grouped
            else EVIDENCE_VERSION,
            query_id=str(plan.query_id),
            sources=list(view.sources),
            request=request,
            engine_version=self.statistics.engine_version,
            result=result,
            request_checksum=checksum(request),
            result_checksum=checksum(result),
            **({"totals_query_id": str(totals_plan.query_id)} if totals_plan else {}),
        )

    async def compare_cohort(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        uid: UUID,
        target_column: str,
        target_value: str,
        columns: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return await self.discover(
            actor, wid, did, uid, columns, target=(target_column, target_value)
        )

    def _check_record(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        plan: QueryPlan,
        view: DatasetView,
        invalid: IngestionError,
    ) -> None:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            record = repo.query_execution(wid, plan.query_id)
            if record.actor_id != actor.id or record.aggregation != "analysis":
                raise IngestionError(
                    "not_found", "The private pattern evidence is unavailable.", 404
                )
            expected = receipt(plan, view.sources, None)
            if (
                record.dataset_id != did
                or record.sql != plan.sql
                or record.receipt.get("outcome") != "executed"
                or any(
                    record.receipt.get(key) != expected[key]
                    for key in ("version", "sources", "parameters")
                )
            ):
                raise invalid

    async def reopen(self, actor: User, wid: UUID, evidence: dict[str, Any]) -> dict[str, Any]:
        invalid = IngestionError(
            "lineage_mismatch", "The saved pattern evidence is inconsistent.", 409
        )
        try:
            if evidence["version"] not in {
                EVIDENCE_VERSION,
                GROUP_EVIDENCE_VERSION,
                COHORT_EVIDENCE_VERSION,
            } or evidence["request_checksum"] != checksum(evidence["request"]):
                raise invalid
            grouped = evidence["version"] == GROUP_EVIDENCE_VERSION
            cohort = evidence["version"] == COHORT_EVIDENCE_VERSION
            if evidence["engine_version"] != self.statistics.engine_version:
                raise IngestionError(
                    "pattern_engine_changed",
                    "This saved pattern needs its original statistics version to be verified.",
                    409,
                )
            sources = evidence["sources"]
            if len(sources) != 1:
                raise invalid
            source = sources[0]
            did, uid = UUID(source["dataset_id"]), UUID(source["upload_id"])
            with self.uow() as repo:
                authorize_sources(repo, actor, wid, sources, did)
            context = await read_complete(
                lambda: self.analytics.describe(actor, wid, did, uid, source)
            )
            _, scope, table, view = await read_complete(
                lambda: self.analytics.context_at(actor, wid, source)
            )
            request = with_sample(
                table,
                cohort_request(
                    context,
                    table,
                    evidence["request"]["target_column"],
                    evidence["request"]["target_value"],
                    tuple(evidence["request"]["selected"]),
                )
                if cohort
                else group_relationship_request(
                    context,
                    table,
                    tuple(evidence["request"]["selected"]),
                    evidence["request"]["group_by"],
                )
                if grouped
                else pattern_request(
                    context,
                    table,
                    tuple(evidence["request"]["selected"]),
                    selection_version=evidence["request"].get("selection_version"),
                ),
            )
            if request != evidence["request"]:
                raise invalid
            plan = replace(
                (cohort_plan if cohort else group_relationship_plan if grouped else pattern_plan)(
                    scope, did, view, request
                ),
                query_id=UUID(evidence["query_id"]),
            )
            self._check_record(actor, wid, did, plan, sampled_view(view, request), invalid)
            value, _ = await self.analytics.replay(actor, wid, plan.query_id)
            totals = None
            if needs_totals(request):
                totals_plan = replace(
                    pattern_plan(scope, did, view, request, totals=True),
                    query_id=UUID(evidence["totals_query_id"]),
                )
                self._check_record(actor, wid, did, totals_plan, view, invalid)
                totals, _ = await self.analytics.replay(actor, wid, totals_plan.query_id)
            elif "totals_query_id" in evidence:
                raise invalid
            result = await read_complete(
                lambda: self._result(value, request, grouped=grouped, totals=totals)
            )
            if result != evidence["result"] or checksum(result) != evidence["result_checksum"]:
                raise invalid
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                authorize_sources(repo, actor, wid, sources, did)
                repo.upload(wid, did, uid)
            return evidence
        except (KeyError, TypeError, ValueError, IndexError):
            raise invalid from None
