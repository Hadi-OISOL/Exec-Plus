"""Use case: Manages reviewable dataset meaning and private user objectives.

What it does: Authorizes definition versions and detects stale context.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, cast
from uuid import UUID, uuid4

from execplus.application.ports import FileParser, ObjectStorage, WorkspaceRepository
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.profiling import Revision, TableData, reconstruct
from execplus.domain.semantics import DatasetView
from execplus.domain.understanding import (
    DOMAINS,
    DataPreference,
    Understanding,
    apply_definition,
    infer_definition,
    questions,
    validate_definition,
)

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


def current_meaning(
    repo: WorkspaceRepository, revision: Revision, view: DatasetView
) -> DatasetView:
    record = repo.latest_understanding(revision.workspace_id, revision.dataset_id)
    if record is None:
        return view
    if record.revision_id != revision.id or record.state != "confirmed":
        raise ClarificationRequiredError(
            "Review and confirm Data understanding for this revision before calculating. "
            "You can still inspect the profile and original file."
        )
    source = {**view.sources[0], "understanding_id": str(record.id)}
    return replace(apply_definition(view, record.definition), sources=(source,))


class UnderstandingService:
    def __init__(
        self, unit_of_work: UnitOfWork, storage: ObjectStorage, parser: FileParser
    ) -> None:
        self.uow = unit_of_work
        self.storage = storage
        self.parser = parser

    def _snapshot(
        self, repo: WorkspaceRepository, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[Revision, TableData]:
        upload = repo.upload(workspace_id, dataset_id, upload_id)
        revision = repo.active_revision(workspace_id, dataset_id, upload_id)
        if revision is None:
            raise IngestionError("not_found", "Profile this upload first.", 404)
        if revision.source_checksum != upload.checksum:
            raise IngestionError(
                "lineage_mismatch", "The retained source no longer matches its revision.", 409
            )
        content = BytesIO(self.storage.read(upload))
        self.parser.parse(
            content, upload.filename, upload.content_type, stored_format=upload.format
        )
        return revision, reconstruct(self.parser.read_table(content, upload.format), revision)

    def overview(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> dict[str, Any]:
        with self.uow() as repo:
            member = repo.membership(workspace_id, actor.id)
            dataset = repo.dataset(workspace_id, dataset_id)
            revision, _ = self._snapshot(repo, workspace_id, dataset_id, upload_id)
            saved = repo.latest_understanding(workspace_id, dataset_id)
            preference = repo.data_preference(workspace_id, dataset_id, actor.id)
            proposal = infer_definition(
                revision.profile, preference.domain_hint if preference else "auto"
            )
            definition = saved.definition if saved else proposal
            state = saved.state if saved else "inferred"
            if saved and saved.revision_id != revision.id:
                state = "needs_review"
                old_columns = {item["name"]: item for item in saved.definition["columns"]}
                definition = {
                    **saved.definition,
                    "columns": [
                        old_columns.get(item["name"], item) for item in proposal["columns"]
                    ],
                }
            return dict(
                revision_id=str(revision.id),
                column_types={
                    item["name"]: item["type"]
                    for item in cast(list[dict[str, Any]], revision.profile["columns"])
                },
                version=saved.version if saved else 0,
                state=state,
                definition=definition,
                proposal=proposal,
                relationship_options=[
                    dict(
                        id=str(path.id),
                        left_dataset_id=str(path.left_dataset_id),
                        left_column=path.left_column,
                        right_dataset_id=str(path.right_dataset_id),
                        right_column=path.right_column,
                        left_name=repo.dataset(workspace_id, path.left_dataset_id).name,
                        right_name=repo.dataset(workspace_id, path.right_dataset_id).name,
                    )
                    for path in repo.join_paths(workspace_id)
                    if dataset_id in {path.left_dataset_id, path.right_dataset_id}
                ],
                questions=questions(definition, revision.profile),
                can_edit=member.role in {"owner", "admin"} or dataset.created_by == actor.id,
                preference=asdict(preference)
                if preference
                else {"domain_hint": "auto", "goal": ""},
                history=[
                    dict(
                        id=str(item.id),
                        version=item.version,
                        state=item.state,
                        revision_id=str(item.revision_id),
                        created_by=str(item.created_by),
                        created_at=item.created_at.isoformat(),
                    )
                    for item in repo.understanding_history(workspace_id, dataset_id)
                ],
            )

    def save(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        revision_id: UUID,
        expected_version: int,
        state: str,
        definition: dict[str, Any],
    ) -> Understanding:
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            member = repo.membership(workspace_id, actor.id)
            dataset = repo.dataset(workspace_id, dataset_id)
            if member.role not in {"owner", "admin"} and dataset.created_by != actor.id:
                raise IngestionError(
                    "forbidden",
                    "The dataset creator or an owner/admin must review shared definitions.",
                    403,
                )
            revision, table = self._snapshot(repo, workspace_id, dataset_id, upload_id)
            latest = repo.latest_understanding(workspace_id, dataset_id)
            if revision.id != revision_id or expected_version != (latest.version if latest else 0):
                raise IngestionError(
                    "definition_conflict",
                    "The data or definitions changed. Reload before saving.",
                    409,
                )
            validated = validate_definition(definition, table, revision.profile, state)
            for relationship in validated["relationships"]:
                path = repo.join_path(workspace_id, UUID(relationship["join_path_id"]))
                if dataset_id not in {path.left_dataset_id, path.right_dataset_id}:
                    raise IngestionError(
                        "not_found", "Relationship not found for this dataset.", 404
                    )
                key = path.left_column if dataset_id == path.left_dataset_id else path.right_column
                column = next(
                    (
                        item
                        for item in cast(list[dict[str, Any]], revision.profile["columns"])
                        if item["name"] == key
                    ),
                    None,
                )
                if relationship["state"] == "confirmed":
                    if column is None:
                        raise IngestionError(
                            "invalid_definition", "The relationship key is missing.", 422
                        )
                    unique_required = (
                        dataset_id == path.right_dataset_id
                        or relationship["cardinality"] == "one_to_one"
                    )
                    if column["missing"] or (
                        unique_required and column["distinct_count"] != len(table.rows)
                    ):
                        raise IngestionError(
                            "invalid_definition",
                            "Relationship keys do not match the declared cardinality.",
                            422,
                        )
            now = datetime.now(timezone.utc)
            record = Understanding(
                uuid4(),
                workspace_id,
                dataset_id,
                upload_id,
                revision.id,
                expected_version + 1,
                state,
                validated,
                actor.id,
                now,
            )
            repo.add(record)
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    f"understanding.{state}",
                    "understanding",
                    record.id,
                    now,
                )
            )
            return record

    def version(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, understanding_id: UUID
    ) -> Understanding:
        with self.uow() as repo:
            repo.membership(workspace_id, actor.id)
            repo.dataset(workspace_id, dataset_id)
            return repo.understanding(workspace_id, dataset_id, understanding_id)

    def preference(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, domain_hint: str, goal: str
    ) -> DataPreference:
        if domain_hint not in DOMAINS or len(goal) > 500 or "\x00" in goal:
            raise IngestionError(
                "invalid_preference",
                "Choose a supported domain and a goal of up to 500 characters.",
                422,
            )
        with self.uow() as repo:
            repo.membership(workspace_id, actor.id)
            repo.dataset(workspace_id, dataset_id)
            preference = DataPreference(
                workspace_id, dataset_id, actor.id, domain_hint, goal.strip()
            )
            repo.save_data_preference(preference)
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    "preference.updated",
                    "dataset",
                    dataset_id,
                    datetime.now(timezone.utc),
                )
            )
            return preference
