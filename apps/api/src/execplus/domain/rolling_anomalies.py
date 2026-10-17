"""Use case: Reviews observed periods against strictly earlier comparable periods.

What it does: Retains an exact trailing MAD/IQR reference for every scored period;
seasonal comparisons use matching phases and never fit on current/future values.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from execplus.domain.decision_analysis import checksum, encoded, fail, number
from execplus.domain.forecasting import next_period
from execplus.domain.temporal_anomalies import MAD_FACTOR, TemporalPoint, _quantile, _score

METHOD = "rolling-reference-mad-iqr-v1"
VERSION = "rolling-anomaly-v1"


@dataclass(frozen=True)
class RollingRequest:
    frequency: str
    evaluation_start: date
    reference_window: int = 20
    season_length: int = 1
    threshold: str = "3.5"
    materiality: str = "0"


def detect_rolling(points: tuple[TemporalPoint, ...], request: RollingRequest) -> dict[str, Any]:
    if request.frequency not in {"daily", "monthly"} or (
        type(request.season_length) is not int
        or request.season_length not in {1, 7 if request.frequency == "daily" else 12}
    ):
        fail("rolling_season", "Compare adjacent periods or matching weekly/yearly phases.")
    if type(request.reference_window) is not int or not 20 <= request.reference_window <= 120:
        fail("rolling_window", "Choose 20 to 120 earlier comparable observations.")
    if type(request.evaluation_start) is not date:
        fail("rolling_start", "Choose the first period to evaluate.")
    if not isinstance(request.threshold, str) or not isinstance(request.materiality, str):
        fail("rolling_threshold", "Enter exact numerical strings for threshold and materiality.")
    threshold, materiality = number(request.threshold), number(request.materiality)
    if not Decimal(3) <= threshold <= Decimal(10) or materiality < 0:
        fail("rolling_threshold", "Use threshold 3-10 and nonnegative materiality.")
    if not 1 <= len(points) <= 1200:
        fail("rolling_size", "Use at most 1,200 complete consecutive periods.")
    previous = None
    for point in points:
        if not isinstance(point, TemporalPoint) or type(point.period) is not date:
            fail("rolling_period", "Every period needs an explicit calendar date.")
        if point.complete is not True or not isinstance(point.actual, Decimal):
            fail("rolling_incomplete", "Use complete exact observations; missing is not zero.")
        number(point.actual)
        if request.frequency == "monthly" and point.period.day != 1:
            fail("rolling_period", "Monthly periods start on the first day of the month.")
        if previous is not None and (
            point.period <= previous or next_period(previous, request.frequency) != point.period
        ):
            fail("rolling_gap", "Periods must be ordered, unique and consecutive.")
        previous = point.period
    starts = [i for i, p in enumerate(points) if p.period == request.evaluation_start]
    if not starts or starts[0] < request.reference_window * request.season_length:
        fail("rolling_start", "Keep the full earlier reference window before evaluation starts.")
    start = starts[0]
    if len(points) - start < 3:
        fail("rolling_evaluation", "Keep at least three evaluation periods.")
    history, findings = [], []
    with localcontext() as context:
        context.prec = 256
        context.rounding = ROUND_HALF_EVEN
        for index, point in enumerate(points):
            row: dict[str, Any] = dict(
                period=point.period.isoformat(),
                actual=encoded(point.actual),
                phase="reference" if index < start else "evaluation",
                expected=None,
                absolute_difference=None,
                score=None,
                flagged=None,
                reference=None,
            )
            if index >= start:
                reference = [
                    points[index - k * request.season_length]
                    for k in range(request.reference_window, 0, -1)
                ]
                values = [p.actual for p in reference]
                center = _quantile(values, "0.5")
                mad = _quantile([abs(v - center) for v in values], "0.5")
                q1, q3 = _quantile(values, "0.25"), _quantile(values, "0.75")
                iqr = q3 - q1
                lower, upper = q1 - threshold * iqr, q3 + threshold * iqr
                distance = abs(point.actual - center)
                unusual = (
                    MAD_FACTOR * distance > threshold * mad
                    if mad
                    else point.actual < lower or point.actual > upper
                )
                row.update(
                    expected=encoded(center),
                    absolute_difference=encoded(distance),
                    score=_score(distance, mad),
                    flagged=bool(unusual and distance >= materiality),
                    reference=dict(
                        start=reference[0].period.isoformat(),
                        end=reference[-1].period.isoformat(),
                        count=len(reference),
                        step=request.season_length,
                        median=encoded(center),
                        mad=encoded(mad),
                        q1=encoded(q1),
                        q3=encoded(q3),
                        iqr=encoded(iqr),
                        scale_method="mad" if mad else "iqr" if iqr else "constant_reference",
                        lower_fence=encoded(lower) if not mad else None,
                        upper_fence=encoded(upper) if not mad else None,
                    ),
                )
                if row["flagged"]:
                    findings.append(
                        dict(
                            id=checksum(dict(method=METHOD, period=row["period"]))[:24],
                            period=row["period"],
                            value=row["actual"],
                            count=1,
                            baseline=row["expected"],
                            absolute_difference=row["absolute_difference"],
                            score=row["score"],
                            reference=row["reference"],
                        )
                    )
            history.append(row)
    return dict(
        version=VERSION,
        method_version=METHOD,
        frequency=request.frequency,
        reference_window=request.reference_window,
        season_length=request.season_length,
        evaluation_start=request.evaluation_start.isoformat(),
        threshold=encoded(threshold),
        materiality=encoded(materiality),
        sample_count=len(points),
        evaluated_periods=len(points) - start,
        flagged_periods=len(findings),
        history=history,
        findings=findings,
        evaluation=dict(
            labels_supplied=False,
            precision=None,
            recall=None,
            calibrated=False,
            current_or_future_fitting=False,
        ),
        limitations=[
            "Flags identify unusual observations, not proven errors, fraud or causes.",
            "Each reference uses only earlier observations; seasonal mode uses matching phases.",
            "Earlier flagged values remain in later windows. Repeated changes can "
            "move the reference and hide later unusual values.",
            "The current value never sets its own reference. These are observed "
            "comparisons, not forecasts.",
            "MAD comparisons use exact cross-products. Zero MAD uses IQR fences; "
            "a constant reference has no statistical score.",
            "Scores are rounded to 28 digits, not probabilities. No calibrated "
            "false-alarm or multiple-testing guarantee exists.",
            "Without independent labels, precision and recall are unknown. "
            "Reviews do not automatically retune thresholds.",
        ],
    )
