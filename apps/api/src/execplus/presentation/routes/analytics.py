"""Use case: Exposes authenticated, structured metric query HTTP contracts.

What it does: Maps validated requests to AnalyticsService and returns executed
results alongside their calculation lineage.
"""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.analytics import (
    AnalyticsService,
    DashboardBreakdown,
    DashboardCard,
)
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.summaries import SummaryService
from execplus.domain.kpi_library import KpiMatch
from execplus.domain.models import CalculationLineage, QueryResult, VerifiedMetricAnswer
from execplus.domain.semantics import AggregationKind, FilterOperator, MetricFilter, MetricRequest
from execplus.presentation.routes.workspaces import Actor

_MAX_DRILL_DOWN_ROWS = 1000

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


class RowsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: list[FilterInput] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=100, ge=1, le=_MAX_DRILL_DOWN_ROWS)


class AskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)


def query_body(result: QueryResult, lineage: CalculationLineage) -> dict[str, object]:
    return {
        "columns": result.columns,
        "rows": result.rows,
        "records_analyzed": result.records_analyzed,
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
    return {"label": answer.label, "value": answer.value, "lineage": asdict(answer.lineage)}


def numerical_answer_body(
    answer: VerifiedMetricAnswer | tuple[QueryResult, CalculationLineage],
) -> dict[str, object]:
    if isinstance(answer, VerifiedMetricAnswer):
        return answer_body(answer)
    result, lineage = answer
    return query_body(result, lineage)


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
    result, lineage = await service.drill_down(
        actor, workspace_id, dataset_id, upload_id, metric_filters(body.filters), body.limit
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
    answer = await intent_router.ask(actor, workspace_id, dataset_id, upload_id, body.question)
    return numerical_answer_body(answer)


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
    return {"summary": await summaries.summarize(summary)}
