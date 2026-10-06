"""Use case: Runs audited internal administration and private support conversations.

What it does: Rechecks staff grants and publishes private, versioned support changes.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.workspaces import UnitOfWork, normalized_email
from execplus.domain.audit import audit_cursor, parse_audit_cursor
from execplus.domain.errors import AuthorizationError
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.jobs import JobStage, JobState
from execplus.domain.operations import (
    JOB_FAILURE_CODES,
    MAX_SUPPORT_EVENTS,
    STAFF_ROLES,
    SUPPORT_CATEGORIES,
    SUPPORT_FEATURES,
    SUPPORT_STATUSES,
    StaffAudit,
    StaffGrant,
    SupportEvent,
    SupportTicket,
    support_text,
    support_transition,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def page_input(limit: int, cursor: str | None, q: str) -> tuple[tuple[datetime, UUID] | None, str]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise IngestionError("invalid_page", "Use a page size from one to one hundred.", 422)
    try:
        before = parse_audit_cursor(cursor)
    except IngestionError:
        raise IngestionError("invalid_page", "Reload the list to start a new page.", 422) from None
    return before, support_text(q, 80, optional=True)


def summary(value: SupportTicket) -> dict[str, Any]:
    return {
        key: item
        for key, item in asdict(value).items()
        if key not in {"description", "feedback_id", "job_id"}
    }


class OperationsService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def access(self, actor: User) -> dict[str, str | None]:
        with self.uow() as repo:
            grant = repo.staff_grant(actor.id)
            return {"role": grant.role if grant and grant.revoked_at is None else None}

    @contextmanager
    def staff_scope(
        self,
        actor: User,
        action: str,
        *,
        workspace_id: UUID | None = None,
        resource_id: UUID | None = None,
        admin: bool = False,
    ) -> Iterator[WorkspaceRepository]:
        try:
            with self.uow() as repo:
                grant = repo.staff_grant(actor.id, lock=True)
                if not grant or grant.revoked_at is not None or (admin and grant.role != "admin"):
                    raise IngestionError(
                        "staff_required", "This action requires active staff access.", 403
                    )
                yield repo
                repo.add_staff_audit(
                    StaffAudit(
                        uuid4(),
                        actor.id,
                        action,
                        "api",
                        "success",
                        now(),
                        workspace_id,
                        resource_id,
                    )
                )
        except (IngestionError, AuthorizationError):
            with self.uow() as repo:
                repo.add_staff_audit(StaffAudit(uuid4(), actor.id, action, "api", "denied", now()))
            raise

    def change_staff(self, email: str, role: str | None) -> dict[str, Any]:
        if role is not None and role not in STAFF_ROLES:
            raise IngestionError("invalid_staff_role", "Choose admin or support staff access.", 422)
        timestamp = now()
        with self.uow() as repo:
            user = repo.staff_user(normalized_email(email))
            previous = repo.staff_grant(user.id)
            if role is None and previous is None:
                raise IngestionError(
                    "staff_missing", "This user has no staff grant to revoke.", 404
                )
            value = StaffGrant(
                user.id,
                role or (previous.role if previous else "support"),
                previous.created_at if previous else timestamp,
                timestamp,
                timestamp if role is None else None,
            )
            repo.set_staff_grant(value)
            repo.add_staff_audit(
                StaffAudit(
                    uuid4(),
                    None,
                    "staff.revoked" if role is None else f"staff.granted_{role}",
                    "operator_cli",
                    "success",
                    timestamp,
                    resource_id=user.id,
                )
            )
        return {"user_id": str(user.id), "role": role, "revoked": role is None}

    def staff(self, actor: User) -> dict[str, Any]:
        with self.staff_scope(actor, "staff.listed") as repo:
            return {"staff": repo.active_staff()}

    def workspaces(
        self, actor: User, *, limit: int = 50, cursor: str | None = None, q: str = ""
    ) -> dict[str, Any]:
        before, q = page_input(limit, cursor, q)
        with self.staff_scope(actor, "admin.workspaces_listed", admin=True) as repo:
            values = repo.admin_workspaces(before=before, q=q, limit=limit + 1)
            selected = values[:limit]
            return {
                "workspaces": [
                    {**value, "plan": {"id": "private_demo", "billing": "unconfigured"}}
                    for value in selected
                ],
                "next_cursor": audit_cursor(selected[-1]["created_at"], selected[-1]["id"])
                if len(values) > limit
                else None,
                "limit": limit,
            }

    def workspace(self, actor: User, wid: UUID) -> dict[str, Any]:
        with self.staff_scope(
            actor, "admin.workspace_opened", workspace_id=wid, admin=True
        ) as repo:
            return {
                **repo.admin_workspace(wid),
                "plan": {"id": "private_demo", "billing": "unconfigured"},
            }

    def _ticket(
        self,
        repo: WorkspaceRepository,
        actor: User,
        wid: UUID,
        tid: UUID,
        *,
        staff: bool,
        lock: bool = False,
    ) -> SupportTicket:
        if not staff:
            repo.membership(wid, actor.id)
        value = repo.support_ticket(wid, tid, lock=lock)
        if not staff and value.requester_id != actor.id:
            raise AuthorizationError("Support request unavailable")
        return value

    def _detail(self, repo: WorkspaceRepository, value: SupportTicket) -> dict[str, Any]:
        diagnostics = None
        if value.job_id:
            job = repo.job(value.workspace_id, value.job_id)
            if job.owner_id != value.requester_id:
                raise AuthorizationError("Support diagnostics unavailable")
            diagnostics = dict(
                id=job.id,
                status=job.status
                if job.status in {state.value for state in JobState}
                else "unknown",
                current_stage=job.current_stage
                if job.current_stage in {stage.value for stage in JobStage}
                else None,
                failure_code=job.failure_code if job.failure_code in JOB_FAILURE_CODES else None,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        return dict(
            ticket=asdict(value),
            events=[asdict(event) for event in repo.support_events(value.workspace_id, value.id)],
            diagnostics=diagnostics,
        )

    @contextmanager
    def _scope(
        self, actor: User, wid: UUID | None, tid: UUID | None, action: str, staff: bool
    ) -> Iterator[WorkspaceRepository]:
        if staff:
            with self.staff_scope(
                actor, action, workspace_id=wid if tid else None, resource_id=tid
            ) as repo:
                yield repo
        else:
            with self.uow() as repo:
                if wid is None:
                    raise AuthorizationError("Workspace required")
                repo.membership(wid, actor.id)
                yield repo

    def tickets(
        self,
        actor: User,
        wid: UUID | None,
        *,
        staff: bool = False,
        limit: int = 50,
        cursor: str | None = None,
        status: str = "",
        priority: str = "",
        q: str = "",
    ) -> dict[str, Any]:
        before, q = page_input(limit, cursor, q)
        if (status and status not in SUPPORT_STATUSES) or (
            priority and priority not in {"normal", "high"}
        ):
            raise IngestionError(
                "invalid_support_filter", "Choose supported status and priority filters.", 422
            )
        with self._scope(actor, wid, None, "support.listed", staff) as repo:
            values = repo.support_tickets(
                workspace_id=wid,
                requester_id=None if staff else actor.id,
                before=before,
                status=status,
                priority=priority,
                q=q,
                limit=limit + 1,
            )
            selected = values[:limit]
            return dict(
                tickets=[summary(value) for value in selected],
                limit=limit,
                next_cursor=audit_cursor(selected[-1].created_at, selected[-1].id)
                if len(values) > limit
                else None,
            )

    def ticket(self, actor: User, wid: UUID, tid: UUID, *, staff: bool = False) -> dict[str, Any]:
        with self._scope(actor, wid, tid, "support.opened", staff) as repo:
            return self._detail(repo, self._ticket(repo, actor, wid, tid, staff=staff))

    def _event(
        self,
        repo: WorkspaceRepository,
        actor: User,
        value: SupportTicket,
        kind: str,
        body: str,
        staff: bool,
    ) -> None:
        repo.add_support_event(
            SupportEvent(
                uuid4(),
                value.workspace_id,
                value.id,
                value.version,
                actor.id,
                "staff" if staff else "requester",
                kind,
                body,
                value.status,
                value.priority,
                value.assignee_id,
                value.updated_at,
            )
        )
        repo.add(
            AuditEvent(
                uuid4(),
                value.workspace_id,
                actor.id,
                f"support.{kind}",
                "support",
                value.id,
                value.updated_at,
            )
        )

    def create(self, actor: User, wid: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        subject = support_text(raw["subject"], 120)
        description = support_text(raw["description"], 4000)
        if raw["feature"] not in SUPPORT_FEATURES or raw["category"] not in SUPPORT_CATEGORIES:
            raise IngestionError("invalid_support", "Choose a supported feature and category.", 422)
        timestamp = now()
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            if repo.support_open_count(wid, actor.id) >= 50:
                raise IngestionError(
                    "support_limit",
                    "Resolve existing requests before opening more than fifty.",
                    409,
                )
            feedback_id, job_id = raw.get("feedback_id"), raw.get("job_id")
            if feedback_id and not repo.support_feedback_owned(wid, feedback_id, actor.id):
                raise AuthorizationError("Feedback unavailable")
            if job_id and repo.job(wid, job_id).owner_id != actor.id:
                raise AuthorizationError("Support diagnostics unavailable")
            value = SupportTicket(
                uuid4(),
                wid,
                actor.id,
                subject,
                description,
                raw["feature"],
                raw["category"],
                "open",
                "normal",
                1,
                timestamp,
                timestamp,
                feedback_id=feedback_id,
                job_id=job_id,
            )
            repo.add_support_ticket(value)
            self._event(repo, actor, value, "created", "", False)
            return self._detail(repo, value)

    def change(
        self,
        actor: User,
        wid: UUID,
        tid: UUID,
        raw: dict[str, Any],
        *,
        staff: bool = False,
        kind: str = "updated",
    ) -> dict[str, Any]:
        body = support_text(raw.get("body", ""), 4000, optional=kind != "message")
        expected = raw["expected_version"]
        if type(expected) is not int or expected < 1:
            raise IngestionError("invalid_support", "Provide the current request version.", 422)
        with self._scope(actor, wid, tid, f"support.{kind}", staff) as repo:
            repo.workspace(wid, lock=True)
            value = self._ticket(repo, actor, wid, tid, staff=staff, lock=True)
            if value.version != expected:
                raise IngestionError(
                    "support_conflict", "This request changed. Reload it before editing.", 409
                )
            if value.version >= MAX_SUPPORT_EVENTS:
                raise IngestionError(
                    "support_limit",
                    "This request reached its timeline limit. Open a new request.",
                    409,
                )
            if kind != "reopened" and value.status == "resolved":
                raise IngestionError("support_resolved", "Reopen this request before editing.", 409)
            if kind == "updated" and not staff:
                raise AuthorizationError("Staff update unavailable")
            status, priority, assignee = value.status, value.priority, value.assignee_id
            if kind == "reopened":
                support_transition(status, "open", reopen=True)
                if repo.support_open_count(wid, value.requester_id) >= 50:
                    raise IngestionError(
                        "support_limit", "Resolve existing requests before reopening more.", 409
                    )
                status = "open"
            elif kind == "message":
                if status == "resolved":
                    raise IngestionError(
                        "support_resolved", "Reopen this request before replying.", 409
                    )
            else:
                if "status" in raw and raw["status"] != status:
                    support_transition(status, raw["status"])
                    status = raw["status"]
                if "priority" in raw:
                    priority = raw["priority"]
                    if priority not in {"normal", "high"}:
                        raise IngestionError(
                            "invalid_support", "Choose normal or high priority.", 422
                        )
                if "assignee_id" in raw:
                    assignee = raw["assignee_id"]
                    grant = repo.staff_grant(assignee, lock=True) if assignee else None
                    if assignee and (not grant or grant.revoked_at is not None):
                        raise IngestionError(
                            "invalid_assignee", "Assign an active staff member.", 422
                        )
                if (status, priority, assignee) == (
                    value.status,
                    value.priority,
                    value.assignee_id,
                ) and not body:
                    raise IngestionError(
                        "support_unchanged", "Choose a change or add a reply.", 422
                    )
            timestamp = now()
            updated = replace(
                value,
                status=status,
                priority=priority,
                assignee_id=assignee,
                version=value.version + 1,
                updated_at=timestamp,
                resolved_at=timestamp
                if status == "resolved" and value.status != "resolved"
                else value.resolved_at
                if status == "resolved"
                else None,
            )
            repo.set_support_ticket(updated, expected)
            self._event(repo, actor, updated, kind, body, staff)
            return self._detail(repo, updated)
