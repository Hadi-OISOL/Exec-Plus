"""Use case: Lets the Trends analyst describe how a measure moves over calendar periods.

What it does: Picks a date field and a measure, keeps only complete periods from governed
period totals, computes direction, best/worst period and first-to-last growth with exact
Decimal arithmetic, and pairs the headline periods with independent filtered checks.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Any

from execplus.domain.guidance import DescriptionContext
from execplus.domain.insights import (
    Card,
    Check,
    Selection,
    _ask,
    _evidence,
    _readable,
    _unit,
    queryable,
)
from execplus.domain.models import Scalar
from execplus.domain.semantics import FilterOperator, MetricFilter

ANALYST = "trend"
MIN_PERIODS = 3
PERIODS = ("day", "week", "month", "quarter", "year")


@dataclass(frozen=True)
class TrendField:
    measure: str
    aggregation: str
    dated: str
    period: str
    unit: str | None
    first_day: date | None
    last_day: date | None


def grain(first: date | None, last: date | None) -> str:
    if first is None or last is None:
        return "month"
    span = (last - first).days
    if span <= 45:
        return "day"
    if span <= 180:
        return "week"
    if span <= 1100:
        return "month"
    if span <= 3700:
        return "quarter"
    return "year"


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def trend_field(context: DescriptionContext, selection: Selection) -> TrendField | None:
    view = context.view
    dated = next(
        (
            column
            for column in context.profile["columns"]
            if (found := view.column(column["name"])) is not None
            and found.type == "date"
            and column["name"] in view.dimensions
            and queryable(column["name"])
        ),
        None,
    )
    if dated is None:
        return None
    rules: dict[str, str] = {}
    if context.state == "confirmed":
        for rule in (context.definition or {}).get("metrics", []):
            rules.setdefault(rule["column"], rule["aggregation"])
    measure = next(
        (
            name
            for name in selection.measures
            if name in view.metrics and rules.get(name, "sum") in {"sum", "avg"}
        ),
        None,
    )
    if measure is None:
        return None
    first, last = _day(dated.get("date_min")), _day(dated.get("date_max"))
    return TrendField(
        measure,
        rules.get(measure, "sum"),
        dated["name"],
        grain(first, last),
        selection.units.get(measure),
        first,
        last,
    )


def next_start(start: date, period: str) -> date:
    if period == "day":
        return start + timedelta(days=1)
    if period == "week":
        return start + timedelta(days=7)
    months = {"month": 1, "quarter": 3, "year": 12}[period]
    index = start.year * 12 + start.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def complete_periods(
    field: TrendField, rows: tuple[tuple[Scalar, ...], ...]
) -> tuple[list[tuple[date, Decimal]], int]:
    found = sorted(
        (start, Decimal(str(value)))
        for start_value, value in rows
        if (start := _day(start_value)) is not None and value is not None
    )
    partial = 0
    if found and field.first_day and field.first_day > found[0][0]:
        found, partial = found[1:], partial + 1
    if (
        found
        and field.last_day
        and field.last_day < next_start(found[-1][0], field.period) - timedelta(days=1)
    ):
        found, partial = found[:-1], partial + 1
    return found, partial


def _label(start: date, period: str) -> str:
    if period == "month":
        return start.strftime("%Y-%m")
    if period == "quarter":
        return f"{start.year}-Q{(start.month - 1) // 3 + 1}"
    if period == "year":
        return str(start.year)
    if period == "week":
        return f"week of {start.isoformat()}"
    return start.isoformat()


def _check(field: TrendField, label: str, start: date, value: Decimal) -> Check:
    return Check(
        f"{label}: {field.aggregation.upper()} of {field.measure} from {start.isoformat()} "
        f"to before {next_start(start, field.period).isoformat()}",
        format(value, "f"),
        field.aggregation,
        field.measure,
        (
            MetricFilter(field.dated, FilterOperator.GTE, start.isoformat()),
            MetricFilter(
                field.dated, FilterOperator.LT, next_start(start, field.period).isoformat()
            ),
        ),
        method=f"duckdb-filtered-{field.aggregation}",
    )


def trend_card(
    field: TrendField, rows: tuple[tuple[Scalar, ...], ...]
) -> tuple[Card | None, list[str]]:
    periods, partial = complete_periods(field, rows)
    word = "Total" if field.aggregation == "sum" else "Average"
    notes = (
        [f"The first or last {field.period} was left out because it is only partly covered."]
        if partial
        else []
    )
    if len(periods) < MIN_PERIODS:
        return None, [
            f"Trends need at least {MIN_PERIODS} complete {field.period}s of {field.dated}; "
            f"this file has {len(periods)}.",
            *notes,
        ]
    (first_start, first), (last_start, last) = periods[0], periods[-1]
    best = max(periods, key=lambda item: (item[1], -item[0].toordinal()))
    worst = min(periods, key=lambda item: (item[1], item[0].toordinal()))
    direction = "rose" if last > first else "fell" if last < first else "was flat"
    unit = _unit(field.unit)

    def label(start: date) -> str:
        return _label(start, field.period)

    statements = [
        f"{word} {field.measure} {direction} from {_readable(first)}{unit} in "
        f"{label(first_start)} to {_readable(last)}{unit} in {label(last_start)}."
    ]
    growth: Decimal | None = None
    if first:
        with localcontext() as context:
            context.prec = 50
            growth = ((last - first) * 100 / abs(first)).quantize(Decimal("0.01"))
        statements[0] = statements[0][:-1] + f" ({'+' if growth > 0 else ''}{growth}%)."
    statements.append(
        f"Best {field.period}: {label(best[0])} ({_readable(best[1])}{unit}); "
        f"worst: {label(worst[0])} ({_readable(worst[1])}{unit})."
    )
    statements.append(
        f"Based on {len(periods)} complete {field.period}s of {field.dated}. "
        "This describes the past; it does not predict or explain the change."
    )
    checks: list[Check] = []
    for name, (start, value) in (
        ("First", periods[0]),
        ("Last", periods[-1]),
        ("Best", best),
        ("Worst", worst),
    ):
        if all(check.filters[0].value != start.isoformat() for check in checks):
            checks.append(_check(field, name, start, value))
    evidence = (
        _evidence(f"First {field.period} ({label(first_start)})", format(first, "f"), field.unit),
        _evidence(f"Last {field.period} ({label(last_start)})", format(last, "f"), field.unit),
        _evidence("Growth", format(growth, "f"), "%")
        if growth is not None
        else _evidence("Growth", "n/a"),
        _evidence(f"Best {field.period}", label(best[0])),
        _evidence(f"Worst {field.period}", label(worst[0])),
    )
    card = Card(
        f"trend:{field.measure}:{field.dated}:{field.period}",
        ANALYST,
        f"How {field.measure} changes over time",
        tuple(statements),
        evidence,
        dict(
            type="line",
            title=f"{word} {field.measure} per {field.period}",
            x=dict(field="label", label=field.dated, unit=None),
            y=dict(field="value", label=f"{word} {field.measure}", unit=field.unit),
            rows=[dict(label=label(start), value=format(value, "f")) for start, value in periods],
        ),
        tuple(checks),
        (
            _ask(f"Show {word.lower()} {field.measure} per {field.period}"),
            _ask(f"Which {field.period} had the highest {field.measure}?"),
        ),
        0.6,
    )
    return card, notes
