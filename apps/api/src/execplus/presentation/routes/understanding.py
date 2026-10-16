"""Use case: Exposes reviewed business definitions and private analysis preferences.

What it does: Validates transport fields and delegates scoped, version-checked changes.
"""

from dataclasses import asdict
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.understanding import UnderstandingService
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["understanding"])


def service(request: Request) -> UnderstandingService:
    result: UnderstandingService = request.app.state.runtime.understanding
    return result


Service = Annotated[UnderstandingService, Depends(service)]


class DefinitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision_id: UUID
    expected_version: int = Field(ge=0, strict=True)
    state: str = Field(max_length=20)
    definition: dict[str, Any]


class PreferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain_hint: str = Field(default="auto", max_length=20)
    goal: str = Field(default="", max_length=500)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/understanding")
async def overview(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    return service.overview(actor, workspace_id, dataset_id, upload_id)


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/understanding",
    status_code=201,
)
async def save(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: DefinitionInput,
    actor: Actor,
    service: Service,
) -> object:
    return asdict(
        service.save(
            actor,
            workspace_id,
            dataset_id,
            upload_id,
            body.revision_id,
            body.expected_version,
            body.state,
            body.definition,
        )
    )


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/preferences")
async def preference(
    workspace_id: UUID, dataset_id: UUID, body: PreferenceInput, actor: Actor, service: Service
) -> object:
    return asdict(service.preference(actor, workspace_id, dataset_id, body.domain_hint, body.goal))


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/understandings/{understanding_id}")
async def version(
    workspace_id: UUID, dataset_id: UUID, understanding_id: UUID, actor: Actor, service: Service
) -> object:
    return asdict(service.version(actor, workspace_id, dataset_id, understanding_id))


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, strict=True)
    role: str = Field(default="", max_length=300)
    focus: str = Field(default="", max_length=500)
    explanation_style: Literal["concise", "step_by_step"] = "concise"


@router.get("/workspaces/{workspace_id}/agent-memory")
async def memory(workspace_id: UUID, actor: Actor, service: Service) -> object:
    return asdict(service.memory(actor, workspace_id))


@router.put("/workspaces/{workspace_id}/agent-memory")
async def save_memory(
    workspace_id: UUID, body: MemoryInput, actor: Actor, service: Service
) -> object:
    return asdict(
        service.save_memory(
            actor,
            workspace_id,
            body.expected_version,
            body.role,
            body.focus,
            body.explanation_style,
        )
    )


@router.delete("/workspaces/{workspace_id}/agent-memory")
async def forget_memory(
    workspace_id: UUID,
    actor: Actor,
    service: Service,
    expected_version: Annotated[int, Query(ge=0)],
) -> object:
    return asdict(service.save_memory(actor, workspace_id, expected_version, forget=True))
