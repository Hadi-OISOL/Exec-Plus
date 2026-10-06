"""Use case: Exposes separate internal administration and requester support workflows.

What it does: Bounds transport fields and delegates staff, ownership and timeline policy.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.operations import OperationsService
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["operations-support"])
ROOT = "/workspaces/{workspace_id}/support-tickets"
STAFF = "/admin/workspaces/{workspace_id}/support-tickets"
Status = Literal["open", "triaged", "in_progress", "waiting_on_customer", "escalated", "resolved"]


def service(request: Request) -> OperationsService:
    value: OperationsService = request.app.state.runtime.operations
    return value


Service = Annotated[OperationsService, Depends(service)]


class CreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    feature: str = Field(min_length=1, max_length=40)
    category: str = Field(min_length=1, max_length=40)
    feedback_id: UUID | None = None
    job_id: UUID | None = None


class VersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, le=200, strict=True)
    body: str = Field(default="", max_length=4000)


class MessageInput(VersionInput):
    body: str = Field(min_length=1, max_length=4000)


class ChangeInput(VersionInput):
    status: Status | None = None
    priority: Literal["normal", "high"] | None = None
    assignee_id: UUID | None = None


@router.get("/admin/access")
def access(actor: Actor, operations: Service) -> object:
    return operations.access(actor)


@router.get("/admin/staff")
def staff(actor: Actor, operations: Service) -> object:
    return operations.staff(actor)


@router.get("/admin/workspaces")
def workspaces(
    actor: Actor,
    operations: Service,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=200),
    q: str = Query("", max_length=80),
) -> object:
    return operations.workspaces(actor, limit=limit, cursor=cursor, q=q)


@router.get("/admin/workspaces/{workspace_id}")
def workspace(workspace_id: UUID, actor: Actor, operations: Service) -> object:
    return operations.workspace(actor, workspace_id)


@router.get(ROOT)
def tickets(
    workspace_id: UUID,
    actor: Actor,
    operations: Service,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=200),
    status: str = "",
    priority: str = "",
    q: str = Query("", max_length=80),
) -> object:
    return operations.tickets(
        actor, workspace_id, limit=limit, cursor=cursor, status=status, priority=priority, q=q
    )


@router.get("/admin/support-tickets")
def support_queue(
    actor: Actor,
    operations: Service,
    workspace_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=200),
    status: str = "",
    priority: str = "",
    q: str = Query("", max_length=80),
) -> object:
    return operations.tickets(
        actor,
        workspace_id,
        staff=True,
        limit=limit,
        cursor=cursor,
        status=status,
        priority=priority,
        q=q,
    )


@router.post(ROOT, status_code=201)
def create(workspace_id: UUID, actor: Actor, operations: Service, body: CreateInput) -> object:
    return operations.create(actor, workspace_id, body.model_dump())


@router.get(ROOT + "/{ticket_id}")
def detail(workspace_id: UUID, ticket_id: UUID, actor: Actor, operations: Service) -> object:
    return operations.ticket(actor, workspace_id, ticket_id)


@router.get(STAFF + "/{ticket_id}")
def staff_detail(workspace_id: UUID, ticket_id: UUID, actor: Actor, operations: Service) -> object:
    return operations.ticket(actor, workspace_id, ticket_id, staff=True)


@router.post(ROOT + "/{ticket_id}/messages", status_code=201)
def message(
    workspace_id: UUID, ticket_id: UUID, actor: Actor, operations: Service, body: MessageInput
) -> object:
    return operations.change(actor, workspace_id, ticket_id, body.model_dump(), kind="message")


@router.post(STAFF + "/{ticket_id}/messages", status_code=201)
def staff_message(
    workspace_id: UUID, ticket_id: UUID, actor: Actor, operations: Service, body: MessageInput
) -> object:
    return operations.change(
        actor, workspace_id, ticket_id, body.model_dump(), staff=True, kind="message"
    )


@router.patch(STAFF + "/{ticket_id}")
def change(
    workspace_id: UUID, ticket_id: UUID, actor: Actor, operations: Service, body: ChangeInput
) -> object:
    return operations.change(
        actor, workspace_id, ticket_id, body.model_dump(exclude_unset=True), staff=True
    )


@router.post(ROOT + "/{ticket_id}/reopen")
def reopen(
    workspace_id: UUID, ticket_id: UUID, actor: Actor, operations: Service, body: VersionInput
) -> object:
    return operations.change(actor, workspace_id, ticket_id, body.model_dump(), kind="reopened")


@router.post(STAFF + "/{ticket_id}/reopen")
def staff_reopen(
    workspace_id: UUID, ticket_id: UUID, actor: Actor, operations: Service, body: VersionInput
) -> object:
    return operations.change(
        actor, workspace_id, ticket_id, body.model_dump(), staff=True, kind="reopened"
    )
