"""Use case: Independently checks bounded rolling-origin smoothing forecasts.

What it does: Verifies component-equation examples, time separation, exact actuals,
method eligibility, missingness, negative predictions and stable replay.
"""

from dataclasses import replace
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal, localcontext

import pytest

from execplus.domain.advanced_forecasting import (
    MAX_CANDIDATES,
    MAX_STATE_UPDATES,
    Candidate,
    advanced_forecast,
    compare_advanced_forecast,
    minimum_history,
    predict,
    registered_candidates,
)
from execplus.domain.forecasting import ForecastPoint, ForecastRequest, forecast, next_period
from execplus.domain.ingestion import IngestionError


def series(values, frequency="daily"):
    period = date(2020, 1, 1)
    points = []
    for value in values:
        points.append(ForecastPoint(period, Decimal(str(value))))
        period = next_period(period, frequency)
    return tuple(points)


@pytest.mark.parametrize(
    "candidate,values,expected",
    [
        (Candidate("simple_exponential", "0.5"), (10, 20, 10), ("12.5", "12.5")),
        (Candidate("holt", "0.5", "0.5"), (10, 12, 15), ("16.75", "19.00")),
        (Candidate("damped_holt", "0.5", "0.5", "0.8"), (10, 12, 15), ("15.536", "16.7008")),
    ],
)
def test_independent_hand_calculated_component_examples(candidate, values, expected):
    assert predict(candidate, tuple(map(Decimal, values)), 2) == tuple(map(Decimal, expected))


def test_additive_seasonal_initialization_and_phase_match_exact_linear_plus_cycle():
    values = tuple(Decimal(100 + 2 * index + (index % 7 - 3)) for index in range(35))
    estimates = predict(Candidate("holt_winters_additive", "0.5", "0.1", "1", "0.1", 7), values, 10)
    assert estimates == tuple(Decimal(100 + 2 * index + (index % 7 - 3)) for index in range(35, 45))


def test_registry_is_fixed_small_and_seasonal_parameters_obey_gamma_bound():
    candidates = registered_candidates(ForecastRequest("daily", 4, 7), "auto", 30)
    assert len(candidates) == MAX_CANDIDATES == 43
    assert candidates[0].method == "last_value"
    assert candidates[1].method == "seasonal_naive"
    assert all(
        Decimal(item.gamma) <= 1 - Decimal(item.alpha)
        for item in candidates
        if item.method == "holt_winters_additive"
    )
    assert candidates == registered_candidates(ForecastRequest("daily", 4, 7), "auto", 30)


@pytest.mark.parametrize("value", ["0", "-4.25", "7.00000000000000000000000000000000000001"])
def test_constant_tie_prefers_baseline_and_preserves_exact_actuals(value):
    points = series([value] * 50)
    result = advanced_forecast(points, ForecastRequest("daily", 4, 7)).to_record()
    assert result["method"]["id"] == "last_value"
    assert result["selection"]["tie_break"] == "registered_candidate_order"
    assert result["history"][0]["actual"] == value
    assert result["uncertainty"]["coverage_guaranteed"] is False
    assert result["uncertainty"]["calibration_independent"] is False
    if len(Decimal(value).as_tuple().digits) <= 18:
        assert Decimal(result["uncertainty"]["width"]) == 0
        assert "ranges collapse" in " ".join(result["limitations"])
    else:
        assert Decimal(result["uncertainty"]["width"]) == Decimal("1e-38")
    if value == "0":
        assert result["accuracy"]["wape_percent"] is None
        assert result["accuracy"]["mape_percent"] is None


def test_trend_candidate_beats_naive_on_independent_linear_fixture():
    result = advanced_forecast(series(range(50)), ForecastRequest("daily", 4)).to_record()
    assert result["method"]["id"] == "holt"
    assert tuple(Decimal(row["estimate"]) for row in result["predictions"]) == tuple(
        map(Decimal, (50, 51, 52, 53))
    )
    assert Decimal(result["accuracy"]["mae"]) == 0
    assert Decimal(result["benchmark"]["accuracy"]["mae"]) == Decimal("2.5")
    assert result["benchmark"]["beats_baseline_mae"] is True


def test_declared_seasonality_repeats_actual_cycle_and_exposes_baseline():
    cycle = (10, 20, 5, 30, 12, 40, 7)
    result = advanced_forecast(series(cycle * 12), ForecastRequest("daily", 7, 7)).to_record()
    assert result["method"]["id"] == "seasonal_naive"
    assert tuple(Decimal(row["estimate"]) for row in result["predictions"]) == tuple(
        map(Decimal, cycle)
    )
    assert Decimal(result["accuracy"]["mae"]) == 0
    assert result["benchmark"]["beats_baseline_mae"] is True


def test_additive_seasonal_trend_wins_on_distinct_trend_plus_cycle_fixture():
    cycle = (-12, 4, 8, -3, 15, -9, -3)
    values = [100 + 2 * index + cycle[index % 7] for index in range(84)]
    result = advanced_forecast(series(values), ForecastRequest("daily", 7, 7)).to_record()
    assert result["method"]["id"] == "holt_winters_additive"
    assert tuple(Decimal(row["estimate"]) for row in result["predictions"]) == tuple(
        Decimal(100 + 2 * index + cycle[index % 7]) for index in range(84, 91)
    )
    assert Decimal(result["accuracy"]["mae"]) == 0
    assert result["benchmark"]["beats_baseline_mae"] is True


