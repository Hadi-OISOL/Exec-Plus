"""Use case: Persists resumable upload sessions and per-user storage quota overrides.

What it does: Scopes sessions to workspace and owner, sums stored and reserved bytes per user.
"""

from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, func, or_, select

from execplus.domain.ingestion import IngestionError
from execplus.domain.upload_sessions import PROCESSING, RESERVING, UploadSession
from execplus.infrastructure.persistence import schema as s

t = s.upload_sessions


class SQLUploadSessionRepository:
    connection: Connection

    def add_upload_session(self, value: UploadSession) -> None:
        self.connection.execute(t.insert().values(**asdict(value)))

    def upload_session(
        self, workspace_id: UUID, session_id: UUID, owner_id: UUID, *, lock: bool = False
    ) -> UploadSession:
        statement = select(t).where(
            t.c.id == session_id, t.c.workspace_id == workspace_id, t.c.created_by == owner_id
        )
        row = (
            self.connection.execute(statement.with_for_update() if lock else statement)
            .mappings()
            .first()
        )
        if row is None:
            raise IngestionError(
                "upload_session_not_found", "This upload session is unavailable.", 404
            )
        return UploadSession(**row)

    def upload_session_by_id(self, session_id: UUID, *, lock: bool = False) -> UploadSession:
        statement = select(t).where(t.c.id == session_id)
        row = (
            self.connection.execute(statement.with_for_update() if lock else statement)
            .mappings()
            .one()
        )
        return UploadSession(**row)

    def upload_sessions(
        self, workspace_id: UUID, owner_id: UUID, status: str | None
    ) -> tuple[UploadSession, ...]:
        statement = select(t).where(t.c.workspace_id == workspace_id, t.c.created_by == owner_id)
        if status is not None:
            statement = statement.where(t.c.status == status)
        rows = self.connection.execute(statement.order_by(t.c.created_at.desc()).limit(100))
        return tuple(UploadSession(**row) for row in rows.mappings())

    def set_upload_session(self, value: UploadSession) -> None:
        values: dict[str, Any] = asdict(value)
        self.connection.execute(t.update().where(t.c.id == value.id).values(**values))

    def stale_upload_sessions(self, now: datetime, limit: int) -> tuple[UUID, ...]:
        rows = self.connection.execute(
            select(t.c.id)
            .where(
                or_(
                    (t.c.status == "open") & (t.c.expires_at <= now),
                    (t.c.status == PROCESSING) & (t.c.lease_until <= now),
                )
            )
            .order_by(t.c.updated_at)
            .limit(limit)
        )
        return tuple(row.id for row in rows)

    def user_stored_bytes(self, user_id: UUID) -> int:
        return int(
            self.connection.execute(
                select(func.coalesce(func.sum(s.uploads.c.size), 0)).where(
                    s.uploads.c.created_by == user_id
                )
            ).scalar_one()
        )

    def user_reserved_bytes(self, user_id: UUID, exclude: UUID | None = None) -> int:
        statement = select(func.coalesce(func.sum(t.c.size_bytes), 0)).where(
            t.c.created_by == user_id, t.c.status.in_(RESERVING)
        )
        if exclude is not None:
            statement = statement.where(t.c.id != exclude)
        return int(self.connection.execute(statement).scalar_one())

    def lock_user_storage(self, user_id: UUID) -> None:
        self.connection.execute(
            select(s.users.c.id).where(s.users.c.id == user_id).with_for_update()
        )

    def user_storage_quota(self, user_id: UUID) -> int | None:
        value = self.connection.execute(
            select(s.user_storage_quotas.c.quota_bytes).where(
                s.user_storage_quotas.c.user_id == user_id
            )
        ).scalar_one_or_none()
        return None if value is None else int(value)

    def set_user_storage_quota(
        self, user_id: UUID, quota_bytes: int | None, set_by: UUID | None, now: datetime
    ) -> None:
        q = s.user_storage_quotas
        self.connection.execute(q.delete().where(q.c.user_id == user_id))
        if quota_bytes is not None:
            self.connection.execute(
                q.insert().values(
                    user_id=user_id, quota_bytes=quota_bytes, set_by=set_by, updated_at=now
                )
            )
