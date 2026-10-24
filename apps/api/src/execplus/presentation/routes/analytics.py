"""Use case: Exposes authenticated, structured metric query HTTP contracts.

What it does: Maps validated requests to AnalyticsService and returns executed
results alongside their calculation lineage.
"""

import asyncio
from collections.abc import Coroutine
from dataclasses import asdict
from decimal import Decimal
from typing import Annotated, Any, Literal, TypeVar
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.conversation import EvidenceAnswer, NumericalAnswer, answer_lineage
from execplus.application.conversation_context import capture_follow_ups
from execplus.application.services.analytics import (
    AnalyticsService,
    DashboardBreakdown,
    DashboardCard,
)
from execplus.application.services.data_diagrams import DiagramAnswer
from execplus.application.services.discovery import discover
from execplus.application.services.insights import build_insights
from execplus.application.services.intent_router import (
    ConversationAnswer,
    DatasetGuide,
    IntentRouterService,
    PatternAnswer,
)
from execplus.application.services.summaries import SummaryService
from execplus.application.usage_context import usage_scope
from execplus.domain.answer_presentation import decimal_text, recommended_chart, share_of_total
from execplus.domain.kpi_library import KpiMatch
from execplus.domain.models import CalculationLineage, QueryResult, VerifiedMetricAnswer
from execplus.domain.pdf_exports import ReportAnswer
from execplus.domain.semantics import (
    PER_DAY_LABEL,
    AggregationKind,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    RowExtremum,
    RowRequest,
)
from execplus.domain.usage_metering import UsageAttribution
from execplus.presentation.routes.workspaces import Actor

_MAX_DRILL_DOWN_ROWS = 1000
_DISCONNECT_POLL_SECONDS = 0.1
T = TypeVar("T")

router = APIRouter(tags=["analytics"])


def get_analytics_service(request: Request) -> AnalyticsService:
    service: AnalyticsService = request.app.state.runtime.analytics
    return service


def get_intent_router_service(request: Request) -> IntentRouterService:
    service: IntentRouterService = request.app.state.runtime.intent_router
    return service


def get_summary_service(request: Request) -> SummaryService:
    service: SummaryService = request.app.state.runtime.summaries
    return service


Service = Annotated[AnalyticsService, Depends(get_analytics_service)]
IntentRouter = Annotated[IntentRouterService, Depends(get_intent_router_service)]
Summaries = Annotated[SummaryService, Depends(get_summary_service)]


class FilterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str = Field(min_length=1, max_length=100)
    operator: FilterOperator
    value: str | int | float | bool


def metric_filters(items: list[FilterInput]) -> tuple[MetricFilter, ...]:
    return tuple(MetricFilter(item.column, item.operator, item.value) for item in items)


class MetricQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str = Field(min_length=1, max_length=100)
    aggregation: AggregationKind
    group_by: list[str] = Field(default_factory=list, max_length=10)
    filters: list[FilterInput] = Field(default_factory=list, max_length=20)

    def request(self) -> MetricRequest:
        return MetricRequest(
            metric=self.metric,
            aggregation=self.aggregation,
            group_by=tuple(self.group_by),
            filters=metric_filters(self.filters),
        )


class DashboardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: list[FilterInput] = Field(default_factory=list, max_length=20)
    template_id: str | None = Field(default=None, max_length=100)


class ExtremumInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str = Field(min_length=1, max_length=100)
    direction: Literal["min", "max"]


class RowsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: list[FilterInput] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=100, ge=1, le=_MAX_DRILL_DOWN_ROWS)
    extremum: ExtremumInput | None = None


class AskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)


def query_body(result: QueryResult, lineage: CalculationLineage) -> dict[str, object]:
    return {
        "columns": result.columns,
        "rows": jsonable_encoder(
            result.rows,
            custom_encoder={
                Decimal: decimal_text,
                int: lambda value: str(value) if abs(value) > 2**53 - 1 else value,
            },
        ),
        "records_analyzed": result.records_analyzed,
        "matched_records": result.matched_records,
        "lineage": asdict(lineage),
    }


def _breakdown_body(breakdown: DashboardBreakdown | None) -> dict[str, object] | None:
    if breakdown is None:
        return None
    return {"dimension": breakdown.dimension, **query_body(breakdown.result, breakdown.lineage)}


def _kpi_body(match: KpiMatch) -> dict[str, object]:
    return {
        "id": match.definition.id,
        "domain": match.definition.domain.value,
        "version": match.definition.version,
        "name": match.definition.name,
        "description": match.definition.description,
        "unit": match.definition.unit.value,
        "aggregation": match.definition.aggregation.value,
        "column": match.column,
        "explanation": match.explanation,
    }


def _card_body(card: DashboardCard) -> dict[str, object]:
    body = {"metric": card.metric, **query_body(card.result, card.lineage)}
    if card.kpi is not None:
        body["kpi"] = _kpi_body(card.kpi)
    return body


