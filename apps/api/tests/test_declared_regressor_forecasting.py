"""Use case: Verifies holiday and outside-predictor forecasts (engine advanced-v5).

What it does: Checks the offline holiday table, an independent numpy least-squares fit,
the strict validation-selection rule, the seeded synthetic measurement, governed API
replay and that earlier engines keep their exact request and record shapes.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

import numpy
import pytest

from execplus.domain.advanced_forecasting import advanced_forecast
from execplus.domain.calendar_regression import TREND_ONLY, CalendarInputs, fit
from execplus.domain.declared_regressor_evaluation import evaluation_report
from execplus.domain.forecast_series import predictor_values
from execplus.domain.forecasting import ForecastPoint, ForecastRequest
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryResult
from execplus.domain.pakistan_holidays import catalog, holidays
from test_forecast_integration import create
from test_studies import prepare


def test_offline_holiday_table_is_bounded_and_versioned():
    assert catalog()["id"] == "pk-public-fixed-v1"
    assert holidays(date(2024, 1, 1), date(2024, 12, 31)) == tuple(
        date(2024, month, day)
        for month, day in ((2, 5), (3, 23), (5, 1), (5, 28), (8, 14), (11, 9), (12, 25))
    )
    assert date(2021, 11, 9) not in holidays(date(2021, 1, 1), date(2021, 12, 31))
    assert date(2023, 5, 28) not in holidays(date(2023, 1, 1), date(2023, 12, 31))
    for start, end in (
        (date(2019, 12, 1), date(2020, 1, 31)),
        (date(2030, 1, 1), date(2031, 1, 1)),
    ):
        with pytest.raises(ValueError):
            holidays(start, end)


def test_declared_coefficients_match_an_independent_numpy_least_squares_fit():
    rng = random.Random(9)
    size = 60
    periods = tuple(date(2024, 1, 1) + timedelta(days=i) for i in range(size))
    flags = tuple(int(rng.random() < 0.1) for _ in range(size))
    x = tuple(Decimal(f"{rng.uniform(0, 20):.2f}") for _ in range(size))
    y = tuple(
        Decimal(f"{10 + 0.5 * i + 2 * float(x[i]) - 7 * flags[i] + rng.gauss(0, 1):.2f}")
        for i in range(size)
    )
    inputs = CalendarInputs(periods, holidays=flags, predictors=(x,), predictor_names=("x",))
    ours = [float(v) for v in fit(inputs, "daily", size, y, TREND_ONLY, declared=True)]
    design = numpy.array([[1, i, flags[i], float(x[i])] for i in range(size)])
    expected, *_ = numpy.linalg.lstsq(design, numpy.array([float(v) for v in y]), rcond=None)
    assert ours == pytest.approx(expected.tolist(), rel=1e-9)


def points_and_inputs(related):
    rng = random.Random(5)
    total, horizon = 126, 7
    periods = tuple(date(2024, 1, 1) + timedelta(days=i) for i in range(total + horizon))
    x = tuple(Decimal(f"{rng.uniform(0, 10):.2f}") for _ in periods)
    noise = tuple(Decimal(f"{rng.uniform(0, 10):.2f}") for _ in periods)
    points = tuple(
        ForecastPoint(
            periods[i], Decimal(f"{40 + (3 * float(x[i]) if related else 0) + rng.gauss(0, 1):.2f}")
        )
        for i in range(total)
    )
    inputs = CalendarInputs(
        periods, predictors=(x if related else noise,), predictor_names=("driver",)
    )
    return points, ForecastRequest("daily", horizon), inputs


@pytest.mark.parametrize("related", [True, False])
def test_declared_regressors_win_only_with_strictly_lower_validation_error(related):
    points, request, inputs = points_and_inputs(related)
    record = advanced_forecast(points, request, calendar=inputs).to_record()
    assert record["version"] == "forecast-v5"
    candidates = record["selection"]["candidates"]
    declared = [c for c in candidates if c["parameters"].get("declared_regressors")]
    earlier = [c for c in candidates if not c["parameters"].get("declared_regressors")]
    best_declared = min(Decimal(c["metrics"]["mae"]) for c in declared)
    best_earlier = min(Decimal(c["metrics"]["mae"]) for c in earlier)
    regressors = record["regressors"]
    assert (regressors["selected"] == "declared_regressors") == (best_declared < best_earlier)
    assert (regressors["selected"] == "declared_regressors") == related
    assert Decimal(regressors["best_with_declared"]["validation_mae"]) == best_declared
    assert regressors["predictors"][0]["name"] == "driver"
    assert len(regressors["predictors"][0]["future_values"]) == 7
    if related:
        assert Decimal(regressors["predictors"][0]["effect"]) == pytest.approx(Decimal(3), abs=0.1)
    plain = advanced_forecast(points, request, calendar=CalendarInputs(inputs.periods)).to_record()
    assert plain["version"] == "forecast-v4" and "best_with_declared" not in plain["regressors"]


def test_missing_predictor_values_are_refused():
    day = date(2024, 1, 1)
    points = (ForecastPoint(day, Decimal(1)),)

    def result(value):
        return QueryResult(None, ("p", "v"), ((day, value),), 1, 1)

    assert predictor_values(result(Decimal(5)), result(2), result(2), points) == (Decimal(5),)
    for value, present in ((Decimal(5), 1), (None, 2)):
        with pytest.raises(IngestionError):
            predictor_values(result(value), result(present), result(2), points)


@pytest.fixture(scope="module")
def measured():
    return evaluation_report()["scenarios"]


def test_seeded_synthetic_measurement_is_reported_honestly(measured):
    means = {
        name: tuple(
            value[f"mean_{engine}_{kind}_mae"]
            for kind in ("test", "future")
            for engine in ("v2", "v4", "v5")
        )
        for name, value in measured.items()
    }
    assert means == {
        "holiday_closures": ("7.673", "6.634", "2.562", "6.270", "5.997", "2.960"),
        "predictor_driven": ("6.594", "6.594", "1.661", "6.777", "6.777", "1.789"),
        "predictor_wrong_future": ("6.594", "6.594", "1.661", "6.777", "6.777", "7.420"),
        "unrelated_predictor": ("4.918", "5.170", "5.170", "5.095", "5.285", "5.285"),
    }
    assert measured["holiday_closures"]["declared_selected"] == 10
    assert measured["unrelated_predictor"]["declared_selected"] == 0


def predictor_csv(count=70):
    rows = ["day,amount,price,visits"]
    rng = random.Random(4)
    for index in range(count):
        day = date(2024, 1, 1) + timedelta(days=index)
        visits = rng.randint(10, 40)
        closed = day in {date(2024, 2, 5), date(2024, 2, 20)}
        amount = 20 + 3 * visits - (60 if closed else 0) + rng.randint(-2, 2)
        rows.append(f"{day},{amount},{rng.randint(90, 110) / 10},{visits}")
    return ("\n".join(rows) + "\n").encode()


def test_declared_forecast_replays_and_earlier_engines_keep_their_shape(integration):
    env = integration
    owner, _, wid, did, _, root = prepare(env, predictor_csv())
    options = env.client.get(root + "/forecasts/options", headers=owner).json()
    assert {"price", "visits"} <= set(options["predictor_columns"])
    assert options["holiday_calendars"][0]["id"] == "pk-public-fixed-v1"
    future = [str(20 + index) for index in range(7)]
    common = dict(coverage_end="2024-03-10", horizon=7, engine="advanced-v5")
    response = create(
        env,
        owner,
        root,
        **common,
        holiday_calendar="pk-public-fixed-v1",
        holiday_dates=["2024-02-20", "2024-03-14"],
        predictors=[dict(column="visits", aggregation="sum", future_values=future)],
    )
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["method_version"] == "forecast-v5"
    assert len(value["evidence"]["query_ids"]) == 5
    regressors = value["result"]["regressors"]
    assert regressors["selected"] == "declared_regressors"
    assert regressors["predictors"][0]["future_values"] == future
    assert regressors["holidays"]["history_periods_with_holidays"] == 2
    assert regressors["holidays"]["future_holiday_periods"] == [
        {"period": "2024-03-14", "holidays": 1}
    ]
    assert Decimal(regressors["predictors"][0]["effect"]) == pytest.approx(Decimal(3), abs=0.2)
    reopened = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/forecasts/{value['id']}", headers=owner
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json() == value
    calendar_only = create(env, owner, root, **dict(common, engine="advanced-v4"))
    assert calendar_only.status_code == 201, calendar_only.text
    assert not {"holiday_dates", "holiday_calendar", "predictors"} & set(
        calendar_only.json()["request"]
    )
    assert calendar_only.json()["method_version"] == "forecast-v4"
    predictor = dict(column="visits", aggregation="sum", future_values=future)
    for changes in (
        dict(common),
        dict(common, engine="advanced-v4", holiday_calendar="pk-public-fixed-v1"),
        dict(common, predictors=[dict(predictor, future_values=future[:6])]),
        dict(common, predictors=[dict(predictor, column="amount")]),
        dict(common, predictors=[predictor, predictor]),
        dict(common, predictors=[dict(predictor, future_values=["x"] * 7)]),
        dict(common, holiday_dates=["2023-12-31"]),
        dict(common, predictors=[predictor] * 4),
    ):
        refused = create(env, owner, root, **changes)
        assert refused.status_code == 422, (changes, refused.text)
