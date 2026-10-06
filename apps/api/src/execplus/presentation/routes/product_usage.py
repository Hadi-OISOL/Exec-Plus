"""Use case: Exposes bounded workspace product usage and retention.

What it does: Validates reporting windows and delegates role checks to the application service.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder

from execplus.application.services.product_usage import ProductUsageService
from execplus.presentation.routes.workspaces import Actor

router = APIRouter()


def service(request: Request) -> ProductUsageService:
    value: ProductUsageService = request.app.state.runtime.product_usage
    return value


def report_body(value: dict[str, object]) -> object:
    return jsonable_encoder(
        value, custom_encoder={int: lambda item: str(item) if abs(item) > 2**53 - 1 else item}
    )


@router.get("/workspaces/{workspace_id}/product-usage")
def overview(
    workspace_id: UUID,
    actor: Actor,
    usage: Annotated[ProductUsageService, Depends(service)],
    weeks: Annotated[int, Query(ge=1, le=12)] = 8,
) -> object:
    return report_body(usage.overview(actor, workspace_id, weeks))


@router.get("/admin/workspaces/{workspace_id}/product-usage")
def staff_overview(
    workspace_id: UUID,
    actor: Actor,
    usage: Annotated[ProductUsageService, Depends(service)],
    weeks: Annotated[int, Query(ge=1, le=12)] = 8,
) -> object:
    return report_body(usage.staff_overview(actor, workspace_id, weeks))
