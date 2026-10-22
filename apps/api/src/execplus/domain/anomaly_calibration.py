"""Use case: Measures detector false-alarm and detection rates on labelled synthetic data.

What it does: Runs the production MAD/IQR and rolling detectors on seeded null and
injected-spike series, and maps a requested false-alarm target to a fixed threshold
measured that way. Synthetic calibration is not customer calibration.
"""

import random
from datetime import date, timedelta
from decimal import Decimal
from math import pi, sin, sqrt
from typing import Any

from execplus.domain.decision_analysis import detect_distribution, fail
from execplus.domain.rolling_anomalies import RollingRequest, detect_rolling
from execplus.domain.temporal_anomalies import TemporalPoint

CALIBRATED_METHOD = "weighted-mad-iqr-calibrated-v2"
CALIBRATION_VERSION = "synthetic-calibration-v1"
SEED = 20261022
THRESHOLDS = ("3", "3.5", "4", "5", "6", "8", "10")
DISTRIBUTION_TRIALS = 40
DISTRIBUTION_SIZE = 200
ROLLING_TRIALS = 12
ROLLING_SIZE = 200
SPIKE_SHARE = 0.02
SPIKE_SIZE = 8.0
TARGET_THRESHOLDS = {"0.05": "3", "0.01": "6", "0.005": "8"}
MEASURED = {
    "3": {"normal": "0.003375", "heavy_tailed": "0.044750"},
    "6": {"normal": "0.000000", "heavy_tailed": "0.007875"},
    "8": {"normal": "0.000000", "heavy_tailed": "0.003625"},
}
PLACES = Decimal("0.000001")


def _normal(rng: random.Random) -> float:
    return rng.gauss(0.0, 1.0)


def _heavy(rng: random.Random) -> float:
    return rng.gauss(0.0, 1.0) / sqrt(sum(rng.gauss(0.0, 1.0) ** 2 for _ in range(3)) / 3)


FAMILIES = {"normal": _normal, "heavy_tailed": _heavy}


def _decimal(value: float) -> Decimal:
    return Decimal(f"{value:.4f}")


def _ratio(numerator: int, denominator: int) -> str:
    return format((Decimal(numerator) / Decimal(denominator)).quantize(PLACES), "f")


def _rates(flags: int, nulls: int, hits: int, spikes: int) -> dict[str, str | None]:
    return dict(
        false_alarm_rate=_ratio(flags - hits, nulls),
        recall=_ratio(hits, spikes) if spikes else None,
        precision=_ratio(hits, flags) if spikes and flags else None,
        flagged=str(flags),
        null_records=str(nulls),
        injected=str(spikes),
    )


def _distribution_family(name: str, threshold: str) -> dict[str, dict[str, str | None]]:
    rng = random.Random(f"{SEED}-{name}")
    null_flags = null_count = 0
    flags = hits = nulls = spikes = 0
    for _ in range(DISTRIBUTION_TRIALS):
        clean = [_decimal(FAMILIES[name](rng)) for _ in range(DISTRIBUTION_SIZE)]
        result = detect_distribution([(value, 1) for value in clean], threshold)
        null_flags += result["flagged_records"]
        null_count += len(clean)
        marked = set(rng.sample(range(DISTRIBUTION_SIZE), int(DISTRIBUTION_SIZE * SPIKE_SHARE)))
        injected = [
            value + _decimal(SPIKE_SIZE * rng.choice((-1, 1))) if index in marked else value
            for index, value in enumerate(clean)
        ]
        found = {
            Decimal(item["value"])
            for item in detect_distribution([(value, 1) for value in injected], threshold)[
                "findings"
            ]
        }
        for index, value in enumerate(injected):
            flagged = value in found
            flags += flagged
            hits += flagged and index in marked
        nulls += DISTRIBUTION_SIZE - len(marked)
        spikes += len(marked)
    return dict(
        null=_rates(null_flags, null_count, 0, 0),
        injected=_rates(flags, nulls, hits, spikes),
    )


def _rolling(threshold: str) -> dict[str, str | None]:
    rng = random.Random(f"{SEED}-rolling")
    start = date(2025, 1, 1)
    season, window = 7, 20
    first = season * window
    flags = hits = nulls = spikes = 0
    for _ in range(ROLLING_TRIALS):
        values = [
            10 * sin(2 * pi * index / season) + rng.gauss(0.0, 1.0) for index in range(ROLLING_SIZE)
        ]
        marked = set(rng.sample(range(first, ROLLING_SIZE), 2))
        for index in marked:
            values[index] += SPIKE_SIZE * rng.choice((-1, 1))
        points = tuple(
            TemporalPoint(start + timedelta(days=index), _decimal(value))
            for index, value in enumerate(values)
        )
        result = detect_rolling(
            points,
            RollingRequest("daily", start + timedelta(days=first), window, season, threshold),
        )
        flagged = {date.fromisoformat(item["period"]) for item in result["findings"]}
        labelled = {start + timedelta(days=index) for index in marked}
        flags += len(flagged)
        hits += len(flagged & labelled)
        spikes += len(labelled)
        nulls += ROLLING_SIZE - first - len(labelled)
    return _rates(flags, nulls, hits, spikes)


def calibration_report(thresholds: tuple[str, ...] = THRESHOLDS) -> dict[str, Any]:
    return dict(
        version=CALIBRATION_VERSION,
        seed=SEED,
        design=dict(
            distribution_trials=DISTRIBUTION_TRIALS,
            distribution_size=DISTRIBUTION_SIZE,
            rolling_trials=ROLLING_TRIALS,
            rolling_size=ROLLING_SIZE,
            rolling_reference="20 earlier matching weekly phases",
            spike_share=str(SPIKE_SHARE),
            spike_size_generator_units=str(SPIKE_SIZE),
            families=dict(
                normal="standard normal",
                heavy_tailed="Student t with 3 degrees of freedom",
                seasonal="weekly sine amplitude 10 plus standard normal noise",
            ),
        ),
        thresholds={
            threshold: dict(
                distribution={name: _distribution_family(name, threshold) for name in FAMILIES},
                rolling_seasonal=_rolling(threshold),
            )
            for threshold in thresholds
        },
        limitations=[
            "Synthetic labelled data only; customer data can have other shapes and rates.",
            "Rates are measured frequencies over fixed seeded trials, not guarantees.",
        ],
    )


def calibrated_threshold(target: object) -> str:
    if not isinstance(target, str) or target not in TARGET_THRESHOLDS:
        fail("invalid_detector", "Choose a supported false-alarm target: 0.05, 0.01 or 0.005.")
    return TARGET_THRESHOLDS[target]


def calibration_evidence(target: str) -> dict[str, Any]:
    threshold = calibrated_threshold(target)
    return dict(
        version=CALIBRATION_VERSION,
        seed=SEED,
        target_false_alarm_rate=target,
        threshold=threshold,
        measured_false_alarm_rate=MEASURED[threshold],
        rule="Smallest registered threshold whose measured rate is at most the target "
        "on both synthetic null families.",
        label="Synthetic calibration; not a customer false-alarm guarantee.",
    )
