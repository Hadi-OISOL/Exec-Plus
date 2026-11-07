"""Use case: Exposes the dataset brief, purpose, private follow-up answers and automatic dashboards.

What it does: Authorizes callers, attributes model usage and serializes dashboard versions.
"""

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.auto_dashboards import AutoDashboardService
from execplus.application.services.dataset_focus import save as save_focus
from execplus.application.services.dataset_purpose import purpose
from execplus.application.usage_context import usage_scope
from execplus.domain.auto_dashboard import AutoDashboard
from execplus.domain.usage_metering import UsageAttribution
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["auto dashboards"])
ROOT = "/workspaces/{workspace_id}"
SOURCE = ROOT + "/datasets/{dataset_id}/uploads/{upload_id}"


def service(request: Request) -> AutoDashboardService:
    value: AutoDashboardService = request.app.state.runtime.auto_dashboards
    return value


Service = Annotated[AutoDashboardService, Depends(service)]


class UpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_number: int = Field(ge=1)
    shared: bool | None = None
    tiles: list[str] | None = Field(default=None, min_length=1, max_length=9)


def body(item: AutoDashboard, actor_id: UUID) -> dict[str, Any]:
    return {
        **item.payload,
        "id": str(item.id),
        "number": item.number,
        "shared": item.shared,
        "owned": item.owner_id == actor_id,
        "created_at": item.created_at.isoformat(),
    }


@router.get(SOURCE + "/dataset-brief")
async def dataset_brief(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, dashboards: Service
) -> object:
    brief, *_ = await dashboards.brief(actor, workspace_id, dataset_id, upload_id)
    return brief


@router.get(ROOT + "/uploads/{upload_id}/dataset-purpose")
async def dataset_purpose(
    workspace_id: UUID, upload_id: UUID, actor: Actor, request: Request
) -> object:
    return await purpose(request.app.state.runtime.analytics, actor, workspace_id, upload_id)


class FocusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, str] = Field(default_factory=dict, max_length=8)
    status: str


@router.put(ROOT + "/uploads/{upload_id}/dataset-focus")
async def dataset_focus(
    workspace_id: UUID, upload_id: UUID, body: FocusInput, actor: Actor, request: Request
) -> object:
    return await save_focus(
        request.app.state.runtime.analytics,
        actor,
        workspace_id,
        upload_id,
        body.answers,
        body.status,
    )


@router.get(SOURCE + "/auto-dashboard")
async def auto_dashboard(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, dashboards: Service
) -> object:
    with usage_scope(UsageAttribution(workspace_id, actor.id, uuid4(), "summary")):
        latest, others = await dashboards.current(actor, workspace_id, dataset_id, upload_id)
    return dict(
        dashboard=body(latest, actor.id),
        shared=[
            dict(id=str(item.id), number=item.number, created_at=item.created_at.isoformat())
            for item in others
        ],
    )


@router.post(SOURCE + "/auto-dashboard/rebuild", status_code=201)
async def rebuild_dashboard(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, dashboards: Service
) -> object:
    with usage_scope(UsageAttribution(workspace_id, actor.id, uuid4(), "summary")):
        item = await dashboards.build(actor, workspace_id, dataset_id, upload_id)
    return body(item, actor.id)


@router.get(ROOT + "/auto-dashboards/{dashboard_id}")
async def open_dashboard(
    workspace_id: UUID, dashboard_id: UUID, actor: Actor, dashboards: Service
) -> object:
    return body(dashboards.open(actor, workspace_id, dashboard_id), actor.id)


@router.patch(ROOT + "/auto-dashboards/{dashboard_id}")
async def update_dashboard(
    workspace_id: UUID, dashboard_id: UUID, update: UpdateInput, actor: Actor, dashboards: Service
) -> object:
    item = await dashboards.update(
        actor, workspace_id, dashboard_id, update.expected_number, update.shared, update.tiles
    )
    return body(item, actor.id)
