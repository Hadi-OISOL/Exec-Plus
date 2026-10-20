"""Use case: Lets people forecast with one click, or explains kindly why a file cannot be forecast.

What it does: Detects a complete date column, measure, frequency and horizon from profile facts.
"""

from calendar import monthrange
from datetime import date, timedelta
from typing import Any

from execplus.domain.exploration_selection import exploration_rank, suggested_aggregation
from execplus.domain.forecasting import MIN_HISTORY, MIN_HOLDOUT, MIN_TRAINING
from execplus.domain.guidance import DescriptionContext

PREFERRED_HORIZON = {"daily": 14, "monthly": 3}
NO_TIMELINE = "This file has no dates, so we can't forecast over time"


def _horizon(frequency: str, periods: int) -> int | None:
    for horizon in range(PREFERRED_HORIZON[frequency], 0, -1):
        holdout = max(horizon, MIN_HOLDOUT[frequency])
        if periods >= max(MIN_HISTORY[frequency], MIN_TRAINING[frequency] + 2 * holdout):
            return horizon
    return None


def _months(start: date, end: date) -> tuple[date, date, int]:
    first = start if start.day == 1 else (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = (
        end
        if end.day == monthrange(end.year, end.month)[1]
        else end.replace(day=1) - timedelta(days=1)
    )
    count = (last.year - first.year) * 12 + last.month - first.month + 1
    return first, last, max(count, 0)


def no_timeline(context: DescriptionContext, options: dict[str, Any]) -> dict[str, Any]:
    confirmed = options["state"] != "needs_review"
    return dict(
        kind="no_timeline",
        title=NO_TIMELINE,
        message=(
            "Forecasts need a column of real dates, such as 2025-03-01. Seasons, row numbers "
            "and IDs do not say when something happened, and we never guess a timeline from "
            "the order of rows. Here is what works on this file instead."
        ),
        alternatives=[
            dict(
                tool="unusual_values",
                label="Find unusual values",
                description="Check every measurement for rows that stand out. No settings needed.",
                available=True,
            ),
            dict(
                tool="patterns",
                label="Find patterns",
                description="See which measurements move together and how groups differ.",
                available=confirmed,
            ),
            dict(
                tool="scenario",
                label="Try a daily what-if",
                description="You choose a change per day and a number of days; we calculate "
                "the exact result. It is an assumption, not a forecast.",
                available=confirmed and bool(options["metrics"]),
            ),
        ],
    )


def quick_start(context: DescriptionContext, options: dict[str, Any]) -> dict[str, Any]:
    if not options["date_columns"]:
        return no_timeline(context, options)
    if options["state"] != "ready":
        return dict(
            kind="needs_review",
            message="This file has dates. Confirm what its columns mean once, "
            "and we will set up the forecast for you.",
        )
    observed = {item["name"]: item for item in context.profile["columns"]}
    dates = [
        name
        for name in options["date_columns"]
        if not observed[name]["missing"]
        and observed[name]["date_min"]
        and observed[name]["date_max"]
    ]
    metrics = sorted(
        (
            item
            for item in options["metrics"]
            if not observed[item["name"]]["missing"]
            and not observed[item["name"]]["type_conflicts"]
        ),
        key=lambda item: exploration_rank(context, item["name"]),
    )
    if not dates or not metrics:
        return dict(
            kind="advanced",
            message="We could not find a complete date column and measure without gaps. "
            "Choose them in Advanced options.",
        )
    time_column, metric = dates[0], metrics[0]
    start = date.fromisoformat(observed[time_column]["date_min"])
    end = date.fromisoformat(observed[time_column]["date_max"])
    if end >= date.today():
        return dict(
            kind="advanced",
            message="The latest dates reach today or later. Choose a finished date range "
            "in Advanced options.",
        )
    days = (end - start).days + 1
    frequency, periods = "daily", days
    if observed[time_column]["distinct_count"] != days or _horizon("daily", days) is None:
        start, end, periods = _months(start, end)
        frequency = "monthly"
    horizon = _horizon(frequency, periods)
    if horizon is None:
        return dict(
            kind="too_short",
            message=f"A forecast needs at least {MIN_HISTORY['daily']} days in a row or "
            f"{MIN_HISTORY['monthly']} whole months of history. This file covers "
            f"{days} days from {observed[time_column]['date_min']} to "
            f"{observed[time_column]['date_max']}.",
        )
    aggregation = (
        metric["aggregations"][0]
        if len(metric["aggregations"]) == 1
        else suggested_aggregation(metric["name"])
    )
    unit = "days" if frequency == "daily" else "months"
    label = "total" if aggregation == "sum" else "average" if aggregation == "avg" else aggregation
    return dict(
        kind="forecast",
        name=f"{metric['name']} forecast"[:100],
        time_column=time_column,
        metric=metric["name"],
        unit=metric["unit"],
        aggregation=aggregation,
        frequency=frequency,
        horizon=horizon,
        coverage_start=start.isoformat(),
        coverage_end=end.isoformat(),
        periods=periods,
        message=(
            f"Forecast the {frequency} {label} of {metric['name']} for the next {horizon} "
            f"{unit}, learning from {periods} {unit} of history ({start.isoformat()} to "
            f"{end.isoformat()}). By starting, you confirm this file holds every "
            f"{'day' if frequency == 'daily' else 'month'} in that range."
        ),
    )
