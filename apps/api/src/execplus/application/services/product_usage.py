"""Use case: Serves authorized aggregate product activity and cohort reports.

What it does: Captures one aggregate statement without holding workspace/staff locks,
then rechecks exact policy, membership and staff epochs before publishing its report.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.dataset_access import require_workspace_access
from execplus.application.services.operations import OperationsService
from execplus.application.services.workspaces import UnitOfWork
from execplus.domain.dataset_access import denied
from execplus.domain.errors import AuthorizationError
from execplus.domain.ingestion import IngestionError, Membership, User, require_manager
from execplus.domain.operations import StaffAudit, StaffGrant
from execplus.domain.product_usage import report_start, usage_report


def policy_scope(repo: WorkspaceRepository, actor: User, wid: UUID) -> tuple[tuple[str, str], ...]:
    repo.workspace(wid, lock=True)
    require_workspace_access(repo, actor, wid)
    sources = []
    for dataset in repo.datasets(wid):
        policy = repo.dataset_access_policy(wid, dataset.id)
        sources.append((str(dataset.id), str(policy.id) if policy else ""))
    return tuple(sorted(sources))


def staff_access(repo: WorkspaceRepository, actor: User) -> StaffGrant:
    grant = repo.staff_grant(actor.id, lock=True)
    if grant is None or grant.revoked_at is not None or grant.role != "admin":
        raise IngestionError("staff_required", "This action requires active staff access.", 403)
    return grant


def optional_membership(repo: WorkspaceRepository, actor: User, wid: UUID) -> Membership | None:
    try:
        return repo.membership(wid, actor.id)
    except IngestionError as error:
        if error.status != 404:
            raise
        return None


class ProductUsageService:
    def __init__(self, uow: UnitOfWork, operations: OperationsService) -> None:
        self.uow = uow
        self.operations = operations

    def overview(self, actor: User, wid: UUID, weeks: int = 8) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        start = report_start(now, weeks)
        with self.uow() as repo:
            scope = policy_scope(repo, actor, wid)
            membership = repo.membership(wid, actor.id)
            require_manager(membership.role)
        with self.uow() as repo:
            facts = repo.product_usage_facts(wid, start, now)
        result = usage_report(wid, now, weeks, facts)
        with self.uow() as repo:
            current_scope = policy_scope(repo, actor, wid)
            current_member = repo.membership(wid, actor.id)
            require_manager(current_member.role)
            if current_scope != scope or current_member != membership:
                raise denied()
            return result

    def staff_overview(self, actor: User, wid: UUID, weeks: int = 8) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        start = report_start(now, weeks)
        try:
            with self.uow() as repo:
                grant = staff_access(repo, actor)
                scope = policy_scope(repo, actor, wid)
                membership = optional_membership(repo, actor, wid)
            with self.uow() as repo:
                facts = repo.product_usage_facts(wid, start, now)
            result = usage_report(wid, now, weeks, facts)
            with self.uow() as repo:
                if staff_access(repo, actor) != grant:
                    raise IngestionError("staff_required", "Staff access changed. Try again.", 403)
                if (
                    policy_scope(repo, actor, wid) != scope
                    or optional_membership(repo, actor, wid) != membership
                ):
                    raise denied()
                repo.add_staff_audit(
                    StaffAudit(
                        uuid4(),
                        actor.id,
                        "admin.product_usage",
                        "api",
                        "success",
                        datetime.now(timezone.utc),
                        wid,
                    )
                )
                return result
        except (IngestionError, AuthorizationError):
            with self.uow() as repo:
                repo.add_staff_audit(
                    StaffAudit(
                        uuid4(),
                        actor.id,
                        "admin.product_usage",
                        "api",
                        "denied",
                        datetime.now(timezone.utc),
                    )
                )
            raise
