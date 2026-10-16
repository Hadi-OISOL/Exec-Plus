"""Use case: Exposes owner usage summaries and explicit operator accounting controls.

What it does: Validates bounded configuration and independent settlement references,
without exposing prompts, tokens, credentials or public self-assigned paid plans.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.usage_metering import UsageMeteringService, now
from execplus.domain.ingestion import IngestionError
from execplus.domain.usage_metering import UsagePolicy, UsagePrice
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["model-usage"])


def service(request: Request) -> UsageMeteringService:
    value: UsageMeteringService = request.app.state.runtime.usage_metering
    return value


Service = Annotated[UsageMeteringService, Depends(service)]
Money = Annotated[Decimal, Field(ge=0, le=10**12, max_digits=25, decimal_places=12)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PriceInput(Input):
    id: UUID
    provider: str = Field(min_length=1, max_length=160)
    model: str = Field(min_length=1, max_length=160)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    input_per_million: Money
    output_per_million: Money
    cached_input_per_million: Money | None = None
    evidence_ref: str = Field(min_length=1, max_length=160)
    effective_at: datetime


class AllowanceInput(Input):
    expected_version: int = Field(ge=0, strict=True)
    plan_key: str = Field(min_length=1, max_length=80)
    starts_at: datetime
    ends_at: datetime
    max_attempts: int | None = Field(default=None, ge=1, le=10_000_000, strict=True)
    max_in_flight: int | None = Field(default=None, ge=1, le=10_000, strict=True)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    spend_limit: Money | None = None
    reservation_per_attempt: Money | None = None


class ReconcileInput(Input):
    cost: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    evidence_kind: Literal["provider_usage_record", "provider_invoice_record"]
    evidence_ref: str = Field(min_length=1, max_length=120)


class RecoverInput(Input):
    older_than: datetime


@router.get("/workspaces/{workspace_id}/model-usage")
def summary(
    workspace_id: UUID, actor: Actor, metering: Service, days: int = Query(30, ge=1, le=366)
) -> object:
    end = now()
    return metering.summary(actor.id, workspace_id, end - timedelta(days=days), end)


@router.post("/admin/model-prices", status_code=201)
def configure_price(body: PriceInput, actor: Actor, metering: Service) -> object:
    try:
        price = UsagePrice(
            body.id,
            body.provider,
            body.model,
            body.currency,
            body.input_per_million,
            body.output_per_million,
            body.cached_input_per_million,
            body.evidence_ref,
            actor.id,
            body.effective_at,
        )
    except ValueError:
        raise IngestionError(
            "usage_price", "Review the explicit price configuration.", 422
        ) from None
    metering.set_price(actor.id, price)
    return {"id": price.id, "configured": True}


@router.put("/admin/workspaces/{workspace_id}/model-allowance")
def configure_allowance(
    workspace_id: UUID, body: AllowanceInput, actor: Actor, metering: Service
) -> object:
    try:
        policy = UsagePolicy(
            uuid4(),
            workspace_id,
            body.expected_version + 1,
            body.plan_key,
            body.starts_at,
            body.ends_at,
            body.max_attempts,
            body.max_in_flight,
            body.currency,
            body.spend_limit,
            body.reservation_per_attempt,
            actor.id,
        )
    except ValueError:
        raise IngestionError(
            "usage_policy", "Review the explicit workspace allowance.", 422
        ) from None
    metering.set_policy(actor.id, policy, body.expected_version)
    return {"id": policy.id, "version": policy.version}


@router.get("/admin/workspaces/{workspace_id}/model-usage/pending")
def pending(
    workspace_id: UUID, actor: Actor, metering: Service, limit: int = Query(50, ge=1, le=100)
) -> object:
    values = metering.pending(actor.id, workspace_id, limit)
    return {
        "attempts": [
            {
                "id": value.id,
                "operation_id": value.attribution.operation_id,
                "operation": value.attribution.operation,
                "provider": value.provider,
                "model": value.model,
                "created_at": value.created_at,
                "state": value.state,
                "outcome": value.outcome,
                "currency": value.currency,
                "held_exposure": str(value.held_exposure),
                "version": value.version,
            }
            for value in values
        ],
        "limit": limit,
    }


@router.post("/admin/workspaces/{workspace_id}/model-usage/recover")
def recover(workspace_id: UUID, body: RecoverInput, actor: Actor, metering: Service) -> object:
    return metering.recover(actor.id, workspace_id, body.older_than)


@router.post("/admin/workspaces/{workspace_id}/model-usage/{attempt_id}/reconcile")
def reconcile(
    workspace_id: UUID, attempt_id: UUID, body: ReconcileInput, actor: Actor, metering: Service
) -> object:
    try:
        result = metering.reconcile(
            actor.id,
            workspace_id,
            attempt_id,
            body.cost,
            body.currency,
            body.evidence_kind,
            body.evidence_ref,
        )
    except ValueError:
        raise IngestionError(
            "usage_evidence", "Review the independent usage evidence.", 422
        ) from None
    return {
        "id": result.id,
        "state": result.state,
        "version": result.version,
        "cost": str(result.cost),
        "currency": result.currency,
    }
