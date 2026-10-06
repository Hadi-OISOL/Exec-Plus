"""Use case: Verifies honest bounded forecasts and observed actual comparisons.

What it does: Tests chronological separation, exact actuals and missing-data guards.
"""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal, localcontext

import pytest

from execplus.domain.forecasting import (
    ForecastPoint,
    ForecastRequest,
    compare_forecast,
    error_metrics,
    forecast,
    next_period,
)
from execplus.domain.ingestion import IngestionError


def series(values, frequency="daily", start=date(2025, 1, 1)):
    points = []
    for value in values:
        points.append(ForecastPoint(start, Decimal(str(value))))
        start = next_period(start, frequency)
    return tuple(points)


def test_constant_monthly_baseline_has_deterministic_splits_and_exact_actuals():
    points = series(["0.10000000000000000000000000000000000001"] * 12, "monthly")
    result = forecast(points, ForecastRequest("monthly", 3))
    record = result.to_record()
    assert record["method"]["id"] == "last_value"
    assert record["windows"] == {
        "training": {"start": "2025-01-01", "end": "2025-06-01", "count": 6},
        "validation": {"start": "2025-07-01", "end": "2025-09-01", "count": 3},
        "test": {"start": "2025-10-01", "end": "2025-12-01", "count": 3},
        "test_training": {"start": "2025-01-01", "end": "2025-09-01", "count": 9},
        "forecast_training": {"start": "2025-01-01", "end": "2025-12-01", "count": 12},
    }
    assert record["history"][0]["actual"] == str(points[0].actual)
    assert [row["period"] for row in record["predictions"]] == [
        "2026-01-01",
        "2026-02-01",
        "2026-03-01",
    ]
    assert all(isinstance(row["estimate"], str) for row in record["predictions"])
    assert result.serialized == forecast(points, ForecastRequest("monthly", 3)).serialized
    assert json.loads(json.dumps(record, allow_nan=False)) == record
    record["history"][0]["actual"] = "tampered"
    assert result.to_record()["history"][0]["actual"] == str(points[0].actual)
    with pytest.raises(FrozenInstanceError):
        result.serialized = "changed"


def test_linear_trend_wins_validation_and_reports_independent_test_and_baseline():
    record = forecast(series(range(1, 41)), ForecastRequest("daily", 5)).to_record()
    assert record["method"]["id"] == "linear_trend"
    assert [Decimal(row["estimate"]) for row in record["predictions"]] == list(
        map(Decimal, range(41, 46))
    )
    assert Decimal(record["accuracy"]["mae"]) == 0
    assert record["benchmark"]["beats_baseline_mae"] is True
    assert Decimal(record["benchmark"]["accuracy"]["mae"]) == 3
    assert record["uncertainty"]["backtest_coverage"]["inside"] == 5
    assert record["uncertainty"]["coverage_guaranteed"] is False
    assert any("ranges collapse" in item for item in record["limitations"])


def test_test_actuals_never_change_selection_or_holdout_predictions_or_ranges():
    points = series(range(1, 41))
    altered = points[:-5] + tuple(replace(point, actual=Decimal(5)) for point in points[-5:])
    before = forecast(points, ForecastRequest("daily", 5)).to_record()
    after = forecast(altered, ForecastRequest("daily", 5)).to_record()
    assert before["selection"] == after["selection"]
    assert before["method"] == after["method"]
    for first, second in zip(before["backtest"], after["backtest"], strict=True):
        assert {key: first[key] for key in ("estimate", "lower", "upper")} == {
            key: second[key] for key in ("estimate", "lower", "upper")
        }
    assert before["accuracy"] != after["accuracy"]
    assert after["uncertainty"]["backtest_coverage"]["inside"] == 0
    assert Decimal(after["accuracy"]["mae"]) == 33
    assert after["benchmark"]["beats_baseline_mae"] is False
    assert Decimal(after["benchmark"]["mae_difference"]) == -3


def test_monthly_seasonal_naive_requires_training_cycles_and_can_win():
    points = series([10, 40, 20, 70, 35, 95, 40, 30, 75, 20, 50, 5] * 4, "monthly")
    record = forecast(points, ForecastRequest("monthly", 6, 12)).to_record()
    assert record["method"] == {"id": "seasonal_naive", "version": 1, "parameters": {"window": 12}}
    assert Decimal(record["accuracy"]["mae"]) == 0
    assert [Decimal(row["estimate"]) for row in record["predictions"]] == list(
        map(Decimal, [10, 40, 20, 70, 35, 95])
    )
    short = forecast(points[:12], ForecastRequest("monthly", 3, 12)).to_record()
    assert len(short["selection"]["candidates"]) == 3
    assert any("two full declared cycles" in item for item in short["limitations"])


