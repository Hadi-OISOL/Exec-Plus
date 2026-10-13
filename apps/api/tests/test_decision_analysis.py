"""Use case: Independently verifies anomaly statistics and bounded decision outcomes.

What it does: Covers exact weighted references, exhaustive allocation, assumptions and refusals.
"""

import itertools
import random
import statistics
from collections import Counter
from decimal import Decimal

import pytest

from execplus.domain.decision_analysis import allocate, detect_distribution, number
from execplus.domain.ingestion import IngestionError


def weighted(values):
    return list(Counter(Decimal(str(value)) for value in values).items())


def test_weighted_distribution_matches_independent_expanded_statistics():
    values = [Decimal(value) for value in ["1.1", "1.1", "1.2", "1.3", "1.3", "1.4", "1.5", "90"]]
    result = detect_distribution(weighted(values))
    median = statistics.median(values)
    assert Decimal(result["baseline"]) == median
    assert Decimal(result["mad"]) == statistics.median(abs(x - median) for x in values)
    quartiles = statistics.quantiles(values, method="inclusive")
    assert Decimal(result["iqr"]) == quartiles[2] - quartiles[0]
    assert result["flagged_records"] == 1
    assert result["findings"][0]["value"] == "90"
    assert "not probabilities" in " ".join(result["limitations"])


def test_degenerate_central_reference_does_not_divide_by_zero():
    result = detect_distribution([(Decimal("0"), 19), (Decimal("100"), 1)])
    assert result["method"] == "constant_reference"
    assert result["findings"][0]["score"] is None
    assert result["flagged_records"] == 1
    assert detect_distribution([(Decimal("0"), 20)])["findings"] == []


def test_iqr_fallback_and_materiality_are_explicit():
    values = [0, 0, 0, 0, 0, 1, 2, 50]
    result = detect_distribution(weighted(values))
    assert result["method"] == "iqr"
    assert result["findings"][0]["value"] == "50"
    assert detect_distribution(weighted(values), materiality="51")["findings"] == []


def test_counts_and_duplicate_values_do_not_change_weighted_result():
    first = detect_distribution([(1, 10), (2, 10), (100, 2)])
    second = detect_distribution([(100, 1), (2, 10), (1, 10), (100, 1)])
    assert first == second


@pytest.mark.parametrize(
    "value", [None, True, "NaN", "Infinity", "-Infinity", "1e38", "1e-39", "text"]
)
def test_invalid_numbers_are_refused(value):
    with pytest.raises(IngestionError):
        number(value)


@pytest.mark.parametrize("rows", [[], [(1, 7)], [(1, True)], [(None, 10)], [(1, 200001)]])
def test_invalid_distribution_or_insufficient_population_is_refused(rows):
    with pytest.raises(IngestionError):
        detect_distribution(rows)


@pytest.mark.parametrize("threshold,materiality", [("2", "0"), ("11", "0"), ("3.5", "-1")])
def test_detector_parameters_are_bounded(threshold, materiality):
    with pytest.raises(IngestionError):
        detect_distribution([(1, 10)], threshold, materiality)


def test_allocation_matches_exhaustive_small_problem_search():
    generator = random.Random(410)
    for _ in range(30):
        rows = [
            (name, Decimal(generator.randint(1, 5)) / 10, Decimal(generator.randint(0, 9)) / 10)
            for name in ["A", "B", "C"]
        ]
        bounds = {row[0]: (0, generator.randint(1, 3)) for row in rows}
        budget = Decimal(generator.randint(0, 12)) / 10
        result = allocate(rows, budget, "0.1", bounds, True)
        possibilities = []
        for quantities in itertools.product(*(range(bounds[row[0]][1] + 1) for row in rows)):
            cost = sum(row[1] * q for row, q in zip(rows, quantities, strict=True))
            gain = sum(row[2] * q for row, q in zip(rows, quantities, strict=True))
            if cost <= budget:
                possibilities.append((gain, cost, quantities))
        optimum = min(possibilities, key=lambda x: (-x[0], x[1], x[2]))
        assert Decimal(result["benefit"]) == optimum[0]
        assert Decimal(result["cost"]) == optimum[1]
        assert tuple(row["quantity"] for row in result["allocations"]) == optimum[2]


def test_allocation_retains_exact_large_benefits_and_mandatory_constraints():
    result = allocate(
        [("A", "0.10", "9007199254740993.01"), ("B", "0.20", "1")],
        "0.40",
        "0.10",
        {"A": (1, 2), "B": (1, 1)},
        True,
    )
    assert result["benefit"] == "18014398509481987.02"
    assert result["cost"] == "0.40"
    assert result["baseline"]["feasible"] is False


def test_infeasible_allocation_is_not_a_recommendation():
    result = allocate([("A", "10", "20")], "9", "1", {"A": (1, 1)}, True)
    assert result["status"] == "infeasible"
    assert result["benefit"] is None and result["allocations"] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"assumptions_confirmed": False},
        {"budget": "-1"},
        {"quantum": "0"},
        {"budget": "5001"},
        {"quantum": "0.3"},
        {"bounds": {"A": (0, 11)}},
        {"bounds": {"B": (0, 1)}},
        {"bounds": {"A": (True, 1)}},
        {"rows": [("A", "0", "1")]},
        {"rows": [("A", "1", "-1")]},
        {"rows": [("A", "1", "1"), ("A", "1", "1")]},
    ],
)
def test_unsupported_or_unsafe_decision_inputs_are_refused(changes):
    raw = dict(
        rows=[("A", "1", "2")],
        budget="10",
        quantum="1",
        bounds={"A": (0, 1)},
        assumptions_confirmed=True,
    )
    with pytest.raises(IngestionError):
        allocate(**(raw | changes))
