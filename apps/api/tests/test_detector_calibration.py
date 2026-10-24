"""Use case: Verifies measured false-alarm calibration of grouped, seasonal and rolling detectors.

What it does: Recomputes the seeded report, derives every target table independently,
checks one null trial with separate float code and replays each calibrated method
through the governed API while legacy requests keep their original method versions.
"""

import random
from datetime import date, timedelta
from decimal import Decimal
from math import pi, sin
from statistics import median

import pytest

from execplus.domain.anomaly_calibration import FAMILIES, THRESHOLDS, _decimal
from execplus.domain.detector_calibration import (
    CALENDAR_SIZE,
    CALENDAR_TRAINING,
    MEASURED,
    ROLLING_CALIBRATED_METHOD,
    SEASONAL_CALIBRATED_METHOD,
    SEED,
    TARGET_THRESHOLDS,
    TARGETS,
    detector_calibration_report,
    detector_threshold,
)
from execplus.domain.ingestion import IngestionError
from execplus.domain.rolling_anomalies import METHOD as ROLLING
from execplus.domain.temporal_anomalies import (
    TemporalAnomalyRequest,
    TemporalPoint,
    detect_seasonal,
)
from test_advanced_anomaly_integration import create as rolling_create
from test_advanced_anomaly_integration import setup as rolling_setup
from test_calendar_analysis_integration import create as seasonal_create
from test_calendar_analysis_integration import endpoint as calendar_endpoint
from test_calendar_analysis_integration import fixture as seasonal_fixture
from test_decision_analysis_integration import create, endpoint
from test_studies import prepare


@pytest.fixture(scope="module")
def report():
    return detector_calibration_report()


def test_report_is_seeded_and_reproducible(report):
    assert detector_calibration_report(("6",))["thresholds"]["6"] == report["thresholds"]["6"]
    assert report["seed"] == SEED


@pytest.mark.parametrize("detector", ["grouped", "seasonal", "rolling"])
def test_target_tables_are_derived_from_the_measured_report(report, detector):
    for target in TARGETS:
        eligible = [
            threshold
            for threshold in THRESHOLDS
            if all(
                Decimal(report["thresholds"][threshold][detector][name]["false_alarm_rate"])
                <= Decimal(target)
                for name in FAMILIES
            )
        ]
        threshold = TARGET_THRESHOLDS[detector][target]
        assert eligible[0] == threshold
        assert {
            name: report["thresholds"][threshold][detector][name]["false_alarm_rate"]
            for name in FAMILIES
        } == MEASURED[detector][threshold]


def test_rates_fall_as_thresholds_rise_and_grouped_recall_tradeoff_is_visible(report):
    rows = report["thresholds"]
    for detector in ("grouped", "seasonal", "rolling"):
        heavy = [Decimal(rows[t][detector]["heavy_tailed"]["false_alarm_rate"]) for t in THRESHOLDS]
        assert heavy == sorted(heavy, reverse=True) and heavy[0] > heavy[-1]
    recall = [Decimal(rows[t]["grouped"]["normal"]["recall"]) for t in THRESHOLDS]
    assert recall == sorted(recall, reverse=True)
    assert recall[0] == 1 and recall[-1] < Decimal("0.2")


def test_one_seasonal_null_trial_matches_an_independent_float_count():
    rng = random.Random(f"{SEED}-seasonal-normal")
    values = [
        _decimal(10 * sin(2 * pi * index / 7) + rng.gauss(0.0, 1.0))
        for index in range(CALENDAR_SIZE)
    ]
    residuals = [float(values[i] - values[i - 7]) for i in range(7, CALENDAR_TRAINING)]
    center = median(residuals)
    mad = median(abs(r - center) for r in residuals)
    expected = sum(
        0.67448975 * abs(float(values[i] - values[i - 7]) - center) > 3 * mad
        for i in range(CALENDAR_TRAINING, CALENDAR_SIZE)
    )
    start = date(2025, 1, 1)
    points = tuple(TemporalPoint(start + timedelta(days=i), v) for i, v in enumerate(values))
    request = TemporalAnomalyRequest("daily", 7, points[CALENDAR_TRAINING - 1].period, "3")
    assert detect_seasonal(points, request)["flagged_periods"] == expected


