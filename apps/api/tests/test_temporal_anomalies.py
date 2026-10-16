"""Use case: Checks prospective seasonal unusualness independently of its implementation.

What it does: Verifies hand examples, rational reference calculations, chronological
separation, strict boundaries and fixed synthetic detection limits without quality claims.
"""

from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal, localcontext
from fractions import Fraction
from statistics import median

import pytest

from execplus.domain.forecasting import next_period
from execplus.domain.ingestion import IngestionError
from execplus.domain.temporal_anomalies import (
    MAD_FACTOR,
    MAX_PERIODS,
    METHOD,
    TemporalAnomalyRequest,
    TemporalPoint,
    detect_seasonal,
)


def series(values, frequency="daily"):
    period = date(2020, 1, 1)
    result = []
    for value in values:
        result.append(TemporalPoint(period, Decimal(str(value))))
        period = next_period(period, frequency)
    return tuple(result)


def from_residuals(residuals):
    with localcontext() as context:
        context.prec = 256
        values = [Decimal(100)] * 7
        for raw in residuals:
            values.append(values[-7] + Decimal(str(raw)))
    return series(values)


def request(points, training=28, frequency="daily", **changes):
    return TemporalAnomalyRequest(
        frequency, 7 if frequency == "daily" else 12, points[training - 1].period, **changes
    )


def test_hand_calculated_training_reference_and_later_findings():
    points = from_residuals([-2, -1, 0, 1, 2] * 4 + [0] + [0, 6, -6])
    result = detect_seasonal(points, request(points))
    assert result["method_version"] == METHOD
    assert result["reference"] == dict(
        training_start="2020-01-01",
        training_end="2020-01-28",
        residual_count=21,
        baseline="0",
        mad="1",
        q1="-1",
        q3="1",
        iqr="2",
        scale_method="mad",
        lower_residual_fence=None,
        upper_residual_fence=None,
        mad_factor="0.67448975",
        frozen_after_training=True,
    )
    assert [row["residual"] for row in result["history"][-3:]] == ["0", "6", "-6"]
    assert [row["flagged"] for row in result["history"][-3:]] == [False, True, True]
    assert [Decimal(row["score"]) for row in result["history"][-3:]] == [
        Decimal(0),
        Decimal("4.04693850"),
        Decimal("4.04693850"),
    ]
    assert result["training_periods"] == 28 and result["evaluated_periods"] == 3
    assert all(row["flagged"] is None and row["score"] is None for row in result["history"][:28])
    assert [row["period"] for row in result["findings"]] == ["2020-01-30", "2020-01-31"]
    assert all(row["count"] == 1 and len(row["id"]) == 24 for row in result["findings"])
    assert result["evaluation"]["precision"] is None
    assert result["evaluation"]["recall"] is None
    assert result["evaluation"]["false_alarm_rate"] is None
    assert result["evaluation"]["calibrated"] is False


def test_independent_fraction_oracle_for_fifty_residual_populations():
    for seed in range(50):
        multiplier = ((seed + 3) % 16) + 1
        training = [((index * multiplier + seed * seed) % 17) - 8 for index in range(28)]
        later = [seed - 25, 0, 25 - seed]
        points = from_residuals(training + later)
        result = detect_seasonal(points, request(points, training=35))
        center = median(list(map(Fraction, training)))
        scale = median([abs(Fraction(value) - center) for value in training])
        assert scale > 0
        assert Fraction(result["reference"]["baseline"]) == center
        assert Fraction(result["reference"]["mad"]) == scale
        expected = [
            Fraction("0.67448975") * abs(Fraction(value) - center) > Fraction("3.5") * scale
            for value in later
        ]
        assert [row["flagged"] for row in result["history"][-3:]] == expected


