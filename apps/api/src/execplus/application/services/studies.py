"""Use case: Runs and reopens private or explicitly shared descriptive studies.

What it does: Retains immutable methods and receipts, enforces pin limits and scopes collaboration.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.workspaces import checked_name
from execplus.domain.errors import AuthorizationError, ClarificationRequiredError
from execplus.domain.evidence import receipt
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.models import CalculationLineage, QueryResult
from execplus.domain.studies import (
    Department,
    Organization,
    Study,
    StudyBoard,
    StudyVersion,
    ViewDismissals,
    count_plan,
    method_request,
    recommendations,
    validated_method,
)
from execplus.domain.understanding import governed_request

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]
Result = tuple[QueryResult, CalculationLineage]


def audit(repo: WorkspaceRepository, actor: User, wid: UUID, action: str, resource: UUID) -> None:
    repo.add(
        AuditEvent(
            uuid4(),
            wid,
            actor.id,
            action,
            action.split(".")[0],
            resource,
            datetime.now(timezone.utc),
        )
    )


def visible(repo: WorkspaceRepository, actor: User, wid: UUID, study_id: UUID) -> Study:
    repo.membership(wid, actor.id)
    study = repo.study(wid, study_id)
    repo.dataset(wid, study.dataset_id)
    if not study.shared and study.owner_id != actor.id:
        raise AuthorizationError("This study is private")
    return study


def owns(owner_id: UUID, actor: User) -> None:
    if owner_id != actor.id:
        raise IngestionError("forbidden", "Only its owner can change this saved work.", 403)


class StudyService:
    def __init__(self, unit_of_work: UnitOfWork, analytics: AnalyticsService) -> None:
        self.uow = unit_of_work
        self.analytics = analytics

    def suggest(self, actor: User, wid: UUID, did: UUID, uid: UUID) -> dict[str, Any]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.upload(wid, did, uid)
            revision = repo.active_revision(wid, did, uid)
            meaning = repo.latest_understanding(wid, did)
            if (
                not meaning
                or not revision
                or meaning.revision_id != revision.id
                or meaning.state != "confirmed"
            ):
                return dict(
                    state="needs_review",
                    recommendations=[],
                    limitations=["Confirm Data understanding for this snapshot first."],
                )
            preference = repo.data_preference(wid, did, actor.id)
            dismissed = repo.view_dismissals(wid, did, actor.id, meaning.id)
        _, _, _, view = self.analytics._context(actor, wid, did, uid)
        if view.sources[0].get("understanding_id") != str(meaning.id):
            raise ClarificationRequiredError("Meaning changed. Reload recommendations.")
        choices = recommendations(view, preference.goal if preference else "")
        return dict(
            state="ready",
            domain=meaning.definition["domain"],
            revision_id=str(revision.id),
            understanding_id=str(meaning.id),
            dismissed=dismissed,
            columns=meaning.definition["columns"],
            recommendations=[item for item in choices if item["id"] not in dismissed],
            limitations=[
                "Only descriptive views are supported. Confirm units for metric suggestions."
            ],
        )

    def dismiss(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        uid: UUID,
        understanding_id: UUID,
        values: list[str],
    ) -> None:
        suggested = self.suggest(actor, wid, did, uid)
        allowed = {item["id"] for item in suggested["recommendations"]} | set(
            suggested.get("dismissed", [])
        )
        if len(values) > 12 or set(values) - allowed:
            raise IngestionError("invalid_dismissal", "Dismiss only current recommendations.", 422)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            meaning = repo.latest_understanding(wid, did)
            if not meaning or meaning.id != understanding_id:
                raise IngestionError("definition_conflict", "Reload current recommendations.", 409)
            repo.set_view_dismissals(
                ViewDismissals(wid, did, actor.id, understanding_id, sorted(set(values)))
            )
            audit(repo, actor, wid, "view.dismissed", did)

    def list_studies(self, actor: User, wid: UUID, did: UUID) -> list[dict[str, Any]]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.dataset(wid, did)
            return [
                {
                    **asdict(item),
                    "versions": [
                        dict(
                            id=str(version.id),
                            number=version.number,
                            upload_id=str(version.upload_id),
                            created_at=version.created_at.isoformat(),
                        )
                        for version in repo.study_versions(wid, item.id)
                    ],
                }
                for item in repo.studies(wid, did)
                if item.shared or item.owner_id == actor.id
            ]

    async def run(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        uid: UUID,
        name: str,
        question: str,
        method: dict[str, Any],
        revision_id: UUID,
        understanding_id: UUID,
        study_id: UUID | None = None,
        parent_id: UUID | None = None,
    ) -> tuple[Study, StudyVersion, list[Result]]:
        name = checked_name(name)
        question = question.strip()
        if not 1 <= len(question) <= 500 or "\x00" in question:
            raise IngestionError(
                "invalid_study", "Provide a question of up to 500 characters.", 422
            )
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            if study_id:
                study = visible(repo, actor, wid, study_id)
                owns(study.owner_id, actor)
                if study.dataset_id != did:
                    raise AuthorizationError("Study source mismatch")
                versions = repo.study_versions(wid, study.id)
                if not versions or versions[-1].id != parent_id or len(versions) >= 50:
                    raise IngestionError(
                        "study_conflict",
                        "Reload the latest study; at most 50 versions are supported.",
                        409,
                    )
                previous = versions[-1]
                method, question, name = previous.method, previous.question, study.name
            elif parent_id:
                raise IngestionError("invalid_study", "A parent needs an existing study.", 422)
        dataset_name, scope, table, view = self.analytics._context(actor, wid, did, uid)
        source = view.sources[0]
        if source.get("revision_id") != str(revision_id) or source.get("understanding_id") != str(
            understanding_id
        ):
            raise ClarificationRequiredError(
                "Review this snapshot's confirmed meaning before running a study."
            )
        method = validated_method(method, view)
        request = method_request(method)
        if method["kind"] == "metric":
            request = governed_request(view, table, request)
            if (view.definition or {}).get(
                "grain"
            ) == "inventory_snapshot" and request.aggregation.value != "count":
                for column in view.columns:
                    if column.type == "date":
                        index = table.headers.index(column.name)
                        if (
                            len({row[index] for row in table.rows}) > 1
                            and column.name not in request.group_by
                            and not any(item.column == column.name for item in request.filters)
                        ):
                            raise ClarificationRequiredError(
                                "Inventory snapshots span dates. "
                                "Group or filter by the snapshot date first."
                            )
        results: list[Result] = []
        if method["kind"] == "metric":
            results.append(
                await self.analytics._execute(actor, did, dataset_name, scope, table, view, request)
            )
        plans = [
            count_plan(
                scope,
                did,
                view,
                request,
                present_only=False,
                distribution=method["kind"] == "distribution",
            )
        ]
        if method["kind"] != "distribution":
            plans.append(count_plan(scope, did, view, request, present_only=True))
        for plan in plans:
            with self.uow() as repo:
                repo.membership(wid, actor.id)
            lineage = CalculationLineage(
                plan.query_id,
                wid,
                did,
                dataset_name,
                len(table.rows),
                method["column"],
                "count",
                tuple(request.group_by),
                tuple(
                    f"{item.column} {item.operator.value} {item.value!r}"
                    for item in request.filters
                ),
                plan.sql,
            )
            try:
                result = await self.analytics.executor.execute(plan, scope, table, view)
            except Exception:
                self.analytics._persist(
                    actor, replace(lineage, receipt=receipt(plan, view.sources, None))
                )
                raise
            lineage = replace(lineage, receipt=receipt(plan, view.sources, result))
            self.analytics._persist(actor, lineage)
            results.append((result, lineage))
        if any(len(result.rows) > 1000 for result, _ in results):
            raise IngestionError(
                "study_too_many_groups", "Use filters to reduce the study below 1,001 groups.", 422
            )
        if method["kind"] == "distribution" and method["order"]:
            actual = {str(row[-2]) for row in results[0][0].rows if row[-2] is not None}
            if actual - set(method["order"]):
                raise IngestionError(
                    "category_order_incomplete",
                    "Include every observed response in the declared order.",
                    422,
                )
        now = datetime.now(timezone.utc)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            revision = repo.active_revision(wid, did, uid)
            meaning = repo.latest_understanding(wid, did)
            if (
                not revision
                or revision.id != revision_id
                or not meaning
                or meaning.id != understanding_id
            ):
                raise IngestionError(
                    "study_conflict", "Source or meaning changed. Run again with current data.", 409
                )
            if study_id:
                study = visible(repo, actor, wid, study_id)
                owns(study.owner_id, actor)
                versions = repo.study_versions(wid, study_id)
                if versions[-1].id != parent_id:
                    raise IngestionError(
                        "study_conflict", "Another rerun finished first. Reload the study.", 409
                    )
                number = versions[-1].number + 1
            else:
                study = Study(uuid4(), wid, did, actor.id, name, False, now)
                repo.add(study)
                number = 1
            upload = repo.upload(wid, did, uid)
            version = StudyVersion(
                uuid4(),
                wid,
                study.id,
                number,
                uid,
                parent_id,
                question,
                method,
                dict(
                    method_version="descriptive-v1",
                    query_ids=[str(item[0].query_id) for item in results],
                    sources=list(view.sources),
                    preparation=revision.recipe,
                    preparation_version=revision.algorithm,
                    definition=meaning.definition,
                    source_uploaded_at=upload.created_at.isoformat(),
                    component=self._component(method, view),
                    limitations=[
                        "Descriptive snapshot results; no causal or population inference.",
                        "A saved snapshot is historical and does not automatically refresh.",
                    ],
                ),
                actor.id,
                now,
            )
            repo.add(version)
            audit(repo, actor, wid, "study.rerun" if number > 1 else "study.created", version.id)
        return study, version, results

    def _component(self, method: dict[str, Any], view: Any) -> str:
        if method["kind"] == "missingness":
            return "table"
        if method["kind"] == "distribution":
            return "distribution"
        if not method["group_by"]:
            return "card"
        return "line" if view.column(method["group_by"][0]).type == "date" else "bar"

    async def open(
        self, actor: User, wid: UUID, version_id: UUID
    ) -> tuple[Study, StudyVersion, list[Result]]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            version = repo.study_version(wid, version_id)
            study = visible(repo, actor, wid, version.study_id)
        results = []
        for value in version.evidence["query_ids"]:
            with self.uow() as repo:
                visible(repo, actor, wid, version.study_id)
            results.append(await self.analytics.replay(actor, wid, UUID(value)))
        with self.uow() as repo:
            study = visible(repo, actor, wid, version.study_id)
            audit(repo, actor, wid, "study.opened", version.id)
        return study, version, results

    def share(self, actor: User, wid: UUID, study_id: UUID, shared: bool) -> None:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            study = visible(repo, actor, wid, study_id)
            owns(study.owner_id, actor)
            repo.set_study_shared(wid, study_id, shared)
            audit(repo, actor, wid, "study.shared" if shared else "study.unshared", study_id)

    def boards(self, actor: User, wid: UUID) -> tuple[StudyBoard, ...]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            return tuple(
                item for item in repo.study_boards(wid) if item.shared or item.owner_id == actor.id
            )

    def save_board(
        self,
        actor: User,
        wid: UUID,
        name: str,
        shared: bool,
        pins: list[str],
        board_id: UUID | None = None,
        expected_version: int = 0,
    ) -> StudyBoard:
        name = checked_name(name)
        if len(pins) > 6 or len(set(pins)) != len(pins):
            raise IngestionError(
                "pin_limit", "A dashboard supports at most six distinct pinned results.", 422
            )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            if board_id:
                board = repo.study_board(wid, board_id)
                owns(board.owner_id, actor)
                if board.version != expected_version:
                    raise IngestionError(
                        "board_conflict", "Reload the dashboard before editing.", 409
                    )
            elif expected_version:
                raise IngestionError(
                    "board_conflict", "A new dashboard starts at version zero.", 409
                )
            for pin in pins:
                version = repo.study_version(wid, UUID(pin))
                study = visible(repo, actor, wid, version.study_id)
                if shared and not study.shared:
                    raise IngestionError(
                        "private_pin",
                        "Share each study explicitly before sharing its dashboard.",
                        422,
                    )
            value = StudyBoard(
                board_id or uuid4(),
                wid,
                actor.id,
                name,
                shared,
                expected_version + 1,
                pins,
                board.created_at if board_id else datetime.now(timezone.utc),
            )
            if board_id:
                repo.set_study_board(value)
            else:
                repo.add(value)
            audit(
                repo, actor, wid, "dashboard.updated" if board_id else "dashboard.created", value.id
            )
            return value

    async def open_board(
        self, actor: User, wid: UUID, board_id: UUID
    ) -> tuple[StudyBoard, list[Any]]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            board = repo.study_board(wid, board_id)
            if not board.shared and board.owner_id != actor.id:
                raise AuthorizationError("This dashboard is private")
        results = [await self.open(actor, wid, UUID(pin)) for pin in board.pins]
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            current = repo.study_board(wid, board_id)
            if current != board:
                raise IngestionError("board_conflict", "This dashboard changed. Reload it.", 409)
            for study, _, _ in results:
                visible(repo, actor, wid, study.id)
            audit(repo, actor, wid, "dashboard.opened", board.id)
        return board, results

    async def compare(self, actor: User, wid: UUID, before: UUID, after: UUID) -> dict[str, Any]:
        left = await self.open(actor, wid, before)
        right = await self.open(actor, wid, after)
        if left[0].id != right[0].id:
            raise IngestionError(
                "comparison_mismatch", "Compare two versions of the same study.", 422
            )
        compatible = (
            left[1].method == right[1].method
            and left[1].evidence["definition"] == right[1].evidence["definition"]
        )
        differences = []
        if compatible and left[1].method["kind"] == "metric":
            left_rows = {tuple(row[:-1]): row[-1] for row in left[2][0][0].rows}
            right_rows = {tuple(row[:-1]): row[-1] for row in right[2][0][0].rows}
            with localcontext() as context:
                context.prec = 60
                for key in left_rows.keys() | right_rows.keys():
                    first, second = left_rows.get(key), right_rows.get(key)
                    differences.append(
                        dict(
                            group=key,
                            before=str(first) if first is not None else None,
                            after=str(second) if second is not None else None,
                            delta=str(Decimal(str(second)) - Decimal(str(first)))
                            if first is not None and second is not None
                            else None,
                        )
                    )
        with self.uow() as repo:
            visible(repo, actor, wid, left[0].id)
            audit(repo, actor, wid, "study.compared", right[1].id)
        return dict(
            before=left,
            after=right,
            comparable=compatible,
            differences=differences,
            limitation="Differences describe snapshots, not causes."
            if compatible
            else "Definitions or methods changed. Compare evidence; no delta is asserted.",
        )


class OrganizationService:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self.uow = unit_of_work

    def list(self, actor: User) -> list[dict[str, Any]]:
        with self.uow() as repo:
            return [
                {
                    **asdict(item),
                    "departments": [
                        asdict(department) for department in repo.departments(item.id, actor.id)
                    ],
                }
                for item in repo.organizations(actor.id)
            ]

    def create(self, actor: User, name: str) -> Organization:
        record = Organization(uuid4(), actor.id, checked_name(name), datetime.now(timezone.utc))
        with self.uow() as repo:
            repo.user(actor.id)
            repo.add(record)
        return record

    def attach(self, actor: User, wid: UUID, organization_id: UUID, department: str) -> Department:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            member = repo.membership(wid, actor.id)
            organization = repo.organization(organization_id)
            if member.role != "owner" or organization.owner_id != actor.id:
                raise IngestionError(
                    "forbidden", "Own both the organization and workspace to group them.", 403
                )
            current = repo.department(wid)
            if current and current.organization_id != organization_id:
                raise IngestionError(
                    "organization_conflict",
                    "This workspace already belongs to an organization.",
                    409,
                )
            record = Department(wid, organization_id, checked_name(department))
            repo.set_department(record)
            audit(repo, actor, wid, "department.updated", wid)
            return record
