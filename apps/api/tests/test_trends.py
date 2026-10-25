"""Use case: Verifies the Trends analyst's period arithmetic and cross-check plan.

What it does: Checks complete-period selection, direction, growth, best/worst periods, exact
evidence strings and the independent filtered checks against hand-computed values.
"""

from datetime import date
from decimal import Decimal

from execplus.domain.semantics import FilterOperator
from execplus.domain.trends import (
    TrendField,
    complete_periods,
    grain,
    next_start,
    trend_card,
)

MONTHS = (
    (date(2024, 1, 1), Decimal("30.5")),
    (date(2024, 2, 1), Decimal("60")),
    (date(2024, 3, 1), Decimal("15")),
    (date(2024, 4, 1), Decimal("90")),
    (date(2024, 5, 1), Decimal("120")),
    (date(2024, 6, 1), Decimal("75")),
    (date(2024, 7, 1), Decimal("45.75")),
    (date(2024, 8, 1), Decimal("999")),
)


def field(first=date(2024, 1, 1), last=date(2024, 8, 10), period="month") -> TrendField:
    return TrendField("amount", "sum", "day", period, "PKR", first, last)


def test_grain_follows_the_date_span():
    assert grain(date(2024, 1, 1), date(2024, 1, 31)) == "day"
    assert grain(date(2024, 1, 1), date(2024, 5, 1)) == "week"
    assert grain(date(2024, 1, 1), date(2024, 12, 31)) == "month"
    assert grain(date(2020, 1, 1), date(2024, 12, 31)) == "quarter"
    assert grain(None, None) == "month"
    assert next_start(date(2024, 12, 1), "month") == date(2025, 1, 1)
    assert next_start(date(2024, 10, 1), "quarter") == date(2025, 1, 1)
    assert next_start(date(2024, 2, 26), "week") == date(2024, 3, 4)


def test_partial_first_and_last_periods_are_left_out():
    rows = tuple((start.isoformat(), value) for start, value in MONTHS)
    periods, partial = complete_periods(field(), (*rows, (None, Decimal(5))))
    assert [start for start, _ in periods] == [start for start, _ in MONTHS[:-1]]
    assert partial == 1
    periods, partial = complete_periods(field(first=date(2024, 1, 2)), rows)
    assert periods[0][0] == date(2024, 2, 1) and partial == 2


def test_trend_card_reports_direction_growth_and_extremes_exactly():
    card, notes = trend_card(field(), tuple((start, value) for start, value in MONTHS))
    assert card is not None
    assert card.analyst == "trend"
    first, last = Decimal("30.5"), Decimal("45.75")
    growth = ((last - first) * 100 / first).quantize(Decimal("0.01"))
    assert str(growth) == "50.00"
    assert card.statements[0] == (
        "Total amount rose from 30.5 PKR in 2024-01 to 45.75 PKR in 2024-07 (+50.00%)."
    )
    assert card.statements[1] == "Best month: 2024-05 (120 PKR); worst: 2024-03 (15 PKR)."
    evidence = {item["label"]: item["value"] for item in card.evidence}
    assert evidence["First month (2024-01)"] == "30.5"
    assert evidence["Last month (2024-07)"] == "45.75"
    assert evidence["Growth"] == "50.00"
    assert evidence["Best month"] == "2024-05" and evidence["Worst month"] == "2024-03"
    assert [row["value"] for row in card.chart["rows"]] == [
        "30.5",
        "60",
        "15",
        "90",
        "120",
        "75",
        "45.75",
    ]
    assert "999" not in str(card.chart)
    assert notes and "partly covered" in notes[0]
    assert [check.primary for check in card.checks] == ["30.5", "45.75", "120", "15"]
    best = card.checks[2]
    assert best.aggregation == "sum" and best.secondary is None
    assert [(item.operator, item.value) for item in best.filters] == [
        (FilterOperator.GTE, "2024-05-01"),
        (FilterOperator.LT, "2024-06-01"),
    ]


def test_falling_series_and_zero_start_avoid_invented_growth():
    rows = (
        (date(2024, 1, 1), Decimal(0)),
        (date(2024, 2, 1), Decimal(5)),
        (date(2024, 3, 1), Decimal(2)),
    )
    card, _ = trend_card(field(last=date(2024, 3, 31)), rows)
    assert card is not None
    assert "(+" not in card.statements[0] and "rose from 0 PKR" in card.statements[0]
    assert {item["label"]: item["value"] for item in card.evidence}["Growth"] == "n/a"
    falling = (
        (date(2024, 1, 1), Decimal(9)),
        (date(2024, 2, 1), Decimal(6)),
        (date(2024, 3, 1), Decimal(3)),
    )
    card, _ = trend_card(field(last=date(2024, 3, 31)), falling)
    assert "fell from 9 PKR" in card.statements[0] and "(-66.67%)" in card.statements[0]


def test_too_few_complete_periods_returns_a_limitation_not_a_card():
    rows = ((date(2024, 1, 1), Decimal(1)), (date(2024, 2, 1), Decimal(2)))
    card, notes = trend_card(field(last=date(2024, 2, 29)), rows)
    assert card is None
    assert "at least 3 complete months" in notes[0] and "has 2" in notes[0]