def test_strict_mad_boundary_uses_exact_cross_products_and_inclusive_materiality():
    with localcontext() as context:
        context.prec = 256
        training = [
            -2 * MAD_FACTOR,
            -2 * MAD_FACTOR,
            Decimal(0),
            2 * MAD_FACTOR,
            2 * MAD_FACTOR,
        ] * 4 + [Decimal(0)]
        above = Decimal(7) + Decimal("1e-38")
        points = from_residuals([*training, Decimal(7), above, Decimal(-8)])
    result = detect_seasonal(points, request(points, materiality="8"))
    assert [row["flagged"] for row in result["history"][-3:]] == [False, False, True]
    result = detect_seasonal(points, request(points))
    assert [row["flagged"] for row in result["history"][-3:]] == [False, True, True]
    assert Decimal(result["history"][-2]["score"]) == Decimal("3.5")


def test_zero_mad_uses_training_iqr_fences_with_strict_boundaries():
    points = from_residuals([-2] * 6 + [0] * 11 + [2] * 4 + [-9, 7, "7.1"])
    result = detect_seasonal(points, request(points))
    assert result["reference"]["scale_method"] == "iqr"
    assert result["reference"]["lower_residual_fence"] == "-9.0"
    assert result["reference"]["upper_residual_fence"] == "7.0"
    assert [row["flagged"] for row in result["history"][-3:]] == [False, False, True]
    assert all(row["score"] is None for row in result["history"])


def test_zero_spread_flags_declared_changes_without_statistical_score():
    points = from_residuals([0] * 21 + [0, 1, -1])
    result = detect_seasonal(points, request(points))
    assert result["reference"]["scale_method"] == "constant_reference"
    assert [row["flagged"] for row in result["history"][-3:]] == [False, True, True]
    assert all(row["score"] is None for row in result["history"])


@pytest.mark.parametrize("value", ["0", "-5.25", "1.00000000000000000000000000000000000001"])
def test_constant_exact_values_and_caller_decimal_context_do_not_change_result(value):
    points = series([value] * 40)
    expected = detect_seasonal(points, request(points))
    with localcontext() as context:
        context.prec = 4
        context.rounding = ROUND_DOWN
        actual = detect_seasonal(points, request(points))
    assert actual == expected
    assert actual["findings"] == []
    assert all(row["actual"] == value for row in actual["history"])


def test_training_bias_accounts_for_a_constant_linear_change_plus_weekly_cycle():
    points = series([100 + 2 * index + (index % 7) * 20 for index in range(49)])
    result = detect_seasonal(points, request(points))
    assert result["reference"]["baseline"] == "14"
    assert result["findings"] == []
    assert all(row["expected"] == row["actual"] for row in result["history"][28:])


def test_twelve_month_season_handles_real_calendar_boundaries():
    points = series([10 + (index % 12) ** 2 for index in range(48)], "monthly")
    result = detect_seasonal(points, request(points, 36, "monthly"))
    assert result["reference"]["residual_count"] == 24
    assert result["history"][36]["reference_period"] == "2022-01-01"
    assert result["history"][36]["period"] == "2023-01-01"
    assert result["findings"] == []


def test_future_perturbation_and_extension_do_not_refit_or_rewrite_earlier_scores():
    points = series([100 + (index % 7) * 10 + (index % 3) for index in range(70)])
    parameters = request(points, 35)
    original = detect_seasonal(points, parameters)
    changed = (*points[:55], replace(points[55], actual=Decimal("1e37")), *points[56:])
    modified = detect_seasonal(changed, parameters)
    assert modified["reference"] == original["reference"]
    assert modified["history"][:55] == original["history"][:55]
    assert modified["history"][55]["expected"] == original["history"][55]["expected"]
    short = detect_seasonal(points[:50], parameters)
    assert short["reference"] == original["reference"]
    assert short["history"] == original["history"][:50]
    assert all(row["reference_period"] < row["period"] for row in original["history"][7:])


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "unsorted",
        "incomplete",
        "bool_complete",
        "datetime",
        "float",
        "nan",
        "infinity",
    ],
)
def test_invalid_or_incomplete_periods_never_become_zero(mutation):
    points = list(series(range(40)))
    if mutation == "missing":
        del points[10]
    elif mutation == "duplicate":
        points[10] = points[9]
    elif mutation == "unsorted":
        points[10], points[11] = points[11], points[10]
    elif mutation == "incomplete":
        points[10] = replace(points[10], complete=False)
    elif mutation == "bool_complete":
        points[10] = replace(points[10], complete=1)
    elif mutation == "datetime":
        points[10] = replace(points[10], period=datetime(2020, 1, 11))
    elif mutation == "float":
        points[10] = replace(points[10], actual=1.1)
    else:
        points[10] = replace(points[10], actual=Decimal(mutation))
    with pytest.raises(IngestionError):
        detect_seasonal(tuple(points), TemporalAnomalyRequest("daily", 7, date(2020, 1, 28)))


