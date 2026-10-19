"""Use case: Exposes Google sign-in, the Google connection and sheet import.

What it does: Runs the browser redirects, returns non-secret configuration and delegates the work.
"""

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.google_access import GoogleAccessService
from execplus.domain.ingestion import IngestionError
from execplus.presentation.routes.workspaces import Actor, public_upload

router = APIRouter(tags=["google"])
STATE_COOKIE = "execplus_oauth"
STATE_SECONDS = 600


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


def finish(service: GoogleAccessService, fragment: str) -> RedirectResponse:
    response = RedirectResponse(f"{service.web_origin}/workspace{fragment}", status_code=302)
    response.delete_cookie(STATE_COOKIE, path="/auth/google")
    return response


@router.get("/auth/google/config")
async def config(service: OptionalService) -> object:
    return service.config() if service else dict(enabled=False, picker=None)


@router.get("/auth/google/start")
async def start(service: Service) -> Response:
    url, sealed = await run_in_threadpool(service.start_sign_in)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        sealed,
        max_age=STATE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=service.api_url.startswith("https://"),
        path="/auth/google",
    )
    return response


@router.get("/auth/google/callback")
async def callback(
    request: Request,
    service: Service,
    code: str = "",
    state: str = "",
    error: str = "",
) -> Response:
    if error or not code or not state:
        return finish(service, "#google_error=google_denied")
    try:
        token = await run_in_threadpool(
            service.finish_sign_in, code, state, request.cookies.get(STATE_COOKIE, "")
        )
    except IngestionError as failure:
        return finish(service, f"#google_error={quote(failure.code)}")
    return finish(service, f"#session={quote(token)}")


@router.post("/integrations/google/connect")
async def connect(actor: Actor, service: Service) -> object:
    return dict(url=await run_in_threadpool(service.start_connect, actor))


@router.get("/integrations/google/callback")
async def connected(service: Service, code: str = "", state: str = "", error: str = "") -> Response:
    if error or not code or not state:
        return finish(service, "?google_error=google_denied")
    try:
        await run_in_threadpool(service.finish_connect, code, state)
    except IngestionError as failure:
        return finish(service, f"?google_error={quote(failure.code)}")
    return finish(service, "?google=connected")


@router.get("/integrations/google/status")
async def status(actor: Actor, service: Service) -> object:
    return await run_in_threadpool(service.status, actor)


@router.delete("/integrations/google", status_code=204)
async def disconnect(actor: Actor, service: Service) -> Response:
    await run_in_threadpool(service.disconnect, actor)
    return Response(status_code=204)


@router.get("/integrations/google/picker-token")
async def picker_token(actor: Actor, service: Service) -> object:
    result = await run_in_threadpool(service.picker_token, actor)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.get("/integrations/google/spreadsheets/{spreadsheet_id}")
async def spreadsheet(spreadsheet_id: str, actor: Actor, service: Service) -> object:
    return await run_in_threadpool(service.spreadsheet, actor, spreadsheet_id)


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/google-sheets/import", status_code=201
)
async def import_sheet(
    workspace_id: UUID, dataset_id: UUID, body: ImportInput, actor: Actor, service: Service
) -> object:
    upload = await run_in_threadpool(
        service.import_sheet, actor, workspace_id, dataset_id, body.spreadsheet_id, body.sheet_id
    )
    return public_upload(upload)
