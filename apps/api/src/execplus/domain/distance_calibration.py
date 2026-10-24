"""Use case: Measures false-alarm rates of the distribution-drift and multi-measure detectors.

What it does: Runs the production two-window drift comparison and reference-cohort
Mahalanobis detector on seeded synthetic data with no injected change, maps a
requested false-alarm target to a fixed measured threshold and returns the evidence
stored with calibrated results. Synthetic calibration is not customer calibration.
"""

import random
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from typing import Any

from execplus.domain.anomaly_calibration import FAMILIES, _decimal, _rates
from execplus.domain.decision_analysis import encoded, fail
from execplus.domain.distribution_drift import CALIBRATED_METHOD as DRIFT_CALIBRATED_METHOD
from execplus.domain.distribution_drift import DriftRequest, compare_drift
from execplus.domain.multivariate_anomalies import (
    CALIBRATED_METHOD as MULTIVARIATE_CALIBRATED_METHOD,
)
from execplus.domain.multivariate_anomalies import detect_multivariate
from execplus.domain.temporal_anomalies import TemporalPoint

VERSION = "synthetic-distance-calibration-v1"
SEED = 20261024
TARGETS = ("0.05", "0.01", "0.005")
DRIFT_WINDOWS = ((8, 8), (14, 14), (30, 30), (60, 60), (90, 30))
DRIFT_TRIALS = 400
DRIFT_COEFFICIENTS = ("1", "1.1", "1.22", "1.36", "1.48", "1.63", "1.73", "1.95", "2.2")
MULTIVARIATE_DIMENSIONS = (2, 3, 4)
MULTIVARIATE_REFERENCES = (30, 100, 300)
MULTIVARIATE_TRIALS = 20
MULTIVARIATE_COMPARISONS = 50
MULTIVARIATE_THRESHOLDS = (
    "6",
    "8",
    "10",
    "12",
    "14",
    "16",
    "20",
    "25",
    "30",
    "40",
    "50",
    "75",
    "100",
)
DRIFT_TARGETS = {"0.05": "1.36", "0.01": "1.63", "0.005": "1.73"}
DRIFT_MEASURED = {
    "1.36": {"normal": "0.030500", "heavy_tailed": "0.033500"},
    "1.63": {"normal": "0.005000", "heavy_tailed": "0.007500"},
    "1.73": {"normal": "0.003000", "heavy_tailed": "0.005000"},
}
MULTIVARIATE_TARGETS = {
    "2": {"0.05": "10", "0.01": "30", "0.005": "75"},
    "3": {"0.05": "14", "0.01": "40", "0.005": "75"},
    "4": {"0.05": "20", "0.01": "50", "0.005": "75"},
}
MULTIVARIATE_MEASURED = {
    "2": {
        "10": {"normal": "0.011667", "heavy_tailed": "0.045333"},
        "30": {"normal": "0.000000", "heavy_tailed": "0.009667"},
        "75": {"normal": "0.000000", "heavy_tailed": "0.003333"},
    },
    "3": {
        "14": {"normal": "0.007333", "heavy_tailed": "0.043000"},
        "40": {"normal": "0.000000", "heavy_tailed": "0.008667"},
        "75": {"normal": "0.000000", "heavy_tailed": "0.003333"},
    },
    "4": {
        "20": {"normal": "0.003667", "heavy_tailed": "0.037000"},
        "50": {"normal": "0.000000", "heavy_tailed": "0.008333"},
        "75": {"normal": "0.000000", "heavy_tailed": "0.003333"},
    },
}


def drift_separation(coefficient: str, reference: int, comparison: int) -> Decimal:
    """Two-sample Kolmogorov-Smirnov scaling: coefficient * sqrt((n + m) / (n * m))."""
    with localcontext() as context:
        context.prec, context.rounding = 28, ROUND_HALF_EVEN
        root = (Decimal(reference + comparison) / Decimal(reference * comparison)).sqrt()
        return min(Decimal(coefficient) * root, Decimal(1))


