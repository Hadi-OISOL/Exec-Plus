"""Use case: Exposes the tested hypotheses for an upload and each member's private feedback.

What it does: Authorizes the caller, attributes model usage and serializes hypotheses-v1.
"""

import asyncio
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from execplus.application.services.hypotheses import hypotheses, save_feedback
from execplus.application.usage_context import usage_scope
from execplus.domain.usage_metering import UsageAttribution
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["hypotheses"])
ROOT = "/workspaces/{workspace_id}"


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["group_gap", "relationship", "concentration", "recent_change"]
    vote: Literal["like", "dislike"]
    reason: Literal["too_obvious", "not_relevant", "wrong_measure"] | None = None


@router.get(ROOT + "/uploads/{upload_id}/hypotheses")
async def upload_hypotheses(
    workspace_id: UUID, upload_id: UUID, actor: Actor, request: Request
) -> object:
    runtime = request.app.state.runtime
    router_service = runtime.intent_router
    with usage_scope(UsageAttribution(workspace_id, actor.id, uuid4(), "summary")):
        return await hypotheses(
            runtime.analytics,
            actor,
            workspace_id,
            upload_id,
            model=router_service.model if router_service.interpretation_enabled else None,
        )


@router.put(ROOT + "/hypothesis-feedback")
async def hypothesis_feedback(
    workspace_id: UUID, body: FeedbackInput, actor: Actor, request: Request
) -> object:
    feedback = await asyncio.to_thread(
        save_feedback,
        request.app.state.runtime.analytics,
        actor,
        workspace_id,
        body.kind,
        body.vote,
        body.reason,
    )
    return {"feedback": feedback}
