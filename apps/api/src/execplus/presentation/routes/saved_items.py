"""Use case: Exposes saved questions, prompts, and dashboard configurations.

What it does: Maps validated requests to SavedItemService, enforcing that a
private saved item stays invisible until its owner explicitly shares it.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from execplus.application.services.saved_items import SavedItemService
from execplus.domain.ingestion import IngestionError
from execplus.domain.saved_items import SavedItem
from execplus.presentation.routes.analytics import (
    DashboardInput,
    IntentRouter,
    MetricQueryInput,
    dashboard,
    numerical_answer_body,
    query_body,
)
from execplus.presentation.routes.analytics import Service as Analytics
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["saved-items"])


def get_saved_item_service(request: Request) -> SavedItemService:
    service: SavedItemService = request.app.state.runtime.saved_items
    return service


Service = Annotated[SavedItemService, Depends(get_saved_item_service)]


class SavedItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(question|prompt|dashboard|analysis)$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)
    shared: bool = False

    @model_validator(mode="after")
    def validate_configuration(self) -> "SavedItemInput":
        if self.kind == "dashboard":
            DashboardInput.model_validate(self.payload)
        elif self.kind == "analysis":
            if set(self.payload) != {"query_id"}:
                raise ValueError("Analysis requires a query ID")
            UUID(str(self.payload["query_id"]))
        elif "question" in self.payload or self.kind == "prompt":
            question = self.payload.get("question")
            if (
                set(self.payload) != {"question"}
                or not isinstance(question, str)
                or not 1 <= len(question.strip()) <= 500
            ):
                raise ValueError("Provide one bounded question")
        else:
            MetricQueryInput.model_validate(self.payload)
        return self


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


@router.post("/workspaces/{workspace_id}/saved-items/{item_id}/run")
async def run_saved_item(
    workspace_id: UUID,
    item_id: UUID,
    actor: Actor,
    service: Service,
    analytics: Analytics,
    intent_router: IntentRouter,
) -> object:
    item = await service.get_item(actor, workspace_id, item_id)
    if item.kind == "analysis":
        result, lineage = await analytics.replay(
            actor, workspace_id, UUID(str(item.payload["query_id"]))
        )
        return query_body(result, lineage)
    if item.kind in {"question", "prompt"}:
        if "question" in item.payload:
            answer = await intent_router.ask(
                actor, workspace_id, item.dataset_id, item.upload_id, str(item.payload["question"])
            )
            return numerical_answer_body(answer)
        try:
            body = MetricQueryInput.model_validate(item.payload)
        except ValueError:
            raise IngestionError(
                "invalid_saved_item", "The saved query configuration is invalid.", 422
            ) from None
        result, lineage = await analytics.run_query(
            actor, workspace_id, item.dataset_id, item.upload_id, body.request()
        )
        return query_body(result, lineage)
    try:
        body_dashboard = DashboardInput.model_validate(item.payload)
    except ValueError:
        raise IngestionError(
            "invalid_saved_item", "The saved dashboard configuration is invalid.", 422
        ) from None
    return await dashboard(
        workspace_id, item.dataset_id, item.upload_id, body_dashboard, actor, analytics
    )