def test_untouched_future_perturbation_cannot_change_selection_ranges_or_test_predictions():
    points = series([20 + index + (index % 3) for index in range(64)])
    changed = points[:-4] + tuple(
        replace(point, actual=point.actual + 1000) for point in points[-4:]
    )
    before = advanced_forecast(points, ForecastRequest("daily", 4, 7)).to_record()
    after = advanced_forecast(changed, ForecastRequest("daily", 4, 7)).to_record()
    assert before["selection"] == after["selection"]
    assert before["method"] == after["method"]
    assert before["uncertainty"]["width"] == after["uncertainty"]["width"]
    for left, right in zip(before["backtest"], after["backtest"], strict=True):
        assert {key: left[key] for key in ("period", "estimate", "lower", "upper")} == {
            key: right[key] for key in ("period", "estimate", "lower", "upper")
        }
    assert before["accuracy"] != after["accuracy"]
    assert before["predictions"] != after["predictions"]


def test_expanding_folds_never_include_own_future_and_finish_before_test():
    result = advanced_forecast(series(range(50)), ForecastRequest("daily", 4)).to_record()
    folds = result["selection"]["folds"]
    assert [fold["training"]["count"] for fold in folds] == [34, 38, 42]
    assert [fold["validation"]["count"] for fold in folds] == [4, 4, 4]
    for fold in folds:
        assert date.fromisoformat(fold["training"]["end"]) + timedelta(
            days=1
        ) == date.fromisoformat(fold["validation"]["start"])
        assert fold["validation"]["end"] < result["windows"]["test"]["start"]
    assert result["uncertainty"]["error_count"] == 12


@pytest.mark.parametrize("frequency,season,horizon", [("daily", 7, 30), ("monthly", 12, 12)])
def test_long_horizon_minimum_history_and_eligible_methods(frequency, season, horizon):
    request = ForecastRequest(frequency, horizon, season)
    required = minimum_history(request, "holt_winters_additive")
    assert required == 2 * season + 4 * horizon
    with pytest.raises(IngestionError) as error:
        advanced_forecast(series(range(required - 1), frequency), request, "holt_winters_additive")
    assert error.value.code == "forecast_insufficient_history"
    result = advanced_forecast(
        series(range(required), frequency), request, "holt_winters_additive"
    ).to_record()
    assert {item["method"] for item in result["selection"]["candidates"]} == {
        "last_value",
        "seasonal_naive",
        "holt_winters_additive",
    }


def test_auto_excludes_seasonal_families_when_earliest_training_is_too_short():
    result = advanced_forecast(
        series(range(18), "monthly"), ForecastRequest("monthly", 3, 12)
    ).to_record()
    assert not any(
        item["method"] in {"seasonal_naive", "holt_winters_additive"}
        for item in result["selection"]["candidates"]
    )
    assert "fewer than two" in result["selection"]["excluded"][0]["reason"]


def test_negative_forecasts_are_not_clipped():
    result = advanced_forecast(
        series([50 - index for index in range(50)]), ForecastRequest("daily", 4), "holt"
    ).to_record()
    assert tuple(Decimal(row["estimate"]) for row in result["predictions"]) == tuple(
        map(Decimal, (0, -1, -2, -3))
    )


def test_maximum_history_work_is_recorded_and_under_explicit_budget():
    result = advanced_forecast(
        series([Decimal(index % 7) + index for index in range(1200)]),
        ForecastRequest("daily", 4, 7),
    ).to_record()
    assert len(result["history"]) == 1200
    assert result["selection"]["state_updates_bound"] <= MAX_STATE_UPDATES
    assert result["selection"]["state_updates_bound"] == 43 * (1184 + 1188 + 1192) + 1196 + 1200


def test_result_is_independent_of_callers_decimal_context():
    points = series([Decimal(index) / 7 for index in range(40)])
    expected = advanced_forecast(points, ForecastRequest("daily", 4, 7))
    with localcontext() as context:
        context.prec = 4
        context.rounding = ROUND_DOWN
        assert advanced_forecast(points, ForecastRequest("daily", 4, 7)) == expected


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda values: values[:4] + values[5:], "forecast_missing_period"),
        (
            lambda values: (replace(values[0], complete=False), *values[1:]),
            "forecast_incomplete_period",
        ),
        (
            lambda values: (replace(values[0], actual=Decimal("NaN")), *values[1:]),
            "forecast_value",
        ),
    ],
)
def test_missing_incomplete_or_invalid_source_is_refused(mutate, code):
    with pytest.raises(IngestionError) as error:
        advanced_forecast(mutate(series(range(40))), ForecastRequest("daily", 4))
    assert error.value.code == code


@pytest.mark.parametrize("family,season", [("unknown", None), ("holt_winters_additive", None)])
def test_unknown_or_undeclared_seasonal_request_is_refused(family, season):
    with pytest.raises(IngestionError):
        advanced_forecast(series(range(40)), ForecastRequest("daily", 4, season), family)


def test_saved_comparison_retains_pending_periods_and_original_advanced_record():
    result = advanced_forecast(series(range(40)), ForecastRequest("daily", 4)).to_record()
    snapshot = repr(result)
    comparison = compare_advanced_forecast(result, (ForecastPoint(date(2020, 2, 10), Decimal(40)),))
    assert comparison["observed_count"] == 1 and comparison["pending_count"] == 3
    assert comparison["rows"][1]["actual"] is None
    assert comparison["metrics"]["mae"] == "0"
    assert repr(result) == snapshot


def test_legacy_engine_is_unchanged_and_not_silently_upgraded():
    points = series(range(40))
    result = forecast(points, ForecastRequest("daily", 3)).to_record()
    assert result["version"] == "forecast-v1"
    assert result["method"]["id"] == "linear_trend"
    assert result["selection"]["criterion"] == "validation_mae"
    assert "folds" not in result["selection"]
