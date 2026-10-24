"""Use case: Independently checks calendar-regressor advanced forecasts (advanced-v4).

What it does: Pins byte-identical v2/v3 records, recomputes least-squares effects with
NumPy, verifies validation-only selection, reports the seeded synthetic measurement
and replays event-column forecasts through the governed API.
"""

import hashlib
import json
import random
from datetime import date, timedelta
from decimal import Decimal

import numpy
import pytest

from execplus.domain.advanced_forecasting import advanced_forecast, compare_advanced_forecast
from execplus.domain.calendar_regression import CalendarInputs
from execplus.domain.forecasting import ForecastPoint, ForecastRequest, next_period
from execplus.domain.regressor_evaluation import evaluation_report
from test_forecast_integration import create
from test_studies import prepare


def series(values, frequency="daily", start=date(2020, 1, 1)):
    period, points = start, []
    for value in values:
        points.append(ForecastPoint(period, Decimal(str(value))))
        period = next_period(period, frequency)
    return tuple(points)


def calendar_for(points, request, events=None):
    periods, period = [p.period for p in points], points[-1].period
    for _ in range(request.horizon):
        period = next_period(period, request.frequency)
        periods.append(period)
    return CalendarInputs(tuple(periods), events)


def digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def test_v2_and_v3_records_stay_byte_identical():
    rng = random.Random(7)
    daily = series([100 + 2 * i + (i % 7 - 3) + rng.randint(-5, 5) for i in range(90)])
    monthly = series([50 + (i % 12) * 3 + rng.randint(-9, 9) for i in range(60)], "monthly")
    expected = [
        (daily, ForecastRequest("daily", 4, 7), False, "3a0bca6fa7193c38"),
        (daily, ForecastRequest("daily", 4, 7), True, "006b2e990417ebe2"),
        (monthly, ForecastRequest("monthly", 3, 12), False, "68f4dd7b9faf2bce"),
        (monthly, ForecastRequest("monthly", 3, 12), True, "65d97e85ca6e68e6"),
    ]
    for points, request, calibrated, prefix in expected:
        record = advanced_forecast(points, request, "auto", calibrated).to_record()
        assert digest(record).startswith(prefix)
        assert "regressors" not in record


def weekly_points(seed=3, length=84, events=None):
    rng = random.Random(seed)
    effect = (0, 4, 8, 6, 2, 20, 25)
    values = []
    for index in range(length):
        day = date(2024, 1, 1) + timedelta(days=index)
        bump = 30 * events[index] if events else 0
        values.append(round(50 + 0.1 * index + effect[day.weekday()] + bump + rng.gauss(0, 1), 2))
    return series(values, start=date(2024, 1, 1))


