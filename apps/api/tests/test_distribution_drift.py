"""Use case: Checks exact two-window distances independently of their computation.

What it does: Uses hand calculations and quantile-coupling oracles to test coverage,
strict review thresholds, rational evidence and explicit descriptive limitations.
"""

from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal, localcontext
from fractions import Fraction

import pytest

from execplus.domain.distribution_drift import DriftRequest, compare_drift
from execplus.domain.forecasting import next_period
from execplus.domain.ingestion import IngestionError
from execplus.domain.temporal_anomalies import TemporalPoint


def periods(values, start=date(2020, 1, 1), frequency="daily"):
    result = []
    for value in values:
        result.append(TemporalPoint(start, Decimal(str(value))))
        start = next_period(start, frequency)
    return tuple(result)


def compare(first, second, separation="0.2", materiality="0"):
    return compare_drift(
        periods(first),
        periods(second, date(2024, 1, 1)),
        DriftRequest("daily", separation, materiality),
    )


def fraction(value):
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def test_hand_calculated_two_point_distributions_keep_exact_evidence():
    result = compare([0] * 4 + [2] * 4, [1] * 4 + [3] * 4)
    assert fraction(result["maximum_cdf_separation"]) == Fraction(1, 2)
    assert fraction(result["wasserstein_distance"]) == 1
    assert result["median_change"] == "1.0"
    assert result["separation_location"] == "0"
    assert result["separation_direction"] == "reference_cdf_larger"
    assert result["review_flag"] is True
    assert len(result["findings"]) == 1
    assert [item["value"] for item in result["distribution"]] == ["0", "1", "2", "3"]
    assert [fraction(item["distance_contribution"]) for item in result["distribution"]] == [
        Fraction(1, 2),
        0,
        Fraction(1, 2),
        0,
    ]
    assert len(result["observations"]) == 16
    assert result["evaluation"]["p_value"] is None
    assert result["evaluation"]["false_alarm_rate"] is None


