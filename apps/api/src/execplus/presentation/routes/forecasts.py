"""Use case: Exposes private basic forecasts and actual-versus-forecast evidence.

What it does: Validates bounded requests and returns exact actuals separately from estimates.
"""

from dataclasses import asdict
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

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


class ForecastInput(CoverageInput):
    name: str = Field(min_length=1, max_length=100)
    time_column: str = Field(min_length=1, max_length=200)
    metric: str = Field(min_length=1, max_length=200)
    aggregation: Literal["sum", "avg", "min", "max", "count"]
    filters: list[dict[str, Any]] = Field(default_factory=list, max_length=18)
    frequency: Literal["daily", "monthly"]
    horizon: int = Field(ge=1, le=30, strict=True)
    season_length: int | None = Field(default=None, ge=1, le=12, strict=True)


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
    return asdict(
        await forecasts.create(
            actor, workspace_id, dataset_id, upload_id, body.model_dump(mode="json")
        )
    )


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