def answer_body(answer: VerifiedMetricAnswer) -> dict[str, object]:
    return {
        "label": answer.label,
        "value": decimal_text(answer.value)
        if isinstance(answer.value, Decimal)
        else (str(answer.value) if abs(answer.value) > 2**53 - 1 else answer.value),
        "lineage": asdict(answer.lineage),
    }


def _presentation(
    question: str, answer: NumericalAnswer, follow_ups: tuple[str, ...]
) -> dict[str, object]:
    if isinstance(answer, VerifiedMetricAnswer):
        return {"chart": {"type": "kpi"}, "share_of_total": [], "follow_ups": list(follow_ups)}
    result, lineage = answer
    return {
        "chart": recommended_chart(question, lineage, result.columns, result.rows),
        "share_of_total": share_of_total(lineage, result.rows),
        "follow_ups": list(follow_ups),
    }


def numerical_answer_body(
    answer: ConversationAnswer,
    question: str = "",
    follow_ups: tuple[str, ...] = (),
) -> dict[str, object]:
    if isinstance(answer, ReportAnswer):
        return {
            "kind": "report",
            "report": {
                "thread_id": str(answer.thread_id),
                "turn_id": str(answer.turn_id),
                "label": answer.label,
                "format": answer.format,
                "download_url": answer.download_url,
            },
        }
    if isinstance(answer, DiagramAnswer):
        return {
            "kind": "diagram",
            "diagram": answer.diagram.body(),
            "sources": answer.sources,
            "model_route": answer.model_route,
        }
    if isinstance(answer, PatternAnswer):
        evidence = answer.evidence
        return {
            "kind": "patterns",
            "patterns": evidence["result"],
            "pattern_evidence": {
                "query_id": evidence["query_id"],
                "method_version": evidence["result"]["version"],
                "engine_version": evidence["engine_version"],
                "result_checksum": evidence["result_checksum"],
            },
            "sources": evidence["sources"],
            "model_route": answer.model_route,
        }
    if isinstance(answer, EvidenceAnswer):
        return {
            "kind": answer.kind,
            "data": numerical_answer_body(answer.data, question, follow_ups)
            if answer.data
            else None,
            "additional_data": [
                numerical_answer_body(item, question) for item in answer.additional_data
            ],
            "citations": answer.citations,
            "coverage": answer.coverage,
            "limitations": answer.limitations,
            "model_route": answer.model_route,
            "sources": answer.sources,
            "message": (
                "Weekdays and weekends have different numbers of days, so the first result is "
                "the average per calendar day: each group's exact total divided by the number "
                "of distinct calendar days it contains. The totals follow."
                if answer.data and answer_lineage(answer.data).metric.endswith(PER_DAY_LABEL)
                else "The requested calculations are shown with their individual evidence."
                if answer.coverage == "data"
                else "Calculated data and quoted source statements are shown separately."
            ),
        }
    if isinstance(answer, DatasetGuide):
        return {
            "kind": "overview",
            "message": answer.message,
            "model_route": answer.model_route,
            "guidance": {
                "columns": answer.columns,
                "suggestions": answer.suggestions,
                "definition_state": answer.definition_state,
                "focus": answer.focus,
                "actions": answer.actions,
            },
            "sources": answer.sources,
        }
    body = answer_body(answer) if isinstance(answer, VerifiedMetricAnswer) else query_body(*answer)
    return {**body, "presentation": _presentation(question, answer, follow_ups)}


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/query")
async def query(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: MetricQueryInput,
    actor: Actor,
    service: Service,
) -> object:
    result, lineage = await service.run_query(
        actor, workspace_id, dataset_id, upload_id, body.request()
    )
    return query_body(result, lineage)


async def _wait_for_disconnect(request: Request, finished: asyncio.Event) -> None:
    while not finished.is_set():
        if await request.is_disconnected() or finished.is_set():
            return
        await asyncio.sleep(_DISCONNECT_POLL_SECONDS)


async def _unless_disconnected(request: Request, work: Coroutine[Any, Any, T]) -> T | Response:
    finished = asyncio.Event()
    computation = asyncio.create_task(work)
    disconnected = asyncio.create_task(_wait_for_disconnect(request, finished))
    try:
        completed, _ = await asyncio.wait(
            (computation, disconnected), return_when=asyncio.FIRST_COMPLETED
        )
        if computation in completed:
            return await computation
        await disconnected
        return Response(status_code=499)
    finally:
        finished.set()
        for task in (computation, disconnected):
            if not task.done():
                task.cancel()
        await asyncio.gather(computation, disconnected, return_exceptions=True)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/discovery")
