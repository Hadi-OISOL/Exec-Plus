"""Use case: Exposes approved source selections and explicit private import actions.

What it does: Keeps endpoints and secret references in operator-only registration,
while owners select allowlisted tables/fields and reopen idempotent retained imports.
"""

from dataclasses import asdict
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.source_imports import SourceImportService
from execplus.domain.source_imports import (
    ImportSelection,
    PostgresSource,
    SourceImport,
    SourceTable,
)
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["source-imports"])


def service(request: Request) -> SourceImportService:
    result: SourceImportService = request.app.state.runtime.source_imports
    return result


Service = Annotated[SourceImportService, Depends(service)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TableInput(Input):
    schema_name: str = Field(min_length=1, max_length=63)
    table: str = Field(min_length=1, max_length=63)
    columns: list[str] = Field(min_length=1, max_length=50)

    def selection(self) -> SourceTable:
        return SourceTable(self.schema_name, self.table, tuple(self.columns))


class RegisterInput(Input):
    expected_version: int = Field(ge=0, strict=True)
    label: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=253)
    address: str = Field(min_length=1, max_length=45)
    port: int = Field(ge=1, le=65535, strict=True)
    database: str = Field(min_length=1, max_length=63)
    secret_ref: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    tables: list[TableInput] = Field(min_length=1, max_length=20)
    enabled: bool = Field(default=True, strict=True)
    max_rows: int = Field(default=10000, ge=1, le=10000, strict=True)
    max_bytes: int = Field(default=20 * 1024 * 1024, ge=1, le=20 * 1024 * 1024, strict=True)
    timeout_seconds: int = Field(default=20, ge=1, le=30, strict=True)


class ImportInput(TableInput):
    request_id: UUID
    source_id: UUID
    source_version: int = Field(ge=1, strict=True)
    mode: Literal["upload", "refresh"] = "upload"
    expected_feed_version: int | None = Field(default=None, ge=1, strict=True)


class VersionInput(Input):
    expected_version: int = Field(ge=1, strict=True)


def public_import(value: SourceImport) -> dict[str, object]:
    result = asdict(value)
    result.pop("membership_created_at")
    result.pop("access_reference")
    result["notice"] = (
        "Imported snapshots need meaning review before calculation. "
        "Staged refreshes use the existing explicit review and activation."
    )
    return result


@router.get("/workspaces/{wid}/sources")
def catalog(wid: UUID, actor: Actor, sources: Service) -> object:
    return {"sources": sources.catalog(actor, wid)}


@router.put("/admin/workspaces/{wid}/sources/{source_id}")
def register(
    wid: UUID, source_id: UUID, body: RegisterInput, actor: Actor, sources: Service
) -> object:
    return sources.register(
        actor,
        PostgresSource(
            source_id,
            wid,
            body.expected_version + 1,
            body.label,
            body.host,
            body.address,
            body.port,
            body.database,
            body.secret_ref,
            tuple(table.selection() for table in body.tables),
            body.enabled,
            body.max_rows,
            body.max_bytes,
            body.timeout_seconds,
        ),
        body.expected_version,
    )


@router.post("/workspaces/{wid}/sources/{source_id}/disconnect")
def disconnect(
    wid: UUID, source_id: UUID, body: VersionInput, actor: Actor, sources: Service
) -> object:
    return sources.disconnect(actor, wid, source_id, body.expected_version)


@router.post("/workspaces/{wid}/datasets/{did}/source-imports", status_code=201)
def start(wid: UUID, did: UUID, body: ImportInput, actor: Actor, sources: Service) -> object:
    value = sources.start(
        actor,
        wid,
        body.request_id,
        ImportSelection(
            body.source_id,
            body.source_version,
            did,
            body.selection(),
            body.mode,
            body.expected_feed_version,
        ),
    )
    return public_import(value)


@router.get("/workspaces/{wid}/datasets/{did}/source-imports")
def history(wid: UUID, did: UUID, actor: Actor, sources: Service) -> object:
    return {"imports": [public_import(value) for value in sources.history(actor, wid, did)]}


@router.get("/workspaces/{wid}/source-imports/{import_id}")
def open_import(wid: UUID, import_id: UUID, actor: Actor, sources: Service) -> object:
    return public_import(sources.open(actor, wid, import_id))


@router.post("/admin/workspaces/{wid}/source-imports/{import_id}/recover")
def recover(wid: UUID, import_id: UUID, actor: Actor, sources: Service) -> object:
    value = sources.recover(actor, wid, import_id)
    return dict(id=str(value.id), status=value.status, failure_code=value.failure_code)


@router.get("/admin/workspaces/{wid}/source-imports/pending")
def pending(wid: UUID, actor: Actor, sources: Service) -> object:
    return {"imports": sources.pending(actor, wid)}
