"""Use case: Verifies deterministic weekly product-report definitions.

What it does: Covers UTC/calendar boundaries, mature denominators and missing observations.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.product_usage import UsageFacts, report_start, usage_report


def facts(**overrides):
    values = dict(summary={}, weekly=(), features=(), cohorts=(), retained=(), usage={})
    return UsageFacts(**(values | overrides))


def test_retention_waits_for_the_full_week_and_uses_original_cohort_size():
    now = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
    cohort = date(2026, 9, 21)
    value = usage_report(
        uuid4(),
        now,
        3,
        facts(
            cohorts=((cohort, 3),),
            retained=((cohort, cohort, 3), (cohort, date(2026, 9, 28), 1)),
        ),
    )
    cells = value["cohorts"][0]["cells"]
    assert cells == [
        dict(week_offset=0, eligible=True, retained=3, rate_percent="100.00"),
        dict(week_offset=1, eligible=True, retained=1, rate_percent="33.33"),
        dict(week_offset=2, eligible=False, retained=None, rate_percent=None),
    ]
    assert [row["complete"] for row in value["weekly"]] == [True, True, False]


def test_mature_missing_observation_is_zero_but_future_cells_are_unavailable():
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    cohort = date(2026, 9, 28)
    value = usage_report(uuid4(), now, 4, facts(cohorts=((cohort, 2),)))
    cells = value["cohorts"][0]["cells"]
    assert cells[0]["retained"] == 0
    assert cells[0]["rate_percent"] == "0.00"
    assert all(cell["retained"] is None for cell in cells[1:])


def test_report_window_uses_utc_and_crosses_iso_year_boundary():
    local = datetime(2027, 1, 4, 1, tzinfo=timezone(timedelta(hours=5)))
    assert report_start(local, 2) == datetime(2026, 12, 21, tzinfo=timezone.utc)
    value = usage_report(uuid4(), local, 2, facts())
    assert [row["week_start"] for row in value["weekly"]] == ["2026-12-21", "2026-12-28"]
    assert value["period"]["timezone"] == "UTC"


@pytest.mark.parametrize("weeks", [0, 13, True, 1.5, "4"])
def test_invalid_window_is_rejected(weeks):
    with pytest.raises(IngestionError):
        report_start(datetime.now(timezone.utc), weeks)


def test_naive_clock_is_rejected():
    with pytest.raises(ValueError):
        usage_report(uuid4(), datetime(2026, 10, 6), 8, facts())


def test_empty_report_has_complete_zero_weeks_and_no_invented_cohorts():
    value = usage_report(uuid4(), datetime(2026, 10, 6, tzinfo=timezone.utc), 8, facts())
    assert len(value["weekly"]) == 8
    assert value["cohorts"] == []
    assert all(row["active_users"] == row["actions"] == 0 for row in value["weekly"])
    assert "not predicted churn" in value["definitions"]["inactivity"]
