"""Use case: Compares observed measure distributions in two explicit calendar windows.

What it does: Preserves exact empirical distances and covered periods without
statistical significance, individual anomaly labels or inferred causal effects.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from typing import Any

from execplus.domain.decision_analysis import checksum, encoded, fail, number, quantile
from execplus.domain.forecasting import next_period
from execplus.domain.temporal_anomalies import MAX_PERIODS, TemporalPoint

METHOD = "empirical-window-distance-v1"
CALIBRATED_METHOD = "empirical-window-distance-calibrated-v1"
VERSION = "calendar-distribution-drift-v1"
MIN_WINDOW = 8


@dataclass(frozen=True)
class DriftRequest:
    frequency: str
    minimum_cdf_separation: str
    materiality: str


def _fraction(value: Fraction) -> dict[str, Any]:
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        twos += 1
        denominator //= 2
    while denominator % 5 == 0:
        fives += 1
        denominator //= 5
    exact = denominator == 1
    with localcontext() as context:
        context.prec = (
            max(256, len(str(abs(value.numerator))) + max(twos, fives) + 2) if exact else 28
        )
        context.rounding = ROUND_HALF_EVEN
        display = encoded(Decimal(value.numerator) / Decimal(value.denominator))
    return dict(
        numerator=str(value.numerator),
        denominator=str(value.denominator),
        display=display,
        display_exact=exact,
    )


def _window(points: tuple[TemporalPoint, ...], frequency: str) -> dict[str, Any]:
    if len(points) < MIN_WINDOW:
        fail("drift_window_size", "Use at least eight complete periods in each window.")
    previous = None
    for point in points:
        if not isinstance(point, TemporalPoint) or type(point.period) is not date:
            fail("drift_period", "Choose explicit calendar periods for both windows.")
        if point.complete is not True or not isinstance(point.actual, Decimal):
            fail("drift_incomplete", "Use complete periods with exact decimal values.")
        number(point.actual)
        if frequency == "monthly" and point.period.day != 1:
            fail("drift_period", "Monthly periods must start on the first day of the month.")
        if previous is not None and (
            point.period <= previous or next_period(previous, frequency) != point.period
        ):
            fail("drift_gap", "Each window must contain ordered, consecutive complete periods.")
        previous = point.period
    values = sorted((value, count) for value, count in Counter(p.actual for p in points).items())
    return dict(
        start=points[0].period.isoformat(),
        end=points[-1].period.isoformat(),
        count=len(points),
        distinct_count=len(values),
        minimum=encoded(values[0][0]),
        maximum=encoded(values[-1][0]),
        median=encoded(quantile(values, len(points), Decimal("0.5"))),
        q1=encoded(quantile(values, len(points), Decimal("0.25"))),
        q3=encoded(quantile(values, len(points), Decimal("0.75"))),
    )


def compare_drift(
    reference: tuple[TemporalPoint, ...],
    comparison: tuple[TemporalPoint, ...],
    request: DriftRequest,
) -> dict[str, Any]:
    if request.frequency not in {"daily", "monthly"}:
        fail("drift_frequency", "Choose daily or monthly observed periods.")
    if len(reference) + len(comparison) > MAX_PERIODS:
        fail("drift_size", "Use at most 1,200 complete periods across both windows.")
    if not isinstance(request.minimum_cdf_separation, str) or not isinstance(
        request.materiality, str
    ):
        fail("drift_threshold", "Enter the review thresholds as exact numerical strings.")
    separation = number(request.minimum_cdf_separation)
    materiality = number(request.materiality)
    if not 0 <= separation <= 1 or materiality < 0:
        fail(
            "drift_threshold",
            "Use a distribution separation from 0 to 1 and nonnegative materiality.",
        )
    with localcontext() as context:
        context.prec = 256
        context.rounding = ROUND_HALF_EVEN
        summaries = dict(
            reference=_window(reference, request.frequency),
            comparison=_window(comparison, request.frequency),
        )
        if reference[-1].period >= comparison[0].period:
            fail(
                "drift_overlap", "The comparison window must start after the reference window ends."
            )
        reference_counts = Counter(point.actual for point in reference)
        comparison_counts = Counter(point.actual for point in comparison)
        support = sorted(set(reference_counts) | set(comparison_counts))
        reference_cumulative = comparison_cumulative = 0
        maximum = distance = Fraction(0)
        location = support[0]
        direction = "equal"
        distribution = []
        for index, value in enumerate(support):
            reference_cumulative += reference_counts[value]
            comparison_cumulative += comparison_counts[value]
            reference_cdf = Fraction(reference_cumulative, len(reference))
            comparison_cdf = Fraction(comparison_cumulative, len(comparison))
            gap = abs(reference_cdf - comparison_cdf)
            if gap > maximum:
                maximum, location = gap, value
                direction = (
                    "reference_cdf_larger"
                    if reference_cdf > comparison_cdf
                    else "comparison_cdf_larger"
                )
            next_value = support[index + 1] if index + 1 < len(support) else None
            area = gap * Fraction(next_value - value) if next_value is not None else Fraction(0)
            distance += area
            distribution.append(
                dict(
                    value=encoded(value),
                    reference_count=reference_counts[value],
                    comparison_count=comparison_counts[value],
                    reference_cumulative=reference_cumulative,
                    comparison_cumulative=comparison_cumulative,
                    reference_cdf=_fraction(reference_cdf),
                    comparison_cdf=_fraction(comparison_cdf),
                    absolute_cdf_difference=_fraction(gap),
                    next_value=encoded(next_value) if next_value is not None else None,
                    distance_contribution=_fraction(area),
                )
            )
        flagged = (
            maximum > Fraction(separation) and distance > 0 and distance >= Fraction(materiality)
        )
        median_change = Decimal(summaries["comparison"]["median"]) - Decimal(
            summaries["reference"]["median"]
        )
    return dict(
        version=VERSION,
        method_version=METHOD,
        frequency=request.frequency,
        windows=summaries,
        minimum_cdf_separation=encoded(separation),
        materiality=encoded(materiality),
        maximum_cdf_separation=_fraction(maximum),
        separation_location=encoded(location),
        separation_direction=direction,
        wasserstein_distance=_fraction(distance),
        median_change=encoded(median_change),
        review_flag=flagged,
        findings=[
            dict(
                id=checksum(dict(method=METHOD, windows=summaries))[:24],
                kind="window_distribution_change",
            )
        ]
        if flagged
        else [],
        distribution=distribution,
        observations=[
            dict(window=name, period=point.period.isoformat(), value=encoded(point.actual))
            for name, points in (("reference", reference), ("comparison", comparison))
            for point in points
        ],
        evaluation=dict(
            kind="descriptive_two_window_comparison",
            calibrated=False,
            p_value=None,
            false_alarm_rate=None,
            thresholds_selected_automatically=False,
        ),
        limitations=[
            "This compares distributions of observed period totals or averages, "
            "not individual records.",
            "The windows must use the same confirmed measure, unit, aggregation "
            "and governed population.",
            "A distribution change is not a causal explanation or proof of bad data.",
            "Seasonality, a different mix of weekdays, holidays or population composition "
            "can change these distances.",
            "The chosen windows and thresholds are explicit review rules, "
            "not a statistical significance test.",
            "No calibrated false-alarm rate, confidence level "
            "or automatic refresh monitoring is supplied.",
            "Exact numerators and denominators are retained; "
            "nonterminating decimal displays are rounded to 28 significant digits.",
            "Equal distributions can hide changes in time order or individual records. "
            "This is not a trend or row-level anomaly detector.",
        ],
    )
