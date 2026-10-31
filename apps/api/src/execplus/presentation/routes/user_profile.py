"""Use case: Lets a signed-in person read, answer, redo or forget their own onboarding profile.

What it does: Validates transport fields and delegates version-checked, actor-only changes.
"""

from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.understanding import UnderstandingService
from execplus.domain.user_profile import UserProfile, questionnaire
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["user-profile"])


def service(request: Request) -> UnderstandingService:
    result: UnderstandingService = request.app.state.runtime.understanding
    return result


Service = Annotated[UnderstandingService, Depends(service)]


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, strict=True)
    preferred_name: str = Field(default="", max_length=120)
    answers: dict[str, Any] = Field(default_factory=dict)
    status: Literal["completed", "skipped"] = "completed"


def _view(profile: UserProfile) -> dict[str, Any]:
    return {**asdict(profile), "status": profile.status, "questionnaire": questionnaire()}


@router.get("/me/profile")
async def profile(actor: Actor, service: Service) -> object:
    return _view(service.profile(actor))


@router.put("/me/profile")
async def save_profile(body: ProfileInput, actor: Actor, service: Service) -> object:
    return _view(
        service.save_profile(
            actor, body.expected_version, body.preferred_name, body.answers, body.status
        )
    )


@router.delete("/me/profile")
async def forget_profile(
    actor: Actor, service: Service, expected_version: Annotated[int, Query(ge=0)]
) -> object:
    return _view(service.save_profile(actor, expected_version, forget=True))
