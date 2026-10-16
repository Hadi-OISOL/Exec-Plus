"""Use case: Downloads source-checked answers, dashboards and analyses.

What it does: Accepts identifiers and format choices only, delegates authorization
and replay, and returns private attachments without public storage URLs.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.result_exports import ResultExportService
from execplus.domain.exports import ExportDownload
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["result-exports"])
ROOT = "/workspaces/{workspace_id}"
Format = Literal["pdf", "xlsx", "csv", "png"]
Chart = Annotated[int, Query(ge=0, le=100)]


def service(request: Request) -> ResultExportService:
    value: ResultExportService = request.app.state.runtime.result_exports
    return value


Service = Annotated[ResultExportService, Depends(service)]


def attachment(value: ExportDownload) -> Response:
    return Response(
        value.content,
        media_type=value.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{value.filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(ROOT + "/threads/{thread_id}/turns/{turn_id}/export.{format}")
async def answer(
    workspace_id: UUID,
    thread_id: UUID,
    turn_id: UUID,
    format: Format,
    actor: Actor,
    exports: Service,
    chart: Chart = 0,
) -> Response:
    return attachment(await exports.thread(actor, workspace_id, thread_id, turn_id, format, chart))


@router.get(ROOT + "/datasets/{dataset_id}/forecasts/{record_id}/export.{format}")
async def forecast(
    workspace_id: UUID,
    dataset_id: UUID,
    record_id: UUID,
    format: Format,
    actor: Actor,
    exports: Service,
    chart: Chart = 0,
) -> Response:
    return attachment(
        await exports.record(actor, workspace_id, "forecast", record_id, dataset_id, format, chart)
    )


@router.get(
    ROOT + "/datasets/{dataset_id}/forecasts/{forecast_id}/comparisons/{record_id}/export.{format}"
)
async def forecast_comparison(
    workspace_id: UUID,
    dataset_id: UUID,
    forecast_id: UUID,
    record_id: UUID,
    format: Format,
    actor: Actor,
    exports: Service,
    chart: Chart = 0,
) -> Response:
    return attachment(
        await exports.record(
            actor,
            workspace_id,
            "forecast_comparison",
            record_id,
            dataset_id,
            format,
            chart,
            forecast_id,
        )
    )


@router.get(ROOT + "/datasets/{dataset_id}/analyses/{record_id}/export.{format}")
async def analysis(
    workspace_id: UUID,
    dataset_id: UUID,
    record_id: UUID,
    format: Format,
    kind: Literal["scenario", "anomaly", "allocation"],
    actor: Actor,
    exports: Service,
    chart: Chart = 0,
) -> Response:
    return attachment(
        await exports.record(actor, workspace_id, kind, record_id, dataset_id, format, chart)
    )


@router.get(ROOT + "/study-versions/{record_id}/export.{format}")
async def study(
    workspace_id: UUID,
    record_id: UUID,
    format: Format,
    actor: Actor,
    exports: Service,
    chart: Chart = 0,
) -> Response:
    return attachment(
        await exports.record(actor, workspace_id, "study", record_id, None, format, chart)
    )


@router.get(ROOT + "/study-boards/{record_id}/export.{format}")
async def board(
    workspace_id: UUID,
    record_id: UUID,
    format: Format,
    actor: Actor,
    exports: Service,
    chart: Chart = 0,
) -> Response:
    return attachment(
        await exports.record(actor, workspace_id, "dashboard", record_id, None, format, chart)
    )


class DashboardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_ids: list[UUID] = Field(min_length=1, max_length=12)
    name: str = Field(default="Current dashboard", min_length=1, max_length=100)
    format: Format
    chart: int = Field(default=0, ge=0, le=100)


@router.post(ROOT + "/exports/dashboard")
async def dashboard(
    workspace_id: UUID, body: DashboardInput, actor: Actor, exports: Service
) -> Response:
    return attachment(
        await exports.dashboard(
            actor, workspace_id, tuple(body.query_ids), body.name, body.format, body.chart
        )
    )
