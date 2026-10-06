"""Use case: Defines interpretable product activity and weekly retention reports.

What it does: Builds bounded aggregate views with explicit maturity and inactivity semantics.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from execplus.domain.ingestion import IngestionError

ACTIVITY_FEATURES = {
    "upload.stored": "uploads",
    "cleaning.applied": "preparation",
    "revision.restored": "preparation",
    "job.submitted": "conversation",
    "saved_item.created": "saved_analysis",
    "study.created": "studies",
    "study.rerun": "studies",
    "study.opened": "studies",
    "study.compared": "studies",
    "dashboard.created": "dashboards",
    "dashboard.updated": "dashboards",
    "dashboard.opened": "dashboards",
    "forecast.created": "forecasts",
    "forecast.opened": "forecasts",
    "forecast.compared": "forecasts",
    "document.ingested": "knowledge",
    "knowledge.searched": "knowledge",
    "report.scheduled": "reports",
}
ACTIVATION_ACTIONS = (
    "conversation.complete",
    "saved_item.created",
    "study.created",
    "study.rerun",
    "forecast.created",
)


@dataclass(frozen=True)
class UsageFacts:
    summary: dict[str, int]
    weekly: tuple[tuple[date, int, int], ...]
    features: tuple[tuple[str, int, int], ...]
    cohorts: tuple[tuple[date, int], ...]
    retained: tuple[tuple[date, date, int], ...]
    usage: dict[str, int]


def week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def report_start(now: datetime, weeks: int) -> datetime:
    if type(weeks) is not int or not 1 <= weeks <= 12:
        raise IngestionError("invalid_usage_window", "Choose one to twelve weeks.", 422)
    if now.tzinfo is None:
        raise ValueError("Usage reporting requires an aware clock")
    start = week_start(now.astimezone(timezone.utc).date()) - timedelta(weeks=weeks - 1)
    return datetime.combine(start, datetime.min.time(), timezone.utc)


def usage_report(
    workspace_id: UUID, now: datetime, weeks: int, facts: UsageFacts
) -> dict[str, object]:
    start = report_start(now, weeks)
    now = now.astimezone(timezone.utc)
    current_week = week_start(now.date())
    observed = {period: (users, actions) for period, users, actions in facts.weekly}
    retained = {(cohort, active): people for cohort, active, people in facts.retained}
    weekly: list[dict[str, object]] = []
    for index in range(weeks):
        period = start.date() + timedelta(weeks=index)
        users, actions = observed.get(period, (0, 0))
        weekly.append(
            dict(
                week_start=period.isoformat(),
                active_users=users,
                actions=actions,
                complete=period < current_week,
            )
        )
    cohorts: list[dict[str, object]] = []
    for cohort, size in facts.cohorts:
        cells: list[dict[str, object]] = []
        for offset in range(weeks):
            period = cohort + timedelta(weeks=offset)
            eligible = period < current_week
            count = retained.get((cohort, period), 0) if eligible else None
            percent = (
                str(
                    (Decimal(count) * 100 / Decimal(size)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                )
                if count is not None and size
                else None
            )
            cells.append(
                dict(week_offset=offset, eligible=eligible, retained=count, rate_percent=percent)
            )
        cohorts.append(dict(cohort_week=cohort.isoformat(), users=size, cells=cells))
    return {
        "version": "usage-v1",
        "workspace_id": str(workspace_id),
        "as_of": now.isoformat(),
        "period": {
            "start": start.isoformat(),
            "end": now.isoformat(),
            "weeks": weeks,
            "timezone": "UTC",
        },
        "summary": facts.summary,
        "weekly": weekly,
        "features": [
            dict(feature=feature, users=users, actions=actions)
            for feature, users, actions in facts.features
        ],
        "cohorts": cohorts,
        "usage": facts.usage,
        "definitions": {
            "activity": "Distinct people with recorded deliberate product actions. "
            "Background query completions, staff/support actions and sign-ins do not count.",
            "cohort": "The UTC Monday week of each person's first recorded qualifying "
            "action in this workspace, including history before the displayed window.",
            "retention": "People from that cohort active in the indicated completed UTC "
            "week, divided by the original cohort size. This is weekly, not cumulative.",
            "activation": "Current members with a recorded successful conversation, "
            "saved analysis, study or forecast. A submitted question alone is not activation.",
            "inactivity": "Current members previously active but with no qualifying action "
            "in the last fourteen days. This is a follow-up signal, not predicted churn.",
        },
        "limitations": [
            "Recorded activity is a documented subset of product use; uninstrumented "
            "legacy queries, passive views and off-platform work are not measured.",
            "Current-week retention is unavailable until the week ends; weekly activity "
            "for that week is provisional. Historical cohorts include "
            "subsequently removed members.",
            "Counts are not billing entitlements, paid-customer retention or a churn model.",
            "Usage totals cover the displayed period. Query counts include background "
            "computations; those computations do not independently establish human retention.",
            "Reopening saved evidence and sample uploads can count as deliberate activity. "
            "Actions count recorded events, not unique browser visits or sessions.",
        ],
    }
