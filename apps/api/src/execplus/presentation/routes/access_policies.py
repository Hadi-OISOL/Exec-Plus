"""Use case: Exposes explicit owner-managed row and column access policies.

What it does: Validates bounded grants and keeps ordinary actor scope separate from management.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.access_policies import AccessPolicyService
from execplus.application.services.dataset_access import dataset_access
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["dataset-access"])


def get_service(request: Request) -> AccessPolicyService:
    service: AccessPolicyService = request.app.state.runtime.access_policies
    return service


Service = Annotated[AccessPolicyService, Depends(get_service)]


class RowCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str = Field(min_length=1, max_length=200)
    operator: str = Field(max_length=5)
    value: str = Field(min_length=1, max_length=200)


class UserGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    columns: list[str] | None = Field(default=None, max_length=1000)
    conditions: list[RowCondition] = Field(default_factory=list, max_length=12)


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, strict=True)
    enabled: bool = Field(strict=True)
    grants: list[UserGrant] = Field(default_factory=list, max_length=50)


@router.get("/workspaces/{workspace_id}/dataset-access")
def catalog(workspace_id: UUID, actor: Actor, service: Service) -> object:
    return {"datasets": service.catalog(actor, workspace_id)}


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/access-policy")
def overview(workspace_id: UUID, dataset_id: UUID, actor: Actor, service: Service) -> object:
    return service.overview(actor, workspace_id, dataset_id)


@router.put("/workspaces/{workspace_id}/datasets/{dataset_id}/access-policy")
def save(
    workspace_id: UUID, dataset_id: UUID, body: PolicyInput, actor: Actor, service: Service
) -> object:
    return service.save(
        actor,
        workspace_id,
        dataset_id,
        body.expected_version,
        body.enabled,
        [grant.model_dump(mode="json") for grant in body.grants],
    )


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/access-scope")
def scope(workspace_id: UUID, dataset_id: UUID, actor: Actor, service: Service) -> object:
    with service.uow() as repo:
        access = dataset_access(repo, actor, workspace_id, dataset_id)
        return {
            "restricted": access.restricted,
            "policy_version": access.policy.version if access.policy else 0,
            "notice": (
                "You can use only the rows and fields shared with you. "
                "Original files and shared source edits are unavailable."
            )
            if access.restricted
            else "",
        }
