"""Use case: Defines source windows and method dispatch for calendar anomaly evidence.

What it does: Keeps explicit seasonal and distribution-comparison requests separate
from the existing snapshot detector and reuses governed complete calendar series.
"""

from datetime import date
from typing import Any

from execplus.domain.decision_analysis import fail
from execplus.domain.detector_calibration import (
    ROLLING_CALIBRATED_METHOD,
    SEASONAL_CALIBRATED_METHOD,
    detector_evidence,
    detector_threshold,
)
from execplus.domain.distribution_drift import METHOD as DRIFT_METHOD
from execplus.domain.distribution_drift import DriftRequest, compare_drift
from execplus.domain.forecast_series import coverage, series_values
from execplus.domain.models import QueryResult
from execplus.domain.rolling_anomalies import METHOD as ROLLING_METHOD
from execplus.domain.rolling_anomalies import RollingRequest, detect_rolling
from execplus.domain.temporal_anomalies import METHOD as SEASONAL_METHOD
from execplus.domain.temporal_anomalies import (
    TemporalAnomalyRequest,
    TemporalPoint,
    detect_seasonal,
)

CALIBRATED_CALENDAR = {
    SEASONAL_CALIBRATED_METHOD: (SEASONAL_METHOD, "seasonal"),
    ROLLING_CALIBRATED_METHOD: (ROLLING_METHOD, "rolling"),
}
CALENDAR_METHODS = frozenset({SEASONAL_METHOD, DRIFT_METHOD, ROLLING_METHOD, *CALIBRATED_CALENDAR})


def is_calendar_anomaly(raw: dict[str, Any]) -> bool:
    return raw.get("kind") == "robust_distribution" and raw.get("model") in CALENDAR_METHODS


def calendar_windows(raw: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if not is_calendar_anomaly(raw) or raw.get("aggregation") not in {"sum", "avg"}:
        fail("calendar_method", "Choose a supported calendar method and total or average.")
    windows: tuple[dict[str, Any], ...]
    if raw.get("model") in {SEASONAL_METHOD, ROLLING_METHOD, *CALIBRATED_CALENDAR}:
        windows = (dict(raw),)
    else:
        windows = tuple(
            {
                **raw,
                "coverage_start": raw.get(f"{name}_start"),
                "coverage_end": raw.get(f"{name}_end"),
            }
            for name in ("reference", "comparison")
        )
    boundaries = tuple(coverage(window) for window in windows)
    if len(boundaries) == 2 and boundaries[0][1] >= boundaries[1][0]:
        fail("drift_overlap", "The comparison window must start after the reference window ends.")
    total = sum(
        (end - start).days + 1
        if raw["frequency"] == "daily"
        else (end.year - start.year) * 12 + end.month - start.month + 1
        for start, end in boundaries
    )
    if total > 1200:
        fail("calendar_size", "Use at most 1,200 complete periods across the selected windows.")
    return windows


def calculate_calendar(raw: dict[str, Any], results: list[list[QueryResult]]) -> dict[str, Any]:
    if raw.get("model") in CALIBRATED_CALENDAR:
        base, detector = CALIBRATED_CALENDAR[raw["model"]]
        target = raw.get("target_false_alarm_rate")
        if raw.get("threshold") != "3.5":
            fail("invalid_detector", "A false-alarm target sets the threshold.")
        threshold = detector_threshold(detector, target)
        return _calendar(raw | dict(model=base, threshold=threshold), results) | dict(
            method_version=raw["model"], calibration=detector_evidence(detector, str(target))
        )
    return _calendar(raw, results)


def _calendar(raw: dict[str, Any], results: list[list[QueryResult]]) -> dict[str, Any]:
    windows = calendar_windows(raw)
    if len(results) != len(windows):
        fail("calendar_evidence", "Each selected window needs complete calendar evidence.")
    points = [
        tuple(TemporalPoint(period, value) for period, value in series_values(values, window))
        for window, values in zip(windows, results, strict=True)
    ]
    if raw["model"] == ROLLING_METHOD:
        try:
            start = date.fromisoformat(raw["evaluation_start"])
        except (KeyError, TypeError, ValueError):
            fail("rolling_start", "Choose an explicit first evaluation period.")
        return detect_rolling(
            points[0],
            RollingRequest(
                raw["frequency"],
                start,
                raw["reference_window"],
                raw["season_length"],
                raw["threshold"],
                raw["materiality"],
            ),
        )
    if raw["model"] == SEASONAL_METHOD:
        try:
            training_end = date.fromisoformat(raw["training_end"])
        except (KeyError, TypeError, ValueError):
            fail("temporal_training", "Choose an explicit calendar training boundary.")
        return detect_seasonal(
            points[0],
            TemporalAnomalyRequest(
                raw["frequency"],
                raw["season_length"],
                training_end,
                raw["threshold"],
                raw["materiality"],
            ),
        )
    return compare_drift(
        points[0],
        points[1],
        DriftRequest(raw["frequency"], raw["minimum_cdf_separation"], raw["materiality"]),
    )
