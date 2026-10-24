"""Use case: Verifies measured false-alarm calibration of the drift and multi-measure detectors.

What it does: Recomputes the seeded report, derives every target table from it, checks
one drift and one multi-measure null trial with independent float code and replays both
calibrated methods through the governed API while legacy requests keep their versions.
"""

import random
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pytest

from execplus.domain.anomaly_calibration import FAMILIES, _decimal
from execplus.domain.distance_calibration import (
    DRIFT_CALIBRATED_METHOD,
    DRIFT_COEFFICIENTS,
    DRIFT_MEASURED,
    DRIFT_TARGETS,
    MULTIVARIATE_CALIBRATED_METHOD,
    MULTIVARIATE_MEASURED,
    MULTIVARIATE_TARGETS,
    MULTIVARIATE_THRESHOLDS,
    SEED,
    TARGETS,
    distance_calibration_report,
    drift_evidence,
    drift_separation,
    multivariate_evidence,
)
from execplus.domain.distribution_drift import DriftRequest, compare_drift
from execplus.domain.ingestion import IngestionError
from execplus.domain.multivariate_anomalies import METHOD as MULTI
from execplus.domain.multivariate_anomalies import detect_multivariate
from execplus.domain.temporal_anomalies import TemporalPoint
from test_advanced_anomaly_integration import create as multi_create
from test_advanced_anomaly_integration import setup as multi_setup
from test_calendar_analysis_integration import DRIFT, endpoint
from test_calendar_analysis_integration import create as drift_create
from test_calendar_analysis_integration import fixture as drift_fixture


@pytest.fixture(scope="module")
def report():
    return distance_calibration_report()


def eligible(rows, target):
    return [
        key
        for key, families in rows.items()
        if all(Decimal(families[name]["false_alarm_rate"]) <= Decimal(target) for name in FAMILIES)
    ]


def test_drift_targets_are_derived_from_the_measured_report(report):
    assert report["seed"] == SEED and list(report["drift"]) == list(DRIFT_COEFFICIENTS)
    for target in TARGETS:
        coefficient = DRIFT_TARGETS[target]
        assert eligible(report["drift"], target)[0] == coefficient
        assert {
            name: report["drift"][coefficient][name]["false_alarm_rate"] for name in FAMILIES
        } == DRIFT_MEASURED[coefficient]


@pytest.mark.parametrize("dimensions", ["2", "3", "4"])
def test_multivariate_targets_are_derived_per_measure_count(report, dimensions):
    rows = report["multivariate"][dimensions]
    assert list(rows) == list(MULTIVARIATE_THRESHOLDS)
    for target in TARGETS:
        threshold = MULTIVARIATE_TARGETS[dimensions][target]
        assert eligible(rows, target)[0] == threshold
        assert {
            name: rows[threshold][name]["false_alarm_rate"] for name in FAMILIES
        } == MULTIVARIATE_MEASURED[dimensions][threshold]


def test_rates_fall_as_thresholds_rise(report):
    tables = [report["drift"], *report["multivariate"].values()]
    for table in tables:
        for name in FAMILIES:
            rates = [Decimal(row[name]["false_alarm_rate"]) for row in table.values()]
            assert rates == sorted(rates, reverse=True) and rates[0] > rates[-1]


def test_drift_separation_matches_the_ks_scaling_formula():
    assert drift_separation("1.36", 8, 8) == Decimal("0.68")
    assert abs(float(drift_separation("1.63", 90, 30)) - 1.63 * (120 / 2700) ** 0.5) < 1e-12
    assert drift_separation("2.2", 8, 8) == Decimal("1")


def test_one_drift_null_trial_matches_an_independent_ks_statistic():
    rng = random.Random(f"{SEED}-drift-normal")
    start = date(2025, 1, 1)
    reference = [_decimal(100 + 5 * FAMILIES["normal"](rng)) for _ in range(8)]
    comparison = [_decimal(100 + 5 * FAMILIES["normal"](rng)) for _ in range(8)]
    expected = max(
        abs(
            sum(v <= x for v in reference) / len(reference)
            - sum(v <= x for v in comparison) / len(comparison)
        )
        for x in reference + comparison
    )
    result = compare_drift(
        tuple(TemporalPoint(start + timedelta(days=i), v) for i, v in enumerate(reference)),
        tuple(TemporalPoint(start + timedelta(days=8 + i), v) for i, v in enumerate(comparison)),
        DriftRequest("daily", "0", "0"),
    )
    separation = result["maximum_cdf_separation"]
    assert int(separation["numerator"]) / int(separation["denominator"]) == pytest.approx(expected)


