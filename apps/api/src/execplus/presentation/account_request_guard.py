"""Use case: Bounds account and local administrative requests before JSON parsing.

What it does: Rejects foreign origins, wrong media types and oversized streamed bodies.
"""

import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_CREDENTIAL_PATHS = {
    "/auth/register",
    "/auth/login",
    "/auth/password",
    "/auth/disable",
    "/auth/oauth/exchange",
}
_CONNECTOR_CREDENTIAL_PATH = re.compile(r"/connectors/[^/]+/credentials")
_GUIDE_PATH = re.compile(r"/workspaces/[^/]+/onboarding-progress")
_APPROVAL_PATH = re.compile(r"/workspaces/[^/]+/invitations/[^/]+/identity-approval")
_ADMIN_PATHS = (
    re.compile(r"/admin/incidents/thresholds/[^/]+"),
    re.compile(r"/admin/workspaces/[^/]+/plan"),
    re.compile(r"/admin/plans/[^/]+"),
)


class AccountRequestGuard:
    def __init__(self, app: ASGIApp, web_origin: str) -> None:
        self.app, self.web_origin = app, web_origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        protected = scope.get("method") in {"POST", "PUT", "PATCH"} and (
            path in _CREDENTIAL_PATHS
            or _CONNECTOR_CREDENTIAL_PATH.fullmatch(path)
            or _GUIDE_PATH.fullmatch(path)
            or _APPROVAL_PATH.fullmatch(path)
            or any(pattern.fullmatch(path) for pattern in _ADMIN_PATHS)
        )
        if scope["type"] != "http" or not protected:
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        origin = headers.get(b"origin")
        origins = [value for key, value in scope.get("headers", []) if key.lower() == b"origin"]
        if (
            len(origins) > 1
            or (path == "/auth/oauth/exchange" and origin is None)
            or (origin is not None and origin != self.web_origin.encode("utf-8"))
        ):
            await self.reject(
                scope,
                receive,
                send,
                403,
                "request_origin",
                "Use the configured application address.",
            )
            return
        if (
            headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
            != b"application/json"
        ):
            await self.reject(
                scope, receive, send, 415, "request_media_type", "Send a JSON request."
            )
            return
        declared = headers.get(b"content-length")
        if declared is not None and (
            not declared.isdigit() or len(declared) > 8 or int(declared) > 8192
        ):
            await self.reject(
                scope, receive, send, 413, "request_too_large", "This JSON request is too large."
            )
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > 8192:
                await self.reject(
                    scope,
                    receive,
                    send,
                    413,
                    "request_too_large",
                    "This JSON request is too large.",
                )
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        consumed = False

        async def bounded_receive() -> Message:
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

    @staticmethod
    async def reject(
        scope: Scope, receive: Receive, send: Send, status: int, code: str, message: str
    ) -> None:
        response = JSONResponse(
            {"error": {"code": code, "message": message}},
            status_code=status,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
        await response(scope, receive, send)
