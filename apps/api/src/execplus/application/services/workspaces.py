"""Use case: Orchestrates authorized workspace and ingestion workflows.

What it does: Applies role, seat, tenant, retention, and audit policies through ports.
"""

import hashlib
import logging
import re
import unicodedata
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import BinaryIO
from uuid import UUID, uuid4

from execplus.application.ports import FileParser, ObjectStorage, WorkspaceRepository
from execplus.domain.ingestion import (
    AuditEvent,
    Dataset,
    IngestionError,
    Invitation,
    Membership,
    MemberView,
    Upload,
    User,
    Workspace,
    require_manager,
    require_seat_limit,
)

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]
logger = logging.getLogger(__name__)


def normalized_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise IngestionError("invalid_email", "Enter a valid email address.", 422)
    return value


def checked_name(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 100 or any(ord(char) < 32 for char in value):
        raise IngestionError(
            "invalid_name", "Use a name containing 1 to 100 printable characters.", 422
        )
    return value


class WorkspaceService:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        storage: ObjectStorage,
        parser: FileParser,
        max_upload_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self.uow = unit_of_work
        self.storage = storage
        self.parser = parser
        self.max_upload_bytes = max_upload_bytes

    def _authorize(
        self, repo: WorkspaceRepository, actor: User, workspace_id: UUID, *, manager: bool = False
    ) -> Membership:
        member = repo.membership(workspace_id, actor.id)
        if manager:
            require_manager(member.role)
        return member

    def _audit(
        self,
        repo: WorkspaceRepository,
        actor: User,
        workspace_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
    ) -> None:
        repo.add(
            AuditEvent(
                uuid4(),
                workspace_id,
                actor.id,
                action,
                resource_type,
                resource_id,
                datetime.now(timezone.utc),
            )
        )

    def list_workspaces(self, actor: User) -> tuple[Workspace, ...]:
        with self.uow() as repo:
            return repo.workspaces(actor.id)

    def create_workspace(self, actor: User, name: str, seat_limit: int) -> Workspace:
        require_seat_limit(seat_limit)
        now = datetime.now(timezone.utc)
        workspace = Workspace(uuid4(), checked_name(name), seat_limit, now, now)
        with self.uow() as repo:
            repo.add(workspace)
            repo.add(Membership(workspace.id, actor.id, "owner", now))
            self._audit(repo, actor, workspace.id, "workspace.created", "workspace", workspace.id)
            self._audit(repo, actor, workspace.id, "membership.created", "user", actor.id)
        return workspace

    def list_members(self, actor: User, workspace_id: UUID) -> tuple[MemberView, ...]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            return tuple(
                MemberView(
                    item.workspace_id, item.user_id, item.role, repo.user(item.user_id).email
                )
                for item in repo.members(workspace_id)
            )

    def _occupied(self, repo: WorkspaceRepository, workspace_id: UUID) -> int:
        now = datetime.now(timezone.utc)
        return len(repo.members(workspace_id)) + sum(
            invitation.status == "pending" and invitation.expires_at > now
            for invitation in repo.invitations(workspace_id)
        )

    def set_seat_limit(self, actor: User, workspace_id: UUID, seat_limit: int) -> None:
        require_seat_limit(seat_limit)
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            member = self._authorize(repo, actor, workspace_id, manager=True)
            if member.role != "owner":
                raise IngestionError("forbidden", "Only the owner can change the seat limit.", 403)
            if self._occupied(repo, workspace_id) > seat_limit:
                raise IngestionError(
                    "seat_limit_reached", "Remove a member or revoke an invitation first.", 409
                )
            repo.set_seat_limit(workspace_id, seat_limit)
            self._audit(
                repo, actor, workspace_id, "workspace.seats_changed", "workspace", workspace_id
            )

    def remove_member(self, actor: User, workspace_id: UUID, user_id: UUID) -> None:
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            manager = self._authorize(repo, actor, workspace_id, manager=True)
            member = repo.membership(workspace_id, user_id)
            if member.role == "owner" or (member.role == "admin" and manager.role != "owner"):
                raise IngestionError(
                    "forbidden", "This membership cannot be removed by your role.", 403
                )
            repo.remove_member(workspace_id, user_id)
            self._audit(repo, actor, workspace_id, "membership.removed", "user", user_id)

    def list_invitations(self, actor: User, workspace_id: UUID) -> tuple[Invitation, ...]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id, manager=True)
            return repo.invitations(workspace_id)

    def invite(self, actor: User, workspace_id: UUID, email: str, role: str) -> Invitation:
        email = normalized_email(email)
        if role not in {"admin", "member"}:
            raise IngestionError("invalid_role", "Invite an admin or member.", 422)
        now = datetime.now(timezone.utc)
        with self.uow() as repo:
            workspace = repo.workspace(workspace_id, lock=True)
            manager = self._authorize(repo, actor, workspace_id, manager=True)
            if role == "admin" and manager.role != "owner":
                raise IngestionError("forbidden", "Only the owner can invite an admin.", 403)
            if any(
                repo.user(member.user_id).email == email for member in repo.members(workspace_id)
            ):
                raise IngestionError("already_member", "This person is already a member.", 409)
            if any(
                item.email == email and item.status == "pending" and item.expires_at > now
                for item in repo.invitations(workspace_id)
            ):
                raise IngestionError("already_invited", "An active invitation already exists.", 409)
            if self._occupied(repo, workspace_id) >= workspace.seat_limit:
                raise IngestionError(
                    "seat_limit_reached", "All seats are occupied or reserved by invitations.", 409
                )
            invitation = Invitation(
                uuid4(),
                workspace_id,
                email,
                role,
                "pending",
                now + timedelta(days=7),
                actor.id,
                now,
            )
            repo.add(invitation)
            self._audit(
                repo, actor, workspace_id, "invitation.created", "invitation", invitation.id
            )
        return invitation

    def accept_invitation(self, actor: User, workspace_id: UUID, invitation_id: UUID) -> Membership:
        with self.uow() as repo:
            workspace = repo.workspace(workspace_id, lock=True)
            invitation = repo.invitation(workspace_id, invitation_id)
            if invitation.email != actor.email:
                raise IngestionError("not_found", "The invitation is unavailable.", 404)
            now = datetime.now(timezone.utc)
            if invitation.status != "pending" or invitation.expires_at <= now:
                raise IngestionError(
                    "invitation_unavailable",
                    "This invitation has expired or is no longer pending.",
                    409,
                )
            members = repo.members(workspace_id)
            if any(member.user_id == actor.id for member in members):
                raise IngestionError("already_member", "You are already a member.", 409)
            if len(members) >= workspace.seat_limit:
                raise IngestionError(
                    "seat_limit_reached", "The workspace has no available seats.", 409
                )
            member = Membership(workspace_id, actor.id, invitation.role, now)
            repo.add(member)
            repo.set_invitation_status(workspace_id, invitation_id, "accepted")
            self._audit(
                repo, actor, workspace_id, "invitation.accepted", "invitation", invitation_id
            )
            self._audit(repo, actor, workspace_id, "membership.created", "user", actor.id)
        return member

    def revoke_invitation(self, actor: User, workspace_id: UUID, invitation_id: UUID) -> None:
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            self._authorize(repo, actor, workspace_id, manager=True)
            invitation = repo.invitation(workspace_id, invitation_id)
            if invitation.status != "pending":
                raise IngestionError(
                    "invitation_unavailable", "Only a pending invitation can be revoked.", 409
                )
            repo.set_invitation_status(workspace_id, invitation_id, "revoked")
            self._audit(
                repo, actor, workspace_id, "invitation.revoked", "invitation", invitation_id
            )

    def list_datasets(self, actor: User, workspace_id: UUID) -> tuple[Dataset, ...]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            return repo.datasets(workspace_id)

    def get_dataset(self, actor: User, workspace_id: UUID, dataset_id: UUID) -> Dataset:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            return repo.dataset(workspace_id, dataset_id)

    def create_dataset(self, actor: User, workspace_id: UUID, name: str) -> Dataset:
        now = datetime.now(timezone.utc)
        dataset = Dataset(uuid4(), workspace_id, checked_name(name), actor.id, now, now)
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            self._authorize(repo, actor, workspace_id)
            repo.add(dataset)
            self._audit(repo, actor, workspace_id, "dataset.created", "dataset", dataset.id)
        return dataset

    def rename_dataset(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, name: str
    ) -> Dataset:
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            self._authorize(repo, actor, workspace_id)
            dataset = repo.rename_dataset(workspace_id, dataset_id, checked_name(name))
            self._audit(repo, actor, workspace_id, "dataset.renamed", "dataset", dataset_id)
            return dataset

    def list_uploads(self, actor: User, workspace_id: UUID, dataset_id: UUID) -> tuple[Upload, ...]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            repo.dataset(workspace_id, dataset_id)
            return repo.uploads(workspace_id, dataset_id)

    def get_upload(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> Upload:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            return repo.upload(workspace_id, dataset_id, upload_id)

    def upload(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        filename: str,
        content_type: str,
        content: BinaryIO,
    ) -> Upload:
        self.get_dataset(actor, workspace_id, dataset_id)
        content.seek(0, 2)
        size = content.tell()
        if size > self.max_upload_bytes:
            raise IngestionError("file_too_large", "Files must be at most 20 MiB.", 413)
        content.seek(0)
        structure = self.parser.parse(content, filename, content_type)
        content.seek(0)
        digest = hashlib.sha256()
        while chunk := content.read(65536):
            digest.update(chunk)
        content.seek(0)
        upload_id = uuid4()
        key = f"workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/original"
        upload = Upload(
            upload_id,
            workspace_id,
            dataset_id,
            unicodedata.normalize("NFKC", filename).strip(),
            content_type,
            size,
            key,
            digest.hexdigest(),
            "stored",
            structure.format,
            structure.row_count,
            structure.column_count,
            actor.id,
            datetime.now(timezone.utc),
        )
        attempted = False
        try:
            with self.uow() as repo:
                repo.workspace(workspace_id, lock=True)
                self._authorize(repo, actor, workspace_id)
                repo.dataset(workspace_id, dataset_id)
                attempted = True
                self.storage.put(upload, content)
                repo.add(upload)
                self._audit(repo, actor, workspace_id, "upload.stored", "upload", upload.id)
        except Exception:
            if attempted:
                try:
                    self.storage.delete(upload)
                except Exception:
                    logger.error(
                        "upload_cleanup_failed workspace_id=%s upload_id=%s",
                        workspace_id,
                        upload.id,
                    )
            raise
        return upload

    def download(self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID) -> bytes:
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            self._authorize(repo, actor, workspace_id)
            upload = repo.upload(workspace_id, dataset_id, upload_id)
            content = self.storage.read(upload)
            self._audit(repo, actor, workspace_id, "upload.downloaded", "upload", upload_id)
            return content

    def audit_events(self, actor: User, workspace_id: UUID) -> tuple[AuditEvent, ...]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id, manager=True)
            return repo.audit_events(workspace_id)
