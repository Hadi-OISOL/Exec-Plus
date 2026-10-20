"""Use case: Stores local allowance decisions in existing workspace transactions.

What it does: Serializes stock checks/admissions and initializes native workspaces
without adding financial accounting or trusting browser-supplied usage totals.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, func, select, text

from execplus.domain.ingestion import IngestionError
from execplus.domain.plans import CATALOG, OPERATIONS, require_active, require_capacity
from execplus.infrastructure.persistence import schema as s


class SQLPlanRepository:
    connection: Connection

    def lock_plan_catalog(self) -> None:
        self.connection.execute(text("SELECT pg_advisory_xact_lock(17301, 26)"))

    def plan_assignment(self, wid: UUID) -> dict[str, Any] | None:
        row = (
            self.connection.execute(
                select(s.workspace_plans)
                .where(s.workspace_plans.c.workspace_id == wid)
                .order_by(s.workspace_plans.c.version.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def plan_catalog(self) -> list[dict[str, Any]]:
        values = {key: {"key": key, "version": 1, **value} for key, value in CATALOG.items()}
        for row in self.connection.execute(
            select(s.plan_catalog).order_by(s.plan_catalog.c.version)
        ).mappings():
            values[row["key"]] = dict(row)
        return list(values.values())

    def add_plan_catalog(self, value: dict[str, Any]) -> None:
        self.connection.execute(s.plan_catalog.insert().values(**value))

    def add_plan_assignment(self, value: dict[str, Any]) -> None:
        self.connection.execute(s.workspace_plans.insert().values(**value))
        self.connection.execute(
            s.audit_events.insert().values(
                id=uuid4(),
                workspace_id=value["workspace_id"],
                actor_id=value["assigned_by"],
                action="plan.default_assigned"
                if value["basis"] == "native_default"
                else "plan.assigned",
                resource_type="workspace_plan",
                resource_id=value["id"],
                created_at=value["created_at"],
            )
        )

    def initialize_native_workspace_plan(
        self, workspace_id: UUID, actor_id: UUID, now: datetime
    ) -> None:
        if (
            self.connection.execute(
                select(s.local_accounts.c.user_id).where(s.local_accounts.c.user_id == actor_id)
            ).first()
            is None
            and self.connection.execute(
                select(s.external_identities.c.user_id).where(
                    s.external_identities.c.user_id == actor_id
                )
            ).first()
            is None
        ):
            return
        if self.plan_assignment(workspace_id) is not None:
            return
        demo = next(item for item in self.plan_catalog() if item["key"] == "demo")
        self.add_plan_assignment(
            dict(
                id=uuid4(),
                workspace_id=workspace_id,
                version=1,
                plan_key="demo",
                plan_version=demo["version"],
                limits=demo["limits"],
                starts_at=now,
                ends_at=now + timedelta(days=30),
                assigned_by=actor_id,
                basis="native_default",
                created_at=now,
            )
        )

    def plan_stock(self, wid: UUID, kind: str, now: datetime) -> int:
        if kind == "seats":
            members = self.connection.execute(
                select(func.count())
                .select_from(s.memberships)
                .where(s.memberships.c.workspace_id == wid)
            ).scalar_one()
            pending = self.connection.execute(
                select(func.count())
                .select_from(s.invitations)
                .where(
                    s.invitations.c.workspace_id == wid,
                    s.invitations.c.status == "pending",
                    s.invitations.c.expires_at > now,
                )
            ).scalar_one()
            return int(members + pending)
        if kind == "file_bytes":
            return 0
        table = {"datasets": s.datasets, "storage_bytes": s.uploads, "saved_studies": s.studies}[
            kind
        ]
        count = (
            func.coalesce(func.sum(table.c.size), 0) if kind == "storage_bytes" else func.count()
        )
        return int(
            self.connection.execute(
                select(count).select_from(table).where(table.c.workspace_id == wid)
            ).scalar_one()
        )

    def check_plan_stock(self, wid: UUID, kind: str, amount: int, now: datetime) -> None:
        self.connection.execute(
            select(s.workspaces.c.id).where(s.workspaces.c.id == wid).with_for_update()
        ).scalar_one()
        assignment = self.plan_assignment(wid)
        require_active(assignment, now)
        require_capacity(assignment, kind, self.plan_stock(wid, kind, now), amount)

    def plan_used(self, wid: UUID, kind: str, start: datetime, end: datetime) -> int:
        return int(
            self.connection.execute(
                select(func.coalesce(func.sum(s.plan_admissions.c.quantity), 0)).where(
                    s.plan_admissions.c.workspace_id == wid,
                    s.plan_admissions.c.kind == kind,
                    s.plan_admissions.c.created_at >= start,
                    s.plan_admissions.c.created_at < end,
                )
            ).scalar_one()
        )

    def admit_plan_operation(
        self, wid: UUID, actor_id: UUID, kind: str, request_id: UUID, input_hash: str, now: datetime
    ) -> bool:
        if kind not in OPERATIONS:
            raise ValueError("Use a registered product operation")
        self.connection.execute(
            select(s.workspaces.c.id).where(s.workspaces.c.id == wid).with_for_update()
        ).scalar_one()
        assignment = self.plan_assignment(wid)
        if assignment is None:
            return True
        previous = (
            self.connection.execute(
                select(s.plan_admissions).where(
                    s.plan_admissions.c.workspace_id == wid,
                    s.plan_admissions.c.actor_id == actor_id,
                    s.plan_admissions.c.kind == kind,
                    s.plan_admissions.c.request_id == request_id,
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["input_hash"] != input_hash:
                raise IngestionError(
                    "plan_request_conflict",
                    "This operation identifier already belongs to different inputs.",
                    409,
                )
            return False
        assignment = self.plan_assignment(wid)
        require_active(assignment, now)
        if assignment is not None:
            used = self.plan_used(wid, kind, assignment["starts_at"], assignment["ends_at"])
            require_capacity(assignment, kind, used)
        self.connection.execute(
            s.plan_admissions.insert().values(
                workspace_id=wid,
                actor_id=actor_id,
                kind=kind,
                request_id=request_id,
                input_hash=input_hash,
                assignment_id=assignment["id"] if assignment else None,
                quantity=1,
                created_at=now,
            )
        )
        return True
