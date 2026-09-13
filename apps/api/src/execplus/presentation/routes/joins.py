"""Use case: Exposes cross-dataset join path declarations and joined queries.

What it does: Maps validated requests to JoinService and returns executed
results alongside their calculation lineage.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.joins import JoinService
from execplus.domain.join_paths import JoinPath
from execplus.domain.semantics import AggregationKind, MetricRequest
from execplus.presentation.routes.analytics import FilterInput, metric_filters, query_body
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["joins"])


def get_join_service(request: Request) -> JoinService:
    service: JoinService = request.app.state.runtime.joins
    return service


Service = Annotated[JoinService, Depends(get_join_service)]


class JoinPathInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left_dataset_id: UUID
    left_column: str = Field(min_length=1, max_length=100)
    right_dataset_id: UUID
    right_column: str = Field(min_length=1, max_length=100)


class JoinQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left_upload_id: UUID
    right_upload_id: UUID
    metric: str = Field(min_length=1, max_length=100)
    aggregation: AggregationKind
    group_by: list[str] = Field(default_factory=list, max_length=10)
    filters: list[FilterInput] = Field(default_factory=list, max_length=20)

    def request(self) -> MetricRequest:
        return MetricRequest(
            metric=self.metric,
            aggregation=self.aggregation,
            group_by=tuple(self.group_by),
            filters=metric_filters(self.filters),
        )


def _join_path_body(path: JoinPath) -> dict[str, object]:
    return {
        "id": str(path.id),
        "workspace_id": str(path.workspace_id),
        "left_dataset_id": str(path.left_dataset_id),
        "left_column": path.left_column,
        "right_dataset_id": str(path.right_dataset_id),
        "right_column": path.right_column,
        "created_by": str(path.created_by),
        "created_at": path.created_at.isoformat(),
    }


@router.post("/workspaces/{workspace_id}/join-paths", status_code=201)
async def create_join_path(
    workspace_id: UUID, body: JoinPathInput, actor: Actor, service: Service
) -> object:
    path = await service.create_join_path(
        actor,
        workspace_id,
        body.left_dataset_id,
        body.left_column,
        body.right_dataset_id,
        body.right_column,
    )
    return _join_path_body(path)


@router.get("/workspaces/{workspace_id}/join-paths")
async def list_join_paths(workspace_id: UUID, actor: Actor, service: Service) -> object:
    paths = await service.list_join_paths(actor, workspace_id)
    return [_join_path_body(path) for path in paths]


@router.post("/workspaces/{workspace_id}/join-paths/{join_path_id}/query")
async def query_join_path(
    workspace_id: UUID,
    join_path_id: UUID,
    body: JoinQueryInput,
    actor: Actor,
    service: Service,
) -> object:
    result, lineage = await service.run_join_query(
        actor,
        workspace_id,
        join_path_id,
        body.left_upload_id,
        body.right_upload_id,
        body.request(),
    )
    return query_body(result, lineage)
