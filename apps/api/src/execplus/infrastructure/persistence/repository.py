"""Use case: Persists workspace operations atomically.

What it does: Implements scoped lookups and transaction-scoped PostgreSQL row locks.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import TypeVar
from uuid import UUID

from sqlalchemy import Connection, Engine, Table, delete, select, update
from sqlalchemy.dialects.postgresql import insert

from execplus.application.ports import WorkspaceRepository
from execplus.domain.ingestion import (
    AuditEvent,
    Dataset,
    IngestionError,
    Invitation,
    Membership,
    Upload,
    User,
    Workspace,
)
from execplus.domain.profiling import Revision, UsageEvent
from execplus.infrastructure.persistence import schema as s

Record = TypeVar(
    "Record",
    User,
    Workspace,
    Membership,
    Invitation,
    Dataset,
    Upload,
    AuditEvent,
    Revision,
    UsageEvent,
)


class SQLWorkspaceRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def _one(self, record: type[Record], table: Table, **keys: UUID) -> Record:
        row = self.connection.execute(select(table).filter_by(**keys)).mappings().first()
        if row is None:
            raise IngestionError("not_found", "The requested resource is unavailable.", 404)
        return record(**row)

    def _many(self, record: type[Record], table: Table, **keys: UUID) -> tuple[Record, ...]:
        rows = self.connection.execute(select(table).filter_by(**keys).order_by(table.c.created_at))
        return tuple(record(**row) for row in rows.mappings())

    def user(self, user_id: UUID) -> User:
        return self._one(User, s.users, id=user_id)

    def workspaces(self, user_id: UUID) -> tuple[Workspace, ...]:
        statement = (
            select(s.workspaces).join(s.memberships).where(s.memberships.c.user_id == user_id)
        )
        return tuple(Workspace(**row) for row in self.connection.execute(statement).mappings())

    def workspace(self, workspace_id: UUID, *, lock: bool = False) -> Workspace:
        statement = select(s.workspaces).where(s.workspaces.c.id == workspace_id)
        if lock:
            statement = statement.with_for_update()
        row = self.connection.execute(statement).mappings().first()
        if row is None:
            raise IngestionError("not_found", "The requested workspace is unavailable.", 404)
        return Workspace(**row)

    def membership(self, workspace_id: UUID, user_id: UUID) -> Membership:
        return self._one(Membership, s.memberships, workspace_id=workspace_id, user_id=user_id)

    def members(self, workspace_id: UUID) -> tuple[Membership, ...]:
        return self._many(Membership, s.memberships, workspace_id=workspace_id)

    def invitations(self, workspace_id: UUID) -> tuple[Invitation, ...]:
        return self._many(Invitation, s.invitations, workspace_id=workspace_id)

    def invitation(self, workspace_id: UUID, invitation_id: UUID) -> Invitation:
        return self._one(Invitation, s.invitations, workspace_id=workspace_id, id=invitation_id)

    def set_invitation_status(self, workspace_id: UUID, invitation_id: UUID, status: str) -> None:
        self.connection.execute(
            update(s.invitations)
            .where(
                s.invitations.c.workspace_id == workspace_id,
                s.invitations.c.id == invitation_id,
            )
            .values(status=status)
        )

    def remove_member(self, workspace_id: UUID, user_id: UUID) -> None:
        self.connection.execute(
            delete(s.memberships).where(
                s.memberships.c.workspace_id == workspace_id,
                s.memberships.c.user_id == user_id,
            )
        )

    def set_seat_limit(self, workspace_id: UUID, limit: int) -> None:
        self.connection.execute(
            update(s.workspaces)
            .where(s.workspaces.c.id == workspace_id)
            .values(
                seat_limit=limit,
                updated_at=datetime.now(timezone.utc),
            )
        )

    def datasets(self, workspace_id: UUID) -> tuple[Dataset, ...]:
        return self._many(Dataset, s.datasets, workspace_id=workspace_id)

    def dataset(self, workspace_id: UUID, dataset_id: UUID) -> Dataset:
        return self._one(Dataset, s.datasets, workspace_id=workspace_id, id=dataset_id)

    def rename_dataset(self, workspace_id: UUID, dataset_id: UUID, name: str) -> Dataset:
        self.dataset(workspace_id, dataset_id)
        self.connection.execute(
            update(s.datasets)
            .where(
                s.datasets.c.workspace_id == workspace_id,
                s.datasets.c.id == dataset_id,
            )
            .values(name=name, updated_at=datetime.now(timezone.utc))
        )
        return self.dataset(workspace_id, dataset_id)

    def uploads(self, workspace_id: UUID, dataset_id: UUID) -> tuple[Upload, ...]:
        return self._many(Upload, s.uploads, workspace_id=workspace_id, dataset_id=dataset_id)

    def upload(self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID) -> Upload:
        return self._one(
            Upload, s.uploads, workspace_id=workspace_id, dataset_id=dataset_id, id=upload_id
        )

    def audit_events(self, workspace_id: UUID) -> tuple[AuditEvent, ...]:
        return self._many(AuditEvent, s.audit_events, workspace_id=workspace_id)

    def revisions(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[Revision, ...]:
        return self._many(
            Revision,
            s.revisions,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            upload_id=upload_id,
        )

    def revision(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID, revision_id: UUID
    ) -> Revision:
        return self._one(
            Revision,
            s.revisions,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            upload_id=upload_id,
            id=revision_id,
        )

    def active_revision(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> Revision | None:
        row = (
            self.connection.execute(
                select(s.revision_heads).filter_by(
                    workspace_id=workspace_id, dataset_id=dataset_id, upload_id=upload_id
                )
            )
            .mappings()
            .first()
        )
        return (
            self.revision(workspace_id, dataset_id, upload_id, row["revision_id"]) if row else None
        )

    def set_active_revision(self, revision: Revision) -> None:
        statement = insert(s.revision_heads).values(
            workspace_id=revision.workspace_id,
            dataset_id=revision.dataset_id,
            upload_id=revision.upload_id,
            revision_id=revision.id,
        )
        self.connection.execute(
            statement.on_conflict_do_update(
                index_elements=["workspace_id", "dataset_id", "upload_id"],
                set_={"revision_id": revision.id},
            )
        )

    def usage_events(self, workspace_id: UUID) -> tuple[UsageEvent, ...]:
        return self._many(UsageEvent, s.usage_events, workspace_id=workspace_id)

    def add(
        self,
        record: Workspace
        | Membership
        | Invitation
        | Dataset
        | Upload
        | AuditEvent
        | Revision
        | UsageEvent,
    ) -> None:
        tables = {
            Workspace: s.workspaces,
            Membership: s.memberships,
            Invitation: s.invitations,
            Dataset: s.datasets,
            Upload: s.uploads,
            AuditEvent: s.audit_events,
            Revision: s.revisions,
            UsageEvent: s.usage_events,
        }
        self.connection.execute(tables[type(record)].insert().values(**asdict(record)))


class SQLUnitOfWork:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def __call__(self) -> Iterator[WorkspaceRepository]:
        with self.engine.begin() as connection:
            yield SQLWorkspaceRepository(connection)