def test_daily_seasonality_repeats_only_declared_cycle_without_peeking():
    points = series([1, 3, 5, 2, 8, 7, 4] * 8)
    record = forecast(points, ForecastRequest("daily", 10, 7)).to_record()
    assert record["method"]["id"] == "seasonal_naive"
    assert [Decimal(row["estimate"]) for row in record["predictions"]] == list(
        map(Decimal, [1, 3, 5, 2, 8, 7, 4, 1, 3, 5])
    )


def test_zero_actual_metrics_are_defined_without_fake_percentage_accuracy():
    metrics = error_metrics((Decimal(0), Decimal(10)), (Decimal(2), Decimal(8)))
    assert metrics == {
        "count": 2,
        "mae": "2",
        "rmse": "2",
        "wape_percent": "40.0",
        "mape_percent": None,
        "mape_count": 1,
        "zero_actual_count": 1,
    }
    zeros = error_metrics((Decimal(0), Decimal(0)), (Decimal(0), Decimal(1)))
    assert zeros["wape_percent"] is None
    assert zeros["mape_percent"] is None
    assert Decimal(zeros["mae"]) == Decimal("0.5")
    empty = error_metrics((), ())
    assert empty["count"] == 0 and empty["rmse"] is None


def test_negative_actuals_and_predictions_are_not_clipped_or_wrongly_signed():
    metrics = error_metrics((Decimal(-10), Decimal(-20)), (Decimal(-8), Decimal(-25)))
    assert Decimal(metrics["mae"]) == Decimal("3.5")
    assert Decimal(metrics["mape_percent"]) == Decimal("22.5")
    record = forecast(series(range(20, -20, -1)), ForecastRequest("daily", 4)).to_record()
    assert Decimal(record["predictions"][0]["estimate"]) == -20
    assert any("not silently clipped" in item for item in record["limitations"])


def test_decimal_context_does_not_round_actuals_or_change_estimates():
    points = series(["12345678901234567890123456789012345678"] * 28)
    ordinary = forecast(points, ForecastRequest("daily", 4)).to_record()
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        low_precision = forecast(points, ForecastRequest("daily", 4)).to_record()
    assert ordinary == low_precision
    assert ordinary["history"][0]["actual"] == "12345678901234567890123456789012345678"
    assert ordinary["backtest"][0]["error"] == "-9876543210987654322"


@pytest.mark.parametrize(
    ("forecast_request", "code"),
    [
        (ForecastRequest("weekly", 3), "forecast_frequency"),
        (ForecastRequest("daily", 31), "forecast_horizon"),
        (ForecastRequest("monthly", 13), "forecast_horizon"),
        (ForecastRequest("daily", 0), "forecast_horizon"),
        (ForecastRequest("daily", True), "forecast_horizon"),
        (ForecastRequest("daily", 2, 12), "forecast_season"),
        (ForecastRequest("monthly", 2, True), "forecast_season"),
    ],
)
def test_invalid_frequency_horizon_and_season_are_rejected(forecast_request, code):
    with pytest.raises(IngestionError) as caught:
        forecast(series([10] * 100), forecast_request)
    assert caught.value.code == code


@pytest.mark.parametrize("count,horizon,minimum", [(27, 1, 28), (28, 30, 74), (73, 30, 74)])
def test_horizon_needs_two_separate_holdouts_and_sufficient_training(count, horizon, minimum):
    with pytest.raises(IngestionError) as caught:
        forecast(series([10] * count), ForecastRequest("daily", horizon))
    assert caught.value.code == "forecast_insufficient_history"
    assert str(minimum) in str(caught.value)


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda rows: rows[:10] + rows[11:], "forecast_missing_period"),
        (lambda rows: (*rows[:10], rows[9], *rows[10:]), "forecast_order"),
        (lambda rows: tuple(reversed(rows)), "forecast_order"),
        (
            lambda rows: (*rows[:-1], replace(rows[-1], complete=False)),
            "forecast_incomplete_period",
        ),
        (lambda rows: (*rows[:-1], replace(rows[-1], actual=Decimal("NaN"))), "forecast_value"),
        (
            lambda rows: (*rows[:-1], replace(rows[-1], actual=Decimal("Infinity"))),
            "forecast_value",
        ),
        (lambda rows: (*rows[:-1], replace(rows[-1], actual=Decimal("1e100"))), "forecast_value"),
        (lambda rows: (*rows[:-1], replace(rows[-1], actual=Decimal("1e-100"))), "forecast_value"),
        (
            lambda rows: (*rows[:-1], replace(rows[-1], period=datetime(2025, 2, 1))),
            "forecast_period",
        ),
    ],
)
def test_invalid_history_fails_without_imputation(mutate, code):
    with pytest.raises(IngestionError) as caught:
        forecast(mutate(series([10] * 40)), ForecastRequest("daily", 3))
    assert caught.value.code == code


