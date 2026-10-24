"""Use case: Exposes multi-turn conversation threads over a dataset.

What it does: Each turn resolves against the prior turn's stored, structured
lineage rather than raw prompt history, and always records what was executed
or why it was not.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.intent_router import ConversationAnswer
from execplus.application.services.threads import ThreadService
from execplus.domain.ingestion import User
from execplus.domain.threads import Thread, ThreadSummary, ThreadTurn
from execplus.presentation.routes.analytics import numerical_answer_body
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["threads"])


def get_thread_service(request: Request) -> ThreadService:
    service: ThreadService = request.app.state.runtime.threads
    return service


Service = Annotated[ThreadService, Depends(get_thread_service)]


async def resolved_answer_body(
    service: ThreadService,
    actor: User,
    workspace_id: UUID,
    thread_id: UUID,
    turn_id: UUID,
    answer: ConversationAnswer | None,
) -> dict[str, object] | None:
    if answer is None:
        return None
    question, follow_ups = await service.presentation_context(
        actor, workspace_id, thread_id, turn_id
    )
    body = numerical_answer_body(answer, question, follow_ups)
    narrative = await service.validated_narrative(
        actor,
        workspace_id,
        thread_id,
        turn_id,
        answer=answer,
    )
    if narrative is not None:
        body["narrative"] = narrative
    return body


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
        "title": thread.title,
    }


class RenameChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)


def _chat_body(summary: ThreadSummary) -> dict[str, object]:
    return {
        **_thread_body(summary.thread),
        "title": summary.display_title,
        "named": summary.thread.title is not None,
        "dataset_name": summary.dataset_name,
        "filename": summary.filename,
        "last_activity": summary.last_activity.isoformat(),
        "turn_count": summary.turn_count,
    }


def _turn_body(turn: ThreadTurn) -> dict[str, object]:
    clarification = turn.evidence.get("clarification")
    raw_choices = clarification.get("choices", []) if isinstance(clarification, dict) else []
    choices = (
        [choice for choice in raw_choices if isinstance(choice, str) and 0 < len(choice) <= 500][:6]
        if isinstance(raw_choices, list)
        else []
    )
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
        "clarification": {"choices": choices}
        if turn.kind == "ambiguous" and isinstance(clarification, dict)
        else None,
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


@router.get("/workspaces/{workspace_id}/threads")
async def list_chats(
    workspace_id: UUID,
    actor: Actor,
    service: Service,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    after: Annotated[str, Query(max_length=100)] = "",
) -> object:
    cursor = None
    if after:
        try:
            moment, _, identifier = after.partition("|")
            cursor = (datetime.fromisoformat(moment), UUID(identifier))
            if cursor[0].tzinfo is None:
                raise ValueError
        except ValueError:
            raise HTTPException(
                422, "Use the last chat's 'last_activity|id' as the cursor."
            ) from None
    return [_chat_body(item) for item in service.list_chats(actor, workspace_id, q, limit, cursor)]


@router.patch("/workspaces/{workspace_id}/threads/{thread_id}")
async def rename_chat(
    workspace_id: UUID, thread_id: UUID, body: RenameChatInput, actor: Actor, service: Service
) -> object:
    return _thread_body(service.rename_chat(actor, workspace_id, thread_id, body.title))


@router.delete("/workspaces/{workspace_id}/threads/{thread_id}", status_code=204)
async def hide_chat(
    workspace_id: UUID, thread_id: UUID, actor: Actor, service: Service
) -> Response:
    service.hide_chat(actor, workspace_id, thread_id)
    return Response(status_code=204)


@router.get("/workspaces/{workspace_id}/threads/{thread_id}/turns/{turn_id}/answer")
async def historical_answer(
    workspace_id: UUID, thread_id: UUID, turn_id: UUID, actor: Actor, service: Service
) -> object:
    answer = await service.resolve(actor, workspace_id, thread_id, turn_id)
    return await resolved_answer_body(service, actor, workspace_id, thread_id, turn_id, answer)


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
        "answer": await resolved_answer_body(
            service,
            actor,
            workspace_id,
            thread_id,
            turn.id,
            answer,
        ),
    }
