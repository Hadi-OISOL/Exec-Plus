"""Use case: Exposes redacted internal incident review to active staff administrators.

What it does: Bounds list and optimistic transition inputs without accepting raw logs,
customer content, freeform diagnostic messages or occurrence ingestion from clients.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.incidents import IncidentService
from execplus.domain.operational_metrics import AlertPolicy
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["internal-incidents"])


def service(request: Request) -> IncidentService:
    value: IncidentService = request.app.state.runtime.incidents
    return value


Service = Annotated[IncidentService, Depends(service)]


class IncidentChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    status: Literal["acknowledged", "resolved"]


class ThresholdChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, strict=True)
    enabled: bool = Field(strict=True)
    window_minutes: int = Field(ge=1, le=60, strict=True)
    minimum_requests: int = Field(ge=1, le=1_000_000, strict=True)
    minimum_failures: int = Field(ge=1, le=1_000_000, strict=True)
    failure_basis_points: int = Field(ge=0, le=10_000, strict=True)


@router.put("/admin/incidents/thresholds/{category}")
def threshold(
    category: Literal["ingestion", "exports", "analysis", "queue", "other"],
    body: ThresholdChange,
    actor: Actor,
    incidents: Service,
) -> object:
    values = body.model_dump()
    values["version"] = values.pop("expected_version")
    return incidents.change_threshold(actor, AlertPolicy(category=category, **values))


@router.get("/admin/incidents/{incident_id}/references")
def references(incident_id: UUID, actor: Actor, incidents: Service) -> object:
    return incidents.references(actor, incident_id)


@router.get("/admin/incidents")
def incidents(
    actor: Actor,
    incidents: Service,
    status: Literal["active", "open", "acknowledged", "resolved", "all"] = "active",
    limit: int = Query(50, ge=1, le=100),
) -> object:
    return incidents.list(actor, status, limit)


@router.patch("/admin/incidents/{incident_id}")
def change_incident(
    incident_id: UUID, body: IncidentChange, actor: Actor, incidents: Service
) -> object:
    return incidents.change(actor, incident_id, body.expected_version, body.status)
