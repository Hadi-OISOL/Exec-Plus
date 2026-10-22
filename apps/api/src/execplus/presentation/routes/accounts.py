"""Use case: Exposes bounded local password accounts and private onboarding.

What it does: Maps explicit account actions to shared sessions and authorized workspace services.
"""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.accounts import AccountService
from execplus.domain.accounts import AccountSession
from execplus.presentation.routes.workspaces import SESSION_COOKIE, Actor, set_session_cookie

router = APIRouter(tags=["local accounts"])


def service(request: Request) -> AccountService:
    accounts: AccountService = request.app.state.runtime.accounts
    return accounts


Service = Annotated[AccountService, Depends(service)]


def peer(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128, repr=False)


class RegistrationInput(AccountInput):
    display_name: str = Field(min_length=1, max_length=100)
    workspace_name: str = Field(min_length=1, max_length=100)


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128, repr=False)
    new_password: str = Field(min_length=1, max_length=128, repr=False)


class DisableInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=128, repr=False)
    confirmed: bool = Field(strict=True)


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: UUID
    identity_checked: bool = Field(strict=True)


class GuideInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, lt=2147483647, strict=True)
    active_step: str = Field(min_length=1, max_length=30)
    skipped_steps: list[str] = Field(default_factory=list, max_length=8)
    paused: bool = Field(default=False, strict=True)
    finished: bool = Field(default=False, strict=True)


@router.get("/auth/options")
def options(accounts: Service) -> object:
    return {
        "local_registration_enabled": accounts.registration_enabled,
        "email_verification": "unavailable",
        "password_recovery": "authorized_local_operator",
    }


@router.post("/auth/register", status_code=202)
def register(body: RegistrationInput, request: Request, accounts: Service) -> dict[str, str]:
    accounts.register(
        body.email, body.password, body.display_name, body.workspace_name, peer(request)
    )
    return {
        "message": "If this address was available, your local account is ready. "
        "Try signing in with your password. No email has been sent or verified."
    }


@router.post("/auth/login")
def login(body: AccountInput, request: Request, response: Response, accounts: Service) -> object:
    return issued(
        request, response, accounts, accounts.login(body.email, body.password, peer(request))
    )


def issued(
    request: Request, response: Response, accounts: AccountService, session: AccountSession
) -> object:
    remaining = session.expires_at - accounts.clock()
    set_session_cookie(request, response, session.token, int(remaining.total_seconds()))
    return asdict(session)


@router.get("/auth/account")
def account(actor: Actor, accounts: Service) -> object:
    return accounts.profile(actor)


@router.get("/auth/account/events")
def events(actor: Actor, accounts: Service) -> object:
    return {"events": accounts.events(actor)}


@router.post("/auth/password")
def password(
    body: PasswordInput, request: Request, response: Response, actor: Actor, accounts: Service
) -> object:
    return issued(
        request,
        response,
        accounts,
        accounts.change_password(actor, body.current_password, body.new_password, peer(request)),
    )


@router.post("/auth/disable", status_code=204)
def disable(body: DisableInput, request: Request, actor: Actor, accounts: Service) -> Response:
    accounts.disable(actor, body.password, body.confirmed, peer(request))
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return response


@router.post(
    "/workspaces/{workspace_id}/invitations/{invitation_id}/identity-approval", status_code=204
)
def approve_invitation(
    workspace_id: UUID, invitation_id: UUID, body: ApprovalInput, actor: Actor, accounts: Service
) -> Response:
    accounts.approve_invitation(
        actor, workspace_id, invitation_id, body.account_id, body.identity_checked
    )
    return Response(status_code=204)


@router.get("/workspaces/{workspace_id}/onboarding-progress")
def guide(workspace_id: UUID, actor: Actor, accounts: Service) -> object:
    return accounts.guide(actor, workspace_id)


@router.put("/workspaces/{workspace_id}/onboarding-progress")
def save_guide(workspace_id: UUID, body: GuideInput, actor: Actor, accounts: Service) -> object:
    return accounts.save_guide(actor, workspace_id, **body.model_dump())
