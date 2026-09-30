"""Use case: Schedules self-subscribed reports with delivery-time authorization.

What it does: Claims each due slot once, replays saved evidence, and audits safe delivery outcomes.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from execplus.application.ports import EmailDelivery, WorkspaceRepository
from execplus.application.services.analytics import AnalyticsService, UnitOfWork
from execplus.domain.activation import ReportDelivery, ReportSchedule
from execplus.domain.ingestion import AuditEvent, IngestionError, User


class ReportService:
    def __init__(
        self, uow: UnitOfWork, analytics: AnalyticsService, email: EmailDelivery, web_origin: str
    ) -> None:
        self.uow = uow
        self.analytics = analytics
        self.email = email
        self.web_origin = web_origin.rstrip("/")

    def _item(self, repo: WorkspaceRepository, actor: User, wid: UUID, itemid: UUID) -> UUID:
        repo.membership(wid, actor.id)
        item = repo.saved_item(wid, itemid)
        if (not item.shared and item.owner_id != actor.id) or item.kind != "analysis":
            raise IngestionError("not_found", "Choose an accessible saved analysis.", 404)
        return UUID(str(item.payload["query_id"]))

    async def create(
        self, actor: User, wid: UUID, itemid: UUID, interval_hours: int
    ) -> ReportSchedule:
        if not 1 <= interval_hours <= 8760:
            raise IngestionError(
                "invalid_schedule", "Choose an interval from 1 to 8760 hours.", 422
            )
        now = datetime.now(timezone.utc)
        schedule = ReportSchedule(
            uuid4(),
            wid,
            actor.id,
            itemid,
            interval_hours,
            now + timedelta(hours=interval_hours),
            True,
            now,
        )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self._item(repo, actor, wid, itemid)
            if len(repo.report_schedules(wid, actor.id)) >= 20:
                raise IngestionError(
                    "schedule_limit",
                    "At most twenty schedules per workspace member are supported.",
                    422,
                )
            repo.add(schedule)
            repo.add(
                AuditEvent(
                    uuid4(), wid, actor.id, "report.scheduled", "report_schedule", schedule.id, now
                )
            )
        return schedule

    async def list_schedules(self, actor: User, wid: UUID) -> tuple[ReportSchedule, ...]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            return repo.report_schedules(wid, actor.id)

    async def unsubscribe(self, actor: User, wid: UUID, scheduleid: UUID) -> None:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            schedule = repo.report_schedule(wid, scheduleid)
            if schedule.owner_id != actor.id:
                raise IngestionError("not_found", "The schedule is unavailable.", 404)
            repo.set_report_schedule(replace(schedule, enabled=False))
            repo.add(
                AuditEvent(
                    uuid4(),
                    wid,
                    actor.id,
                    "report.unsubscribed",
                    "report_schedule",
                    scheduleid,
                    datetime.now(timezone.utc),
                )
            )

    async def deliver_due(self, now: datetime | None = None) -> dict[str, int]:
        now = now or datetime.now(timezone.utc)
        counts = {"sent": 0, "failed": 0, "unauthorized": 0, "cancelled": 0}
        with self.uow() as repo:
            due = repo.due_schedules(now)
        for wid, scheduleid in due:
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                try:
                    schedule = repo.report_schedule(wid, scheduleid)
                except IngestionError as error:
                    if error.status == 404:
                        continue
                    raise
                if not schedule.enabled or schedule.next_due > now:
                    continue
                if repo.report_delivery(wid, scheduleid, schedule.next_due) is not None:
                    continue
                delivery = ReportDelivery(
                    uuid4(), wid, scheduleid, schedule.next_due, "claimed", now
                )
                repo.add(delivery)
                repo.set_report_schedule(
                    replace(schedule, next_due=now + timedelta(hours=schedule.interval_hours))
                )
                actor = repo.user(schedule.owner_id)
            status = "failed"
            try:
                with self.uow() as repo:
                    query_id = self._item(repo, actor, wid, schedule.item_id)
                result, lineage = await self.analytics.replay(actor, wid, query_id)
                with self.uow() as repo:
                    repo.workspace(wid, lock=True)
                    latest = repo.report_schedule(wid, scheduleid)
                    if not latest.enabled:
                        status = "cancelled"
                    else:
                        self._item(repo, actor, wid, latest.item_id)
                        values = "\n".join(
                            " | ".join(str(cell) for cell in row) for row in result.rows
                        )
                        body = (
                            "Saved analysis (original revision)\n"
                            + " | ".join(result.columns)
                            + "\n"
                            + values
                            + f"\nEvidence: {lineage.query_id}\n"
                            + f"Manage or unsubscribe: {self.web_origin}/workspace"
                            + f"?workspace={wid}&saved={latest.item_id}\n"
                        )
                        self.email.send(
                            actor.email, "ExecPlus saved analysis report", body, delivery.id
                        )
                        status = "sent"
            except IngestionError as error:
                status = "unauthorized" if error.status in {403, 404} else "failed"
            except Exception:
                status = "failed"
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                repo.set_report_delivery(replace(delivery, status=status))
                if status == "unauthorized":
                    try:
                        latest = repo.report_schedule(wid, scheduleid)
                    except IngestionError as error:
                        if error.status != 404:
                            raise
                        status = "cancelled"
                    else:
                        repo.set_report_schedule(replace(latest, enabled=False))
                repo.add(
                    AuditEvent(
                        uuid4(),
                        wid,
                        actor.id,
                        f"report.{status}",
                        "report_delivery",
                        delivery.id,
                        now,
                    )
                )
            counts[status] += 1
        return counts
