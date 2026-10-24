"""Use case: Measures false-alarm rates of the grouped, seasonal and rolling detectors.

What it does: Runs the production detectors on seeded synthetic series with no
injected changes, maps a requested false-alarm target to a fixed measured
threshold per detector and returns the calibration evidence stored with results.
Synthetic calibration is not customer calibration.
"""

import random
from datetime import date, timedelta
from decimal import Decimal
from math import pi, sin
from typing import Any

from execplus.domain.analysis_extensions import detect_segments
from execplus.domain.anomaly_calibration import FAMILIES, SPIKE_SIZE, THRESHOLDS, _decimal, _rates
from execplus.domain.decision_analysis import fail
from execplus.domain.rolling_anomalies import RollingRequest, detect_rolling
from execplus.domain.temporal_anomalies import (
    TemporalAnomalyRequest,
    TemporalPoint,
    detect_seasonal,
)

SEGMENT_CALIBRATED_METHOD = "segmented-mad-iqr-calibrated-v1"
SEASONAL_CALIBRATED_METHOD = "seasonal-residual-mad-iqr-calibrated-v1"
ROLLING_CALIBRATED_METHOD = "rolling-reference-mad-iqr-calibrated-v1"
VERSION = "synthetic-detector-calibration-v1"
SEED = 20261024
GROUP_SIZES = (10, 25, 50, 100)
GROUP_TRIALS = 40
CALENDAR_TRIALS = 30
CALENDAR_SIZE = 200
CALENDAR_TRAINING = 140
TARGETS = ("0.05", "0.01", "0.005")
TARGET_THRESHOLDS = {
    "grouped": {"0.05": "3", "0.01": "6", "0.005": "8"},
    "seasonal": {"0.05": "3", "0.01": "5", "0.005": "6"},
    "rolling": {"0.05": "3.5", "0.01": "8", "0.005": "8"},
}
MEASURED = {
    "grouped": {
        "3": {"normal": "0.007830", "heavy_tailed": "0.049189"},
        "6": {"normal": "0.000275", "heavy_tailed": "0.007838"},
        "8": {"normal": "0.000137", "heavy_tailed": "0.003649"},
    },
    "seasonal": {
        "3": {"normal": "0.007778", "heavy_tailed": "0.022222"},
        "5": {"normal": "0.000000", "heavy_tailed": "0.007222"},
        "6": {"normal": "0.000000", "heavy_tailed": "0.005000"},
    },
    "rolling": {
        "3.5": {"normal": "0.008889", "heavy_tailed": "0.045556"},
        "8": {"normal": "0.000000", "heavy_tailed": "0.005000"},
    },
}


def _grouped(name: str, threshold: str) -> dict[str, str | None]:
    rng = random.Random(f"{SEED}-grouped-{name}")
    flags = records = hits = spikes = 0
    for _ in range(GROUP_TRIALS):
        rows: list[tuple[object, object, object]] = []
        marked: set[tuple[str, Decimal]] = set()
        for index, size in enumerate(GROUP_SIZES):
            label, center, scale = f"g{index}", 100 * (index + 1), index + 1
            for position in range(size):
                value = _decimal(center + scale * FAMILIES[name](rng))
                if name == "normal" and position == 0 and size >= 25:
                    value += _decimal(scale * SPIKE_SIZE * rng.choice((-1, 1)))
                    marked.add((label, value))
                rows.append((label, value, 1))
        result = detect_segments(rows, threshold, "0", 8)
        found = {(item["segment"], Decimal(item["value"])) for item in result["findings"]}
        hit = len(found & marked)
        flags += sum(item["count"] for item in result["findings"])
        hits += hit
        spikes += len(marked)
        records += len(rows) - len(marked)
    return _rates(flags, records, hits, spikes)


def _calendar(detector: str, name: str, threshold: str) -> dict[str, str | None]:
    rng = random.Random(f"{SEED}-{detector}-{name}")
    start = date(2025, 1, 1)
    flags = periods = 0
    for _ in range(CALENDAR_TRIALS):
        points = tuple(
            TemporalPoint(
                start + timedelta(days=index),
                _decimal(10 * sin(2 * pi * index / 7) + FAMILIES[name](rng)),
            )
            for index in range(CALENDAR_SIZE)
        )
        result = (
            detect_seasonal(
                points,
                TemporalAnomalyRequest("daily", 7, points[CALENDAR_TRAINING - 1].period, threshold),
            )
            if detector == "seasonal"
            else detect_rolling(
                points, RollingRequest("daily", points[CALENDAR_TRAINING].period, 20, 7, threshold)
            )
        )
        flags += result["flagged_periods"]
        periods += result["evaluated_periods"]
    return _rates(flags, periods, 0, 0)


def detector_calibration_report(thresholds: tuple[str, ...] = THRESHOLDS) -> dict[str, Any]:
    return dict(
        version=VERSION,
        seed=SEED,
        design=dict(
            grouped=dict(
                trials=GROUP_TRIALS,
                group_sizes=list(GROUP_SIZES),
                groups="centers 100/200/300/400 with scales 1/2/3/4; minimum support 8",
                injected="normal family only: one spike of 8 scale units per group of 25+",
            ),
            calendar=dict(
                trials=CALENDAR_TRIALS,
                periods=CALENDAR_SIZE,
                seasonal_training_periods=CALENDAR_TRAINING,
                rolling_reference="20 earlier matching weekly phases",
                series="weekly sine amplitude 10 plus family noise; no injected changes",
            ),
            families=dict(
                normal="standard normal", heavy_tailed="Student t with 3 degrees of freedom"
            ),
        ),
        thresholds={
            threshold: dict(
                grouped={name: _grouped(name, threshold) for name in FAMILIES},
                seasonal={name: _calendar("seasonal", name, threshold) for name in FAMILIES},
                rolling={name: _calendar("rolling", name, threshold) for name in FAMILIES},
            )
            for threshold in thresholds
        },
        rule="Smallest registered threshold whose measured false-alarm rate is at most "
        "the target on both synthetic families for that detector.",
        limitations=[
            "Synthetic data only; customer data can have other shapes and rates.",
            "Rates are measured frequencies over fixed seeded trials, not guarantees.",
            "Calendar rates count flagged evaluation periods in unchanged synthetic series.",
        ],
    )


def detector_threshold(detector: str, target: object) -> str:
    supported = TARGET_THRESHOLDS[detector]
    if not isinstance(target, str) or target not in supported:
        fail(
            "invalid_detector",
            "Choose a supported false-alarm target for this detector: "
            + ", ".join(supported)
            + ".",
        )
    return supported[target]


def detector_evidence(detector: str, target: str) -> dict[str, Any]:
    threshold = detector_threshold(detector, target)
    return dict(
        version=VERSION,
        seed=SEED,
        detector=detector,
        target_false_alarm_rate=target,
        threshold=threshold,
        measured_false_alarm_rate=MEASURED[detector][threshold],
        rule="Smallest registered threshold whose measured rate is at most the target "
        "on both synthetic families for this detector.",
        label="Synthetic calibration; not a customer false-alarm guarantee.",
    )
