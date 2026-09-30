"""Use case: Exposes adaptive views, study versions and department dashboards.

What it does: Validates bounded requests and serializes executed evidence without invented numbers.
"""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from execplus.application.services.studies import OrganizationService, Result, StudyService
from execplus.domain.studies import Study, StudyVersion
from execplus.presentation.routes.analytics import query_body
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["studies"])
ROOT = "/workspaces/{workspace_id}"
SOURCE = ROOT + "/datasets/{dataset_id}/uploads/{upload_id}"


def service(request: Request) -> StudyService:
    value: StudyService = request.app.state.runtime.studies
    return value


def organizations(request: Request) -> OrganizationService:
    value: OrganizationService = request.app.state.runtime.organizations
    return value


Service = Annotated[StudyService, Depends(service)]
Organizations = Annotated[OrganizationService, Depends(organizations)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Named(Input):
    name: str = Field(min_length=1, max_length=100)


class DepartmentInput(Input):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=100)


class StudyInput(Named):
    question: str = Field(min_length=1, max_length=500)
    method: dict[str, Any]
    revision_id: UUID
    understanding_id: UUID


class RerunInput(Input):
    upload_id: UUID
    parent_id: UUID
    revision_id: UUID
    understanding_id: UUID


class ShareInput(Input):
    shared: bool


class BoardInput(Named):
    shared: bool = False
    pins: list[UUID] = Field(default_factory=list, max_length=6)
    expected_version: int = Field(default=0, ge=0)


class DismissInput(Input):
    understanding_id: UUID
    dismissed: list[str] = Field(max_length=12)


def study_body(value: tuple[Study, StudyVersion, list[Result]]) -> dict[str, Any]:
    study, version, results = value
    output: list[dict[str, Any]] = [query_body(result, lineage) for result, lineage in results]
    method = version.method
    limitations = list(version.evidence["limitations"])
    if method["kind"] == "distribution":
        rows = list(output[0]["rows"])
        if method["order"]:
            positions = {value: index for index, value in enumerate(method["order"])}
            rows.sort(
                key=lambda row: (
                    *[str(value) for value in row[:-2]],
                    positions.get(str(row[-2]), len(positions)),
                )
            )
        display = dict(columns=output[0]["columns"], rows=rows)
        counts = [int(row[-1]) for row in rows]
    else:
        totals, present = output[-2], output[-1]
        counts = [int(row[-1]) for row in totals["rows"]]
        present_rows = {tuple(row[:-1]): int(row[-1]) for row in present["rows"]}
        coverage = [
            [
                *row[:-1],
                int(row[-1]),
                present_rows.get(tuple(row[:-1]), 0),
                int(row[-1]) - present_rows.get(tuple(row[:-1]), 0),
            ]
            for row in totals["rows"]
        ]
        display = (
            dict(columns=output[0]["columns"], rows=output[0]["rows"])
            if method["kind"] == "metric"
            else dict(
                columns=[*method["group_by"], "sample_count", "present_count", "missing_count"],
                rows=coverage,
            )
        )
        display["coverage"] = dict(
            columns=[*method["group_by"], "sample_count", "present_count", "missing_count"],
            rows=coverage,
        )
    if not counts or sum(counts) == 0:
        limitations.append("No matching records; there is insufficient data for a finding.")
    elif any(count < 5 for count in counts):
        limitations.append(
            "Some groups have fewer than five records. "
            "Small samples are unstable and not anonymous."
        )
    meaning = next(
        item
        for item in version.evidence["definition"]["columns"]
        if item["name"] == method["column"]
    )
    return dict(
        study=asdict(study),
        version=asdict(version),
        results=output,
        display=display,
        sample_count=sum(counts),
        unit="records"
        if method["kind"] != "metric" or method["aggregation"] == "count"
        else meaning["currency"] or meaning["unit"] or f"by {meaning['unit_column']}",
        limitations=limitations,
    )


@router.get(SOURCE + "/adaptive-views")
async def adaptive_views(
    workspace_id: UUID, dataset_id: UUID, upload_id: UUID, actor: Actor, studies: Service
) -> object:
    return studies.suggest(actor, workspace_id, dataset_id, upload_id)


