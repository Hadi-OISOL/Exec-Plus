"""Use case: Exposes authenticated workspace and raw-file upload HTTP contracts.

What it does: Maps transport data to application services and returns safe metadata.
"""

from dataclasses import asdict
from tempfile import TemporaryFile
from typing import Annotated, BinaryIO, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from execplus.application.ports import IdentityProvider
from execplus.application.services.workspaces import WorkspaceService
from execplus.domain.ingestion import IngestionError, Upload, User
from execplus.domain.profiling import Cleaning
from execplus.domain.samples import SAMPLES

router = APIRouter(tags=["workspaces"])


def get_service(request: Request) -> WorkspaceService:
    service: WorkspaceService = request.app.state.runtime.service
    return service


def get_actor(request: Request) -> User:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise IngestionError("unauthenticated", "A valid session token is required.", 401)
    identity: IdentityProvider = request.app.state.runtime.identity
    return identity.authenticate(token)


Actor = Annotated[User, Depends(get_actor)]
Service = Annotated[WorkspaceService, Depends(get_service)]


class NameInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)


class WorkspaceInput(NameInput):
    seat_limit: int = Field(default=3, ge=3, le=50, strict=True)


class SeatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seat_limit: int = Field(ge=3, le=50, strict=True)


class InvitationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    role: str = "member"


def public_upload(upload: Upload) -> dict[str, object]:
    result: dict[str, object] = asdict(upload)
    result.pop("storage_key")
    return result


@router.get("/auth/me")
def me(actor: Actor) -> User:
    return actor


@router.post("/auth/logout", status_code=204)
def logout(request: Request, actor: Actor) -> Response:
    identity: IdentityProvider = request.app.state.runtime.identity
    identity.revoke(request.headers["authorization"].partition(" ")[2])
    return Response(status_code=204)


@router.get("/workspaces")
def workspaces(actor: Actor, service: Service) -> object:
    return service.list_workspaces(actor)


@router.post("/workspaces", status_code=201)
def create_workspace(body: WorkspaceInput, actor: Actor, service: Service) -> object:
    return service.create_workspace(actor, body.name, body.seat_limit)


@router.patch("/workspaces/{workspace_id}/seats", status_code=204)
def seats(workspace_id: UUID, body: SeatInput, actor: Actor, service: Service) -> Response:
    service.set_seat_limit(actor, workspace_id, body.seat_limit)
    return Response(status_code=204)


@router.get("/workspaces/{workspace_id}/members")
def members(workspace_id: UUID, actor: Actor, service: Service) -> object:
    return service.list_members(actor, workspace_id)


@router.delete("/workspaces/{workspace_id}/members/{user_id}", status_code=204)
def remove_member(workspace_id: UUID, user_id: UUID, actor: Actor, service: Service) -> Response:
    service.remove_member(actor, workspace_id, user_id)
    return Response(status_code=204)


@router.get("/workspaces/{workspace_id}/invitations")
def invitations(workspace_id: UUID, actor: Actor, service: Service) -> object:
    return service.list_invitations(actor, workspace_id)


@router.post("/workspaces/{workspace_id}/invitations", status_code=201)
def invite(workspace_id: UUID, body: InvitationInput, actor: Actor, service: Service) -> object:
    return service.invite(actor, workspace_id, body.email, body.role)


@router.post("/workspaces/{workspace_id}/invitations/{invitation_id}/accept")
def accept(workspace_id: UUID, invitation_id: UUID, actor: Actor, service: Service) -> object:
    return service.accept_invitation(actor, workspace_id, invitation_id)


@router.delete("/workspaces/{workspace_id}/invitations/{invitation_id}", status_code=204)
def revoke(workspace_id: UUID, invitation_id: UUID, actor: Actor, service: Service) -> Response:
    service.revoke_invitation(actor, workspace_id, invitation_id)
    return Response(status_code=204)


@router.get("/workspaces/{workspace_id}/datasets")
def datasets(workspace_id: UUID, actor: Actor, service: Service) -> object:
    return service.list_datasets(actor, workspace_id)


@router.post("/workspaces/{workspace_id}/datasets", status_code=201)
def create_dataset(workspace_id: UUID, body: NameInput, actor: Actor, service: Service) -> object:
    return service.create_dataset(actor, workspace_id, body.name)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}")
