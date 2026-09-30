"""Use case: Exposes staged refresh, descriptive monitoring and private in-app alerts.

What it does: Validates bounded inputs and serializes exact query evidence for workspace members.
"""

import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import Field, ValidationError

from execplus.application.services.monitoring import MonitoringService
from execplus.application.services.refresh import RefreshService, editor
from execplus.domain.ingestion import IngestionError
from execplus.presentation.routes.analytics import query_body
from execplus.presentation.routes.studies import Input
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["refresh and alerts"])
ROOT = "/workspaces/{workspace_id}"
DATA = ROOT + "/datasets/{dataset_id}"


def refresh_service(request: Request) -> RefreshService:
    value: RefreshService = request.app.state.runtime.refresh
    return value


def monitoring_service(request: Request) -> MonitoringService:
    value: MonitoringService = request.app.state.runtime.monitoring
    return value


Refresh = Annotated[RefreshService, Depends(refresh_service)]
Monitoring = Annotated[MonitoringService, Depends(monitoring_service)]


class Dates(Input):
    as_of: datetime
    coverage_start: date | None = None
    coverage_end: date | None = None


class ConfigInput(Dates):
    upload_id: UUID
    revision_id: UUID
    understanding_id: UUID
    expected_version: int = Field(ge=0)
    interval_hours: int = Field(default=24, ge=1, le=8760)
    freshness_hours: int = Field(default=48, ge=1, le=8760)
    enabled: bool = False


class StageInput(Dates):
    request_id: UUID
    expected_version: int = Field(ge=1)
    mode: str = Field(max_length=10)
    keys: list[str] = Field(default_factory=list, max_length=4)
    duplicates: str = Field(max_length=20)


class ReviewInput(Input):
    definition: dict[str, Any] | None = None
    reject: bool = False


class MonitorInput(Input):
    name: str = Field(min_length=1, max_length=100)
    method: dict[str, Any]
    relevance: int = Field(default=3, ge=1, le=5)
    date_column: str | None = Field(default=None, max_length=100)
    segment: str | None = Field(default=None, max_length=100)


class AlertInput(Input):
    operator: str = Field(max_length=5)
    threshold: str = Field(max_length=100)
    cooldown_minutes: int = Field(default=60, ge=1, le=10080)


@router.get(DATA + "/refresh")
async def overview(workspace_id: UUID, dataset_id: UUID, actor: Actor, refresh: Refresh) -> object:
    return refresh.overview(actor, workspace_id, dataset_id)


@router.put(DATA + "/refresh")
async def configure(
    workspace_id: UUID, dataset_id: UUID, body: ConfigInput, actor: Actor, refresh: Refresh
) -> object:
    data = body.model_dump()
    uid = data.pop("upload_id")
    return asdict(refresh.configure(actor, workspace_id, dataset_id, uid, **data))


@router.post(DATA + "/refresh/candidates", status_code=201)
async def stage(
    workspace_id: UUID,
    dataset_id: UUID,
    actor: Actor,
    refresh: Refresh,
    options: Annotated[str, Form(max_length=5000)],
    file: Annotated[UploadFile, File()],
) -> object:
    with refresh.uow() as repo:
        editor(repo, actor, workspace_id, dataset_id)
    try:
        body = StageInput.model_validate(json.loads(options))
    except (ValueError, ValidationError) as exc:
        raise IngestionError("invalid_refresh", "Invalid refresh options.", 422) from exc
    content = await file.read(refresh.uploads.max_upload_bytes + 1)
    if len(content) > refresh.uploads.max_upload_bytes:
        raise IngestionError("file_too_large", "Files must be at most 20 MiB.", 413)
    return asdict(
        refresh.stage(
            actor,
            workspace_id,
            dataset_id,
            filename=file.filename or "",
            content_type=file.content_type or "application/octet-stream",
            content=content,
            **body.model_dump(),
        )
    )


@router.post(ROOT + "/refresh-candidates/{candidate_id}/review")
async def review(
    workspace_id: UUID, candidate_id: UUID, body: ReviewInput, actor: Actor, refresh: Refresh
) -> object:
    return asdict(refresh.review(actor, workspace_id, candidate_id, body.definition, body.reject))


@router.post(ROOT + "/refresh-candidates/{candidate_id}/activate")
async def activate(
    workspace_id: UUID, candidate_id: UUID, actor: Actor, refresh: Refresh
) -> object:
    return asdict(refresh.activate(actor, workspace_id, candidate_id))


@router.get(DATA + "/monitors")
async def monitors(
    workspace_id: UUID, dataset_id: UUID, actor: Actor, monitoring: Monitoring
) -> object:
    return monitoring.list_monitors(actor, workspace_id, dataset_id)


@router.post(DATA + "/monitors", status_code=201)
async def create_monitor(
    workspace_id: UUID, dataset_id: UUID, body: MonitorInput, actor: Actor, monitoring: Monitoring
) -> object:
    return asdict(monitoring.create(actor, workspace_id, dataset_id, **body.model_dump()))


@router.delete(ROOT + "/monitors/{monitor_id}", status_code=204)
async def disable_monitor(
    workspace_id: UUID, monitor_id: UUID, actor: Actor, monitoring: Monitoring
) -> None:
    monitoring.disable(actor, workspace_id, monitor_id)


@router.post(DATA + "/observations/process")
async def process_observations(
    workspace_id: UUID, dataset_id: UUID, actor: Actor, monitoring: Monitoring
) -> object:
    with monitoring.uow() as repo:
        editor(repo, actor, workspace_id, dataset_id)
    return await monitoring.process(workspace_id=workspace_id, dataset_id=dataset_id)


@router.get(DATA + "/observations")
async def observations(
    workspace_id: UUID, dataset_id: UUID, actor: Actor, monitoring: Monitoring
) -> object:
    return await monitoring.ranked(actor, workspace_id, dataset_id)


@router.get(ROOT + "/observations/{observation_id}")
async def open_observation(
    workspace_id: UUID, observation_id: UUID, actor: Actor, monitoring: Monitoring
) -> object:
    value, results = await monitoring.open(actor, workspace_id, observation_id)
    return {**value, "results": {key: query_body(*result) for key, result in results.items()}}


@router.post(ROOT + "/monitors/{monitor_id}/alerts", status_code=201)
async def subscribe(
    workspace_id: UUID, monitor_id: UUID, body: AlertInput, actor: Actor, monitoring: Monitoring
) -> object:
    return asdict(monitoring.subscribe(actor, workspace_id, monitor_id, **body.model_dump()))


@router.delete(ROOT + "/alerts/{rule_id}", status_code=204)
async def unsubscribe(
    workspace_id: UUID, rule_id: UUID, actor: Actor, monitoring: Monitoring
) -> None:
    monitoring.unsubscribe(actor, workspace_id, rule_id)


@router.post(ROOT + "/alert-events/{event_id}/read", status_code=204)
async def read(workspace_id: UUID, event_id: UUID, actor: Actor, monitoring: Monitoring) -> None:
    monitoring.read(actor, workspace_id, event_id)
