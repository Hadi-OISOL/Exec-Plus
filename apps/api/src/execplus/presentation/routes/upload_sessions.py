"""Use case: Exposes resumable chunked uploads, personal storage use and staff quota overrides.

What it does: Bounds chunk bodies while streaming and delegates ownership, quota and ingestion.
"""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from execplus.application.services.operations import OperationsService
from execplus.application.services.upload_sessions import UploadSessionService
from execplus.domain.ingestion import IngestionError
from execplus.presentation.routes.workspaces import Actor, public_upload

router = APIRouter(tags=["upload-sessions"])
ROOT = "/workspaces/{workspace_id}/upload-sessions"


def service(request: Request) -> UploadSessionService:
    value: UploadSessionService = request.app.state.runtime.upload_sessions
    return value


def operations(request: Request) -> OperationsService:
    value: OperationsService = request.app.state.runtime.operations
    return value


Service = Annotated[UploadSessionService, Depends(service)]
Operations = Annotated[OperationsService, Depends(operations)]


class SessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0, le=10**12, strict=True)
    content_type: str = Field(default="", max_length=100)
    sha256: str | None = Field(default=None, max_length=64)
    dataset_id: UUID | None = None
    purpose: Literal["upload"] = "upload"


class QuotaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quota_bytes: int | None = Field(ge=0, le=10**12, strict=True)


def public(view: dict[str, Any]) -> dict[str, Any]:
    upload = view.get("upload")
    return {**view, "upload": public_upload(upload) if upload is not None else None}


@router.post(ROOT, status_code=201)
def start(workspace_id: UUID, body: SessionInput, actor: Actor, sessions: Service) -> object:
    return public(
        sessions.start(
            actor,
            workspace_id,
            filename=body.filename,
            size_bytes=body.size_bytes,
            content_type=body.content_type,
            sha256=body.sha256,
            dataset_id=body.dataset_id,
            purpose=body.purpose,
        )
    )


@router.get(ROOT)
def list_sessions(
    workspace_id: UUID,
    actor: Actor,
    sessions: Service,
    status: Annotated[
        Literal["open", "processing", "completed", "failed", "cancelled", "expired"] | None,
        Query(),
    ] = None,
) -> object:
    return [public(item) for item in sessions.list_sessions(actor, workspace_id, status)]


@router.get(ROOT + "/{session_id}")
def get_session(workspace_id: UUID, session_id: UUID, actor: Actor, sessions: Service) -> object:
    return public(sessions.get(actor, workspace_id, session_id))


@router.put(ROOT + "/{session_id}/chunks/{index}")
async def put_chunk(
    workspace_id: UUID,
    session_id: UUID,
    index: Annotated[int, Path(ge=0, le=1_000_000)],
    request: Request,
    actor: Actor,
    sessions: Service,
    chunk_sha256: Annotated[str | None, Header(alias="X-Chunk-SHA256", max_length=64)] = None,
) -> object:
    limit = sessions.chunk_bytes
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdecimal() or int(declared) > limit):
        raise IngestionError("invalid_chunk_size", f"Chunks must be at most {limit} bytes.", 413)
    body = bytearray()
    async for part in request.stream():
        body += part
        if len(body) > limit:
            raise IngestionError(
                "invalid_chunk_size", f"Chunks must be at most {limit} bytes.", 413
            )
    return await run_in_threadpool(
        sessions.put_chunk, actor, workspace_id, session_id, index, bytes(body), chunk_sha256
    )


@router.post(ROOT + "/{session_id}/complete", status_code=201)
def complete(
    workspace_id: UUID,
    session_id: UUID,
    actor: Actor,
    sessions: Service,
    background: BackgroundTasks,
) -> object:
    view, pending = sessions.complete(actor, workspace_id, session_id)
    if pending:
        background.add_task(sessions.process, session_id)
    result = public(view)
    return {"upload": result["upload"], "status": result["status"], "session": result}


@router.delete(ROOT + "/{session_id}", status_code=204)
def cancel(workspace_id: UUID, session_id: UUID, actor: Actor, sessions: Service) -> Response:
    sessions.cancel(actor, workspace_id, session_id)
    return Response(status_code=204)


@router.get("/me/storage")
def storage(actor: Actor, sessions: Service) -> object:
    return sessions.storage_summary(actor)


@router.put("/admin/users/{user_id}/storage-quota")
def set_quota(user_id: UUID, body: QuotaInput, actor: Actor, staff: Operations) -> object:
    return staff.set_storage_quota(actor, user_id, body.quota_bytes)
