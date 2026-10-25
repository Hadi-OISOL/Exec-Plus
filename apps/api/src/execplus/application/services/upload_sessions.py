"""Use case: Accepts large files as resumable, checksummed chunks and ingests them once complete.

What it does: Stores each chunk in object storage, enforces owner-only sessions and per-user
quotas, then streams the parts through the existing single-upload ingestion path or hands the
assembled file to another consumer such as staged refresh.
"""

import hashlib
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from tempfile import TemporaryFile
from typing import Any, BinaryIO, TypeVar, cast
from uuid import UUID, uuid4

from execplus.application.ports import ObjectStorage, WorkspaceRepository
from execplus.application.services.dataset_access import require_full_access
from execplus.application.services.workspaces import WorkspaceService
from execplus.domain.ingestion import (
    AuditEvent,
    IngestionError,
    Upload,
    User,
    file_too_large,
    validate_filename,
)
from execplus.domain.upload_sessions import (
    CANCELLED,
    COMPLETED,
    EXPIRED,
    FAILED,
    OPEN,
    PROCESSING,
    UploadSession,
    require_supported,
    safe_label,
    valid_sha256,
)

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]
logger = logging.getLogger(__name__)
LEASE = timedelta(minutes=30)
CONSUMED = "consumed_elsewhere"
T = TypeVar("T")


def now() -> datetime:
    return datetime.now(timezone.utc)