def _window(rng: random.Random, family: str, start: date, size: int) -> tuple[TemporalPoint, ...]:
    return tuple(
        TemporalPoint(start + timedelta(days=index), _decimal(100 + 5 * FAMILIES[family](rng)))
        for index in range(size)
    )


def _drift_separations(family: str) -> list[tuple[Fraction, int, int]]:
    rng = random.Random(f"{SEED}-drift-{family}")
    observed = []
    for reference_size, comparison_size in DRIFT_WINDOWS:
        for _ in range(DRIFT_TRIALS):
            start = date(2025, 1, 1)
            reference = _window(rng, family, start, reference_size)
            comparison = _window(
                rng, family, start + timedelta(days=reference_size), comparison_size
            )
            result = compare_drift(reference, comparison, DriftRequest("daily", "0", "0"))
            separation = result["maximum_cdf_separation"]
            observed.append(
                (
                    Fraction(int(separation["numerator"]), int(separation["denominator"])),
                    reference_size,
                    comparison_size,
                )
            )
    return observed


def _multivariate_distances(family: str, dimensions: int) -> list[Fraction]:
    rng = random.Random(f"{SEED}-multivariate-{family}-{dimensions}")
    metrics = [f"m{index}" for index in range(dimensions)]
    distances: list[Fraction] = []
    for reference_size in MULTIVARIATE_REFERENCES:
        for _ in range(MULTIVARIATE_TRIALS):
            rows = [
                (
                    f"r{index}",
                    "reference" if index < reference_size else "comparison",
                    *(
                        _decimal(10 * (axis + 1) + (axis + 1) * FAMILIES[family](rng))
                        for axis in range(dimensions)
                    ),
                )
                for index in range(reference_size + MULTIVARIATE_COMPARISONS)
            ]
            result = detect_multivariate(
                dict(
                    metrics=metrics,
                    reference_label="reference",
                    comparison_label="comparison",
                    threshold="1000000",
                    identifier_column="id",
                    cohort_column="cohort",
                ),
                rows,
            )
            distances.extend(
                Fraction(
                    int(record["squared_distance"]["numerator"]),
                    int(record["squared_distance"]["denominator"]),
                )
                for record in result["records"]
                if record["phase"] == "comparison"
            )
    return distances


def distance_calibration_report() -> dict[str, Any]:
    drift = {family: _drift_separations(family) for family in FAMILIES}
    multivariate = {
        str(dimensions): {
            family: _multivariate_distances(family, dimensions) for family in FAMILIES
        }
        for dimensions in MULTIVARIATE_DIMENSIONS
    }
    return dict(
        version=VERSION,
        seed=SEED,
        design=dict(
            drift=dict(
                windows=[list(pair) for pair in DRIFT_WINDOWS],
                trials_per_window_pair=DRIFT_TRIALS,
                series="independent daily values 100 + 5 * family noise; no injected change",
                separation_rule="coefficient * sqrt((n + m) / (n * m)), capped at 1",
                materiality="0",
            ),
            multivariate=dict(
                dimensions=list(MULTIVARIATE_DIMENSIONS),
                reference_sizes=list(MULTIVARIATE_REFERENCES),
                trials_per_reference_size=MULTIVARIATE_TRIALS,
                comparison_records_per_trial=MULTIVARIATE_COMPARISONS,
                records="independent measures with centres 10/20/30/40 and scales 1/2/3/4; "
                "comparison drawn from the reference distribution",
            ),
            families=dict(
                normal="standard normal", heavy_tailed="Student t with 3 degrees of freedom"
            ),
        ),
        drift={
            coefficient: {
                family: _rates(
                    sum(
                        value > Fraction(drift_separation(coefficient, n, m))
                        for value, n, m in drift[family]
                    ),
                    len(drift[family]),
                    0,
                    0,
                )
                for family in FAMILIES
            }
            for coefficient in DRIFT_COEFFICIENTS
        },
        multivariate={
            dimensions: {
                threshold: {
                    family: _rates(
                        sum(value > Fraction(threshold) for value in values),
                        len(values),
                        0,
                        0,
                    )
                    for family, values in families.items()
                }
                for threshold in MULTIVARIATE_THRESHOLDS
            }
            for dimensions, families in multivariate.items()
        },
        rule="Smallest registered threshold whose measured false-alarm rate is at most "
        "the target on both synthetic families for that detector and measure count.",
        limitations=[
            "Synthetic data only; customer data can have other shapes and rates.",
            "Rates are measured frequencies over fixed seeded trials, not guarantees.",
            "Drift windows are independent draws; autocorrelation, seasonality or a "
            "different weekday mix raise false alarms.",
            "Multi-measure records are independent draws from the reference distribution; "
            "correlated, skewed or contaminated references change the rates.",
        ],
    )


