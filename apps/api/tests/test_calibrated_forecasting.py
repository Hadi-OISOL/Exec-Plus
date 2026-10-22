"""Use case: Independently checks split-conformal calibrated advanced forecast ranges.

What it does: Pins byte-identical v2 records, recomputes v3 widths with separate
Fraction code, checks window separation and measures seeded coverage.
"""

import hashlib
import json
import random
from datetime import date
from decimal import Decimal
from fractions import Fraction

import pytest

from execplus.domain.advanced_forecasting import (
    advanced_forecast,
    compare_advanced_forecast,
    minimum_history,
)
from execplus.domain.forecasting import ForecastPoint, ForecastRequest, next_period
from execplus.domain.ingestion import IngestionError


def series(values, frequency="daily"):
    period = date(2020, 1, 1)
    points = []
    for value in values:
        points.append(ForecastPoint(period, Decimal(str(value))))
        period = next_period(period, frequency)
    return tuple(points)


def golden_cases():
    rng = random.Random(7)
    return [
        (
            series([100 + 2 * i + (i % 7 - 3) + rng.randint(-5, 5) for i in range(70)]),
            ForecastRequest("daily", 4, 7),
            "auto",
            "bfc6440ae07b1b7a3c5d0fd5bf8472ddfbfd57de86305257e667bc40566d6a89",
        ),
        (
            series([50 + rng.randint(-9, 9) for _ in range(40)], "monthly"),
            ForecastRequest("monthly", 3, None),
            "auto",
            "ac0cefdf338c2faff49110498a42dbf653542f9476101bee183b8a7ec3865867",
        ),
        (
            series([10 + i for i in range(40)]),
            ForecastRequest("daily", 3, None),
            "damped_holt",
            "79f0e8fc7dcba53494eb870d5099d76c3822a0048198d64db8298abfc7f11580",
        ),
    ]


def test_v2_records_stay_byte_identical_to_the_pre_calibration_release():
    for points, request, family, expected in golden_cases():
        record = advanced_forecast(points, request, family).to_record()
        digest = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
        assert digest == expected
        assert record["version"] == "forecast-v2"


def independent_forecast(method, parameters, values, steps):
    if method == "last_value":
        return [Fraction(values[-1])] * steps
    alpha = Fraction(parameters["alpha"])
    level = Fraction(values[0])
    for value in values[1:]:
        level = alpha * Fraction(value) + (1 - alpha) * level
    return [level] * steps


def test_calibrated_widths_match_an_independent_split_conformal_computation():
    rng = random.Random(20261022)
    level, raw = 100, []
    for _ in range(64):
        level += rng.randint(-4, 4)
        raw.append(level + rng.randint(-6, 6))
    request = ForecastRequest("daily", 4, None)
    record = advanced_forecast(
        series(raw), request, "simple_exponential", calibrated=True
    ).to_record()
    assert record["version"] == "forecast-v3"
    method = record["method"]
    assert method["id"] in {"last_value", "simple_exponential"}
    holdout = 4
    first_origin = len(raw) - 4 * holdout
    origins = range(first_origin - holdout - 8, first_origin - holdout + 1)
    assert len(origins) == 9
    assert record["windows"]["calibration"]["count"] == first_origin - origins[0]
    for step in range(holdout):
        residuals = sorted(
            abs(
                Fraction(raw[origin + step])
                - independent_forecast(method["id"], method["parameters"], raw[:origin], holdout)[
                    step
                ]
            )
            for origin in origins
        )
        expected = residuals[7]
        assert abs(Fraction(record["uncertainty"]["step_widths"][step]) - expected) <= Fraction(
            1, 10**9
        )
        prediction = record["predictions"][step]
        width = Decimal(prediction["upper"]) - Decimal(prediction["estimate"])
        assert abs(Fraction(width) - expected) <= Fraction(1, 10**9)
    uncertainty = record["uncertainty"]
    assert uncertainty["calibration_independent"] is True
    assert uncertainty["coverage_guaranteed"] is False
    assert uncertainty["nominal_coverage"] == "0.8" and uncertainty["conformal_rank"] == 8
    assert any("calibration windows" in item for item in record["limitations"])
    assert not any(item.startswith("Error ranges") for item in record["limitations"])


def test_calibration_windows_end_before_selection_and_need_longer_history():
    request = ForecastRequest("daily", 4, None)
    assert minimum_history(request, "auto", calibrated=True) == minimum_history(request) + 12
    short = series([index % 5 for index in range(minimum_history(request))])
    advanced_forecast(short, request)
    with pytest.raises(IngestionError) as error:
        advanced_forecast(short, request, calibrated=True)
    assert error.value.code == "forecast_insufficient_history"
    points = series([index % 5 + index for index in range(60)])
    record = advanced_forecast(points, request, calibrated=True).to_record()
    assert record["windows"]["calibration"]["end"] < record["windows"]["validation"]["start"]
    assert compare_advanced_forecast(record, points[-2:])["observed_count"] == 0


def test_measured_calibrated_coverage_on_seeded_series_is_near_nominal():
    rng = random.Random(11)
    inside = {False: 0, True: 0}
    total = 0
    for _ in range(60):
        level, raw = 200.0, []
        for _ in range(72):
            level += rng.gauss(0, 2)
            raw.append(round(level + rng.gauss(0, 5), 3))
        points = series(raw)
        request = ForecastRequest("daily", 4, None)
        for calibrated in (False, True):
            record = advanced_forecast(
                points, request, "simple_exponential", calibrated=calibrated
            ).to_record()
            inside[calibrated] += record["uncertainty"]["backtest_coverage"]["inside"]
        total += 4
    print("coverage v2", inside[False] / total, "v3", inside[True] / total, "n", total)
    assert 0.7 <= inside[True] / total <= 0.92


def test_calibrated_engine_saves_reopens_exports_and_refuses_short_history(integration):
    from test_forecast_integration import create, daily
    from test_result_exports import download_text
    from test_studies import prepare

    env = integration
    owner, _, wid, did, _, root = prepare(env, daily(60))
    response = create(env, owner, root, engine="advanced-v3", coverage_end="2024-02-29")
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["request"]["engine"] == "advanced-v3"
    assert run["method_version"] == run["result"]["version"] == "forecast-v3"
    assert len(run["result"]["uncertainty"]["step_widths"]) == 4
    assert "80% split-conformal calibration" in " ".join(run["result"]["commentary"])
    path = f"/workspaces/{wid}/datasets/{did}/forecasts/{run['id']}"
    assert env.client.get(path, headers=owner).json() == run
    exported = download_text(env.client.get(path + "/export.pdf", headers=owner), "pdf")
    assert "split_conformal_per_step_v1" in exported
    assert "separate earlier calibration" in " ".join(exported.split())
    short_owner, _, _, _, _, short_root = prepare(env, daily())
    refused = create(env, short_owner, short_root, engine="advanced-v3")
    assert refused.status_code == 422, refused.text