async def discovery(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    actor: Actor,
    service: Service,
    request: Request,
) -> object:
    if await request.is_disconnected():
        return Response(status_code=499)
    brief = await _unless_disconnected(
        request,
        discover(
            service,
            actor,
            workspace_id,
            dataset_id,
            upload_id,
            patterns=request.app.state.runtime.intent_router.patterns,
        ),
    )
    if isinstance(brief, Response):
        return brief
    return {
        **brief.metadata,
        "findings": [
            {
                "id": finding.id,
                "title": finding.title,
                "text": finding.text,
                "kind": finding.kind,
                "metric": finding.metric,
                "aggregation": finding.aggregation,
                "question": finding.question,
                "query": query_body(finding.result, finding.lineage),
            }
            for finding in brief.findings
        ],
    }


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/analyst-overview")
async def analyst_overview(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    actor: Actor,
    service: Service,
    request: Request,
) -> object:
    if await request.is_disconnected():
        return Response(status_code=499)
    router_service = request.app.state.runtime.intent_router
    with usage_scope(UsageAttribution(workspace_id, actor.id, uuid4(), "summary")):
        return await _unless_disconnected(
            request,
            build_insights(
                service,
                actor,
                workspace_id,
                dataset_id,
                upload_id,
                statistics=router_service.patterns.statistics,
                model=router_service.model,
            ),
        )


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/dashboard")
async def dashboard(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: DashboardInput,
    actor: Actor,
    service: Service,
) -> object:
    summary = await service.dashboard_summary(
        actor, workspace_id, dataset_id, upload_id, metric_filters(body.filters), body.template_id
    )
    return {
        "cards": [_card_body(card) for card in summary.cards],
        "trend": _breakdown_body(summary.trend),
        "breakdown": _breakdown_body(summary.breakdown),
    }


@router.get(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/dashboard-templates"
)
async def dashboard_templates(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    templates = await service.list_dashboard_templates(actor, workspace_id, dataset_id, upload_id)
    return [
        {
            "id": template.id,
            "domain": template.domain.value,
            "name": template.name,
            "description": template.description,
        }
        for template in templates
    ]


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/rows")
async def rows(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: RowsInput,
    actor: Actor,
    service: Service,
) -> object:
    request = RowRequest(
        metric_filters(body.filters),
        extremum=RowExtremum(body.extremum.column, body.extremum.direction)
        if body.extremum
        else None,
    )
    if body.extremum is None:
        result, lineage = await service.drill_down(
            actor, workspace_id, dataset_id, upload_id, request.filters, body.limit
        )
    else:
        result, lineage = await service.query_records(
            actor, workspace_id, dataset_id, upload_id, request, body.limit, "structured:records"
        )
    return query_body(result, lineage)


@router.get("/workspaces/{workspace_id}/queries/{query_id}")
async def query_lineage(
    workspace_id: UUID, query_id: UUID, actor: Actor, service: Service
) -> object:
    lineage = await service.get_lineage(actor, workspace_id, query_id)
    return asdict(lineage)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/kpis")
async def kpis(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    matches = await service.list_kpis(actor, workspace_id, dataset_id, upload_id)
    return [_kpi_body(match) for match in matches]


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/kpis/{kpi_id}")
async def compute_kpi(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    kpi_id: str,
    actor: Actor,
    service: Service,
) -> object:
    answer = await service.compute_kpi(actor, workspace_id, dataset_id, upload_id, kpi_id)
    return answer_body(answer)


@router.get(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/suggested-questions"
)
async def suggested_questions(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    return await service.suggested_questions(actor, workspace_id, dataset_id, upload_id)


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/ask")
async def ask(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: AskInput,
    actor: Actor,
    intent_router: IntentRouter,
) -> object:
    with capture_follow_ups() as follow_ups:
        answer = await intent_router.ask(actor, workspace_id, dataset_id, upload_id, body.question)
    return numerical_answer_body(answer, body.question, tuple(follow_ups.questions))


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/dashboard/summary"
)
async def dashboard_summary_narrative(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: DashboardInput,
    actor: Actor,
    service: Service,
    summaries: Summaries,
) -> object:
    summary = await service.dashboard_summary(
        actor, workspace_id, dataset_id, upload_id, metric_filters(body.filters), body.template_id
    )
    with usage_scope(UsageAttribution(workspace_id, actor.id, uuid4(), "summary")):
        narrative = await summaries.compose(summary)
    await service.record_narrative(
        actor, workspace_id, narrative.evidence_ids, narrative.text, narrative.model_route
    )
    return {"summary": narrative.text, "evidence_ids": narrative.evidence_ids}


@router.post("/workspaces/{workspace_id}/queries/{query_id}/replay")
async def replay_query(
    workspace_id: UUID, query_id: UUID, actor: Actor, service: Service
) -> object:
    result, lineage = await service.replay(actor, workspace_id, query_id)
    return query_body(result, lineage)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/schema")
async def schema_view(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    view = await service.get_view(actor, workspace_id, dataset_id, upload_id)
    return {"columns": [asdict(column) for column in view.columns]}
