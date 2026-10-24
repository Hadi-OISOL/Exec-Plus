"""Use case: Controls local workspace allowances without billing integrations.

What it does: Reuses workspace transactions for explicit assignments, private
remaining allowances and immutable operation admission before bounded work.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.dataset_access import require_workspace_access
from execplus.domain.errors import AuthorizationError
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.operations import StaffAudit
from execplus.domain.plans import (
    LIMITS,
    OPERATIONS,
    STOCK,
    checked_key,
    checked_limits,
    checked_period,
    fingerprint,
    usage_notices,
    usage_state,
)

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


def now() -> datetime:
    return datetime.now(timezone.utc)


def operator(repo: WorkspaceRepository, actor: User) -> None:
    repo.require_active_actor(actor.id)
    grant = repo.staff_grant(actor.id, lock=True)
    if grant is None or grant.revoked_at is not None or grant.role != "admin":
        raise IngestionError(
            "staff_required", "An active administrator must assign local plans.", 403
        )


def admit(
    repo: WorkspaceRepository, actor: User, wid: UUID, kind: str, identifier: UUID, inputs: Any
) -> bool:
    repo.workspace(wid, lock=True)
    repo.membership(wid, actor.id)
    return repo.admit_plan_operation(wid, actor.id, kind, identifier, fingerprint(inputs), now())


def allowances(
    repo: WorkspaceRepository, wid: UUID, *, stock: bool = True
) -> tuple[dict[str, Any] | None, dict[str, Any], datetime]:
    assignment = repo.plan_assignment(wid)
    current = now()
    values = {}
    for kind in sorted(LIMITS):
        limit = assignment["limits"][kind] if assignment else None
        used = (
            (repo.plan_stock(wid, kind, current) if stock else None)
            if kind in STOCK
            else (
                repo.plan_used(wid, kind, assignment["starts_at"], assignment["ends_at"])
                if assignment
                else None
            )
        )
        values[kind] = {
            "limit": limit,
            "used": used,
            "remaining": max(0, limit - used) if limit is not None and used is not None else None,
            "basis": "per_file"
            if kind == "file_bytes"
            else "current_resources"
            if kind in STOCK
            else "period_operations",
        }
    return assignment, values, current


def ratio(used: int | None, limit: int | None) -> Fraction | None:
    if used is None or limit is None:
        return None
    return Fraction(used, limit) if limit else Fraction(1)


class PlanService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def catalog(self, actor: User) -> list[dict[str, Any]]:
        with self.uow() as repo:
            repo.require_active_actor(actor.id)
            return [
                {key: item[key] for key in ("key", "name", "version", "limits")}
                for item in repo.plan_catalog()
            ]

    def configure(
        self, actor: User, key: str, name: str, limits: dict[str, Any], expected: int
    ) -> dict[str, Any]:
        from execplus.application.services.workspaces import checked_name

        key, name, limits = checked_key(key), checked_name(name), checked_limits(limits)
        with self.uow() as repo:
            operator(repo, actor)
            repo.lock_plan_catalog()
            previous = next((item for item in repo.plan_catalog() if item["key"] == key), None)
            version = previous["version"] if previous else 0
            if expected != version:
                raise IngestionError(
                    "plan_version", "The local catalog changed. Reload it first.", 409
                )
            value = dict(
                key=key,
                version=version + 1,
                name=name,
                limits=limits,
                created_by=actor.id,
                created_at=now(),
            )
            repo.add_plan_catalog(value)
            repo.add_staff_audit(
                StaffAudit(uuid4(), actor.id, "plan.configured", "api", "success", now())
            )
            return value

    def assign(
        self,
        actor: User,
        wid: UUID,
        key: str,
        expected: int,
        starts_at: datetime,
        ends_at: datetime,
    ) -> dict[str, Any]:
        checked_period(starts_at, ends_at)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            operator(repo, actor)
            previous = repo.plan_assignment(wid)
            version = previous["version"] if previous else 0
            if expected != version:
                raise IngestionError(
                    "plan_version", "The workspace plan changed. Reload it first.", 409
                )
            selected = next(
                (item for item in repo.plan_catalog() if item["key"] == checked_key(key)), None
            )
            if selected is None:
                raise IngestionError("plan_key", "Choose an existing local plan.", 422)
            value = dict(
                id=uuid4(),
                workspace_id=wid,
                version=version + 1,
                plan_key=key,
                plan_version=selected["version"],
                limits=selected["limits"],
                starts_at=starts_at,
                ends_at=ends_at,
                assigned_by=actor.id,
                basis="administrator",
                created_at=now(),
            )
            repo.add_plan_assignment(value)
            repo.add_staff_audit(
                StaffAudit(
                    uuid4(),
                    actor.id,
                    "plan.assigned",
                    "api",
                    "success",
                    now(),
                    workspace_id=wid,
                    resource_id=value["id"],
                )
            )
            return value

    def assigned(self, actor: User, wid: UUID) -> dict[str, Any] | None:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            operator(repo, actor)
            return repo.plan_assignment(wid)

    def summary(self, actor: User, wid: UUID) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            if repo.membership(wid, actor.id).role != "owner":
                raise IngestionError(
                    "forbidden", "The workspace owner can view remaining allowances.", 403
                )
            require_workspace_access(repo, actor, wid)
            assignment, values, current = allowances(repo, wid)
            return {
                "assignment": assignment,
                "allowances": values,
                "active": assignment is None
                or assignment["starts_at"] <= current < assignment["ends_at"],
                "billing": (
                    "No billing or payment activation. "
                    "These are local administrator-controlled allowances."
                ),
                "counting": (
                    "Processing counts admitted upload profiling, governed queries "
                    "and new bounded model work. A model's source query and each "
                    "separately admitted computation count separately. "
                    "Failed started work counts. Original receipt replay is not charged again."
                ),
            }

    def usage(self, actor: User, wid: UUID) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            grant = repo.staff_grant(actor.id)
            staff = grant is not None and grant.revoked_at is None and grant.role == "admin"
            limited = False
            if staff:
                repo.require_active_actor(actor.id)
                try:
                    require_workspace_access(repo, actor, wid)
                except (IngestionError, AuthorizationError):
                    limited = True
                repo.add_staff_audit(
                    StaffAudit(uuid4(), actor.id, "plan.usage_viewed", "api", "success", now(), wid)
                )
            else:
                if repo.membership(wid, actor.id).role not in {"owner", "admin"}:
                    raise IngestionError(
                        "forbidden",
                        "Workspace owners and administrators can view usage.",
                        403,
                    )
                require_workspace_access(repo, actor, wid)
            assignment, values, current = allowances(repo, wid, stock=not limited)
            today = current.date()
            first = datetime.combine(today - timedelta(days=29), datetime.min.time(), timezone.utc)
            for value in values.values():
                value["state"] = usage_state(value["used"], value["limit"])
            return {
                "assignment": assignment,
                "active": assignment is None
                or assignment["starts_at"] <= current < assignment["ends_at"],
                "allowances": values,
                "notices": usage_notices(values),
                "daily": {
                    "from": first.date().isoformat(),
                    "to": today.isoformat(),
                    "kinds": sorted(OPERATIONS | {"uploads"}),
                    "rows": repo.plan_daily(wid, first, current + timedelta(seconds=1)),
                },
                "access_limited": limited,
                "counting": (
                    "Exact counts of recorded admissions and stored uploads. Days use UTC. "
                    "Uploads, connector imports, questions and analyses count as processing; "
                    "receipt replays are not counted again."
                ),
            }

    def overview(self, actor: User, limit: int = 50) -> dict[str, Any]:
        with self.uow() as repo:
            operator(repo, actor)
            current = now()
            rows = []
            for item in repo.plan_usage_overview():
                kinds = {
                    kind: {
                        "used": item["used"].get(kind, 0),
                        "limit": item["limits"][kind],
                        "state": usage_state(item["used"].get(kind, 0), item["limits"][kind]),
                    }
                    for kind in sorted(OPERATIONS)
                }
                top = max(
                    (
                        (r, kind)
                        for kind, value in kinds.items()
                        if (r := ratio(value["used"], value["limit"])) is not None
                    ),
                    default=(Fraction(0), None),
                )
                rows.append(
                    {
                        "workspace_id": item["workspace_id"],
                        "name": item["name"],
                        "plan_key": item["plan_key"],
                        "starts_at": item["starts_at"],
                        "ends_at": item["ends_at"],
                        "active": item["starts_at"] <= current < item["ends_at"],
                        "operations": kinds,
                        "highest": top[1],
                        "highest_percent": int(top[0] * 100) if top[1] else 0,
                        "_rank": top[0],
                    }
                )
            # shortcut: ranks every assigned workspace in memory; page in SQL past ~10k plans.
            rows.sort(key=lambda row: (-row["_rank"], row["name"], str(row["workspace_id"])))
            repo.add_staff_audit(
                StaffAudit(uuid4(), actor.id, "plan.usage_listed", "api", "success", now())
            )
            return {
                "workspaces": [
                    {k: v for k, v in row.items() if k != "_rank"} for row in rows[:limit]
                ],
                "total": len(rows),
                "limit": limit,
            }
