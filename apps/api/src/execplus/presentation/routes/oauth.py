"""Use case: Completes provider sign-in without placing application sessions in URLs or storage.

What it does: Uses HttpOnly browser-bound cookies and an exact-origin, one-use JSON exchange.
"""

import base64
import hashlib
import re
import secrets

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from execplus.domain.ingestion import IngestionError
from execplus.presentation.routes import workspaces

router = APIRouter(tags=["oauth"])
BROWSER_COOKIE = "execplus_oauth_browser"
EXCHANGE_COOKIE = "execplus_oauth_exchange"
RETURN_COOKIE = "execplus_oauth_return"
CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}")


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


def mobile_binding(request: Request, return_to: str, challenge: str) -> str | None:
    if not return_to and not challenge:
        return None
    if return_to not in request.app.state.mobile_returns or not CHALLENGE.fullmatch(challenge):
        raise IngestionError("oauth_return_invalid", "This app address is not allowed.", 400)
    return challenge


def mark_return(response: Response, return_to: str | None, api_url: str) -> None:
    if return_to is None:
        response.delete_cookie(RETURN_COOKIE, path="/")
        return
    response.set_cookie(
        RETURN_COOKIE,
        return_to,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=api_url.startswith("https://"),
        path="/",
    )


def mobile_return(request: Request) -> str | None:
    value = request.cookies.get(RETURN_COOKIE, "")
    return value if value in request.app.state.mobile_returns else None


def finish_mobile(return_to: str, handoff: str | None) -> Response:
    query = f"handoff={handoff}" if handoff else "error=oauth_state_invalid"
    response = RedirectResponse(
        f"{return_to}?{query}",
        status_code=302,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
    response.delete_cookie(RETURN_COOKIE, path="/")
    return response


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
    handoff: str | None = Field(default=None, min_length=32, max_length=128)
    verifier: str | None = Field(default=None, min_length=43, max_length=128)


@router.post("/auth/oauth/exchange")
async def exchange(body: ExchangeInput, request: Request) -> Response:
    origin(request)
    if body.handoff and body.verifier:
        digest = hashlib.sha256(body.verifier.encode("ascii", "replace")).digest()
        handoff = body.handoff
        binding = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    else:
        handoff = request.cookies.get(EXCHANGE_COOKIE, "")
        binding = request.cookies.get(BROWSER_COOKIE, "")
    result = await run_in_threadpool(
        request.app.state.runtime.oauth_state.exchange, handoff, binding
    )
    response = JSONResponse(result, headers={"Cache-Control": "no-store"})
    response.delete_cookie(EXCHANGE_COOKIE, path="/")
    if "token" in result:
        workspaces.set_session_cookie(request, response, result["token"])
    return response