@router.post(SOURCE + "/adaptive-views/dismissals", status_code=204)
async def dismiss_views(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: DismissInput,
    actor: Actor,
    studies: Service,
) -> Response:
    studies.dismiss(
        actor, workspace_id, dataset_id, upload_id, body.understanding_id, body.dismissed
    )
    return Response(status_code=204)


@router.post(SOURCE + "/studies", status_code=201)
async def create_study(
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
    body: StudyInput,
    actor: Actor,
    studies: Service,
) -> object:
    return study_body(
        await studies.run(
            actor,
            workspace_id,
            dataset_id,
            upload_id,
            body.name,
            body.question,
            body.method,
            body.revision_id,
            body.understanding_id,
        )
    )


@router.get(ROOT + "/datasets/{dataset_id}/studies")
async def list_studies(
    workspace_id: UUID, dataset_id: UUID, actor: Actor, studies: Service
) -> object:
    return studies.list_studies(actor, workspace_id, dataset_id)


@router.get(ROOT + "/study-versions/{version_id}")
async def open_study(
    workspace_id: UUID, version_id: UUID, actor: Actor, studies: Service
) -> object:
    return study_body(await studies.open(actor, workspace_id, version_id))


@router.post(ROOT + "/studies/{study_id}/rerun", status_code=201)
async def rerun_study(
    workspace_id: UUID, study_id: UUID, body: RerunInput, actor: Actor, studies: Service
) -> object:
    study, previous, _ = await studies.open(actor, workspace_id, body.parent_id)
    if study.id != study_id:
        from execplus.domain.errors import AuthorizationError

        raise AuthorizationError("Study version mismatch")
    return study_body(
        await studies.run(
            actor,
            workspace_id,
            study.dataset_id,
            body.upload_id,
            study.name,
            previous.question,
            previous.method,
            body.revision_id,
            body.understanding_id,
            study.id,
            previous.id,
        )
    )


@router.patch(ROOT + "/studies/{study_id}", status_code=204)
async def share_study(
    workspace_id: UUID, study_id: UUID, body: ShareInput, actor: Actor, studies: Service
) -> Response:
    studies.share(actor, workspace_id, study_id, body.shared)
    return Response(status_code=204)


@router.get(ROOT + "/study-comparison")
async def compare_studies(
    workspace_id: UUID, before: UUID, after: UUID, actor: Actor, studies: Service
) -> object:
    value = await studies.compare(actor, workspace_id, before, after)
    return {**value, "before": study_body(value["before"]), "after": study_body(value["after"])}


@router.get(ROOT + "/study-boards")
async def list_boards(workspace_id: UUID, actor: Actor, studies: Service) -> object:
    return [asdict(board) for board in studies.boards(actor, workspace_id)]


@router.post(ROOT + "/study-boards", status_code=201)
async def create_board(
    workspace_id: UUID, body: BoardInput, actor: Actor, studies: Service
) -> object:
    return asdict(
        studies.save_board(
            actor,
            workspace_id,
            body.name,
            body.shared,
            [str(pin) for pin in body.pins],
            expected_version=body.expected_version,
        )
    )


@router.patch(ROOT + "/study-boards/{board_id}")
async def update_board(
    workspace_id: UUID, board_id: UUID, body: BoardInput, actor: Actor, studies: Service
) -> object:
    return asdict(
        studies.save_board(
            actor,
            workspace_id,
            body.name,
            body.shared,
            [str(pin) for pin in body.pins],
            board_id,
            body.expected_version,
        )
    )


@router.get(ROOT + "/study-boards/{board_id}")
async def open_board(workspace_id: UUID, board_id: UUID, actor: Actor, studies: Service) -> object:
    board, values = await studies.open_board(actor, workspace_id, board_id)
    return dict(board=asdict(board), studies=[study_body(value) for value in values])


@router.get("/organizations")
async def list_organizations(actor: Actor, orgs: Organizations) -> object:
    return orgs.list(actor)


@router.post("/organizations", status_code=201)
async def create_organization(body: Named, actor: Actor, orgs: Organizations) -> object:
    return asdict(orgs.create(actor, body.name))


@router.post(ROOT + "/department")
async def attach_department(
    workspace_id: UUID, body: DepartmentInput, actor: Actor, orgs: Organizations
) -> object:
    return asdict(orgs.attach(actor, workspace_id, body.organization_id, body.name))
