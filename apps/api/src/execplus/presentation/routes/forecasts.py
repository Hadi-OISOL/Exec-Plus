"""Use case: Exposes private basic forecasts and actual-versus-forecast evidence.

What it does: Validates bounded requests and returns exact actuals separately from estimates.
"""

from dataclasses import asdict
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from execplus.application.services.forecasts import ForecastService
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["forecasts"])
ROOT = "/workspaces/{workspace_id}/datasets/{dataset_id}"
SOURCE = ROOT + "/uploads/{upload_id}/forecasts"
RUNS = ROOT + "/forecasts"


def service(request: Request) -> ForecastService:
    value: ForecastService = request.app.state.runtime.forecasts
    return value


Service = Annotated[ForecastService, Depends(service)]


class CoverageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision_id: UUID
    understanding_id: UUID
    coverage_start: str = Field(min_length=10, max_length=10)
    coverage_end: str = Field(min_length=10, max_length=10)
    coverage_confirmed: Literal[True]


DateText = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class PredictorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str = Field(min_length=1, max_length=200)
    aggregation: Literal["sum", "avg"] = "avg"
    future_values: list[
        Annotated[str, Field(min_length=1, max_length=40, pattern=r"^-?\d+(\.\d+)?$")]
    ] = Field(min_length=1, max_length=30)


class ForecastInput(CoverageInput):
    name: str = Field(min_length=1, max_length=100)
    time_column: str = Field(min_length=1, max_length=200)
    metric: str = Field(min_length=1, max_length=200)
    aggregation: Literal["sum", "avg", "min", "max", "count"]
    filters: list[dict[str, Any]] = Field(default_factory=list, max_length=18)
    frequency: Literal["daily", "monthly"]
    horizon: int = Field(ge=1, le=30, strict=True)
    season_length: int | None = Field(default=None, ge=1, le=12, strict=True)
    engine: Literal["basic-v1", "advanced-v2", "advanced-v3", "advanced-v4", "advanced-v5"] = (
        "basic-v1"
    )
    method_family: Literal[
        "auto", "simple_exponential", "holt", "damped_holt", "holt_winters_additive"
    ] = "auto"
    event_column: str | None = Field(default=None, min_length=1, max_length=200)
    future_event_periods: list[DateText] = Field(default_factory=list, max_length=30)
    holiday_dates: list[DateText] = Field(default_factory=list, max_length=400)
    holiday_calendar: Literal["pk-public-fixed-v1"] | None = None
    predictors: list[PredictorInput] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def compatible_engine(self) -> "ForecastInput":
        if (self.event_column or self.future_event_periods) and self.engine not in {
            "advanced-v4",
            "advanced-v5",
        }:
            raise ValueError("Event columns require the calendar-effects engine.")
        declared = bool(self.holiday_dates or self.holiday_calendar or self.predictors)
        if declared != (self.engine == "advanced-v5"):
            raise ValueError("Declared holidays or predictors need the declared-regressors engine.")
        if any(len(item.future_values) != self.horizon for item in self.predictors):
            raise ValueError("Give one future predictor value per forecast period.")
        if self.future_event_periods and not self.event_column:
            raise ValueError("Choose the event column before future event periods.")
        if self.engine == "basic-v1" and self.method_family != "auto":
            raise ValueError("Specific smoothing methods require the advanced engine.")
        if self.method_family == "holt_winters_additive" and self.season_length is None:
            raise ValueError("Declare the seasonal cycle for this method.")
        return self


class ComparisonInput(CoverageInput):
    upload_id: UUID


@router.get(SOURCE + "/options")
async def options(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, forecasts: Service
) -> object:
    return await forecasts.options(actor, workspace_id, dataset_id, upload_id)


@router.post(SOURCE, status_code=201)
async def create(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: ForecastInput,
    actor: Actor,
    forecasts: Service,
) -> object:
    raw = body.model_dump(mode="json")
    if body.engine == "basic-v1":
        raw.pop("engine")
        raw.pop("method_family")
    if body.event_column is None:
        raw.pop("event_column")
        raw.pop("future_event_periods")
    for key, empty in (("holiday_dates", []), ("holiday_calendar", None), ("predictors", [])):
        if raw[key] == empty:
            raw.pop(key)
    return asdict(await forecasts.create(actor, workspace_id, dataset_id, upload_id, raw))


@router.get(RUNS)
def list_forecasts(
    workspace_id: UUID, dataset_id: UUID, actor: Actor, forecasts: Service
) -> object:
    return forecasts.list_forecasts(actor, workspace_id, dataset_id)


@router.get(RUNS + "/{forecast_id}")
async def open_forecast(
    workspace_id: UUID, dataset_id: UUID, forecast_id: UUID, actor: Actor, forecasts: Service
) -> object:
    return asdict(await forecasts.open(actor, workspace_id, dataset_id, forecast_id))


@router.post(RUNS + "/{forecast_id}/compare", status_code=201)
async def compare(
    workspace_id: UUID,
    dataset_id: UUID,
    forecast_id: UUID,
    body: ComparisonInput,
    actor: Actor,
    forecasts: Service,
) -> object:
    return asdict(
        await forecasts.compare(
            actor, workspace_id, dataset_id, forecast_id, body.model_dump(mode="json")
        )
    )


@router.get(RUNS + "/{forecast_id}/comparisons")
def comparisons(
    workspace_id: UUID, dataset_id: UUID, forecast_id: UUID, actor: Actor, forecasts: Service
) -> object:
    return forecasts.comparisons(actor, workspace_id, dataset_id, forecast_id)


@router.get(RUNS + "/{forecast_id}/comparisons/{comparison_id}")
async def open_comparison(
    workspace_id: UUID,
    dataset_id: UUID,
    forecast_id: UUID,
    comparison_id: UUID,
    actor: Actor,
    forecasts: Service,
) -> object:
    return asdict(
        await forecasts.open_comparison(actor, workspace_id, dataset_id, forecast_id, comparison_id)
    )
