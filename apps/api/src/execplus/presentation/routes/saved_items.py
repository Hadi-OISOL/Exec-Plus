"""Use case: Exposes saved questions, prompts, and dashboard configurations.

What it does: Maps validated requests to SavedItemService, enforcing that a
private saved item stays invisible until its owner explicitly shares it.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.saved_items import SavedItemService
from execplus.domain.saved_items import SavedItem
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["saved-items"])


def get_saved_item_service(request: Request) -> SavedItemService:
    service: SavedItemService = request.app.state.runtime.saved_items
    return service


Service = Annotated[SavedItemService, Depends(get_saved_item_service)]


class SavedItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(question|prompt|dashboard)$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)
    shared: bool = False


def _saved_item_body(item: SavedItem) -> dict[str, object]:
    return {
        "id": str(item.id),
        "workspace_id": str(item.workspace_id),
        "dataset_id": str(item.dataset_id),
        "upload_id": str(item.upload_id),
        "owner_id": str(item.owner_id),
        "kind": item.kind,
        "name": item.name,
        "description": item.description,
        "payload": item.payload,
        "shared": item.shared,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/saved-items",
    status_code=201,
)
async def create_saved_item(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: SavedItemInput,
    actor: Actor,
    service: Service,
) -> object:
    item = await service.create(
        actor,
        workspace_id,
        dataset_id,
        upload_id,
        body.kind,
        body.name,
        body.description,
        body.payload,
        body.shared,
    )
    return _saved_item_body(item)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/saved-items")
async def list_saved_items(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    items = await service.list_items(actor, workspace_id, dataset_id, upload_id)
    return [_saved_item_body(item) for item in items]


@router.get("/workspaces/{workspace_id}/saved-items/{item_id}")
async def get_saved_item(
    workspace_id: UUID, item_id: UUID, actor: Actor, service: Service
) -> object:
    item = await service.get_item(actor, workspace_id, item_id)
    return _saved_item_body(item)


@router.delete("/workspaces/{workspace_id}/saved-items/{item_id}", status_code=204)
async def delete_saved_item(
    workspace_id: UUID, item_id: UUID, actor: Actor, service: Service
) -> Response:
    await service.delete_item(actor, workspace_id, item_id)
    return Response(status_code=204)