@pytest.mark.parametrize(
    "changes",
    [
        dict(frequency="weekly"),
        dict(season_length=1),
        dict(season_length=True),
        dict(threshold="2"),
        dict(threshold="11"),
        dict(threshold=3.5),
        dict(materiality="-1"),
        dict(materiality=0),
        dict(training_end=date(2019, 12, 31)),
        dict(training_end=date(2020, 1, 27)),
        dict(training_end=date(2020, 2, 8)),
        dict(training_end="2020-01-28"),
    ],
)
def test_invalid_cycles_thresholds_and_training_boundaries_are_explicit(changes):
    points = series(range(40))
    with pytest.raises(IngestionError):
        detect_seasonal(points, replace(request(points), **changes))


def test_monthly_partial_date_and_short_training_are_refused():
    points = series(range(40), "monthly")
    with pytest.raises(IngestionError, match="training"):
        detect_seasonal(points, request(points, 35, "monthly"))
    changed = (replace(points[0], period=date(2020, 1, 2)), *points[1:])
    with pytest.raises(IngestionError, match="first day"):
        detect_seasonal(changed, request(points, 36, "monthly"))


def test_period_cap_is_complete_and_deterministic():
    points = series([0] * MAX_PERIODS)
    result = detect_seasonal(points, request(points))
    assert len(result["history"]) == MAX_PERIODS
    assert result == detect_seasonal(points, request(points))
    with pytest.raises(IngestionError, match="1,200"):
        detect_seasonal(
            (*points, TemporalPoint(points[-1].period + timedelta(days=1), Decimal(0))),
            request(points),
        )


@pytest.mark.parametrize("frequency", ["daily", "monthly"])
def test_unordered_dates_at_calendar_limit_fail_with_a_domain_error(frequency):
    points = series(range(40), frequency)
    edge = date(9999, 12, 31) if frequency == "daily" else date(9999, 12, 1)
    changed = (replace(points[0], period=edge), *points[1:])
    with pytest.raises(IngestionError, match="ordered"):
        detect_seasonal(changed, request(points, frequency=frequency))


@pytest.mark.parametrize(
    "case,expected_flags,true_positive,false_positive,false_negative",
    [
        ("stable_weekly", [], 0, 0, 0),
        ("isolated_with_echo", [28, 35], 1, 1, 0),
        ("persistent_level_shift", list(range(28, 35)), 7, 0, 14),
    ],
)
def test_fixed_synthetic_detection_evaluation_exposes_echo_and_adaptation_limits(
    case, expected_flags, true_positive, false_positive, false_negative
):
    values = [10 + (index % 7) * 20 for index in range(49)]
    labels = set()
    if case == "isolated_with_echo":
        values[28] += 100
        labels = {28}
    elif case == "persistent_level_shift":
        values[28:] = [value + 100 for value in values[28:]]
        labels = set(range(28, 49))
    points = series(values)
    result = detect_seasonal(points, request(points))
    flagged = {index for index, row in enumerate(result["history"]) if row["flagged"]}
    assert flagged == set(expected_flags)
    assert (len(flagged & labels), len(flagged - labels), len(labels - flagged)) == (
        true_positive,
        false_positive,
        false_negative,
    )
    assert result["evaluation"]["threshold_selected_on_evaluation"] is False
    assert result["evaluation"]["false_alarm_rate"] is None
    assert "opposite residual" in " ".join(result["limitations"])
    assert "after one cycle" in " ".join(result["limitations"])