def test_unsupported_targets_are_refused():
    assert detector_threshold("rolling", "0.01") == "8"
    for target in ("0.5", None, 0.01):
        with pytest.raises(IngestionError):
            detector_threshold("grouped", target)


def test_grouped_calibrated_version_replays_and_legacy_grouping_is_unchanged(integration):
    env = integration
    rows = b"".join(
        f"{city},{value},1\n".encode()
        for city in ("Karachi", "Lahore")
        for value in (10, 11, 12, 10, 11, 12, 10, 11, 12)
    )
    data = b"city,amount,cost\n" + rows + b"Lahore,500,2\n"
    headers, _, _, _, _, root = prepare(env, data)
    calibrated = create(env, headers, root, segment_column="city", target_false_alarm_rate="0.01")
    assert calibrated.status_code == 201, calibrated.text
    run = calibrated.json()["run"]
    assert run["method_version"] == "segmented-mad-iqr-calibrated-v1"
    assert run["result"]["threshold"] == "6"
    assert run["result"]["calibration"]["detector"] == "grouped"
    assert run["result"]["calibration"]["measured_false_alarm_rate"] == MEASURED["grouped"]["6"]
    assert [(f["segment"], f["value"]) for f in run["result"]["findings"]] == [("Lahore", "500")]
    reopened = env.client.get(endpoint(root, calibrated.json()), headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == run
    legacy = create(env, headers, root, segment_column="city")
    assert legacy.status_code == 201, legacy.text
    assert legacy.json()["run"]["method_version"] == "segmented-mad-iqr-v1"
    assert "calibration" not in legacy.json()["run"]["result"]
    assert "target_false_alarm_rate" not in legacy.json()["run"]["request"]
    refused = create(
        env, headers, root, segment_column="city", target_false_alarm_rate="0.01", threshold="4"
    )
    assert refused.status_code == 422, refused.text


def test_seasonal_calibrated_model_replays_with_its_measured_threshold(integration):
    env = integration
    owner, _, _, _, _, root = seasonal_fixture(env)
    response = seasonal_create(
        env, owner, root, model=SEASONAL_CALIBRATED_METHOD, target_false_alarm_rate="0.01"
    )
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    assert run["method_version"] == SEASONAL_CALIBRATED_METHOD
    assert run["result"]["method_version"] == SEASONAL_CALIBRATED_METHOD
    assert run["result"]["threshold"] == "5"
    assert run["result"]["calibration"]["measured_false_alarm_rate"] == MEASURED["seasonal"]["5"]
    reopened = env.client.get(calendar_endpoint(root, response.json()), headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == run
    legacy = seasonal_create(env, owner, root)
    assert legacy.status_code == 201, legacy.text
    assert "target_false_alarm_rate" not in legacy.json()["run"]["request"]
    assert legacy.json()["run"]["method_version"] == "seasonal-residual-mad-iqr-v1"
    for changes in (
        dict(model=SEASONAL_CALIBRATED_METHOD),
        dict(target_false_alarm_rate="0.01"),
        dict(model=SEASONAL_CALIBRATED_METHOD, target_false_alarm_rate="0.01", threshold="4"),
    ):
        assert seasonal_create(env, owner, root, **changes).status_code == 422


def test_rolling_calibrated_model_replays_with_its_measured_threshold(integration):
    env = integration
    owner, *_, root = rolling_setup(env, ROLLING)
    response = rolling_create(
        env,
        owner,
        root,
        ROLLING,
        dict(model=ROLLING_CALIBRATED_METHOD, target_false_alarm_rate="0.005"),
    )
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    assert run["method_version"] == ROLLING_CALIBRATED_METHOD
    assert run["result"]["threshold"] == "8"
    assert run["result"]["findings"]
    url = root.split("/uploads/")[0] + "/decision-analysis/" + run["id"]
    reopened = env.client.get(url, headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == run
