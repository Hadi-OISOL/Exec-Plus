"""Use case: Independently checks grouped findings, compound assumptions and resource decisions.

What it does: Verifies exact arithmetic, coverage, limits and compatibility without model outputs.
"""

import random
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product

import pytest

from execplus.domain.analysis_extensions import allocate_resources, detect_segments
from execplus.domain.decision_analysis import detect_distribution
from execplus.domain.ingestion import IngestionError
from execplus.domain.scenarios import compare_scenarios


def test_groups_reveal_local_spike_without_comparing_different_baselines():
    rows = [("Small", "10", 8), ("Small", "100", 1), ("Large", "100", 10)]
    result = detect_segments(rows, "3.5", "0", 8)
    assert result["flagged_records"] == 1
    assert result["findings"][0]["segment"] == "Small"
    assert result["findings"][0]["value"] == "100"
    assert result["covered_records"] == 19
    assert result == detect_segments(list(reversed(rows)), "3.5", "0", 8)
    assert Decimal(result["groups"][0]["baseline"]) == Decimal("100")


def test_group_coverage_never_calls_missing_or_sparse_records_normal():
    rows = [("A", "10", 8), ("A", None, 2), ("B", "99", 7), (None, "1", 4)]
    result = detect_segments(rows, "3.5", "0", 8)
    assert result["sample_count"] == 21
    assert result["covered_records"] == 8
    assert result["excluded_records"] == 13
    groups = {group["segment"]: group for group in result["groups"]}
    assert groups[None]["status"] == "missing_group"
    assert groups["B"]["status"] == "insufficient_support"
    assert groups["A"]["missing_records"] == 2
    assert "baseline" not in groups["B"]


def test_group_finding_ids_include_identity_and_weighted_statistics_match_v1():
    values = [("1", 5), ("2", 3), ("300", 1)]
    result = detect_segments(
        [(name, value, count) for name in ["A", "B"] for value, count in values], "3.5", "0", 8
    )
    assert len({finding["id"] for finding in result["findings"]}) == 2
    reference = detect_distribution(values)
    for group in result["groups"]:
        assert group["baseline"] == reference["baseline"]
        assert group["mad"] == reference["mad"]
        assert group["iqr"] == reference["iqr"]


@pytest.mark.parametrize(
    "rows,minimum",
    [
        ([], 8),
        ([("A", 1, True)], 8),
        ([("A", 1, 200001)], 8),
        ([(str(i), 1, 8) for i in range(33)], 8),
        ([("A", "Infinity", 8)], 8),
        ([("A", 1, 8)], 7),
        ([("A", 1, 8)], True),
        ([("A", i, 1) for i in range(1001)], 8),
    ],
)
def test_segment_limits_refuse_incomplete_or_unbounded_queries(rows, minimum):
    with pytest.raises(IngestionError):
        detect_segments(rows, "3.5", "0", minimum)


def test_two_resources_change_the_best_decision_and_preserve_exact_values():
    result = allocate_resources(
        [("A", "0.1", "9007199254740993.01", "4"), ("B", "0.2", "9007199254740994.02", "1")],
        "0.4",
        "0.1",
        {"A": (0, 2), "B": (0, 2)},
        True,
        "2",
    )
    assert result["solver_status"] == "optimal"
    assert result["benefit"] == "18014398509481988.04"
    assert result["resource_used"] == "2"
    assert [a["quantity"] for a in result["allocations"]] == [0, 2]
    assert result["cost"] == "0.4"