class UploadSessionService:
    def __init__(
        self,
        uow: UnitOfWork,
        storage: ObjectStorage,
        workspaces: WorkspaceService,
        *,
        chunk_bytes: int = 8 * 1024 * 1024,
        inline_bytes: int = 20 * 1024 * 1024,
        session_hours: int = 24,
    ) -> None:
        self.uow = uow
        self.storage = storage
        self.workspaces = workspaces
        self.chunk_bytes = chunk_bytes
        self.inline_bytes = inline_bytes
        self.session_hours = session_hours

    def _member(self, repo: WorkspaceRepository, actor: User, workspace_id: UUID) -> None:
        repo.workspace(workspace_id, lock=True)
        repo.membership(workspace_id, actor.id)

    def _audit(self, repo: WorkspaceRepository, session: UploadSession, action: str) -> None:
        repo.add(
            AuditEvent(
                uuid4(),
                session.workspace_id,
                session.created_by,
                action,
                "upload_session",
                session.id,
                now(),
            )
        )

    def _view(self, repo: WorkspaceRepository, session: UploadSession) -> dict[str, Any]:
        value = session.public()
        if session.status == OPEN and session.expires_at <= now():
            value["status"] = EXPIRED
        upload: Upload | None = None
        if session.upload_id is not None and session.dataset_id is not None:
            try:
                upload = repo.upload(session.workspace_id, session.dataset_id, session.upload_id)
            except IngestionError as error:
                if error.status != 404:
                    raise
        value["upload"] = upload
        return value

    def _discard_parts(self, session: UploadSession) -> None:
        try:
            self.storage.delete_prefix(session.prefix)
        except Exception:
            logger.error(
                "upload_session_cleanup_failed workspace_id=%s session_id=%s",
                session.workspace_id,
                session.id,
            )

    def start(
        self,
        actor: User,
        workspace_id: UUID,
        *,
        filename: str,
        size_bytes: int,
        content_type: str,
        sha256: str | None = None,
        dataset_id: UUID | None = None,
        purpose: str = "upload",
    ) -> dict[str, Any]:
        name = validate_filename(filename)
        require_supported(name, content_type)
        if purpose != "upload":
            raise IngestionError("invalid_purpose", "Only file uploads use upload sessions.", 422)
        if size_bytes > self.workspaces.max_upload_bytes:
            raise file_too_large(self.workspaces.max_upload_bytes)
        if size_bytes <= 0:
            raise IngestionError("empty_file", "The file is empty.", 422)
        checksum = valid_sha256(sha256)
        timestamp = now()
        session = UploadSession(
            uuid4(),
            workspace_id,
            dataset_id,
            actor.id,
            name,
            content_type,
            size_bytes,
            checksum,
            self.chunk_bytes,
            [],
            OPEN,
            None,
            None,
            None,
            None,
            timestamp + timedelta(hours=self.session_hours),
            timestamp,
            timestamp,
        )
        with self.uow() as repo:
            self._member(repo, actor, workspace_id)
            if dataset_id is not None:
                require_full_access(repo, actor, workspace_id, dataset_id)
            repo.check_plan_stock(workspace_id, "file_bytes", size_bytes, timestamp)
            repo.check_plan_stock(workspace_id, "storage_bytes", size_bytes, timestamp)
            self.workspaces.check_storage(repo, actor.id, size_bytes)
            repo.add_upload_session(session)
            view = self._view(repo, session)
        logger.info(
            "upload_session_started workspace_id=%s session_id=%s size=%s",
            workspace_id,
            session.id,
            size_bytes,
        )
        return view

    def get(self, actor: User, workspace_id: UUID, session_id: UUID) -> dict[str, Any]:
        with self.uow() as repo:
            self._member(repo, actor, workspace_id)
            return self._view(repo, repo.upload_session(workspace_id, session_id, actor.id))

    def list_sessions(
        self, actor: User, workspace_id: UUID, status: str | None
    ) -> list[dict[str, Any]]:
        with self.uow() as repo:
            self._member(repo, actor, workspace_id)
            views = [
                self._view(repo, item)
                for item in repo.upload_sessions(workspace_id, actor.id, status)
            ]
        return [item for item in views if status is None or item["status"] == status]

    def put_chunk(
        self,
        actor: User,
        workspace_id: UUID,
        session_id: UUID,
        index: int,
        content: bytes,
        declared_sha256: str | None,
    ) -> dict[str, Any]:
        declared = valid_sha256(declared_sha256)
        if declared is None:
            raise IngestionError("invalid_checksum", "Send the chunk's X-Chunk-SHA256 header.", 422)
        digest = hashlib.sha256(content).hexdigest()
        if digest != declared:
            raise IngestionError(
                "hash_mismatch", "The chunk does not match its checksum. Send it again.", 409
            )
        with self.uow() as repo:
            self._member(repo, actor, workspace_id)
            session = repo.upload_session(workspace_id, session_id, actor.id)
            if not session.accepts(index, len(content), digest, now()):
                return self._progress(session)
        self.storage.put_part(session.part_key(index, digest), content, digest)
        with self.uow() as repo:
            self._member(repo, actor, workspace_id)
            session = repo.upload_session(workspace_id, session_id, actor.id, lock=True)
            timestamp = now()
            if not session.accepts(index, len(content), digest, timestamp):
                return self._progress(session)
            self.workspaces.check_storage(repo, actor.id, session.size_bytes, session.id)
            session = replace(
                session,
                chunk_hashes=[*session.chunk_hashes, digest],
                expires_at=timestamp + timedelta(hours=self.session_hours),
                updated_at=timestamp,
            )
            repo.set_upload_session(session)
        return self._progress(session)

    def _progress(self, session: UploadSession) -> dict[str, Any]:
        return {
            "received_bytes": session.received_bytes,
            "next_chunk": session.next_chunk,
            "total_chunks": session.total_chunks,
            "status": session.status,
        }

    def _claim(
        self,
        actor: User,
        workspace_id: UUID,
        session_id: UUID,
        dataset_id: UUID | None = None,
        marker: str | None = None,
    ) -> tuple[UploadSession, dict[str, Any]]:
        with self.uow() as repo:
            self._member(repo, actor, workspace_id)
            session = repo.upload_session(workspace_id, session_id, actor.id, lock=True)
            timestamp = now()
            if session.status != OPEN or session.expires_at <= timestamp:
                raise IngestionError(
                    "session_closed", "This upload session can no longer be completed.", 409
                )
            if session.next_chunk < session.total_chunks:
                raise IngestionError(
                    "upload_incomplete", f"Send chunk {session.next_chunk} before completing.", 409
                )
            if marker is not None and session.dataset_id != dataset_id:
                raise IngestionError(
                    "session_mismatch", "This upload session belongs to another dataset.", 409
                )
            session = replace(
                session,
                status=PROCESSING,
                lease_until=timestamp + LEASE,
                error_code=marker,
                updated_at=timestamp,
            )
            repo.set_upload_session(session)
            return session, self._view(repo, session)

    def complete(
        self, actor: User, workspace_id: UUID, session_id: UUID
    ) -> tuple[dict[str, Any], bool]:
        session, view = self._claim(actor, workspace_id, session_id)
        if session.size_bytes > self.inline_bytes:
            return view, True
        return self.process(session.id, reraise=True), False

    def consume(
        self,
        actor: User,
        workspace_id: UUID,
        session_id: UUID,
        dataset_id: UUID,
        use: Callable[[UploadSession, bytes], T],
    ) -> T:
        session, _ = self._claim(actor, workspace_id, session_id, dataset_id, CONSUMED)
        try:
            with TemporaryFile(mode="w+b") as content:
                self._assemble(session, cast(BinaryIO, content))
                result = use(session, content.read())
        except IngestionError as error:
            self._close(session, FAILED, error.code, str(error)[:300])
            raise
        except Exception:
            logger.exception("upload_session_consume_failed session_id=%s", session.id)
            self._close(session, FAILED, "internal_error", "The file could not be processed.")
            raise
        self._close(session, COMPLETED, None, None)
        return result

    def _close(
        self, session: UploadSession, status: str, code: str | None, message: str | None
    ) -> None:
        outcome = replace(
            session, status=status, error_code=code, error_message=message, lease_until=None
        )
        with self.uow() as repo:
            repo.workspace(session.workspace_id, lock=True)
            outcome = replace(outcome, updated_at=now())
            repo.set_upload_session(outcome)
            self._audit(repo, outcome, f"upload_session.{status}")
        self._discard_parts(outcome)

    def process(self, session_id: UUID, *, reraise: bool = False) -> dict[str, Any]:
        with self.uow() as repo:
            session = repo.upload_session_by_id(session_id)
            actor = repo.user(session.created_by)
            if session.status != PROCESSING:
                return self._view(repo, session)
        if session.error_code == CONSUMED:
            self._close(
                session, FAILED, "interrupted", "Staging this file was interrupted. Send it again."
            )
            with self.uow() as repo:
                return self._view(repo, repo.upload_session_by_id(session_id))
        failure: IngestionError | None = None
        try:
            with TemporaryFile(mode="w+b") as content:
                self._assemble(session, cast(BinaryIO, content))
                session = self._target_dataset(actor, session)
                upload = self.workspaces.upload(
                    actor,
                    session.workspace_id,
                    cast(UUID, session.dataset_id),
                    session.filename,
                    session.content_type,
                    cast(BinaryIO, content),
                    _quota_session=session.id,
                )
            outcome = replace(session, status=COMPLETED, upload_id=upload.id)
            action = "upload_session.completed"
        except IngestionError as error:
            failure = error
            outcome = replace(
                session, status=FAILED, error_code=error.code, error_message=str(error)[:300]
            )
            action = "upload_session.failed"
        except Exception:
            logger.exception("upload_session_failed session_id=%s", session.id)
            outcome = replace(
                session,
                status=FAILED,
                error_code="internal_error",
                error_message="The upload could not be processed. Try again.",
            )
            action = "upload_session.failed"
        with self.uow() as repo:
            repo.workspace(session.workspace_id, lock=True)
            outcome = replace(outcome, lease_until=None, updated_at=now())
            repo.set_upload_session(outcome)
            self._audit(repo, outcome, action)
            view = self._view(repo, outcome)
        self._discard_parts(outcome)
        logger.info("upload_session_processed session_id=%s outcome=%s", outcome.id, outcome.status)
        if reraise and failure is not None:
            raise failure
        return view

    def _assemble(self, session: UploadSession, content: BinaryIO) -> None:
        whole = hashlib.sha256()
        for index, digest in enumerate(session.chunk_hashes):
            part = self.storage.read_part(session.part_key(index, digest), session.chunk_size)
            if (
                len(part) != session.expected_length(index)
                or hashlib.sha256(part).hexdigest() != digest
            ):
                raise IngestionError(
                    "storage_integrity", "A stored chunk failed its integrity check.", 503
                )
            whole.update(part)
            content.write(part)
        if session.sha256 is not None and whole.hexdigest() != session.sha256:
            raise IngestionError(
                "checksum_mismatch", "The assembled file does not match its SHA-256 checksum.", 409
            )
        content.seek(0)

    def _target_dataset(self, actor: User, session: UploadSession) -> UploadSession:
        if session.dataset_id is not None:
            return session
        stem = safe_label(PurePosixPath(session.filename).stem, 100, "My data")
        dataset = self.workspaces.create_dataset(actor, session.workspace_id, stem)
        session = replace(session, dataset_id=dataset.id)
        with self.uow() as repo:
            repo.set_upload_session(session)
        return session

    def cancel(self, actor: User, workspace_id: UUID, session_id: UUID) -> None:
        with self.uow() as repo:
            self._member(repo, actor, workspace_id)
            session = repo.upload_session(workspace_id, session_id, actor.id, lock=True)
            if session.status in {PROCESSING, COMPLETED}:
                raise IngestionError(
                    "session_closed", "This upload is already being processed or finished.", 409
                )
            if session.status != CANCELLED:
                session = replace(session, status=CANCELLED, updated_at=now())
                repo.set_upload_session(session)
                self._audit(repo, session, "upload_session.cancelled")
        self._discard_parts(session)

    def sweep(self, limit: int = 20) -> dict[str, int]:
        expired = recovered = 0
        with self.uow() as repo:
            candidates = repo.stale_upload_sessions(now(), limit)
        for session_id in candidates:
            with self.uow() as repo:
                session = repo.upload_session_by_id(session_id, lock=True)
                timestamp = now()
                if session.status == OPEN and session.expires_at <= timestamp:
                    session = replace(session, status=EXPIRED, updated_at=timestamp)
                    repo.set_upload_session(session)
                    claimed = False
                elif session.status == PROCESSING and (
                    session.lease_until is None or session.lease_until <= timestamp
                ):
                    session = replace(session, lease_until=timestamp + LEASE, updated_at=timestamp)
                    repo.set_upload_session(session)
                    claimed = True
                else:
                    continue
            if claimed:
                self.process(session.id)
                recovered += 1
            else:
                self._discard_parts(session)
                expired += 1
        return {"expired": expired, "recovered": recovered}

    def storage_summary(self, actor: User) -> dict[str, int]:
        with self.uow() as repo:
            stored, reserved, quota = self.workspaces.storage_usage(repo, actor.id)
        return {
            "used_bytes": stored,
            "quota_bytes": quota,
            "open_upload_bytes": reserved,
            "max_upload_bytes": self.workspaces.max_upload_bytes,
            "chunk_size": self.chunk_bytes,
        }
