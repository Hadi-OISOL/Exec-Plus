"""Use case: Serves authorized aggregate product activity and cohort reports.

What it does: Checks workspace management or explicit staff grants around metadata-only reporting.
"""

from datetime import datetime, timezone
from uuid import UUID

from execplus.application.services.operations import OperationsService
from execplus.application.services.workspaces import UnitOfWork
from execplus.domain.ingestion import User, require_manager
from execplus.domain.product_usage import report_start, usage_report


class ProductUsageService:
    def __init__(self, uow: UnitOfWork, operations: OperationsService) -> None:
        self.uow = uow
        self.operations = operations

    def overview(self, actor: User, wid: UUID, weeks: int = 8) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        start = report_start(now, weeks)
        with self.uow() as repo:
            require_manager(repo.membership(wid, actor.id).role)
            facts = repo.product_usage_facts(wid, start, now)
            require_manager(repo.membership(wid, actor.id).role)
        return usage_report(wid, now, weeks, facts)

    def staff_overview(self, actor: User, wid: UUID, weeks: int = 8) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        start = report_start(now, weeks)
        with self.operations.staff_scope(
            actor, "admin.product_usage", workspace_id=wid, admin=True
        ) as repo:
            repo.workspace(wid)
            facts = repo.product_usage_facts(wid, start, now)
        return usage_report(wid, now, weeks, facts)
