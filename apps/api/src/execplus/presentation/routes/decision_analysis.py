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
    target_false_alarm_rate: Literal["0.05", "0.01", "0.005"] | None = None

    @model_validator(mode="after")
    def calibrated_threshold(self) -> "AnomalyInput":
        if self.target_false_alarm_rate and self.threshold != "3.5":
            raise ValueError("A false-alarm target sets the threshold.")
        return self


class MultivariateInput(SourceInput):
    kind: Literal["robust_distribution"] = "robust_distribution"
    model: Literal["reference-mahalanobis-squared-v1"] = "reference-mahalanobis-squared-v1"
    metrics: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        min_length=2, max_length=4
    )
    identifier_column: str = Field(min_length=1, max_length=200)
    cohort_column: str = Field(min_length=1, max_length=200)
    reference_label: str = Field(min_length=1, max_length=200)
    comparison_label: str = Field(min_length=1, max_length=200)
    threshold: str = Field(default="9", min_length=1, max_length=50)


class CalendarInput(SourceInput):
    kind: Literal["robust_distribution"] = "robust_distribution"
    metric: str = Field(min_length=1, max_length=200)
    aggregation: Literal["sum", "avg"]
    time_column: str = Field(min_length=1, max_length=200)
    frequency: Literal["daily", "monthly"]
    coverage_confirmed: bool = Field(strict=True)
    materiality: str = Field(min_length=1, max_length=100)


class CalibratedCalendar(CalendarInput):
    model: str
    threshold: str
    target_false_alarm_rate: Literal["0.05", "0.01", "0.005"] | None = None

    @model_validator(mode="after")
    def calibrated_model(self) -> "CalibratedCalendar":
        calibrated = self.model.endswith("-calibrated-v1")
        if calibrated != (self.target_false_alarm_rate is not None) or (
            calibrated and self.threshold != "3.5"
        ):
            raise ValueError("A calibrated method needs a target and sets the threshold.")
        return self


def calendar_raw(body: CalibratedCalendar) -> dict[str, object]:
    raw = body.model_dump(mode="json")
    if body.target_false_alarm_rate is None:
        raw.pop("target_false_alarm_rate")
    return raw


class SeasonalAnomalyInput(CalibratedCalendar):
    model: Literal["seasonal-residual-mad-iqr-v1", "seasonal-residual-mad-iqr-calibrated-v1"] = (
        "seasonal-residual-mad-iqr-v1"
    )
    coverage_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    coverage_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    training_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    season_length: int = Field(ge=7, le=12, strict=True)
    threshold: str = Field(default="3.5", min_length=1, max_length=50)


class RollingAnomalyInput(CalibratedCalendar):
    model: Literal["rolling-reference-mad-iqr-v1", "rolling-reference-mad-iqr-calibrated-v1"] = (
        "rolling-reference-mad-iqr-v1"
    )
    coverage_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    coverage_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    evaluation_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reference_window: int = Field(default=20, ge=20, le=120, strict=True)
    season_length: int = Field(default=1, ge=1, le=12, strict=True)
    threshold: str = Field(default="3.5", min_length=1, max_length=50)


class DriftInput(CalendarInput):
    model: Literal["empirical-window-distance-v1"] = "empirical-window-distance-v1"
    reference_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reference_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    comparison_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    comparison_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    minimum_cdf_separation: str = Field(min_length=1, max_length=100)


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


class LargeQuantityBound(Input):
    candidate: str = Field(min_length=1, max_length=200)
    minimum: int = Field(ge=0, le=100, strict=True)
    maximum: int = Field(ge=0, le=100, strict=True)


class AdditionalResource(Input):
    column: str = Field(min_length=1, max_length=200)
    capacity: str = Field(min_length=1, max_length=100)


class CapacitySensitivity(Input):
    column: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=100)
    capacities: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        min_length=2, max_length=5
    )


class Precedence(Input):
    candidate: str = Field(min_length=1, max_length=200)
    after: str = Field(min_length=1, max_length=200)


class ScheduleInput(Input):
    period_budgets: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        min_length=2, max_length=12
    )
    precedence: list[Precedence] = Field(default_factory=list, max_length=40)


class LargeAllocationInput(SourceInput):
    kind: Literal["bounded_allocation"] = "bounded_allocation"
    model: Literal[
        "cp-sat-integer-allocation-v1",
        "cp-sat-capacity-sensitivity-v2",
        "cp-sat-scheduled-allocation-v1",
    ] = "cp-sat-integer-allocation-v1"
    schedule: ScheduleInput | None = None
    capacity_sensitivity: CapacitySensitivity | None = None
    entity_column: str = Field(min_length=1, max_length=200)
    cost_column: str = Field(min_length=1, max_length=200)
    benefit_column: str = Field(min_length=1, max_length=200)
    budget: str = Field(min_length=1, max_length=100)
    maximum_quantity: int = Field(default=1, ge=0, le=100, strict=True)
    bounds: list[LargeQuantityBound] = Field(default_factory=list, max_length=50)
    assumptions_confirmed: bool = Field(strict=True)
    resources: list[AdditionalResource] = Field(default_factory=list, max_length=3)
    prerequisites: list[Prerequisite] = Field(default_factory=list, max_length=40)
    exclusions: list[Exclusion] = Field(default_factory=list, max_length=40)


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


