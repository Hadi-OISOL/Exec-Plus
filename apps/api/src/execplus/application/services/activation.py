"""Use case: Provides evidence-linked activation and tenant-safe feedback analytics.

What it does: Authorizes observations, comparisons, checklists and aggregate usage signals.
"""

from collections import Counter
from datetime import datetime, timezone
from uuid import UUID, uuid4

from execplus.application.services.analytics import AnalyticsService, UnitOfWork
from execplus.domain.activation import Feedback, comparison, observations
from execplus.domain.ingestion import AuditEvent, IngestionError, User, require_manager

FEATURES = {"upload", "profile", "dashboard", "question", "knowledge", "report", "onboarding"}
CATEGORIES = {"helpful", "confusing", "incorrect", "slow", "missing_feature"}


class ActivationService:
    def __init__(self, uow: UnitOfWork, analytics: AnalyticsService, release: str) -> None:
        self.uow = uow
        self.analytics = analytics
        self.release = release

    async def insights(
        self, actor: User, wid: UUID, did: UUID, uid: UUID
    ) -> list[dict[str, object]]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.upload(wid, did, uid)
            revision = repo.active_revision(wid, did, uid)
            if revision is None:
                raise IngestionError("not_found", "Profile this upload first.", 404)
            return observations(revision)

    async def compare(
        self, actor: User, wid: UUID, current_id: UUID, previous_id: UUID
    ) -> dict[str, object]:
        current, current_lineage = await self.analytics.replay(actor, wid, current_id)
        previous, previous_lineage = await self.analytics.replay(actor, wid, previous_id)
        if (
            current_lineage.dataset_id != previous_lineage.dataset_id
            or current_lineage.metric != previous_lineage.metric
            or current_lineage.aggregation != previous_lineage.aggregation
            or current_lineage.grouping
            or previous_lineage.grouping
            or len(current.rows) != 1
            or len(previous.rows) != 1
        ):
            raise IngestionError(
                "incomparable", "Compare the same metric and aggregation without grouping.", 422
            )
        result = comparison(current.rows[0][0], previous.rows[0][0], current_id, previous_id)
        await self.analytics.record_narrative(
            actor,
            wid,
            (str(previous_id), str(current_id)),
            str(result["observation"]),
            "deterministic:comparison-v1",
        )
        return result

    async def feedback(
        self, actor: User, wid: UUID, feature: str, rating: int, category: str
    ) -> Feedback:
        if feature not in FEATURES or category not in CATEGORIES or not 1 <= rating <= 5:
            raise IngestionError(
                "invalid_feedback", "Choose a supported feature, rating and category.", 422
            )
        now = datetime.now(timezone.utc)
        entry = Feedback(uuid4(), wid, actor.id, feature, rating, category, self.release, now)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            repo.add(entry)
            repo.add(
                AuditEvent(uuid4(), wid, actor.id, "feedback.recorded", "feedback", entry.id, now)
            )
        return entry

    async def overview(self, actor: User, wid: UUID, *, manager: bool = False) -> dict[str, object]:
        with self.uow() as repo:
            membership = repo.membership(wid, actor.id)
            if manager:
                require_manager(membership.role)
            workspace = repo.workspace(wid)
            members = repo.members(wid)
            datasets = repo.datasets(wid)
            usage = repo.usage_events(wid)
            events = repo.audit_events(wid)
            feedback = repo.feedback(wid) if manager else ()
        kinds = Counter(event.action for event in events)
        quantities = Counter[str]()
        for event in usage:
            quantities[event.kind] += event.quantity
        completed = {
            "workspace": True,
            "invite_teammate": len(members) > 1,
            "upload": quantities["upload"] > 0 or kinds["upload.stored"] > 0,
            "explore_dashboard_or_question": kinds["query.executed"] > 0,
            "save_analysis": kinds["saved_item.created"] > 0,
        }
        weeks: dict[str, set[UUID]] = {}
        for activity in events:
            iso = activity.created_at.isocalendar()
            weeks.setdefault(f"{iso.year}-W{iso.week:02}", set()).add(activity.actor_id)
        returning = set()
        seen: set[UUID] = set()
        for week in sorted(weeks):
            returning.update(seen & weeks[week])
            seen.update(weeks[week])
        return {
            "checklist": [{"id": key, "complete": value} for key, value in completed.items()],
            "next_steps": [key for key, done in completed.items() if not done],
            "datasets": len(datasets),
            "seats": {"used": len(members), "limit": workspace.seat_limit},
            "feature_adoption": dict(sorted(kinds.items())) if manager else {},
            "weekly_active_users": {key: len(value) for key, value in sorted(weeks.items())}
            if manager
            else {},
            "returning_users": len(returning) if manager else None,
            "retention_definition": "An actor with activity in at least two ISO calendar weeks.",
            "usage": dict(sorted(quantities.items())) if manager else {},
            "support_signals": {
                "negative_feedback": sum(item.rating <= 2 for item in feedback),
                "failed_queries": kinds["query.failed"],
            }
            if manager
            else {},
        }
