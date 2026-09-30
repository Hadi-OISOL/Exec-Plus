"""Use case: Exposes authenticated Phase 3 activation and knowledge contracts.

What it does: Bounds transport inputs and delegates authorization to application services.
"""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.activation import ActivationService
from execplus.application.services.knowledge import KnowledgeService
from execplus.application.services.reports import ReportService
from execplus.domain.ingestion import IngestionError
from execplus.domain.knowledge import MAX_DOCUMENT_BYTES
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["activation-knowledge"])


def activation(request: Request) -> ActivationService:
    service: ActivationService = request.app.state.runtime.activation
    return service


def knowledge(request: Request) -> KnowledgeService:
    service: KnowledgeService = request.app.state.runtime.knowledge
    return service


def reports(request: Request) -> ReportService:
    service: ReportService = request.app.state.runtime.reports
    return service


Activation = Annotated[ActivationService, Depends(activation)]
Knowledge = Annotated[KnowledgeService, Depends(knowledge)]
Reports = Annotated[ReportService, Depends(reports)]


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feature: str = Field(max_length=40)
    category: str = Field(max_length=40)
    rating: int = Field(ge=1, le=5)


class ComparisonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_query_id: UUID
    previous_query_id: UUID


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: UUID
    interval_hours: int = Field(ge=1, le=8760)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/insights")
async def insights(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Activation
) -> object:
    return await service.insights(actor, workspace_id, dataset_id, upload_id)


@router.post("/workspaces/{workspace_id}/comparisons")
async def compare(
    workspace_id: UUID, body: ComparisonInput, actor: Actor, service: Activation
) -> object:
    return await service.compare(actor, workspace_id, body.current_query_id, body.previous_query_id)


@router.post("/workspaces/{workspace_id}/feedback", status_code=201)
async def feedback(
    workspace_id: UUID, body: FeedbackInput, actor: Actor, service: Activation
) -> object:
    return asdict(
        await service.feedback(actor, workspace_id, body.feature, body.rating, body.category)
    )


@router.get("/workspaces/{workspace_id}/onboarding")
async def onboarding(workspace_id: UUID, actor: Actor, service: Activation) -> object:
    return await service.overview(actor, workspace_id)


@router.get("/workspaces/{workspace_id}/usage-analytics")
async def usage(workspace_id: UUID, actor: Actor, service: Activation) -> object:
    return await service.overview(actor, workspace_id, manager=True)


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/documents", status_code=201)
async def ingest_document(
    workspace_id: UUID,
    dataset_id: UUID,
    actor: Actor,
    service: Knowledge,
    request: Request,
    name: Annotated[str, Query(max_length=100)],
    shared: bool = False,
) -> object:
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise IngestionError("document_too_large", "Documents must be at most 1 MiB.", 413)
    return asdict(
        await service.ingest(actor, workspace_id, dataset_id, name, bytes(content), shared)
    )


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/documents")
async def list_documents(
    workspace_id: UUID, dataset_id: UUID, actor: Actor, service: Knowledge
) -> object:
    return await service.list_documents(actor, workspace_id, dataset_id)


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/knowledge/search")
async def search(
    workspace_id: UUID, dataset_id: UUID, body: SearchInput, actor: Actor, service: Knowledge
) -> object:
    return {
        "passages": await service.search(actor, workspace_id, dataset_id, body.query, body.limit),
        "mode": "reference-hybrid-v1",
        "answer_type": "source_passages",
    }


@router.get("/workspaces/{workspace_id}/documents/{document_id}/chunks/{chunk_id}")
async def citation(
    workspace_id: UUID, document_id: UUID, chunk_id: UUID, actor: Actor, service: Knowledge
) -> object:
    return await service.citation(actor, workspace_id, document_id, chunk_id)


@router.delete("/workspaces/{workspace_id}/documents/{document_id}", status_code=204)
async def delete_document(
    workspace_id: UUID, document_id: UUID, actor: Actor, service: Knowledge
) -> Response:
    await service.delete(actor, workspace_id, document_id)
    return Response(status_code=204)


@router.post("/workspaces/{workspace_id}/report-schedules", status_code=201)
async def schedule(
    workspace_id: UUID, body: ScheduleInput, actor: Actor, service: Reports
) -> object:
    return asdict(await service.create(actor, workspace_id, body.item_id, body.interval_hours))


@router.get("/workspaces/{workspace_id}/report-schedules")
async def schedules(workspace_id: UUID, actor: Actor, service: Reports) -> object:
    return [asdict(item) for item in await service.list_schedules(actor, workspace_id)]


@router.delete("/workspaces/{workspace_id}/report-schedules/{schedule_id}", status_code=204)
async def unsubscribe(
    workspace_id: UUID, schedule_id: UUID, actor: Actor, service: Reports
) -> Response:
    await service.unsubscribe(actor, workspace_id, schedule_id)
    return Response(status_code=204)


@router.get("/workspaces/{workspace_id}/catalog")
async def catalog(
    workspace_id: UUID, actor: Actor, request: Request, q: str = ""
) -> object:
    return request.app.state.runtime.catalog.search(actor, workspace_id, q)