def test_fifty_independent_quantile_coupling_oracles_include_unequal_sample_sizes():
    for seed in range(50):
        first = [((i * (seed + 3)) % 11) - 5 for i in range(8 + seed % 5)]
        second = [((i * (seed + 5)) % 13) - 4 for i in range(8 + (seed * 3) % 5)]
        result = compare(first, second)
        left, right = sorted(first), sorted(second)
        n, m = len(left), len(right)
        expected_wasserstein = Fraction(
            sum(abs(left[i // m] - right[i // n]) for i in range(n * m)), n * m
        )
        expected_ks = max(
            abs(
                Fraction(sum(x <= value for x in left), n)
                - Fraction(sum(x <= value for x in right), m)
            )
            for value in set(left + right)
        )
        assert fraction(result["wasserstein_distance"]) == expected_wasserstein
        assert fraction(result["maximum_cdf_separation"]) == expected_ks


def test_repeating_decimal_is_not_presented_as_an_exact_decimal():
    result = compare([0] * 8, [0] * 8 + [3], separation="0")
    distance = result["wasserstein_distance"]
    assert distance == dict(
        numerator="1",
        denominator="3",
        display="0.3333333333333333333333333333",
        display_exact=False,
    )
    assert fraction(result["maximum_cdf_separation"]) == Fraction(1, 9)
    assert result["maximum_cdf_separation"]["display_exact"] is False
    assert result["review_flag"] is True


def test_strict_cdf_threshold_and_inclusive_exact_materiality():
    first, second = [0] * 4 + [2] * 4, [1] * 4 + [3] * 4
    assert compare(first, second, separation="0.5")["review_flag"] is False
    assert compare(first, second, separation="0.499", materiality="1")["review_flag"] is True
    assert (
        compare(
            first,
            second,
            separation="0.499",
            materiality="1.00000000000000000000000000000000000001",
        )["review_flag"]
        is False
    )


@pytest.mark.parametrize("values", [[0] * 8, [-5] * 8, list(range(8)), [0, 0, 0, 2, 2, 3, 3, 3]])
def test_order_changes_with_identical_distributions_are_not_drift(values):
    result = compare(values, list(reversed(values)), separation="0")
    assert fraction(result["maximum_cdf_separation"]) == 0
    assert fraction(result["wasserstein_distance"]) == 0
    assert result["review_flag"] is False and result["findings"] == []
    assert "time order" in " ".join(result["limitations"])


def test_variance_change_with_unchanged_median_remains_visible():
    result = compare([-1] * 4 + [1] * 4, [-3] * 4 + [3] * 4)
    assert result["median_change"] == "0.0"
    assert fraction(result["wasserstein_distance"]) == 2
    assert fraction(result["maximum_cdf_separation"]) == Fraction(1, 2)
    assert result["review_flag"] is True


def test_high_precision_negative_values_and_callers_decimal_context_do_not_round_evidence():
    first = ["-1.00000000000000000000000000000000000001"] * 8
    second = ["-1.00000000000000000000000000000000000002"] * 8
    expected = compare(first, second)
    assert fraction(expected["wasserstein_distance"]) == Fraction(1, 10**38)
    assert expected["wasserstein_distance"]["display_exact"] is True
    assert [point["value"] for point in expected["observations"][:8]] == first
    with localcontext() as context:
        context.prec = 4
        context.rounding = ROUND_DOWN
        actual = compare(first, second)
    assert actual == expected


def test_monthly_windows_can_have_a_declared_gap_between_them():
    reference = periods(range(12), frequency="monthly")
    comparison = periods(range(12), date(2024, 1, 1), "monthly")
    result = compare_drift(reference, comparison, DriftRequest("monthly", "0.2", "0"))
    assert result["windows"]["reference"]["end"] == "2020-12-01"
    assert result["windows"]["comparison"]["start"] == "2024-01-01"
    assert result["review_flag"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "short",
        "gap",
        "duplicate",
        "order",
        "incomplete",
        "complete_integer",
        "float",
        "nan",
        "datetime",
        "overlap",
    ],
)
def test_bad_or_incomplete_windows_are_refused_instead_of_filled(mutation):
    reference = list(periods(range(10)))
    comparison = periods(range(10), date(2024, 1, 1))
    if mutation == "empty":
        reference = []
    elif mutation == "short":
        reference = reference[:7]
    elif mutation == "gap":
        del reference[4]
    elif mutation == "duplicate":
        reference[4] = reference[3]
    elif mutation == "order":
        reference.reverse()
    elif mutation in {"incomplete", "complete_integer"}:
        reference[4] = replace(reference[4], complete=False if mutation == "incomplete" else 1)
    elif mutation == "float":
        reference[4] = replace(reference[4], actual=1.5)
    elif mutation == "nan":
        reference[4] = replace(reference[4], actual=Decimal("NaN"))
    elif mutation == "datetime":
        reference[4] = replace(reference[4], period=datetime(2020, 1, 5))
    else:
        comparison = tuple(reference)
    with pytest.raises(IngestionError):
        compare_drift(tuple(reference), comparison, DriftRequest("daily", "0.2", "0"))


@pytest.mark.parametrize(
    "parameters",
    [
        DriftRequest("weekly", "0.2", "0"),
        DriftRequest("daily", "-0.1", "0"),
        DriftRequest("daily", "1.01", "0"),
        DriftRequest("daily", "0.2", "-1"),
        DriftRequest("daily", 0.2, "0"),
        DriftRequest("daily", "0.2", 0),
    ],
)
def test_invalid_review_rules_are_explicit(parameters):
    with pytest.raises(IngestionError):
        compare_drift(periods(range(8)), periods(range(8), date(2024, 1, 1)), parameters)


def test_complete_workload_cap_and_fraction_sums_are_bounded():
    reference = periods([0] * 600)
    comparison = periods([1] * 600, date(2024, 1, 1))
    result = compare_drift(reference, comparison, DriftRequest("daily", "0", "0"))
    assert len(result["observations"]) == 1200
    assert fraction(result["wasserstein_distance"]) == 1
    more = (*comparison, TemporalPoint(comparison[-1].period + timedelta(days=1), Decimal(1)))
    with pytest.raises(IngestionError, match="1,200"):
        compare_drift(reference, more, DriftRequest("daily", "0", "0"))