def test_one_multivariate_null_trial_matches_independent_numpy_distances():
    rng = random.Random(f"{SEED}-multivariate-normal-3")
    rows = [
        (
            f"r{index}",
            "reference" if index < 30 else "comparison",
            *(_decimal(10 * (a + 1) + (a + 1) * FAMILIES["normal"](rng)) for a in range(3)),
        )
        for index in range(80)
    ]
    result = detect_multivariate(
        dict(
            metrics=["a", "b", "c"],
            reference_label="reference",
            comparison_label="comparison",
            threshold="14",
            identifier_column="id",
            cohort_column="cohort",
        ),
        rows,
    )
    values = np.array([[float(v) for v in row[2:]] for row in rows])
    reference, comparison = values[:30], values[30:]
    inverse = np.linalg.inv(np.cov(reference, rowvar=False, ddof=1))
    delta = comparison - reference.mean(axis=0)
    expected = np.einsum("ij,jk,ik->i", delta, inverse, delta)
    observed = [
        float(
            Fraction(
                int(r["squared_distance"]["numerator"]), int(r["squared_distance"]["denominator"])
            )
        )
        for r in result["records"]
        if r["phase"] == "comparison"
    ]
    assert observed == pytest.approx(expected.tolist(), rel=1e-9)
    assert result["flagged_records"] == int((expected > 14).sum())


def test_unsupported_targets_and_measure_counts_are_refused():
    assert max(map(len, (DRIFT_CALIBRATED_METHOD, MULTIVARIATE_CALIBRATED_METHOD))) <= 40
    assert drift_evidence("0.01", 8, 8)["threshold"] == "1.63"
    assert multivariate_evidence("0.05", 4)["threshold"] == "20"
    for call in (
        lambda: drift_evidence("0.5", 8, 8),
        lambda: drift_evidence(None, 8, 8),
        lambda: multivariate_evidence(0.01, 2),
        lambda: multivariate_evidence("0.01", 5),
    ):
        with pytest.raises(IngestionError):
            call()


def shifted(rows):
    return [
        ",".join([*row.split(",")[:2], "50" if index >= 8 else row.split(",")[2], "999"])
        for index, row in enumerate(rows)
    ]


def test_drift_calibrated_model_replays_and_legacy_drift_is_unchanged(integration):
    env = integration
    owner, _, _, _, _, root = drift_fixture(env, DRIFT, mutate=shifted)
    response = drift_create(
        env,
        owner,
        root,
        DRIFT,
        model=DRIFT_CALIBRATED_METHOD,
        target_false_alarm_rate="0.01",
        minimum_cdf_separation=None,
    )
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    assert run["method_version"] == DRIFT_CALIBRATED_METHOD
    assert "minimum_cdf_separation" not in run["request"]
    result = run["result"]
    assert result["method_version"] == DRIFT_CALIBRATED_METHOD
    assert result["minimum_cdf_separation"] == "0.815"
    assert result["calibration"]["threshold"] == "1.63"
    assert result["evaluation"]["calibrated"] is True
    assert result["evaluation"]["false_alarm_rate"] == DRIFT_MEASURED["1.63"]
    assert result["review_flag"] is True
    reopened = env.client.get(endpoint(root, response.json()), headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == run
    legacy = drift_create(env, owner, root, DRIFT)
    assert legacy.status_code == 201, legacy.text
    legacy_run = legacy.json()["run"]
    assert legacy_run["method_version"] == DRIFT
    assert "target_false_alarm_rate" not in legacy_run["request"]
    assert legacy_run["result"]["evaluation"]["calibrated"] is False
    assert "calibration" not in legacy_run["result"]
    for changes in (
        dict(model=DRIFT_CALIBRATED_METHOD),
        dict(model=DRIFT_CALIBRATED_METHOD, target_false_alarm_rate="0.01"),
        dict(target_false_alarm_rate="0.01"),
        dict(minimum_cdf_separation=None),
    ):
        assert drift_create(env, owner, root, DRIFT, **changes).status_code == 422


def test_multivariate_calibrated_model_replays_and_legacy_is_unchanged(integration):
    env = integration
    owner, *_, root = multi_setup(env, MULTI)
    response = multi_create(
        env,
        owner,
        root,
        MULTI,
        dict(model=MULTIVARIATE_CALIBRATED_METHOD, target_false_alarm_rate="0.01"),
    )
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    assert run["method_version"] == MULTIVARIATE_CALIBRATED_METHOD
    result = run["result"]
    assert result["threshold"]["display"] == "30"
    assert result["calibration"]["dimensions"] == 2
    assert result["evaluation"]["calibrated"] is True
    assert result["evaluation"]["false_alarm_rate"] == MULTIVARIATE_MEASURED["2"]["30"]
    assert {f["record_id"] for f in result["findings"]} >= {"r65", "r66"}
    url = root.split("/uploads/")[0] + "/decision-analysis/" + run["id"]
    reopened = env.client.get(url, headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == run
    legacy = multi_create(env, owner, root, MULTI)
    assert legacy.status_code == 201, legacy.text
    assert legacy.json()["run"]["method_version"] == MULTI
    assert "target_false_alarm_rate" not in legacy.json()["run"]["request"]
    assert legacy.json()["run"]["result"]["evaluation"]["calibrated"] is False
    for changes in (
        dict(model=MULTIVARIATE_CALIBRATED_METHOD),
        dict(target_false_alarm_rate="0.01"),
        dict(model=MULTIVARIATE_CALIBRATED_METHOD, target_false_alarm_rate="0.01", threshold="5"),
    ):
        assert multi_create(env, owner, root, MULTI, changes).status_code == 422