def test_resource_decisions_match_independent_rational_oracle():
    rng = random.Random(801)
    for _ in range(25):
        rows = [
            (
                name,
                str(rng.randint(1, 7) / 10),
                str(rng.randint(0, 12) / 10),
                str(rng.randint(0, 5) / 10),
            )
            for name in ["A", "B", "C"]
        ]
        bounds = {row[0]: (rng.randint(0, 1), 2) for row in rows}
        result = allocate_resources(rows, "0.8", "0.1", bounds, True, "0.5")
        feasible = []
        for quantities in product(range(3), repeat=3):
            if any(q < bounds[row[0]][0] for row, q in zip(rows, quantities, strict=True)):
                continue
            totals = tuple(
                sum(Fraction(row[i]) * q for row, q in zip(rows, quantities, strict=True))
                for i in (1, 2, 3)
            )
            if totals[0] <= Fraction(8, 10) and totals[2] <= Fraction(5, 10):
                feasible.append((-totals[1], totals[0], totals[2], quantities))
        if not feasible:
            assert result["solver_status"] == "infeasible"
            assert result["allocations"] == [] and result["benefit"] is None
        else:
            best = min(feasible)
            assert Fraction(result["benefit"]) == -best[0]
            assert Fraction(result["cost"]) == best[1]
            assert Fraction(result["resource_used"]) == best[2]
            assert tuple(a["quantity"] for a in result["allocations"]) == best[3]


@pytest.mark.parametrize("resource,capacity", [("-1", "1"), (None, "1"), ("1", "-1"), ("1", "NaN")])
def test_resource_invalid_or_missing_values_refuse(resource, capacity):
    with pytest.raises(IngestionError):
        allocate_resources([("A", "1", "2", resource)], "10", "1", {"A": (0, 1)}, True, capacity)


def test_resource_work_limit_and_required_minimum_infeasibility():
    with pytest.raises(IngestionError, match="100,000"):
        allocate_resources(
            [(str(i), "1", "2", "1") for i in range(6)],
            "10",
            "1",
            {str(i): (0, 10) for i in range(6)},
            True,
            "10",
        )
    result = allocate_resources([("A", "1", "2", "2")], "10", "1", {"A": (1, 1)}, True, "1")
    assert result["status"] == "infeasible"
    assert result["baseline"]["feasible"] is False


def scenario(changes):
    return dict(
        metric="amount",
        aggregation="sum",
        assumptions_confirmed=True,
        alternatives=[dict(name="Volume and price", operation="compound_percent", drivers=changes)],
    )


def test_compound_scenario_uses_multiplication_not_sum_of_percentages():
    raw = scenario(
        [dict(name="Volume", percent_change="10"), dict(name="Price", percent_change="20")]
    )
    result = compare_scenarios(raw, ((Decimal("100"), 8, 8),))
    assert Decimal(result["alternatives"][0]["result"]) == Decimal("132")
    assert Decimal(result["alternatives"][0]["difference"]) == Decimal("32")
    assert result["method_version"] == "compound-scenarios-v1"
    assert "not measured source relationships" in " ".join(result["limitations"])


def test_compound_exact_high_precision_and_zero_baseline():
    value = "0." + "1" * 38
    raw = scenario([dict(name=str(i), percent_change=value) for i in range(3)])
    base = Decimal("9007199254740993.12345678901234567890123456789012345678")
    result = compare_scenarios(raw, ((base, 8, 8),))
    with localcontext() as ctx:
        ctx.prec = 350
        assert (
            Decimal(result["alternatives"][0]["result"]) == base * (1 + Decimal(value) / 100) ** 3
        )
    assert (
        compare_scenarios(raw, ((Decimal(0), 8, 8),))["alternatives"][0]["percentage_difference"]
        is None
    )


@pytest.mark.parametrize(
    "changes",
    [
        [],
        [dict(name="A", percent_change="-101")],
        [dict(name="A", percent_change="Infinity")],
        [dict(name="A", percent_change=10)],
        [dict(name="A", percent_change="1"), dict(name=" a ", percent_change="2")],
        [dict(name=str(i), percent_change="1") for i in range(4)],
    ],
)
def test_invalid_driver_assumptions_refuse(changes):
    with pytest.raises(IngestionError):
        compare_scenarios(scenario(changes), ((Decimal(100), 8, 8),))
