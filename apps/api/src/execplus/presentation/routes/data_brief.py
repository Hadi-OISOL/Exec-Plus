"""Use case: Exposes the plain-language reading of an upload that its owner is asked to confirm.

What it does: Authorizes the caller and delegates a draft that never saves meaning by itself.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from execplus.application.services.data_brief import DataBriefService
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["data brief"])


def service(request: Request) -> DataBriefService:
    result: DataBriefService = request.app.state.runtime.data_brief
    return result


Service = Annotated[DataBriefService, Depends(service)]


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/data-brief")
async def draft(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    return await service.draft(actor, workspace_id, dataset_id, upload_id)
