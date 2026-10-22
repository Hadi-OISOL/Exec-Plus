"""Use case: Exposes Google sign-in, the Google connection and sheet import.

What it does: Runs the browser redirects, returns non-secret configuration and delegates the work.
"""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.google_access import GoogleAccessService
from execplus.domain.ingestion import IngestionError
from execplus.presentation.routes import oauth
from execplus.presentation.routes.accounts import peer
from execplus.presentation.routes.refresh import Refresh, StageInput
from execplus.presentation.routes.workspaces import Actor, public_upload

router = APIRouter(tags=["google"])


def optional_service(request: Request) -> GoogleAccessService | None:
    result: GoogleAccessService | None = request.app.state.runtime.google_access
    return result


def service(request: Request) -> GoogleAccessService:
    result = optional_service(request)
    if result is None:
        raise IngestionError("google_not_configured", "Google sign-in is not configured.", 404)
    return result


Service = Annotated[GoogleAccessService, Depends(service)]
OptionalService = Annotated[GoogleAccessService | None, Depends(optional_service)]


class ImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spreadsheet_id: str = Field(min_length=1, max_length=120)
    sheet_id: int | None = Field(default=None, ge=0, le=2**31 - 1)


@router.get("/auth/google/config")
async def config(service: OptionalService) -> object:
    return service.config() if service else dict(enabled=False, picker=None)


@router.get("/auth/google/start")
async def start(request: Request, service: Service) -> Response:
    binding = oauth.browser(request)
    url = await run_in_threadpool(service.start_sign_in, binding, peer(request))
    response = RedirectResponse(url, status_code=302)
    oauth.set_browser(response, binding, service.api_url)
    return response


@router.get("/auth/google/callback")
async def callback(
    request: Request, service: Service, code: str = "", state: str = "", error: str = ""
) -> Response:
    try:
        handle = await run_in_threadpool(
            service.finish_sign_in,
            code[:4096],
            state[:129],
            request.cookies.get(oauth.BROWSER_COOKIE, ""),
            bool(error),
        )
    except IngestionError:
        handle = None
    return oauth.finish(service.web_origin, service.api_url, handle)


@router.post("/integrations/google/connect")
async def connect(request: Request, actor: Actor, service: Service) -> Response:
    oauth.origin(request)
    binding = oauth.browser(request)
    url = await run_in_threadpool(
        service.start_connect, actor, binding, oauth.session_token(request), peer(request)
    )
    response = JSONResponse(dict(url=url))
    oauth.set_browser(response, binding, service.api_url)
    return response


@router.get("/integrations/google/callback")
async def connected(
    request: Request, service: Service, code: str = "", state: str = "", error: str = ""
) -> Response:
    try:
        handle = await run_in_threadpool(
            service.finish_connect,
            code[:4096],
            state[:129],
            request.cookies.get(oauth.BROWSER_COOKIE, ""),
            bool(error),
        )
    except IngestionError:
        handle = None
    return oauth.finish(service.web_origin, service.api_url, handle)


@router.get("/integrations/google/status")
async def status(actor: Actor, service: Service) -> object:
    return await run_in_threadpool(service.status, actor)


@router.delete("/integrations/google", status_code=204)
async def disconnect(actor: Actor, service: Service) -> Response:
    await run_in_threadpool(service.disconnect, actor)
    return Response(status_code=204)


@router.get("/integrations/google/picker-token")
async def picker_token(request: Request, actor: Actor, service: Service) -> object:
    result = await run_in_threadpool(service.picker_token, actor, oauth.session_token(request))
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.get("/integrations/google/spreadsheets/{spreadsheet_id}")
async def spreadsheet(
    spreadsheet_id: str, request: Request, actor: Actor, service: Service
) -> object:
    return await run_in_threadpool(
        service.spreadsheet, actor, spreadsheet_id, oauth.session_token(request)
    )


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/google-sheets/import", status_code=201
)
async def import_sheet(
    workspace_id: UUID,
    dataset_id: UUID,
    body: ImportInput,
    request: Request,
    actor: Actor,
    service: Service,
) -> object:
    upload = await run_in_threadpool(
        service.import_sheet,
        actor,
        workspace_id,
        dataset_id,
        body.spreadsheet_id,
        body.sheet_id,
        oauth.session_token(request),
    )
    return public_upload(upload)


class RefreshInput(ImportInput):
    options: StageInput


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/google-sheets/refresh-candidates",
    status_code=201,
)
async def stage_refresh(
    workspace_id: UUID,
    dataset_id: UUID,
    body: RefreshInput,
    request: Request,
    actor: Actor,
    service: Service,
    refresh: Refresh,
) -> object:
    candidate = await run_in_threadpool(
        service.stage_refresh,
        actor,
        workspace_id,
        dataset_id,
        body.spreadsheet_id,
        body.sheet_id,
        oauth.session_token(request),
        refresh,
        body.options.model_dump(),
    )
    return asdict(candidate)