class SourceAlternative(Input):
    name: str = Field(min_length=1, max_length=100)
    price: str = Field(min_length=1, max_length=100)
    quantity: str = Field(min_length=1, max_length=100)
    variable_cost: str = Field(min_length=1, max_length=100)
    fixed_cost: str = Field(min_length=1, max_length=100)


class SourceSensitivity(Input):
    driver: Literal["price", "quantity", "variable_cost", "fixed_cost"]
    percent_changes: list[str] = Field(min_length=2, max_length=21)


class SourceRange(Input):
    low: str = Field(min_length=1, max_length=100)
    high: str = Field(min_length=1, max_length=100)


class TriangularRange(Input):
    low: str = Field(min_length=1, max_length=100)
    likely: str = Field(min_length=1, max_length=100)
    high: str = Field(min_length=1, max_length=100)


class SimulationTarget(Input):
    field: Literal[
        "quantity",
        "revenue",
        "variable_cost",
        "fixed_cost",
        "total_cost",
        "contribution",
        "remaining",
        "margin_percent",
    ]
    direction: Literal["above", "below"]
    value: str = Field(min_length=1, max_length=100)


class ScenarioSimulation(Input):
    drivers: dict[Literal["price", "quantity", "variable_cost", "fixed_cost"], TriangularRange] = (
        Field(min_length=1, max_length=4)
    )
    draws: int = Field(default=10000, ge=1000, le=10000, strict=True)
    seed: int = Field(default=20261024, ge=0, le=2**32 - 1, strict=True)
    target: SimulationTarget | None = None


class ScenarioConstraint(Input):
    field: Literal[
        "quantity",
        "revenue",
        "variable_cost",
        "fixed_cost",
        "total_cost",
        "contribution",
        "remaining",
        "margin_percent",
    ]
    operator: Literal["minimum", "maximum"]
    value: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=100)


class SourceScenarioInput(SourceInput):
    kind: Literal["scenario_comparison"] = "scenario_comparison"
    model: Literal["source-unit-economics-v1", "source-unit-economics-constrained-v2"] = (
        "source-unit-economics-v1"
    )
    constraints: list[ScenarioConstraint] | None = Field(default=None, min_length=1, max_length=12)
    basis: Literal["per_unit", "row_totals"]
    quantity_column: str = Field(min_length=1, max_length=200)
    sales_column: str = Field(min_length=1, max_length=200)
    cost_column: str = Field(min_length=1, max_length=200)
    fixed_cost_column: str | None = Field(default=None, min_length=1, max_length=200)
    alternatives: list[SourceAlternative] = Field(min_length=1, max_length=5)
    sensitivity: SourceSensitivity | None = None
    ranges: (
        dict[Literal["price", "quantity", "variable_cost", "fixed_cost"], SourceRange] | None
    ) = Field(default=None, min_length=1, max_length=4)
    simulation: ScenarioSimulation | None = None
    assumptions_confirmed: bool = Field(strict=True)
    row_basis_confirmed: bool = Field(strict=True)
    parent_run_id: UUID | None = None


@router.post(SOURCE + "/source-scenarios", status_code=201)
async def source_scenarios(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: SourceScenarioInput,
    actor: Actor,
    analyses: Service,
) -> object:
    raw = body.model_dump(mode="json")
    if body.simulation is None:
        raw.pop("simulation")
    return await analyses.create(actor, workspace_id, dataset_id, upload_id, raw)


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


@router.post(SOURCE + "/unusual-values")
async def unusual_values(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, analyses: Service
) -> object:
    return await analyses.unusual_values(actor, workspace_id, dataset_id, upload_id)


@router.post(SOURCE + "/anomalies", status_code=201)
async def anomalies(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: AnomalyInput,
    actor: Actor,
    analyses: Service,
) -> object:
    raw = body.model_dump(mode="json")
    if body.target_false_alarm_rate is None:
        raw.pop("target_false_alarm_rate")
    return await analyses.create(actor, workspace_id, dataset_id, upload_id, raw)


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


@router.post(SOURCE + "/large-allocations", status_code=201)
async def large_allocations(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: LargeAllocationInput,
    actor: Actor,
    analyses: Service,
) -> object:
    raw = body.model_dump(mode="json")
    if body.schedule is None:
        raw.pop("schedule")
    return await analyses.create(actor, workspace_id, dataset_id, upload_id, raw)


@router.post(SOURCE + "/seasonal-anomalies", status_code=201)
async def seasonal_anomalies(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: SeasonalAnomalyInput,
    actor: Actor,
    analyses: Service,
) -> object:
    return await analyses.create(actor, workspace_id, dataset_id, upload_id, calendar_raw(body))


@router.post(SOURCE + "/multivariate-anomalies", status_code=201)
async def multivariate_anomalies(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: MultivariateInput,
    actor: Actor,
    analyses: Service,
) -> object:
    return await analyses.create(
        actor, workspace_id, dataset_id, upload_id, body.model_dump(mode="json")
    )


@router.post(SOURCE + "/rolling-anomalies", status_code=201)
async def rolling_anomalies(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: RollingAnomalyInput,
    actor: Actor,
    analyses: Service,
) -> object:
    return await analyses.create(actor, workspace_id, dataset_id, upload_id, calendar_raw(body))


@router.post(SOURCE + "/distribution-drift", status_code=201)
async def distribution_drift(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: DriftInput,
    actor: Actor,
    analyses: Service,
) -> object:
    return await analyses.create(
        actor, workspace_id, dataset_id, upload_id, body.model_dump(mode="json")
    )


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