def dataset(workspace_id: UUID, dataset_id: UUID, actor: Actor, service: Service) -> object:
    return service.get_dataset(actor, workspace_id, dataset_id)


@router.patch("/workspaces/{workspace_id}/datasets/{dataset_id}")
def rename(
    workspace_id: UUID, dataset_id: UUID, body: NameInput, actor: Actor, service: Service
) -> object:
    return service.rename_dataset(actor, workspace_id, dataset_id, body.name)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads")
def uploads(workspace_id: UUID, dataset_id: UUID, actor: Actor, service: Service) -> object:
    return [
        public_upload(upload) for upload in service.list_uploads(actor, workspace_id, dataset_id)
    ]


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}")
def upload_metadata(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    return public_upload(service.get_upload(actor, workspace_id, dataset_id, upload_id))


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads", status_code=201)
async def upload(
    workspace_id: UUID,
    dataset_id: UUID,
    request: Request,
    actor: Actor,
    service: Service,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
) -> object:
    await run_in_threadpool(service.get_dataset, actor, workspace_id, dataset_id)
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdecimal():
            raise IngestionError("invalid_request", "Invalid content length.", 422)
        if int(declared) > service.max_upload_bytes:
            raise IngestionError("file_too_large", "Files must be at most 20 MiB.", 413)
    size = 0
    with TemporaryFile(mode="w+b") as content:
        async for chunk in request.stream():
            size += len(chunk)
            if size > service.max_upload_bytes:
                raise IngestionError("file_too_large", "Files must be at most 20 MiB.", 413)
            await run_in_threadpool(content.write, chunk)
        result = await run_in_threadpool(
            service.upload,
            actor,
            workspace_id,
            dataset_id,
            filename,
            request.headers.get("content-type", ""),
            cast(BinaryIO, content),
        )
    return public_upload(result)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/content")
def download(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> Response:
    content = service.download(actor, workspace_id, dataset_id, upload_id)
    return Response(
        content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="original-upload.bin"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/workspaces/{workspace_id}/audit-events")
def audit_events(workspace_id: UUID, actor: Actor, service: Service) -> object:
    return service.audit_events(actor, workspace_id)


class CleaningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_id: UUID
    trim: bool = Field(default=False, strict=True)
    drop_duplicates: bool = Field(default=False, strict=True)
    drop_missing: bool = Field(default=False, strict=True)
    mapping: dict[str, str] = Field(default_factory=dict, max_length=1000)

    def step(self) -> Cleaning:
        return {
            "trim": self.trim,
            "drop_duplicates": self.drop_duplicates,
            "drop_missing": self.drop_missing,
            "mapping": self.mapping,
        }


class RestoreInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_id: UUID
    revision_id: UUID


@router.get("/samples")
def samples(actor: Actor) -> object:
    return SAMPLES


@router.post("/workspaces/{workspace_id}/samples/{sample_id}", status_code=201)
def import_sample(workspace_id: UUID, sample_id: str, actor: Actor, service: Service) -> object:
    return public_upload(service.import_sample(actor, workspace_id, sample_id))


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/profile")
def upload_profile(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    return service.profile_upload(actor, workspace_id, dataset_id, upload_id)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/revisions")
def revisions(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, service: Service
) -> object:
    return service.revision_history(actor, workspace_id, dataset_id, upload_id)


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/cleaning/preview"
)
def preview(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: CleaningInput,
    actor: Actor,
    service: Service,
) -> object:
    return service.clean(
        actor, workspace_id, dataset_id, upload_id, body.expected_revision_id, body.step()
    )


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/cleaning/apply",
    status_code=201,
)
def apply_cleaning(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: CleaningInput,
    actor: Actor,
    service: Service,
) -> object:
    return service.clean(
        actor,
        workspace_id,
        dataset_id,
        upload_id,
        body.expected_revision_id,
        body.step(),
        apply=True,
    )


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/restore")
def restore_revision(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: RestoreInput,
    actor: Actor,
    service: Service,
) -> object:
    return service.restore(
        actor, workspace_id, dataset_id, upload_id, body.expected_revision_id, body.revision_id
    )


@router.get("/workspaces/{workspace_id}/usage")
def usage(workspace_id: UUID, actor: Actor, service: Service) -> object:
    return service.usage(actor, workspace_id)
