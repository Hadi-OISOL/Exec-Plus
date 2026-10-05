"""Use case: Exposes multi-turn conversation threads over a dataset.

What it does: Each turn resolves against the prior turn's stored, structured
lineage rather than raw prompt history, and always records what was executed
or why it was not.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.threads import ThreadService
from execplus.domain.threads import Thread, ThreadTurn
from execplus.presentation.routes.analytics import numerical_answer_body
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["threads"])


def get_thread_service(request: Request) -> ThreadService:
    service: ThreadService = request.app.state.runtime.threads
    return service


Service = Annotated[ThreadService, Depends(get_thread_service)]


class AskInThreadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)
    request_id: UUID | None = None


def _thread_body(thread: Thread) -> dict[str, object]:
    return {
        "id": str(thread.id),
        "workspace_id": str(thread.workspace_id),
        "dataset_id": str(thread.dataset_id),
        "upload_id": str(thread.upload_id),
        "owner_id": str(thread.owner_id),
        "created_at": thread.created_at.isoformat(),
    }


def _turn_body(turn: ThreadTurn) -> dict[str, object]:
    return {
        "id": str(turn.id),
        "question": turn.question,
        "kind": turn.kind,
        "query_id": str(turn.query_id) if turn.query_id else None,
        "message": turn.message,
        "model_route": turn.model_route,
        "created_at": turn.created_at.isoformat(),
        "status": turn.status,
        "job_id": str(turn.job_id) if turn.job_id else None,
        "request_id": str(turn.request_id) if turn.request_id else None,
    }


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/threads",
    status_code=201,
)
async def create_thread(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    thread = await service.start_thread(actor, workspace_id, dataset_id, upload_id)
    return _thread_body(thread)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/threads")
async def list_threads(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    return [
        _thread_body(thread)
        for thread in service.list_threads(actor, workspace_id, dataset_id, upload_id)
    ]


@router.get("/workspaces/{workspace_id}/threads/{thread_id}/turns/{turn_id}/answer")
async def historical_answer(
    workspace_id: UUID, thread_id: UUID, turn_id: UUID, actor: Actor, service: Service
) -> object:
    answer = await service.resolve(actor, workspace_id, thread_id, turn_id)
    return numerical_answer_body(answer) if answer is not None else None


@router.get("/workspaces/{workspace_id}/threads/{thread_id}")
async def get_thread(workspace_id: UUID, thread_id: UUID, actor: Actor, service: Service) -> object:
    thread, turns = await service.get_thread(actor, workspace_id, thread_id)
    return {**_thread_body(thread), "turns": [_turn_body(turn) for turn in turns]}


@router.post("/workspaces/{workspace_id}/threads/{thread_id}/ask")
async def ask_in_thread(
    workspace_id: UUID,
    thread_id: UUID,
    body: AskInThreadInput,
    actor: Actor,
    service: Service,
) -> object:
    answer, turn = await service.ask(actor, workspace_id, thread_id, body.question, body.request_id)
    return {
        "turn": _turn_body(turn),
        "answer": numerical_answer_body(answer) if answer is not None else None,
    }
