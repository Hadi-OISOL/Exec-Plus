"""Use case: Verifies measured synthetic calibration of the robust anomaly detectors.

What it does: Recomputes the seeded report, derives the target table independently
and checks the calibrated request version end to end with replay and old requests.
"""

import random
from decimal import Decimal
from statistics import median

import pytest

from execplus.domain.anomaly_calibration import (
    FAMILIES,
    MEASURED,
    SEED,
    TARGET_THRESHOLDS,
    THRESHOLDS,
    _decimal,
    calibrated_threshold,
    calibration_report,
)
from execplus.domain.decision_analysis import detect_distribution
from execplus.domain.ingestion import IngestionError
from test_decision_analysis_integration import create, endpoint
from test_studies import prepare


@pytest.fixture(scope="module")
def report():
    return calibration_report()


def test_report_is_seeded_and_reproducible(report):
    assert calibration_report(("6",))["thresholds"]["6"] == report["thresholds"]["6"]
    assert report["seed"] == SEED


def test_target_table_is_derived_from_the_measured_report(report):
    for target, threshold in TARGET_THRESHOLDS.items():
        eligible = [
            candidate
            for candidate in THRESHOLDS
            if all(
                Decimal(
                    report["thresholds"][candidate]["distribution"][name]["null"][
                        "false_alarm_rate"
                    ]
                )
                <= Decimal(target)
                for name in FAMILIES
            )
        ]
        assert eligible[0] == threshold
        assert {
            name: report["thresholds"][threshold]["distribution"][name]["null"]["false_alarm_rate"]
            for name in FAMILIES
        } == MEASURED[threshold]


def test_rates_fall_as_threshold_rises_and_detection_tradeoff_is_visible(report):
    rows = report["thresholds"]
    heavy = [
        Decimal(rows[t]["distribution"]["heavy_tailed"]["null"]["false_alarm_rate"])
        for t in THRESHOLDS
    ]
    recall = [Decimal(rows[t]["distribution"]["normal"]["injected"]["recall"]) for t in THRESHOLDS]
    assert heavy == sorted(heavy, reverse=True)
    assert recall == sorted(recall, reverse=True)
    assert recall[0] == 1 and recall[-1] < Decimal("0.1")
    assert Decimal(rows["3"]["rolling_seasonal"]["false_alarm_rate"]) > Decimal(
        rows["5"]["rolling_seasonal"]["false_alarm_rate"]
    )


def test_one_null_trial_matches_an_independent_float_mad_count():
    rng = random.Random(f"{SEED}-normal")
    values = [_decimal(rng.gauss(0.0, 1.0)) for _ in range(200)]
    center = median(values)
    mad = median(abs(v - center) for v in values)
    expected = sum(Decimal("0.67448975") * abs(v - center) / mad > 3 for v in values)
    assert detect_distribution([(v, 1) for v in values], "3")["flagged_records"] == expected


def test_unsupported_target_is_refused():
    assert calibrated_threshold("0.01") == "6"
    with pytest.raises(IngestionError):
        calibrated_threshold("0.5")


def test_calibrated_request_version_replays_and_legacy_requests_are_unchanged(integration):
    env = integration
    data = b"city,amount,cost\n" + b"Karachi,10,1\nKarachi,11,1\n" * 6 + b"Lahore,100,2\n"
    headers, _, _, _, _, root = prepare(env, data)
    calibrated = create(env, headers, root, target_false_alarm_rate="0.01")
    assert calibrated.status_code == 201, calibrated.text
    run = calibrated.json()["run"]
    assert run["method_version"] == "weighted-mad-iqr-calibrated-v2"
    assert run["result"]["threshold"] == "6"
    assert run["result"]["calibration"]["measured_false_alarm_rate"] == MEASURED["6"]
    assert [item["value"] for item in run["result"]["findings"]] == ["100"]
    reopened = env.client.get(endpoint(root, calibrated.json()), headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == run
    legacy = create(env, headers, root)
    assert legacy.status_code == 201, legacy.text
    assert "target_false_alarm_rate" not in legacy.json()["run"]["request"]
    assert legacy.json()["run"]["method_version"] == "weighted-mad-iqr-v1"
    assert "calibration" not in legacy.json()["run"]["result"]
    for extra in (dict(threshold="4"), dict(segment_column="city")):
        refused = create(env, headers, root, target_false_alarm_rate="0.01", **extra)
        assert refused.status_code == 422, refused.text