def test_effects_match_an_independent_numpy_least_squares_fit():
    points = weekly_points()
    request = ForecastRequest("daily", 7, None)
    record = advanced_forecast(points, request, calendar=calendar_for(points, request)).to_record()
    regressors = record["regressors"]
    assert record["version"] == "forecast-v4"
    assert regressors["selected"] == "calendar_regression"
    assert record["method"]["id"] == "calendar_regression"
    rows = [
        [1, index, *(int(p.period.weekday() == day) for day in range(1, 7))]
        for index, p in enumerate(points)
    ]
    coefficients, *_ = numpy.linalg.lstsq(
        numpy.array(rows, dtype=float), numpy.array([float(p.actual) for p in points]), rcond=None
    )
    names = ("Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    for name, value in zip(names, coefficients[2:], strict=True):
        assert abs(float(regressors["effects"][name]) - value) < 1e-9
    assert abs(float(regressors["effects"]["Sunday"]) - 25) < 1.5


def test_regression_is_selected_only_when_validation_error_is_strictly_lower():
    rng = random.Random(9)
    level, values = 100.0, []
    for _ in range(84):
        level += rng.gauss(0, 2)
        values.append(round(level, 2))
    points = series(values)
    request = ForecastRequest("daily", 7, None)
    plain = advanced_forecast(points, request).to_record()
    extended = advanced_forecast(points, request, calendar=calendar_for(points, request))
    record = extended.to_record()
    comparison = record["regressors"]
    without, with_calendar = (
        comparison["best_without_regressors"],
        comparison["best_with_regressors"],
    )
    assert Decimal(with_calendar["validation_mae"]) >= Decimal(without["validation_mae"])
    assert comparison["selected"] == "smoothing"
    assert record["method"] == plain["method"]
    assert record["predictions"] == plain["predictions"]
    assert without["test_mae"] == plain["accuracy"]["mae"]
    assert record["accuracy"] == plain["accuracy"]


def test_declared_future_events_raise_event_day_estimates():
    rng = random.Random(5)
    events = tuple(int(rng.random() < 0.15) for _ in range(91))
    points = weekly_points(seed=5, events=events)
    request = ForecastRequest("daily", 7, 7)
    future = (0, 0, 1, 0, 0, 0, 0)
    calendar = calendar_for(points, request, (*events[:84], *future))
    record = advanced_forecast(points, request, calendar=calendar).to_record()
    assert record["regressors"]["selected"] == "calendar_regression"
    assert record["regressors"]["event_declared"] is True
    assert abs(float(record["regressors"]["effects"]["event"]) - 30) < 2
    flagged = record["predictions"][2]
    week_earlier = advanced_forecast(
        points, request, calendar=calendar_for(points, request, (*events[:84], *(0,) * 7))
    ).to_record()["predictions"][2]
    difference = Decimal(flagged["estimate"]) - Decimal(week_earlier["estimate"])
    assert abs(difference - Decimal(record["regressors"]["effects"]["event"])) < Decimal("1e-9")
    assert record["regressors"]["future_event_periods"] == [flagged["period"]]
    comparison = compare_advanced_forecast(record, ())
    assert comparison["pending_count"] == 7


def test_short_monthly_history_excludes_regression_with_a_reason():
    points = series([10 + i % 12 for i in range(30)], "monthly")
    request = ForecastRequest("monthly", 3, None)
    record = advanced_forecast(points, request, calendar=calendar_for(points, request)).to_record()
    assert record["regressors"]["best_with_regressors"] is None
    assert any(item["method"] == "calendar regression" for item in record["selection"]["excluded"])


@pytest.fixture(scope="module")
def measured():
    return evaluation_report()


def test_seeded_synthetic_measurement_is_reported_honestly(measured):
    scenarios = measured["scenarios"]
    for name in ("weekly_undeclared", "yearly_undeclared", "weekly_with_events"):
        row = scenarios[name]
        assert Decimal(row["mean_v4_test_mae"]) < Decimal(row["mean_v2_test_mae"])
    flat = scenarios["no_seasonality"]
    assert flat["calendar_selected"] == 0
    assert flat["mean_v4_test_mae"] == flat["mean_v2_test_mae"]
    assert scenarios["weekly_declared"]["v4_worse"] > 0
    assert (
        evaluation_report(("weekly_declared",), 2)["scenarios"]["weekly_declared"]["runs"]
        == (scenarios["weekly_declared"]["runs"][:2])
    )


def event_csv(count=70):
    rows = ["day,amount,promo,city"]
    rng = random.Random(4)
    for index in range(count):
        day = date(2024, 1, 1) + timedelta(days=index)
        promo = int(index % 9 == 4)
        amount = 50 + (20 if day.weekday() >= 5 else 0) + 30 * promo + rng.randint(-2, 2)
        rows.append(f"{day},{amount},{promo},Karachi")
    return ("\n".join(rows) + "\n").encode()


def test_event_column_forecast_replays_and_old_requests_keep_their_shape(integration):
    env = integration
    owner, _, wid, did, _, root = prepare(env, event_csv())
    common = dict(coverage_end="2024-03-10", horizon=7, engine="advanced-v4")
    response = create(
        env,
        owner,
        root,
        **common,
        event_column="promo",
        future_event_periods=["2024-03-13"],
    )
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["method_version"] == "forecast-v4"
    assert len(value["evidence"]["query_ids"]) == 4
    regressors = value["result"]["regressors"]
    assert regressors["event_declared"] and regressors["future_event_periods"] == ["2024-03-13"]
    reopened = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/forecasts/{value['id']}", headers=owner
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json() == value
    plain = create(env, owner, root, coverage_end="2024-03-10", engine="advanced-v2")
    assert plain.status_code == 201, plain.text
    assert "event_column" not in plain.json()["request"]
    assert "regressors" not in plain.json()["result"]
    without_events = create(env, owner, root, **common)
    assert without_events.status_code == 201, without_events.text
    assert "event_column" not in without_events.json()["request"]
    for changes in (
        dict(common, event_column="promo", future_event_periods=["2024-04-30"]),
        dict(common, event_column="city"),
        dict(coverage_end="2024-03-10", engine="advanced-v2", event_column="promo"),
        dict(common, future_event_periods=["2024-03-13"]),
    ):
        refused = create(env, owner, root, **changes)
        assert refused.status_code == 422, (changes, refused.text)
