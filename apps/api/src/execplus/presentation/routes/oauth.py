"""Use case: Completes provider sign-in without placing application sessions in URLs or storage.

What it does: Uses HttpOnly browser-bound cookies and an exact-origin, one-use JSON exchange.
"""

import secrets

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict

from execplus.domain.ingestion import IngestionError
from execplus.presentation.routes import workspaces

router = APIRouter(tags=["oauth"])
BROWSER_COOKIE = "execplus_oauth_browser"
EXCHANGE_COOKIE = "execplus_oauth_exchange"


def origin(request: Request) -> None:
    values = request.headers.getlist("origin")
    if values != [request.app.state.web_origin]:
        raise IngestionError("request_origin", "Use the configured application address.", 403)


def browser(request: Request) -> str:
    existing = request.cookies.get(BROWSER_COOKIE, "")
    return existing if 32 <= len(existing) <= 128 else secrets.token_urlsafe(32)


def session_token(request: Request) -> str:
    return workspaces.session_token(request)


def set_browser(response: Response, value: str, api_url: str) -> None:
    response.set_cookie(
        BROWSER_COOKIE,
        value,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=api_url.startswith("https://"),
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


def finish(web_origin: str, api_url: str, handoff: str | None) -> Response:
    query = "oauth=complete" if handoff else "oauth_error=oauth_state_invalid"
    response = RedirectResponse(
        f"{web_origin}/workspace?{query}",
        status_code=302,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
    if handoff:
        response.set_cookie(
            EXCHANGE_COOKIE,
            handoff,
            max_age=60,
            httponly=True,
            samesite="lax",
            secure=api_url.startswith("https://"),
            path="/",
        )
    else:
        response.delete_cookie(EXCHANGE_COOKIE, path="/")
    return response


class ExchangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/auth/oauth/exchange")
async def exchange(body: ExchangeInput, request: Request) -> Response:
    origin(request)
    result = await run_in_threadpool(
        request.app.state.runtime.oauth_state.exchange,
        request.cookies.get(EXCHANGE_COOKIE, ""),
        request.cookies.get(BROWSER_COOKIE, ""),
    )
    response = JSONResponse(result, headers={"Cache-Control": "no-store"})
    response.delete_cookie(EXCHANGE_COOKIE, path="/")
    if "token" in result:
        workspaces.set_session_cookie(request, response, result["token"])
    return response