def test_history_is_bounded_and_calendar_overflow_is_actionable():
    with pytest.raises(IngestionError, match="1200"):
        forecast(series([10] * 1201), ForecastRequest("daily", 3))
    with pytest.raises(IngestionError) as caught:
        forecast(series([10] * 28, start=date(9999, 12, 3)), ForecastRequest("daily", 3))
    assert caught.value.code == "forecast_date_range"


def test_monthly_dates_must_be_period_starts_and_daily_leap_days_are_real():
    with pytest.raises(IngestionError) as caught:
        forecast(series([10] * 12, "monthly", date(2025, 1, 2)), ForecastRequest("monthly", 3))
    assert caught.value.code == "forecast_period"
    leap = forecast(
        series([10] * 28, start=date(2024, 2, 1)), ForecastRequest("daily", 2)
    ).to_record()
    assert [row["period"] for row in leap["predictions"]] == ["2024-02-29", "2024-03-01"]


def test_comparison_uses_only_observed_complete_future_periods_and_exact_actuals():
    record = forecast(series([10] * 28), ForecastRequest("daily", 4)).to_record()
    prediction_dates = [date.fromisoformat(item["period"]) for item in record["predictions"]]
    actuals = (
        ForecastPoint(date(2025, 1, 1), Decimal(9999)),
        ForecastPoint(prediction_dates[0], Decimal("10.000000000000000001")),
        ForecastPoint(prediction_dates[1], Decimal(0)),
        ForecastPoint(prediction_dates[2], Decimal(1000), complete=False),
    )
    compared = compare_forecast(record, actuals)
    assert compared["observed_count"] == 2
    assert compared["pending_count"] == 2
    assert compared["rows"][0]["actual"] == "10.000000000000000001"
    assert compared["rows"][0]["error"] == "0.000000000000000001"
    assert compared["rows"][2]["actual"] is None
    assert compared["rows"][2]["pending_reason"] == "incomplete_period"
    assert compared["rows"][3]["pending_reason"] == "not_observed"
    assert compared["metrics"]["mape_percent"] is None
    assert compared["metrics"]["count"] == 2
    empty = compare_forecast(record, ())
    assert empty["observed_count"] == 0 and empty["pending_count"] == 4
    assert empty["metrics"]["mae"] is None


@pytest.mark.parametrize(
    "field,value", [("estimate", "NaN"), ("estimate", 5), ("lower", "Infinity"), ("lower", "100")]
)
def test_comparison_rejects_corrupt_persisted_predictions(field, value):
    record = forecast(series([10] * 28), ForecastRequest("daily", 2)).to_record()
    record["predictions"][0][field] = value
    with pytest.raises(IngestionError):
        compare_forecast(record, ())


def test_comparison_rejects_duplicate_actual_periods_and_unknown_versions():
    record = forecast(series([10] * 28), ForecastRequest("daily", 2)).to_record()
    point = ForecastPoint(date(2025, 1, 29), Decimal(10))
    with pytest.raises(IngestionError) as caught:
        compare_forecast(record, (point, point))
    assert caught.value.code == "forecast_order"
    record["version"] = "future-version"
    with pytest.raises(IngestionError) as caught:
        compare_forecast(record, ())
    assert caught.value.code == "forecast_record"


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("1e1000")])
def test_public_error_metric_helper_rejects_invalid_values(value):
    with pytest.raises(IngestionError):
        error_metrics((value,), (Decimal(1),))
    with pytest.raises(IngestionError):
        error_metrics((Decimal(1),), (value,))


def test_error_metrics_reject_length_mismatch():
    with pytest.raises(IngestionError, match="lengths"):
        error_metrics((Decimal(1),), ())
