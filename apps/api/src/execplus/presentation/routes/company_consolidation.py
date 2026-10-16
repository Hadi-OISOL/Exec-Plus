"""Use case: Exposes explicit private company worksheet preparation and delivery.

What it does: Accepts bounded source, mapping, rate and journal inputs while keeping
source authorization and exact calculation in application and domain services.
"""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.company_consolidation import CompanyConsolidationService
from execplus.application.services.consolidation_exports import ConsolidationExportService
from execplus.presentation.routes.result_exports import Format, attachment
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["company-consolidation"])
ROOT = "/organizations/{organization_id}/consolidations"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Input):
    workspace_id: UUID
    dataset_id: UUID
    upload_id: UUID


class Fields(Source):
    revision_id: UUID
    understanding_id: UUID
    account_column: str = Field(min_length=1, max_length=200)
    amount_column: str = Field(min_length=1, max_length=200)
    counterparty_column: str | None = Field(default=None, min_length=1, max_length=200)
    currency: str = Field(pattern="^[A-Z]{3}$")


class Counterparty(Input):
    raw_value: str = Field(min_length=1, max_length=200)
    company_id: UUID


class Company(Fields):
    period_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    period_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    sign_convention: Literal["debit_positive", "credit_positive"]
    coverage_confirmed: Literal[True]
    counterparties: list[Counterparty] = Field(default_factory=list, max_length=1000)


class Mapping(Input):
    account: str = Field(min_length=1, max_length=200)
    group_account: str = Field(min_length=1, max_length=200)
    rate_key: str = Field(min_length=1, max_length=80)


class Rate(Input):
    key: str = Field(min_length=1, max_length=80)
    basis: Literal["closing", "transaction_average", "historical"]
    value: str = Field(min_length=1, max_length=100)
    as_of: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reference: str = Field(min_length=1, max_length=500)


class Entry(Input):
    company_id: UUID
    account: str = Field(min_length=1, max_length=200)
    counterparty: UUID
    amount: str = Field(min_length=1, max_length=100)


class Elimination(Input):
    name: str = Field(min_length=1, max_length=200)
    entries: list[Entry] = Field(min_length=2, max_length=64)


class Worksheet(Input):
    reporting_currency: str = Field(pattern="^[A-Z]{3}$")
    assumptions_confirmed: Literal[True]
    mappings: dict[str, Annotated[list[Mapping], Field(min_length=1, max_length=256)]] = Field(
        min_length=2, max_length=8
    )
    rates: dict[str, Annotated[list[Rate], Field(min_length=1, max_length=256)]] = Field(
        min_length=2, max_length=8
    )
    eliminations: list[Elimination] = Field(default_factory=list, max_length=100)


class Create(Input):
    name: str = Field(min_length=1, max_length=100)
    companies: list[Company] = Field(min_length=2, max_length=8)
    worksheet: Worksheet


def worksheets(request: Request) -> CompanyConsolidationService:
    value: CompanyConsolidationService = request.app.state.runtime.consolidations
    return value


def exports(request: Request) -> ConsolidationExportService:
    value: ConsolidationExportService = request.app.state.runtime.consolidation_exports
    return value


Service = Annotated[CompanyConsolidationService, Depends(worksheets)]
Exports = Annotated[ConsolidationExportService, Depends(exports)]


@router.get(ROOT + "/options")
def options(organization_id: UUID, actor: Actor, service: Service) -> dict[str, Any]:
    return service.options(actor, organization_id)


@router.post(ROOT + "/source-options")
async def source_options(
    organization_id: UUID, body: Source, actor: Actor, service: Service
) -> dict[str, Any]:
    return await service.source_options(actor, organization_id, body.model_dump(mode="json"))


@router.post(ROOT + "/preview-company")
async def preview(
    organization_id: UUID, body: Fields, actor: Actor, service: Service
) -> dict[str, Any]:
    return await service.preview_company(actor, organization_id, body.model_dump(mode="json"))


@router.get(ROOT)
def listing(organization_id: UUID, actor: Actor, service: Service) -> list[dict[str, Any]]:
    return service.list(actor, organization_id)


@router.post(ROOT, status_code=201)
async def create(
    organization_id: UUID, body: Create, actor: Actor, service: Service
) -> dict[str, Any]:
    return await service.create(actor, organization_id, body.model_dump(mode="json"))


@router.get(ROOT + "/{run_id}")
async def reopen(
    organization_id: UUID, run_id: UUID, actor: Actor, service: Service
) -> dict[str, Any]:
    return await service.open(actor, organization_id, run_id)


@router.get(ROOT + "/{run_id}/export.{format}")
async def download(
    organization_id: UUID, run_id: UUID, format: Format, actor: Actor, service: Exports
) -> Response:
    return attachment(await service.download(actor, organization_id, run_id, format))
