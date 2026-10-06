"""Use case: Persists staff grants and scoped support with bounded metadata projections.

What it does: Enforces tenant lookups, optimistic updates and private-content-free admin queries.
"""

from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from execplus.domain.errors import AuthorizationError
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.operations import StaffAudit, StaffGrant, SupportEvent, SupportTicket
from execplus.infrastructure.persistence import schema as s


def _query_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


class SQLOperationsRepository:
    connection: Connection

    def staff_grant(self, user_id: UUID, *, lock: bool = False) -> StaffGrant | None:
        statement = select(s.staff_grants).where(s.staff_grants.c.user_id == user_id)
        if lock:
            statement = statement.with_for_update(read=True)
        row = self.connection.execute(statement).mappings().one_or_none()
        return StaffGrant(**row) if row else None

    def set_staff_grant(self, value: StaffGrant) -> None:
        self.connection.execute(
            insert(s.staff_grants)
            .values(**asdict(value))
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "role": value.role,
                    "updated_at": value.updated_at,
                    "revoked_at": value.revoked_at,
                },
            )
        )

    def staff_user(self, email: str) -> User:
        row = (
            self.connection.execute(select(s.users).where(s.users.c.email == email))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise IngestionError(
                "user_not_found", "Provision this user before changing staff access.", 404
            )
        return User(**row)

    def active_staff(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            dict(row)
            for row in self.connection.execute(
                select(s.users.c.id, s.users.c.email, s.staff_grants.c.role)
                .join(s.staff_grants, s.users.c.id == s.staff_grants.c.user_id)
                .where(s.staff_grants.c.revoked_at.is_(None))
                .order_by(s.users.c.id)
                .limit(100)
            ).mappings()
        )

    def add_staff_audit(self, value: StaffAudit) -> None:
        self.connection.execute(insert(s.staff_audit).values(**asdict(value)))

    def add_support_ticket(self, value: SupportTicket) -> None:
        self.connection.execute(insert(s.support_tickets).values(**asdict(value)))

    def support_ticket(
        self, workspace_id: UUID, ticket_id: UUID, *, lock: bool = False
    ) -> SupportTicket:
        statement = select(s.support_tickets).where(
            s.support_tickets.c.workspace_id == workspace_id, s.support_tickets.c.id == ticket_id
        )
        if lock:
            statement = statement.with_for_update()
        row = self.connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise AuthorizationError("Support request unavailable")
        return SupportTicket(**row)

    def support_tickets(
        self,
        *,
        workspace_id: UUID | None,
        requester_id: UUID | None,
        before: tuple[datetime, UUID] | None,
        status: str,
        priority: str,
        q: str,
        limit: int,
    ) -> tuple[SupportTicket, ...]:
        table = s.support_tickets
        statement = select(table)
        if workspace_id is not None:
            statement = statement.where(table.c.workspace_id == workspace_id)
        if requester_id is not None:
            statement = statement.where(table.c.requester_id == requester_id)
        if before:
            when, key = before
            statement = statement.where(
                or_(table.c.created_at < when, and_(table.c.created_at == when, table.c.id < key))
            )
        if status:
            statement = statement.where(table.c.status == status)
        if priority:
            statement = statement.where(table.c.priority == priority)
        if q:
            match = table.c.subject.icontains(q, autoescape=True)
            if (query_id := _query_uuid(q)) is not None:
                match = or_(match, table.c.id == query_id)
            statement = statement.where(match)
        rows = self.connection.execute(
            statement.order_by(table.c.created_at.desc(), table.c.id.desc()).limit(limit)
        ).mappings()
        return tuple(SupportTicket(**row) for row in rows)

    def support_open_count(self, workspace_id: UUID, requester_id: UUID) -> int:
        return int(
            self.connection.execute(
                select(func.count())
                .select_from(s.support_tickets)
                .where(
                    s.support_tickets.c.workspace_id == workspace_id,
                    s.support_tickets.c.requester_id == requester_id,
                    s.support_tickets.c.status != "resolved",
                )
            ).scalar_one()
        )

    def set_support_ticket(self, value: SupportTicket, expected_version: int) -> None:
        changed = self.connection.execute(
            update(s.support_tickets)
            .where(
                s.support_tickets.c.workspace_id == value.workspace_id,
                s.support_tickets.c.id == value.id,
                s.support_tickets.c.version == expected_version,
            )
            .values(**asdict(value))
        )
        if changed.rowcount != 1:
            raise IngestionError(
                "support_conflict", "This request changed. Reload it before editing.", 409
            )

    def add_support_event(self, value: SupportEvent) -> None:
        self.connection.execute(insert(s.support_events).values(**asdict(value)))

    def support_events(self, workspace_id: UUID, ticket_id: UUID) -> tuple[SupportEvent, ...]:
        rows = self.connection.execute(
            select(s.support_events)
            .where(
                s.support_events.c.workspace_id == workspace_id,
                s.support_events.c.ticket_id == ticket_id,
            )
            .order_by(s.support_events.c.sequence)
            .limit(200)
        ).mappings()
        return tuple(SupportEvent(**row) for row in rows)

    def support_feedback_owned(
        self, workspace_id: UUID, feedback_id: UUID, requester_id: UUID
    ) -> bool:
        return (
            self.connection.execute(
                select(s.feedback.c.id).where(
                    s.feedback.c.workspace_id == workspace_id,
                    s.feedback.c.id == feedback_id,
                    s.feedback.c.actor_id == requester_id,
                )
            ).first()
            is not None
        )

    def admin_workspaces(
        self, *, before: tuple[datetime, UUID] | None, q: str, limit: int
    ) -> tuple[dict[str, Any], ...]:
        w = s.workspaces
        seats = select(func.count()).where(s.memberships.c.workspace_id == w.c.id).scalar_subquery()
        uploads = select(func.count()).where(s.uploads.c.workspace_id == w.c.id).scalar_subquery()
        storage = (
            select(func.coalesce(func.sum(s.uploads.c.size), 0))
            .where(s.uploads.c.workspace_id == w.c.id)
            .scalar_subquery()
        )
        statement = select(
            w.c.id,
            w.c.name,
            w.c.created_at,
            w.c.seat_limit,
            seats.label("active_seats"),
            uploads.label("uploads"),
            storage.label("storage_bytes"),
        )
        if before:
            when, key = before
            statement = statement.where(
                or_(w.c.created_at < when, and_(w.c.created_at == when, w.c.id < key))
            )
        if q:
            match = w.c.name.icontains(q, autoescape=True)
            if (query_id := _query_uuid(q)) is not None:
                match = or_(match, w.c.id == query_id)
            statement = statement.where(match)
        return tuple(
            dict(row)
            for row in self.connection.execute(
                statement.order_by(w.c.created_at.desc(), w.c.id.desc()).limit(limit)
            ).mappings()
        )

    def admin_workspace(self, workspace_id: UUID) -> dict[str, Any]:
        w = s.workspaces
        row = (
            self.connection.execute(
                select(w.c.id, w.c.name, w.c.created_at, w.c.seat_limit).where(
                    w.c.id == workspace_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise AuthorizationError("Workspace unavailable")
        result = dict(row)
        for name, table in (
            ("active_seats", s.memberships),
            ("uploads", s.uploads),
            ("datasets", s.datasets),
            ("documents", s.documents),
            ("forecasts", s.forecast_runs),
        ):
            result[name] = self.connection.execute(
                select(func.count()).select_from(table).where(table.c.workspace_id == workspace_id)
            ).scalar_one()
        result["storage_bytes"] = self.connection.execute(
            select(func.coalesce(func.sum(s.uploads.c.size), 0)).where(
                s.uploads.c.workspace_id == workspace_id
            )
        ).scalar_one()
        result["owners"] = [
            dict(value)
            for value in self.connection.execute(
                select(s.users.c.id, s.users.c.email)
                .join(s.memberships, s.memberships.c.user_id == s.users.c.id)
                .where(
                    s.memberships.c.workspace_id == workspace_id, s.memberships.c.role == "owner"
                )
            ).mappings()
        ]
        for name, table in (("jobs", s.jobs), ("support", s.support_tickets)):
            result[name] = {
                str(status): count
                for status, count in self.connection.execute(
                    select(table.c.status, func.count())
                    .where(table.c.workspace_id == workspace_id)
                    .group_by(table.c.status)
                ).all()
            }
        return result
