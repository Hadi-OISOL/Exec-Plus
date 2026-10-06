"""Use case: Aggregates operational usage without materializing private event histories.

What it does: Executes tenant-scoped SQL projections for onboarding, usage and mature cohorts.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Date, Select, and_, case, cast, distinct, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.sql.selectable import ScalarSelect

from execplus.domain.product_usage import ACTIVATION_ACTIONS, ACTIVITY_FEATURES, UsageFacts
from execplus.infrastructure.persistence import schema as s


class SQLReportingRepository:
    connection: Connection

    def usage_totals(self, workspace_id: UUID, now: datetime) -> dict[str, int]:
        members = (
            select(func.count())
            .select_from(s.memberships)
            .where(s.memberships.c.workspace_id == workspace_id)
            .scalar_subquery()
        )
        reserved = (
            select(func.count())
            .select_from(s.invitations)
            .where(
                s.invitations.c.workspace_id == workspace_id,
                s.invitations.c.status == "pending",
                s.invitations.c.expires_at > now,
            )
            .scalar_subquery()
        )
        uploads = (
            select(func.count())
            .select_from(s.uploads)
            .where(s.uploads.c.workspace_id == workspace_id)
            .scalar_subquery()
        )
        storage = (
            select(func.coalesce(func.sum(s.uploads.c.size), 0))
            .where(s.uploads.c.workspace_id == workspace_id)
            .scalar_subquery()
        )
        row = (
            self.connection.execute(
                select(
                    members.label("active_seats"),
                    reserved.label("reserved_seats"),
                    s.workspaces.c.seat_limit,
                    uploads.label("uploads"),
                    storage.label("storage_bytes"),
                ).where(s.workspaces.c.id == workspace_id)
            )
            .mappings()
            .one()
        )
        return {str(key): int(value) for key, value in row.items()}

    def activation_overview(self, workspace_id: UUID, *, manager: bool) -> dict[str, object]:
        events, usage, feedback = s.audit_events, s.usage_events, s.feedback
        totals = self.usage_totals(workspace_id, datetime.now(timezone.utc))
        datasets = int(
            self.connection.execute(
                select(func.count())
                .select_from(s.datasets)
                .where(s.datasets.c.workspace_id == workspace_id)
            ).scalar_one()
        )
        kinds = {
            str(action): int(count)
            for action, count in self.connection.execute(
                select(events.c.action, func.count())
                .where(events.c.workspace_id == workspace_id)
                .group_by(events.c.action)
            )
        }
        quantities = {
            str(kind): int(quantity)
            for kind, quantity in self.connection.execute(
                select(usage.c.kind, func.sum(usage.c.quantity))
                .where(usage.c.workspace_id == workspace_id)
                .group_by(usage.c.kind)
            )
        }
        completed = {
            "workspace": True,
            "invite_teammate": totals["active_seats"] > 1,
            "upload": quantities.get("upload", 0) > 0 or kinds.get("upload.stored", 0) > 0,
            "explore_dashboard_or_question": kinds.get("query.executed", 0) > 0,
            "save_analysis": kinds.get("saved_item.created", 0) > 0,
        }
        weeks: dict[str, int] = {}
        returning = 0
        negative = 0
        if manager:
            week = func.to_char(func.timezone("UTC", events.c.created_at), 'IYYY-"W"IW')
            weeks = {
                str(period): int(count)
                for period, count in self.connection.execute(
                    select(week, func.count(distinct(events.c.actor_id)))
                    .where(events.c.workspace_id == workspace_id)
                    .group_by(week)
                    .order_by(week)
                )
            }
            repeat = select(events.c.actor_id).where(events.c.workspace_id == workspace_id)
            repeat = repeat.group_by(events.c.actor_id).having(func.count(distinct(week)) >= 2)
            returning = int(
                self.connection.execute(
                    select(func.count()).select_from(repeat.subquery())
                ).scalar_one()
            )
            negative = int(
                self.connection.execute(
                    select(func.count())
                    .select_from(feedback)
                    .where(
                        feedback.c.workspace_id == workspace_id,
                        feedback.c.rating <= 2,
                    )
                ).scalar_one()
            )
        return {
            "checklist": [dict(id=key, complete=value) for key, value in completed.items()],
            "next_steps": [key for key, done in completed.items() if not done],
            "datasets": datasets,
            "seats": {"used": totals["active_seats"], "limit": totals["seat_limit"]},
            "feature_adoption": dict(sorted(kinds.items())) if manager else {},
            "weekly_active_users": weeks,
            "returning_users": returning if manager else None,
            "retention_definition": "An actor with activity in at least two ISO calendar weeks.",
            "usage": dict(sorted(quantities.items())) if manager else {},
            "support_signals": {
                "negative_feedback": negative,
                "failed_queries": kinds.get("query.failed", 0),
            }
            if manager
            else {},
        }

    def product_usage_facts(self, workspace_id: UUID, start: datetime, now: datetime) -> UsageFacts:
        def array_rows(statement: Select[Any]) -> ScalarSelect[Any]:
            rows = statement.subquery()
            value = func.json_build_array(*rows.c)
            ordered = aggregate_order_by(value, *(column.asc() for column in rows.c))
            return (
                select(func.coalesce(func.json_agg(ordered), func.json_build_array()))
                .select_from(rows)
                .scalar_subquery()
            )

        events, members = s.audit_events, s.memberships
        week = cast(func.date_trunc("week", func.timezone("UTC", events.c.created_at)), Date)
        qualifies = and_(
            events.c.workspace_id == workspace_id,
            events.c.action.in_(tuple(ACTIVITY_FEATURES)),
            events.c.created_at < now,
        )
        window = and_(qualifies, events.c.created_at >= start)
        first = (
            select(
                events.c.actor_id.label("actor_id"),
                func.min(events.c.created_at).label("first_at"),
                func.max(events.c.created_at).label("last_at"),
            )
            .where(qualifies)
            .group_by(events.c.actor_id)
            .cte("first_activity")
        )
        first_week = cast(func.date_trunc("week", func.timezone("UTC", first.c.first_at)), Date)
        weekly = array_rows(
            select(
                week.label("week"),
                func.count(distinct(events.c.actor_id)).label("users"),
                func.count().label("actions"),
            )
            .where(window)
            .group_by(week)
        )
        feature = case(ACTIVITY_FEATURES, value=events.c.action)
        features = array_rows(
            select(
                feature.label("feature"),
                func.count(distinct(events.c.actor_id)).label("users"),
                func.count().label("actions"),
            )
            .where(window)
            .group_by(feature)
        )
        cohorts = array_rows(
            select(first_week.label("cohort"), func.count().label("users"))
            .where(first.c.first_at >= start)
            .group_by(first_week)
        )
        activity = (
            select(events.c.actor_id, week.label("week"))
            .where(window)
            .distinct()
            .cte("active_weeks")
        )
        retained = array_rows(
            select(first_week.label("cohort"), activity.c.week, func.count().label("users"))
            .select_from(first.join(activity, first.c.actor_id == activity.c.actor_id))
            .where(first.c.first_at >= start)
            .group_by(first_week, activity.c.week)
        )
        current = (
            select(members.c.user_id)
            .where(members.c.workspace_id == workspace_id)
            .cte("current_members")
        )
        active_users = (
            select(func.count(distinct(events.c.actor_id))).where(window).scalar_subquery()
        )
        active_members = (
            select(func.count())
            .select_from(first.join(current, current.c.user_id == first.c.actor_id))
            .where(first.c.last_at >= start)
            .scalar_subquery()
        )
        activated_members = (
            select(func.count(distinct(events.c.actor_id)))
            .where(
                events.c.workspace_id == workspace_id,
                events.c.action.in_(ACTIVATION_ACTIONS),
                events.c.created_at < now,
                events.c.actor_id.in_(select(current.c.user_id)),
            )
            .scalar_subquery()
        )
        never_active = (
            select(func.count())
            .select_from(current.outerjoin(first, current.c.user_id == first.c.actor_id))
            .where(first.c.actor_id.is_(None))
            .scalar_subquery()
        )
        inactive = (
            select(func.count())
            .select_from(current.join(first, current.c.user_id == first.c.actor_id))
            .where(first.c.last_at < now - timedelta(days=14))
            .scalar_subquery()
        )
        quantities = array_rows(
            select(s.usage_events.c.kind, func.sum(s.usage_events.c.quantity).label("quantity"))
            .where(
                s.usage_events.c.workspace_id == workspace_id,
                s.usage_events.c.created_at >= start,
                s.usage_events.c.created_at < now,
                s.usage_events.c.kind.in_(("upload", "storage_bytes")),
            )
            .group_by(s.usage_events.c.kind)
        )
        counts = array_rows(
            select(events.c.action, func.count().label("count"))
            .where(
                events.c.workspace_id == workspace_id,
                events.c.created_at >= start,
                events.c.created_at < now,
                events.c.action.in_(("query.executed", "query.failed", "forecast.created")),
            )
            .group_by(events.c.action)
        )
        row = (
            self.connection.execute(
                select(
                    active_users.label("active_users"),
                    active_members.label("active_members"),
                    select(func.count())
                    .select_from(current)
                    .scalar_subquery()
                    .label("current_members"),
                    activated_members.label("activated_members"),
                    never_active.label("never_active_members"),
                    inactive.label("inactive_14d_members"),
                    weekly.label("weekly"),
                    features.label("features"),
                    cohorts.label("cohorts"),
                    retained.label("retained"),
                    quantities.label("quantities"),
                    counts.label("counts"),
                )
            )
            .mappings()
            .one()
        )
        summary = {
            name: int(row[name])
            for name in (
                "active_users",
                "active_members",
                "current_members",
                "activated_members",
                "never_active_members",
                "inactive_14d_members",
            )
        }
        quantities_by_kind = {str(kind): int(quantity) for kind, quantity in row["quantities"]}
        counts_by_action = {str(action): int(count) for action, count in row["counts"]}
        usage = {
            "uploads": quantities_by_kind.get("upload", 0),
            "storage_bytes": quantities_by_kind.get("storage_bytes", 0),
            "queries_completed": counts_by_action.get("query.executed", 0),
            "queries_failed": counts_by_action.get("query.failed", 0),
            "forecasts_created": counts_by_action.get("forecast.created", 0),
        }
        return UsageFacts(
            summary,
            tuple(
                (date.fromisoformat(period), int(users), int(actions))
                for period, users, actions in row["weekly"]
            ),
            tuple(
                (str(name), int(users), int(actions)) for name, users, actions in row["features"]
            ),
            tuple((date.fromisoformat(period), int(users)) for period, users in row["cohorts"]),
            tuple(
                (date.fromisoformat(cohort), date.fromisoformat(active), int(users))
                for cohort, active, users in row["retained"]
            ),
            usage,
        )
