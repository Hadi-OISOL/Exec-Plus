"""Use case: Imports approved PostgreSQL snapshots through normal review boundaries.

What it does: Rechecks versioned source and actor authority in the exact upload or
staged-refresh transaction, with idempotent bounded work and private import history.
"""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any, cast
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.dataset_access import (
    require_full_access,
    require_workspace_access,
)
from execplus.application.services.refresh import RefreshService
from execplus.application.services.workspaces import UnitOfWork, WorkspaceService
from execplus.application.source_ports import SourceExtractor
from execplus.domain.dataset_access import denied
from execplus.domain.ingestion import AuditEvent, IngestionError, Upload, User
from execplus.domain.operations import StaffAudit
from execplus.domain.profiling import Revision
from execplus.domain.refresh import RefreshCandidate
from execplus.domain.source_imports import (
    SOURCE_FAILURES,
    ImportSelection,
    PostgresSource,
    RegisteredSource,
    SourceImport,
    SourceSnapshot,
    invalid,
    snapshot_metadata,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def owner(repo: WorkspaceRepository, actor: User, wid: UUID) -> None:
    if repo.membership(wid, actor.id).role != "owner":
        raise invalid("source_owner", "Only the workspace owner can manage source imports.", 403)


def operator(repo: WorkspaceRepository, actor: User) -> None:
    grant = repo.staff_grant(actor.id, lock=True)
    if grant is None or grant.revoked_at is not None or grant.role != "admin":
        raise invalid("staff_required", "This action requires active staff access.", 403)


def audit(repo: WorkspaceRepository, actor: User, wid: UUID, action: str, rid: UUID) -> None:
    repo.add(AuditEvent(uuid4(), wid, actor.id, action, "source_import", rid, now()))


def public_source(value: RegisteredSource) -> dict[str, Any]:
    source = value.source
    return dict(
        id=str(source.id),
        version=source.version,
        label=source.label,
        enabled=source.enabled,
        tables=[asdict(table) for table in source.tables],
        max_rows=source.max_rows,
        max_bytes=source.max_bytes,
        notice="Imports retain a complete snapshot. Review meanings before calculation.",
    )


class SourceImportService:
    def __init__(
        self,
        uow: UnitOfWork,
        extractor: SourceExtractor,
        uploads: WorkspaceService,
        refresh: RefreshService,
    ) -> None:
        self.uow, self.extractor, self.uploads, self.refresh = uow, extractor, uploads, refresh

    def register(self, actor: User, value: PostgresSource, expected_version: int) -> dict[str, Any]:
        if value.version != expected_version + 1:
            raise invalid("source_version", "Use the next source configuration version.", 409)
        with self.uow() as repo:
            operator(repo, actor)
            repo.workspace(value.workspace_id, lock=True)
            owner(repo, actor, value.workspace_id)
            require_workspace_access(repo, actor, value.workspace_id)
            sources = repo.registered_sources(value.workspace_id)
            prior = next((item for item in sources if item.source.id == value.id), None)
            if expected_version != (prior.source.version if prior else 0):
                raise invalid("source_version", "Source configuration changed; reopen it.", 409)
            if prior is None and len(sources) >= 20:
                raise invalid(
                    "source_limit", "This workspace already has twenty registered sources."
                )
            registered = RegisteredSource(value, actor.id, now())
            repo.add_registered_source(registered)
            repo.add_staff_audit(
                StaffAudit(
                    uuid4(),
                    actor.id,
                    "source.registered",
                    "api",
                    "success",
                    now(),
                    value.workspace_id,
                    value.id,
                )
            )
            audit(repo, actor, value.workspace_id, "source.registered", value.id)
            return public_source(registered)

    def catalog(self, actor: User, wid: UUID) -> list[dict[str, Any]]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            owner(repo, actor, wid)
            require_workspace_access(repo, actor, wid)
            return [public_source(value) for value in repo.registered_sources(wid)]

    def disconnect(
        self, actor: User, wid: UUID, source_id: UUID, expected_version: int
    ) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            owner(repo, actor, wid)
            require_workspace_access(repo, actor, wid)
            prior = repo.registered_source(wid, source_id)
            if prior.source.version != expected_version:
                raise invalid("source_version", "Source configuration changed; reopen it.", 409)
            updated = RegisteredSource(
                replace(prior.source, version=expected_version + 1, enabled=False), actor.id, now()
            )
            repo.add_registered_source(updated)
            audit(repo, actor, wid, "source.disconnected", source_id)
            return public_source(updated)

    def _current(self, repo: WorkspaceRepository, actor: User, value: SourceImport) -> None:
        owner(repo, actor, value.workspace_id)
        member = repo.membership(value.workspace_id, actor.id)
        access = require_full_access(repo, actor, value.workspace_id, value.selection.dataset_id)
        if (
            member.created_at != value.membership_created_at
            or access.reference() != value.access_reference
        ):
            raise denied()

    def open(self, actor: User, wid: UUID, import_id: UUID) -> SourceImport:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            value = repo.source_import(wid, actor.id, import_id)
            self._current(repo, actor, value)
            if value.upload_id is not None:
                repo.upload(wid, value.selection.dataset_id, value.upload_id)
            return value

    def history(self, actor: User, wid: UUID, did: UUID) -> list[SourceImport]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            owner(repo, actor, wid)
            require_full_access(repo, actor, wid, did)
            values = []
            for value in repo.source_imports(wid, actor.id, did):
                try:
                    self._current(repo, actor, value)
                except IngestionError as exc:
                    if exc.status != 404:
                        raise
                else:
                    values.append(value)
            return values

    def _finish(
        self,
        repo: WorkspaceRepository,
        actor: User,
        value: SourceImport,
        snapshot: SourceSnapshot,
        upload: Upload,
        candidate: RefreshCandidate | None,
    ) -> None:
        self._current(repo, actor, value)
        current = repo.registered_source(value.workspace_id, value.selection.source_id).source
        actual = repo.source_import(value.workspace_id, actor.id, value.id)
        if (
            current.version != value.selection.source_version
            or not current.enabled
            or actual != value
            or snapshot.source_version != current.version
        ):
            raise invalid(
                "source_import_conflict", "The source or import changed; start a new import.", 409
            )
        revision = repo.active_revision(value.workspace_id, value.selection.dataset_id, upload.id)
        columns = cast(list[dict[str, Any]], revision.profile["columns"]) if revision else []
        if (
            revision is None
            or [column["name"] for column in columns] != list(value.selection.table.columns)
            or snapshot.extracted_at < value.created_at
            or snapshot.extracted_at > now()
            or upload.size > current.max_bytes
            or upload.row_count > current.max_rows
            or upload.checksum != snapshot.checksum
            or upload.row_count != snapshot.row_count
            or upload.column_count != len(snapshot.columns)
            or tuple(name for name, _ in snapshot.columns) != value.selection.table.columns
            or (
                candidate is not None
                and (
                    candidate.status not in {"queued", "needs_review"}
                    or candidate.created_by != actor.id
                )
            )
        ):
            raise invalid(
                "source_publication_failed", "The import did not produce a complete snapshot.", 409
            )
        completed = replace(
            value,
            status="staged" if candidate else "imported",
            completed_at=now(),
            upload_id=upload.id,
            candidate_id=candidate.id if candidate else None,
            snapshot=snapshot_metadata(snapshot),
        )
        repo.complete_source_import(completed)
        audit(repo, actor, value.workspace_id, f"source.{completed.status}", value.id)

    def _fail(self, value: SourceImport, failure: str) -> SourceImport:
        with self.uow() as repo:
            repo.workspace(value.workspace_id, lock=True)
            current = repo.source_import(value.workspace_id, value.actor_id, value.id)
            if current.status != "extracting":
                return current
            result = replace(current, status="failed", completed_at=now(), failure_code=failure)
            repo.complete_source_import(result)
            audit(repo, repo.user(value.actor_id), value.workspace_id, "source.failed", value.id)
            return result

    def pending(self, actor: User, wid: UUID) -> list[dict[str, object]]:
        with self.uow() as repo:
            operator(repo, actor)
            repo.workspace(wid, lock=True)
            owner(repo, actor, wid)
            require_workspace_access(repo, actor, wid)
            return [
                dict(
                    id=str(value.id),
                    dataset_id=str(value.selection.dataset_id),
                    created_at=value.created_at,
                    status=value.status,
                )
                for value in repo.pending_source_imports(wid)
            ]

    def recover(self, actor: User, wid: UUID, import_id: UUID) -> SourceImport:
        with self.uow() as repo:
            operator(repo, actor)
            repo.workspace(wid, lock=True)
            owner(repo, actor, wid)
            value = repo.source_import_for_recovery(wid, import_id)
            require_full_access(repo, actor, wid, value.selection.dataset_id)
            if value.status != "extracting":
                return value
            if now() - value.created_at < timedelta(minutes=5):
                raise invalid(
                    "source_import_pending", "Allow the active import to finish first.", 409
                )
            result = replace(
                value, status="failed", completed_at=now(), failure_code="source_interrupted"
            )
            repo.complete_source_import(result)
            repo.add_staff_audit(
                StaffAudit(
                    uuid4(), actor.id, "source.recovered", "api", "success", now(), wid, value.id
                )
            )
            audit(repo, actor, wid, "source.recovered", value.id)
            return result

    def start(
        self, actor: User, wid: UUID, request_id: UUID, selection: ImportSelection
    ) -> SourceImport:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            owner(repo, actor, wid)
            access = require_full_access(repo, actor, wid, selection.dataset_id)
            prior = repo.source_import_request(wid, actor.id, request_id)
            if prior is not None:
                self._current(repo, actor, prior)
                if prior.selection != selection:
                    raise invalid(
                        "idempotency_conflict", "This request refers to another import.", 409
                    )
                if prior.status == "extracting":
                    raise invalid(
                        "source_import_pending", "This import is still running; reopen it.", 409
                    )
                return prior
            source = repo.registered_source(wid, selection.source_id).source
            if source.version != selection.source_version:
                raise invalid(
                    "source_version", "Source configuration changed; choose it again.", 409
                )
            source.select(selection.table.schema, selection.table.table, selection.table.columns)
            if repo.active_source_import_count(wid) >= 4:
                raise invalid("source_import_busy", "Four source imports are already running.", 409)
            value = SourceImport(
                uuid4(),
                wid,
                actor.id,
                repo.membership(wid, actor.id).created_at,
                request_id,
                selection,
                access.reference(),
                "extracting",
                now(),
            )
            repo.add_source_import(value)
            audit(repo, actor, wid, "source.started", value.id)
        try:
            snapshot = self.extractor.read(source, selection.table)
            if snapshot.source_version != source.version:
                raise invalid("source_snapshot", "The source snapshot version is inconsistent.")

            def upload_guard(repo: WorkspaceRepository, upload: Upload, _: Revision) -> None:
                self._finish(repo, actor, value, snapshot, upload, None)

            def refresh_guard(repo: WorkspaceRepository, candidate: RefreshCandidate) -> None:
                if "input_upload_id" not in candidate.details:
                    raise invalid(
                        "source_publication_failed", "The source snapshot was not retained.", 409
                    )
                upload = repo.upload(
                    wid, selection.dataset_id, UUID(candidate.details["input_upload_id"])
                )
                self._finish(repo, actor, value, snapshot, upload, candidate)

            if selection.mode == "upload":
                self.uploads.upload(
                    actor,
                    wid,
                    selection.dataset_id,
                    "source-snapshot.csv",
                    "text/csv",
                    BytesIO(snapshot.content),
                    _publication_guard=upload_guard,
                )
            else:
                assert selection.expected_feed_version is not None
                self.refresh.stage(
                    actor,
                    wid,
                    selection.dataset_id,
                    value.id,
                    selection.expected_feed_version,
                    "source-snapshot.csv",
                    "text/csv",
                    snapshot.content,
                    "replace",
                    [],
                    "keep_all",
                    snapshot.extracted_at,
                    None,
                    None,
                    _publication_guard=refresh_guard,
                )
        except Exception as exc:
            failure = (
                exc.code
                if isinstance(exc, IngestionError) and exc.code in SOURCE_FAILURES
                else "source_import_failed"
            )
            finished = self._fail(value, failure)
            if finished.status in {"imported", "staged"}:
                return self.open(actor, wid, value.id)
            raise invalid(
                failure,
                "The source import could not finish. Review its status before retrying.",
                409,
            ) from None
        return self.open(actor, wid, value.id)
