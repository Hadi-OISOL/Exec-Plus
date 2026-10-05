"""Use case: Exposes authorized artifact, lineage and quality metadata.

What it does: Maps bounded resource references to existing records without executing analyses.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from execplus.application.services.artifacts import ArtifactService
from execplus.domain.artifacts import ArtifactKind, ArtifactRef
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["artifacts"])
SOURCE = "/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}"
ARTIFACT = "/workspaces/{workspace_id}/datasets/{dataset_id}/artifacts/{kind}/{artifact_id}"


def service(request: Request) -> ArtifactService:
    value: ArtifactService = request.app.state.runtime.artifacts
    return value


Service = Annotated[ArtifactService, Depends(service)]


@router.get(SOURCE + "/artifacts")
def upload_artifacts(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, artifacts: Service
) -> object:
    return artifacts.upload_artifacts(actor, workspace_id, dataset_id, upload_id)


@router.get(SOURCE + "/quality")
def quality(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    actor: Actor,
    artifacts: Service,
    revision_id: UUID | None = None,
) -> object:
    return artifacts.quality(actor, workspace_id, dataset_id, upload_id, revision_id)


@router.get(ARTIFACT)
def describe(
    workspace_id: UUID,
    dataset_id: UUID,
    kind: ArtifactKind,
    artifact_id: UUID,
    actor: Actor,
    artifacts: Service,
    upload_id: UUID | None = None,
) -> object:
    return artifacts.describe(
        actor, ArtifactRef(workspace_id, dataset_id, kind, artifact_id, upload_id)
    )


@router.get(ARTIFACT + "/lineage")
def lineage(
    workspace_id: UUID,
    dataset_id: UUID,
    kind: ArtifactKind,
    artifact_id: UUID,
    actor: Actor,
    artifacts: Service,
    upload_id: UUID | None = None,
) -> object:
    return artifacts.lineage(
        actor, ArtifactRef(workspace_id, dataset_id, kind, artifact_id, upload_id)
    )
