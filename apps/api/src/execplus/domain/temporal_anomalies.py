"""Use case: Scores later complete calendar periods against earlier seasonal errors.

What it does: Freezes a robust residual reference at an explicit training boundary,
then emits reproducible unusualness evidence without future fitting or probabilities.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from execplus.domain.decision_analysis import checksum, encoded, fail, number, quantile
from execplus.domain.forecasting import next_period

METHOD = "seasonal-residual-mad-iqr-v1"
VERSION = "temporal-anomaly-v1"
MAX_PERIODS = 1200
MIN_TRAINING = {"daily": 28, "monthly": 36}
SEASONS = {"daily": 7, "monthly": 12}
MIN_RESIDUALS = 20
MIN_EVALUATION = 3
MAD_FACTOR = Decimal("0.67448975")


@dataclass(frozen=True)
class TemporalPoint:
    period: date
    actual: Decimal
    complete: bool = True


@dataclass(frozen=True)
class TemporalAnomalyRequest:
    frequency: str
    season_length: int
    training_end: date
    threshold: str = "3.5"
    materiality: str = "0"


def _validate(
    points: tuple[TemporalPoint, ...], request: TemporalAnomalyRequest
) -> tuple[int, Decimal, Decimal]:
    if request.frequency not in SEASONS or (
        type(request.season_length) is not int
        or request.season_length != SEASONS[request.frequency]
    ):
        fail("temporal_season", "Declare a seven-day or twelve-month seasonal cycle.")
    if type(request.training_end) is not date:
        fail("temporal_training", "Choose an explicit calendar training boundary.")
    if not isinstance(request.threshold, str) or not isinstance(request.materiality, str):
        fail("temporal_threshold", "Enter threshold and materiality as exact numerical strings.")
    threshold, materiality = number(request.threshold), number(request.materiality)
    if not Decimal(3) <= threshold <= Decimal(10) or materiality < 0:
        fail("temporal_threshold", "Use threshold 3-10 and nonnegative materiality.")
    if not 1 <= len(points) <= MAX_PERIODS:
        fail("temporal_size", "Use at most 1,200 complete calendar periods.")
    previous = None
    for point in points:
        if not isinstance(point, TemporalPoint) or type(point.period) is not date:
            fail("temporal_period", "Use explicit calendar dates for every observed period.")
        if type(point.complete) is not bool or not point.complete:
            fail("temporal_incomplete", "Every included period must be confirmed complete.")
        if not isinstance(point.actual, Decimal):
            fail("temporal_value", "Observed values must be exact finite decimal amounts.")
        number(point.actual)
        if request.frequency == "monthly" and point.period.day != 1:
            fail("temporal_period", "Monthly periods must start on the first day of the month.")
        if previous is not None:
            consecutive = (
                point.period > previous and next_period(previous, request.frequency) == point.period
            )
            if not consecutive:
                fail(
                    "temporal_gap",
                    "Periods must be ordered, unique and consecutive; gaps are not zero.",
                )
        previous = point.period
    boundaries = [
        index + 1 for index, point in enumerate(points) if point.period == request.training_end
    ]
    if not boundaries:
        fail("temporal_training", "The training boundary must be an included period.")
    count = boundaries[0]
    if count < MIN_TRAINING[request.frequency] or count - request.season_length < MIN_RESIDUALS:
        fail("temporal_training", "Use at least 28 training days or 36 training months.")
    if len(points) - count < MIN_EVALUATION:
        fail("temporal_evaluation", "Keep at least three later periods outside training.")
    return count, threshold, materiality


def _quantile(values: list[Decimal], fraction: str) -> Decimal:
    return quantile([(value, 1) for value in sorted(values)], len(values), Decimal(fraction))


def _score(distance: Decimal, mad: Decimal) -> str | None:
    if not mad:
        return None
    numerator = MAD_FACTOR * distance
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        return encoded(numerator / mad)


def detect_seasonal(
    points: tuple[TemporalPoint, ...], request: TemporalAnomalyRequest
) -> dict[str, Any]:
    training_count, threshold, materiality = _validate(points, request)
    lag = request.season_length
    with localcontext() as context:
        context.prec = 256
        context.rounding = ROUND_HALF_EVEN
        residuals = [
            points[index].actual - points[index - lag].actual
            for index in range(lag, training_count)
        ]
        center = _quantile(residuals, "0.5")
        mad = _quantile([abs(value - center) for value in residuals], "0.5")
        q1, q3 = _quantile(residuals, "0.25"), _quantile(residuals, "0.75")
        iqr = q3 - q1
        scale_method = "mad" if mad else "iqr" if iqr else "constant_reference"
        lower, upper = q1 - threshold * iqr, q3 + threshold * iqr
        history: list[dict[str, Any]] = []
        findings = []
        for index, point in enumerate(points):
            phase = (
                "warmup" if index < lag else "training" if index < training_count else "evaluation"
            )
            row: dict[str, Any] = dict(
                period=point.period.isoformat(),
                actual=encoded(point.actual),
                phase=phase,
                reference_period=None,
                seasonal_reference=None,
                expected=None,
                residual=None,
                absolute_difference=None,
                score=None,
                flagged=None,
            )
            if index >= lag:
                earlier = points[index - lag]
                residual = point.actual - earlier.actual
                distance = abs(residual - center)
                row.update(
                    reference_period=earlier.period.isoformat(),
                    seasonal_reference=encoded(earlier.actual),
                    residual=encoded(residual),
                )
                if phase == "evaluation":
                    unusual = (
                        MAD_FACTOR * distance > threshold * mad
                        if mad
                        else residual < lower or residual > upper
                    )
                    row.update(
                        expected=encoded(earlier.actual + center),
                        absolute_difference=encoded(distance),
                        score=_score(distance, mad),
                        flagged=bool(unusual and distance >= materiality),
                    )
                    if row["flagged"]:
                        findings.append(
                            dict(
                                id=checksum(dict(method=METHOD, period=row["period"]))[:24],
                                period=row["period"],
                                value=row["actual"],
                                count=1,
                                baseline=row["expected"],
                                reference_period=row["reference_period"],
                                seasonal_reference=row["seasonal_reference"],
                                residual=row["residual"],
                                absolute_difference=row["absolute_difference"],
                                score=row["score"],
                            )
                        )
            history.append(row)
    return dict(
        version=VERSION,
        method_version=METHOD,
        method="seasonal_naive_residual",
        frequency=request.frequency,
        season_length=lag,
        threshold=encoded(threshold),
        materiality=encoded(materiality),
        sample_count=len(points),
        training_periods=training_count,
        evaluated_periods=len(points) - training_count,
        flagged_periods=len(findings),
        reference=dict(
            training_start=points[0].period.isoformat(),
            training_end=request.training_end.isoformat(),
            residual_count=len(residuals),
            baseline=encoded(center),
            mad=encoded(mad),
            q1=encoded(q1),
            q3=encoded(q3),
            iqr=encoded(iqr),
            scale_method=scale_method,
            lower_residual_fence=encoded(lower) if not mad else None,
            upper_residual_fence=encoded(upper) if not mad else None,
            mad_factor=encoded(MAD_FACTOR),
            frozen_after_training=True,
        ),
        evaluation=dict(
            kind="chronological_unlabelled_period_scoring",
            labels_supplied=False,
            threshold_selected_on_evaluation=False,
            precision=None,
            recall=None,
            false_alarm_rate=None,
            flag_rate_denominator=len(points) - training_count,
            calibrated=False,
        ),
        history=history,
        findings=findings,
        limitations=[
            "Exploratory unusualness, not proof of an error, fraud or a causal explanation.",
            "The residual center and scale use only periods ending "
            "at the declared training boundary; "
            "later observations never refit the threshold.",
            "Each later seasonal reference uses the already observed value one cycle earlier. "
            "The expected value adds the frozen training residual median.",
            "Training residuals are descriptive fitting evidence, "
            "not held-out alert-quality results.",
            "Later observed periods are scored chronologically, "
            "not predicted before their values exist. "
            "Without independent labels, precision, recall and false-alarm rate are unavailable.",
            "An isolated spike can produce an opposite residual one cycle later. "
            "A sustained change can become the seasonal reference after one cycle.",
            "This method does not model multiple seasonal cycles, holidays, evolving trends, "
            "multivariate effects or distribution drift.",
            "Zero MAD uses IQR fences; zero IQR compares with the constant residual reference. "
            "Such changes have no statistical score.",
            "Scores are approximate 28-digit modified-MAD values, not probabilities. "
            "Flag comparisons use exact cross-products and the declared materiality threshold.",
            "There is no calibrated false-alarm or multiple-testing guarantee. "
            "Thresholds are not automatically tuned using later outcomes or human reviews.",
        ],
    )
