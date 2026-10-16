"""Use case: Exposes owner-managed keys and narrowly scoped integration reads.

What it does: Separates integration credentials from user sessions and validates
all requests before calling existing governed query and shared-board services.
"""

from dataclasses import asdict
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.forecasts import read_complete
from execplus.bootstrap import Runtime
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.integration_access import IntegrationKey
from execplus.presentation.routes.analytics import (
    MetricQueryInput,
    RowsInput,
    metric_filters,
    query_body,
)
from execplus.presentation.routes.studies import study_body
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["customer-integrations"])
ROOT = "/workspaces/{workspace_id}/integrations"
READ = "/integration/v1/workspaces/{workspace_id}"
SOURCE = READ + "/datasets/{dataset_id}/uploads/{upload_id}"


def runtime(request: Request) -> Runtime:
    value: Runtime = request.app.state.runtime
    return value


RuntimeDependency = Annotated[Runtime, Depends(runtime)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KeyInput(Input):
    name: str = Field(min_length=1, max_length=100)
    user_id: UUID | None = None
    dataset_ids: list[UUID] = Field(min_length=1, max_length=20)
    operations: list[Literal["profile:read", "rows:read", "query:read", "boards:read"]] = Field(
        min_length=1, max_length=4
    )
    expires_seconds: int = Field(default=86400, ge=1, le=7776000, strict=True)


class EmbedInput(Input):
    board_id: UUID
    host_origin: str = Field(min_length=1, max_length=300)
    expires_seconds: int = Field(default=300, ge=1, le=300, strict=True)


class ExchangeInput(Input):
    bootstrap_secret: str = Field(min_length=47, max_length=47, repr=False)
    host_origin: str = Field(min_length=1, max_length=300)


class EmbedReadInput(Input):
    session_secret: str = Field(min_length=47, max_length=47, repr=False)
    host_origin: str = Field(min_length=1, max_length=300)


def token(request: Request) -> str:
    scheme, _, value = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise IngestionError("integration_token", "A scoped integration key is required.", 401)
    return value


def embedding_origin(request: Request) -> None:
    if request.headers.get("origin") != request.app.state.web_origin:
        raise IngestionError(
            "embed_origin", "Use the approved ExecPlus frame for this request.", 403
        )


@router.post(ROOT + "/keys", status_code=201)
def create_key(
    workspace_id: UUID, body: KeyInput, actor: Actor, runtime: RuntimeDependency
) -> object:
    return runtime.integration_access.create_key(
        actor,
        workspace_id,
        body.name,
        tuple(body.dataset_ids),
        tuple(body.operations),
        body.expires_seconds,
        body.user_id,
    )


@router.get(ROOT + "/keys")
def keys(workspace_id: UUID, actor: Actor, runtime: RuntimeDependency) -> object:
    return runtime.integration_access.keys(actor, workspace_id)


@router.delete(ROOT + "/keys/{key_id}", status_code=204)
def revoke_key(
    workspace_id: UUID, key_id: UUID, actor: Actor, runtime: RuntimeDependency
) -> Response:
    runtime.integration_access.revoke_key(actor, workspace_id, key_id)
    return Response(status_code=204)


@router.get(SOURCE + "/profile")
async def profile(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    request: Request,
    runtime: RuntimeDependency,
) -> object:
    async def read(actor: User, key: IntegrationKey) -> object:
        value = await read_complete(
            lambda: runtime.service.profile_upload(actor, workspace_id, dataset_id, upload_id)
        )
        return asdict(value)

    return await runtime.integration_access.perform(
        token(request), workspace_id, dataset_id, "profile:read", read
    )


@router.post(SOURCE + "/query")
async def query(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: MetricQueryInput,
    request: Request,
    runtime: RuntimeDependency,
) -> object:
    async def read(actor: User, key: IntegrationKey) -> object:
        result, lineage = await runtime.analytics.run_query(
            actor, workspace_id, dataset_id, upload_id, body.request()
        )
        return query_body(result, lineage)

    return await runtime.integration_access.perform(
        token(request), workspace_id, dataset_id, "query:read", read
    )


@router.post(SOURCE + "/rows")
async def rows(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: RowsInput,
    request: Request,
    runtime: RuntimeDependency,
) -> object:
    async def read(actor: User, key: IntegrationKey) -> object:
        result, lineage = await runtime.analytics.drill_down(
            actor, workspace_id, dataset_id, upload_id, metric_filters(body.filters), body.limit
        )
        return query_body(result, lineage)

    return await runtime.integration_access.perform(
        token(request), workspace_id, dataset_id, "rows:read", read
    )


@router.get(READ + "/boards/{board_id}")
async def board(
    workspace_id: UUID, board_id: UUID, request: Request, runtime: RuntimeDependency
) -> object:
    board, studies = await runtime.integration_access.board_for_key(
        token(request), workspace_id, board_id
    )
    return {"board": asdict(board), "studies": [study_body(value) for value in studies]}


@router.post(ROOT + "/embeds", status_code=201)
def create_embed(
    workspace_id: UUID, body: EmbedInput, actor: Actor, runtime: RuntimeDependency
) -> object:
    return runtime.integration_access.create_embed(
        actor, workspace_id, body.board_id, body.host_origin, body.expires_seconds
    )


@router.delete(ROOT + "/embeds/{grant_id}", status_code=204)
def revoke_embed(
    workspace_id: UUID, grant_id: UUID, actor: Actor, runtime: RuntimeDependency
) -> Response:
    runtime.integration_access.revoke_embed(actor, workspace_id, grant_id)
    return Response(status_code=204)


@router.get("/embed/{grant_id}/descriptor")
def embed_descriptor(grant_id: UUID, runtime: RuntimeDependency) -> object:
    return runtime.integration_access.embed_descriptor(grant_id)


@router.post("/embed/{grant_id}/exchange")
def exchange_embed(
    grant_id: UUID, body: ExchangeInput, request: Request, runtime: RuntimeDependency
) -> object:
    embedding_origin(request)
    return runtime.integration_access.exchange_embed(
        grant_id, body.bootstrap_secret, body.host_origin
    )


@router.post("/embed/session/board")
async def read_embed(body: EmbedReadInput, request: Request, runtime: RuntimeDependency) -> object:
    embedding_origin(request)
    board, studies = await runtime.integration_access.read_embed(
        body.session_secret, body.host_origin
    )
    return {"board": asdict(board), "studies": [study_body(value) for value in studies]}


class WebhookInput(Input):
    dataset_ids: list[UUID] = Field(min_length=1, max_length=20)
    event_types: list[Literal["job.succeeded", "job.failed", "refresh.accepted"]] = Field(
        min_length=1, max_length=3
    )
    destination: str = Field(min_length=1, max_length=2000)


@router.get(ROOT + "/webhooks")
def list_webhooks(workspace_id: UUID, actor: Actor, runtime: RuntimeDependency) -> object:
    return runtime.webhooks.list_subscriptions(actor, workspace_id)


@router.post(ROOT + "/webhooks", status_code=201)
def create_webhook(
    workspace_id: UUID, body: WebhookInput, actor: Actor, runtime: RuntimeDependency
) -> object:
    return runtime.webhooks.create(
        actor, workspace_id, tuple(body.dataset_ids), tuple(body.event_types), body.destination
    )


@router.post(ROOT + "/webhooks/{subscription_id}/rotate")
def rotate_webhook(
    workspace_id: UUID, subscription_id: UUID, actor: Actor, runtime: RuntimeDependency
) -> object:
    return runtime.webhooks.change(actor, workspace_id, subscription_id, rotate=True)


@router.delete(ROOT + "/webhooks/{subscription_id}", status_code=204)
def revoke_webhook(
    workspace_id: UUID, subscription_id: UUID, actor: Actor, runtime: RuntimeDependency
) -> Response:
    runtime.webhooks.change(actor, workspace_id, subscription_id, rotate=False)
    return Response(status_code=204)


@router.get(ROOT + "/webhooks/{subscription_id}/deliveries")
def webhook_deliveries(
    workspace_id: UUID, subscription_id: UUID, actor: Actor, runtime: RuntimeDependency
) -> object:
    return runtime.webhooks.deliveries(actor, workspace_id, subscription_id)


@router.get(ROOT + "/embeds")
def embed_grants(workspace_id: UUID, actor: Actor, runtime: RuntimeDependency) -> object:
    return runtime.integration_access.embeds(actor, workspace_id)
