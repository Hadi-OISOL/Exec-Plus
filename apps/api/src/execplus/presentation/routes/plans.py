"""Use case: Exposes local plan controls and protected allowance summaries.

What it does: Validates exact administrator assignments without payment services.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from execplus.application.services.plans import PlanService
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["local-plans"])


def service(request: Request) -> PlanService:
    value: PlanService = request.app.state.runtime.plans
    return value


Service = Annotated[PlanService, Depends(service)]


class CatalogInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, strict=True)
    name: str = Field(min_length=1, max_length=100)
    limits: dict[str, StrictInt | None]


class AssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, strict=True)
    plan_key: str = Field(min_length=1, max_length=40)
    starts_at: datetime
    ends_at: datetime


@router.get("/plans")
def catalog(actor: Actor, plans: Service) -> object:
    return plans.catalog(actor)


@router.put("/admin/plans/{key}")
def configure(key: str, body: CatalogInput, actor: Actor, plans: Service) -> object:
    return plans.configure(actor, key, body.name, body.limits, body.expected_version)


@router.put("/admin/workspaces/{workspace_id}/plan")
def assign(workspace_id: UUID, body: AssignmentInput, actor: Actor, plans: Service) -> object:
    return plans.assign(
        actor, workspace_id, body.plan_key, body.expected_version, body.starts_at, body.ends_at
    )


@router.get("/workspaces/{workspace_id}/plan")
def summary(workspace_id: UUID, actor: Actor, plans: Service) -> object:
    return plans.summary(actor, workspace_id)


@router.get("/admin/workspaces/{workspace_id}/plan")
def assigned(workspace_id: UUID, actor: Actor, plans: Service) -> object:
    return plans.assigned(actor, workspace_id)


@router.get("/workspaces/{workspace_id}/usage")
def usage(workspace_id: UUID, actor: Actor, plans: Service) -> object:
    return plans.usage(actor, workspace_id)


@router.get("/admin/usage/workspaces")
def overview(actor: Actor, plans: Service, limit: int = Query(50, ge=1, le=200)) -> object:
    return plans.overview(actor, limit)
