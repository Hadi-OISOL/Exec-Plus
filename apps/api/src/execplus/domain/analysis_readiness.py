"""Use case: Gives chat and forecasting the same source-bound eligibility facts.

What it does: Identifies saved meaning, valid columns and remaining declarations without guessing.
"""

from typing import Any

from execplus.domain.guidance import DescriptionContext


def forecast_options(context: DescriptionContext) -> dict[str, Any]:
    view = context.view
    definitions = (view.definition or {}).get("columns", [])
    dates = [c.name for c in view.columns if c.type == "date" and c.name in view.dimensions]
    metrics = []
    for column in definitions:
        if column["name"] not in view.metrics:
            continue
        unit = column["currency"] or column["unit"]
        if not unit:
            continue
        governed = next(
            (
                m
                for m in (view.definition or {}).get("metrics", [])
                if m["column"] == column["name"]
            ),
            None,
        )
        metrics.append(
            dict(
                name=column["name"],
                unit=unit,
                aggregations=[governed["aggregation"]]
                if governed
                else ["sum", "avg", "min", "max", "count"],
            )
        )
    source = view.sources[0]
    limitations = [
        "Basic daily/monthly statistical forecasts; no prescriptive recommendations.",
        "Confirm units and complete period coverage. Missing periods are never filled with zero.",
        "At least 28 daily or 12 monthly periods are needed; longer horizons need more history.",
    ]
    ready = context.state == "confirmed" and bool(source.get("understanding_id"))
    if not ready:
        limitations.insert(0, "Review and confirm Data understanding and measure units first.")
    if not dates:
        limitations.append(
            "A complete date column is required; year/month components alone are insufficient."
        )
    if not metrics:
        limitations.append("A confirmed numeric measure with an explicit unit is required.")
    date_profile: dict[str, Any] = next(
        (c for c in context.profile["columns"] if c["name"] in dates), {}
    )
    blockers = []
    if not ready:
        blockers.append(
            dict(code="meaning", message="Confirm the current data meanings before forecasting.")
        )
    if not dates:
        blockers.append(
            dict(
                code="date",
                message=(
                    "This file has no usable date column. A season or row ID does not place "
                    "measurements on a timeline. Add actual observation dates to forecast "
                    "changes over time."
                ),
            )
        )
    if not metrics:
        blockers.append(
            dict(
                code="metric",
                message="Choose a numeric measure and confirm its fixed unit before forecasting.",
            )
        )
    return dict(
        blockers=blockers,
        meaning_state=context.state,
        state="needs_review" if not ready else "ready" if dates and metrics else "unsupported",
        revision_id=source["revision_id"],
        understanding_id=source.get("understanding_id"),
        date_columns=dates,
        metrics=metrics,
        limitations=limitations,
        defaults=dict(
            coverage_start=date_profile.get("date_min"),
            coverage_end=date_profile.get("date_max"),
        ),
    )