def _target(table: dict[str, str], target: object) -> str:
    if not isinstance(target, str) or target not in table:
        fail(
            "invalid_detector",
            "Choose a supported false-alarm target: " + ", ".join(table) + ".",
        )
    return table[target]


def drift_evidence(target: object, reference: int, comparison: int) -> dict[str, Any]:
    coefficient = _target(DRIFT_TARGETS, target)
    return dict(
        version=VERSION,
        seed=SEED,
        detector="drift",
        target_false_alarm_rate=target,
        threshold=coefficient,
        threshold_kind="ks_coefficient",
        minimum_cdf_separation=encoded(drift_separation(coefficient, reference, comparison)),
        separation_rule="coefficient * sqrt((n + m) / (n * m)), capped at 1",
        measured_false_alarm_rate=DRIFT_MEASURED[coefficient],
        rule="Smallest registered coefficient whose measured rate is at most the target "
        "on both synthetic families.",
        label="Synthetic calibration; not a customer false-alarm guarantee.",
    )


def multivariate_evidence(target: object, dimensions: int) -> dict[str, Any]:
    key = str(dimensions)
    if key not in MULTIVARIATE_TARGETS:
        fail("multivariate_measures", "Choose two to four different confirmed measures.")
    threshold = _target(MULTIVARIATE_TARGETS[key], target)
    return dict(
        version=VERSION,
        seed=SEED,
        detector="multivariate",
        dimensions=dimensions,
        target_false_alarm_rate=target,
        threshold=threshold,
        threshold_kind="squared_distance",
        measured_false_alarm_rate=MULTIVARIATE_MEASURED[key][threshold],
        rule="Smallest registered squared-distance threshold whose measured rate is at most "
        "the target on both synthetic families for this number of measures.",
        label="Synthetic calibration; not a customer false-alarm guarantee.",
    )


def _calibrated(result: dict[str, Any], method: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return result | dict(
        method_version=method,
        calibration=evidence,
        evaluation=result["evaluation"]
        | dict(
            calibrated=True,
            calibration_kind="synthetic",
            false_alarm_rate=evidence["measured_false_alarm_rate"],
        ),
        limitations=[
            item
            for item in result["limitations"]
            if "calibrated" not in item and "not a chi-square" not in item
        ]
        + [
            "The threshold comes from a false-alarm target measured on synthetic unchanged "
            "data (normal and heavy-tailed noise); customer data can have other rates."
        ],
    )


def calibrated_drift(
    reference: tuple[TemporalPoint, ...],
    comparison: tuple[TemporalPoint, ...],
    request: DriftRequest,
    target: object,
) -> dict[str, Any]:
    evidence = drift_evidence(target, len(reference), len(comparison))
    request = DriftRequest(
        request.frequency, evidence["minimum_cdf_separation"], request.materiality
    )
    return _calibrated(
        compare_drift(reference, comparison, request), DRIFT_CALIBRATED_METHOD, evidence
    )


def calibrated_multivariate(raw: dict[str, Any], rows: Any) -> dict[str, Any]:
    if raw.get("threshold") != "9":
        fail("invalid_detector", "A false-alarm target sets the threshold.")
    metrics = raw["metrics"]
    evidence = multivariate_evidence(
        raw.get("target_false_alarm_rate"), len(metrics) if isinstance(metrics, list) else 0
    )
    result = detect_multivariate(raw | dict(threshold=evidence["threshold"]), rows)
    return _calibrated(result, MULTIVARIATE_CALIBRATED_METHOD, evidence)
