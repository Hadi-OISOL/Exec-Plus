"""Use case: Exposes connecting an external data platform and importing one of its sources.

What it does: Runs the browser redirects and delegates browsing, credentials and imports.
"""

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from execplus.application.services.connectors import ConnectorService
from execplus.domain.ingestion import IngestionError
from execplus.presentation.routes.workspaces import Actor, public_upload

router = APIRouter(tags=["connectors"])


def optional_service(request: Request) -> ConnectorService | None:
    result: ConnectorService | None = request.app.state.runtime.connectors
    return result


def service(request: Request) -> ConnectorService:
    result = optional_service(request)
    if result is None:
        raise IngestionError("unknown_connector", "No data platforms are configured.", 404)
    return result


Service = Annotated[ConnectorService, Depends(service)]
OptionalService = Annotated[ConnectorService | None, Depends(optional_service)]


class CredentialsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, str] = Field(max_length=12)

    @field_validator("values")
    @classmethod
    def bounded(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(key) > 40 or len(item) > 500 for key, item in value.items()):
            raise ValueError("Credential values are too long")
        return value


class ImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=600)


def finish(service: ConnectorService, query: str) -> RedirectResponse:
    return RedirectResponse(f"{service.web_origin}/workspace?{query}", status_code=302)


@router.get("/connectors")
async def catalog(actor: Actor, service: OptionalService) -> object:
    return await run_in_threadpool(service.catalog, actor) if service else []


@router.post("/connectors/{provider}/connect")
async def connect(provider: str, actor: Actor, service: Service) -> object:
    return dict(url=await run_in_threadpool(service.start_connect, actor, provider))


@router.get("/connectors/{provider}/callback")
async def callback(provider: str, request: Request, service: Service) -> Response:
    query = dict(request.query_params)
    code, state = query.pop("code", ""), query.pop("state", "")
    if query.get("error") or not code or not state:
        return finish(service, f"connector_error=connector_denied&connector={quote(provider)}")
    try:
        await run_in_threadpool(service.finish_connect, provider, code, state, query)
    except IngestionError as failure:
        return finish(service, f"connector_error={quote(failure.code)}&connector={quote(provider)}")
    return finish(service, f"connector_connected={quote(provider)}")


@router.post("/connectors/{provider}/credentials")
async def credentials(
    provider: str, body: CredentialsInput, actor: Actor, service: Service
) -> object:
    account = await run_in_threadpool(service.save_credentials, actor, provider, body.values)
    return dict(connected=True, account=account)


@router.get("/connectors/{provider}/status")
async def status(provider: str, actor: Actor, service: Service) -> object:
    return await run_in_threadpool(service.status, actor, provider)


@router.delete("/connectors/{provider}", status_code=204)
async def disconnect(provider: str, actor: Actor, service: Service) -> Response:
    await run_in_threadpool(service.disconnect, actor, provider)
    return Response(status_code=204)


@router.get("/connectors/{provider}/sources")
async def sources(
    provider: str,
    actor: Actor,
    service: Service,
    parent: Annotated[str | None, Query(max_length=600)] = None,
) -> object:
    return await run_in_threadpool(service.browse, actor, provider, parent)


@router.post(
    "/workspaces/{workspace_id}/datasets/{dataset_id}/connectors/{provider}/import",
    status_code=201,
)
async def import_source(
    workspace_id: UUID,
    dataset_id: UUID,
    provider: str,
    body: ImportInput,
    actor: Actor,
    service: Service,
) -> object:
    upload = await run_in_threadpool(
        service.import_source, actor, workspace_id, dataset_id, provider, body.source_id
    )
    return public_upload(upload)
