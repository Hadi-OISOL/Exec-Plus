"""Use case: Exposes private anomaly findings, allocation recommendations and human reviews.

What it does: Validates exact bounded inputs and preserves source/owner-scoped evidence responses.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from execplus.application.services.decision_analysis import DecisionAnalysisService
from execplus.presentation.routes.analytics import FilterInput
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["decision analysis"])
ROOT = "/workspaces/{workspace_id}/datasets/{dataset_id}"
SOURCE = ROOT + "/uploads/{upload_id}/decision-analysis"
RUNS = ROOT + "/decision-analysis"


def service(request: Request) -> DecisionAnalysisService:
    value: DecisionAnalysisService = request.app.state.runtime.decision_analysis
    return value


Service = Annotated[DecisionAnalysisService, Depends(service)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceInput(Input):
    name: str = Field(min_length=1, max_length=100)
    revision_id: UUID
    understanding_id: UUID
    filters: list[FilterInput] = Field(default_factory=list, max_length=20)


class AnomalyInput(SourceInput):
    kind: Literal["robust_distribution"] = "robust_distribution"
    metric: str = Field(min_length=1, max_length=200)
    threshold: str = Field(default="3.5", min_length=1, max_length=50)
    materiality: str = Field(default="0", min_length=1, max_length=100)
    segment_column: str | None = Field(default=None, min_length=1, max_length=200)
    minimum_segment_size: int = Field(default=8, ge=8, le=1000, strict=True)


class QuantityBound(Input):
    candidate: str = Field(min_length=1, max_length=200)
    minimum: int = Field(ge=0, le=10, strict=True)
    maximum: int = Field(ge=0, le=10, strict=True)


class Prerequisite(Input):
    candidate: str = Field(min_length=1, max_length=200)
    requires: str = Field(min_length=1, max_length=200)


class Exclusion(Input):
    first: str = Field(min_length=1, max_length=200)
    second: str = Field(min_length=1, max_length=200)


class AllocationInput(SourceInput):
    kind: Literal["bounded_allocation"] = "bounded_allocation"
    entity_column: str = Field(min_length=1, max_length=200)
    cost_column: str = Field(min_length=1, max_length=200)
    benefit_column: str = Field(min_length=1, max_length=200)
    budget: str = Field(min_length=1, max_length=100)
    quantum: str = Field(min_length=1, max_length=100)
    maximum_quantity: int = Field(default=1, ge=0, le=10, strict=True)
    bounds: list[QuantityBound] = Field(default_factory=list, max_length=20)
    assumptions_confirmed: Literal[True]
    resource_column: str | None = Field(default=None, min_length=1, max_length=200)
    resource_capacity: str | None = Field(default=None, min_length=1, max_length=100)
    prerequisites: list[Prerequisite] = Field(default_factory=list, max_length=40)
    exclusions: list[Exclusion] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def paired_resource(self) -> "AllocationInput":
        if (self.resource_column is None) != (self.resource_capacity is None):
            raise ValueError("Declare both the resource column and its capacity.")
        return self


class ReviewInput(Input):
    target: str = Field(min_length=1, max_length=32)
    status: Literal[
        "pending", "approved", "rejected", "expected", "investigate", "data_issue", "dismissed"
    ]
    note: str = Field(min_length=1, max_length=1000)
    expected_version: int = Field(ge=0, le=200, strict=True)


class ScenarioAlternative(Input):
    name: str = Field(min_length=1, max_length=100)
    operation: Literal["replace", "percent_change"]
    value: str = Field(min_length=1, max_length=100)


class ScenarioDriver(Input):
    name: str = Field(min_length=1, max_length=100)
    percent_change: str = Field(min_length=1, max_length=100)


class CompoundAlternative(Input):
    name: str = Field(min_length=1, max_length=100)
    operation: Literal["compound_percent"]
    drivers: list[ScenarioDriver] = Field(min_length=1, max_length=3)


class DailyAlternative(Input):
    name: str = Field(min_length=1, max_length=100)
    operation: Literal["daily_change"]
    daily_change: str = Field(min_length=1, max_length=100)
    days: int = Field(ge=1, le=3650, strict=True)


class ScenarioInput(SourceInput):
    kind: Literal["scenario_comparison"] = "scenario_comparison"
    metric: str = Field(min_length=1, max_length=200)
    aggregation: Literal["sum", "avg"]
    alternatives: list[
        Annotated[
            ScenarioAlternative | CompoundAlternative | DailyAlternative,
            Field(discriminator="operation"),
        ]
    ] = Field(min_length=1, max_length=5)
    assumptions_confirmed: bool = Field(strict=True)
    parent_run_id: UUID | None = None


@router.post(SOURCE + "/scenarios", status_code=201)
async def scenarios(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: ScenarioInput,
    actor: Actor,
    analyses: Service,
) -> object:
    return await analyses.create(
        actor, workspace_id, dataset_id, upload_id, body.model_dump(mode="json")
    )


@router.get(SOURCE + "/options")
async def options(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, analyses: Service
) -> object:
    return await analyses.options(actor, workspace_id, dataset_id, upload_id)


@router.post(SOURCE + "/anomalies", status_code=201)
async def anomalies(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: AnomalyInput,
    actor: Actor,
    analyses: Service,
) -> object:
    return await analyses.create(
        actor, workspace_id, dataset_id, upload_id, body.model_dump(mode="json")
    )


@router.post(SOURCE + "/allocations", status_code=201)
async def allocations(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: AllocationInput,
    actor: Actor,
    analyses: Service,
) -> object:
    raw = body.model_dump(mode="json")
    if not body.prerequisites and not body.exclusions:
        # New optional defaults must not alter the retained legacy request contract.
        raw.pop("prerequisites")
        raw.pop("exclusions")
    return await analyses.create(actor, workspace_id, dataset_id, upload_id, raw)


@router.get(RUNS)
def list_runs(workspace_id: UUID, dataset_id: UUID, actor: Actor, analyses: Service) -> object:
    return analyses.list(actor, workspace_id, dataset_id)


@router.get(RUNS + "/{run_id}")
async def open_run(
    workspace_id: UUID, dataset_id: UUID, run_id: UUID, actor: Actor, analyses: Service
) -> object:
    return await analyses.open(actor, workspace_id, dataset_id, run_id)


@router.post(RUNS + "/{run_id}/reviews", status_code=201)
async def review(
    workspace_id: UUID,
    dataset_id: UUID,
    run_id: UUID,
    body: ReviewInput,
    actor: Actor,
    analyses: Service,
) -> object:
    return await analyses.review(
        actor, workspace_id, dataset_id, run_id, body.model_dump(mode="json")
    )
