"""Use case: Proves exact rule-constrained decisions without trusting the solver.

What it does: Uses a rational exhaustive oracle and explicit invalid, tied and infeasible cases.
"""

import copy
import random
from fractions import Fraction
from itertools import product

import pytest

from execplus.domain.allocation_constraints import (
    RULE_METHOD,
    allocate_selection_rules,
    selection_rules,
    verify_selection_result,
)
from execplus.domain.ingestion import IngestionError


def solve(rows=None, *, prerequisites=None, exclusions=None, bounds=None, **extra):
    rows = rows or [("A", "1", "10", "1"), ("B", "1", "0", "1")]
    return allocate_selection_rules(
        rows,
        extra.pop("budget", "2"),
        extra.pop("quantum", "1"),
        bounds or {row[0]: (0, 2) for row in rows},
        extra.pop("assumptions_confirmed", True),
        prerequisites if prerequisites is not None else [dict(candidate="A", requires="B")],
        exclusions or [],
        **extra,
    )


def test_prerequisite_requires_one_unit_not_matching_quantity_or_time_order():
    result = solve(budget="4")
    assert result["method_version"] == RULE_METHOD
    assert [a["quantity"] for a in result["allocations"]] == [2, 1]
    assert result["benefit"] == "20" and result["cost"] == "3"
    assert result["baseline"] == dict(cost="0", benefit="0", feasible=True)
    assert result["verification"] == dict(
        quantities="passed", resources="passed", selection_rules="passed"
    )


def test_conflicting_rules_disable_optional_action_without_relaxing_rules():
    result = solve(exclusions=[dict(first="B", second="A")])
    assert [a["quantity"] for a in result["allocations"]] == [0, 0]
    assert result["cost"] == "0" and result["status"] == "feasible"
    assert result["selection_rules"]["exclusions"] == [dict(first="A", second="B")]


@pytest.mark.parametrize(
    "extra",
    [
        dict(exclusions=[dict(first="A", second="B")]),
        dict(budget="1"),
        dict(resource_capacity="1"),
        dict(bounds={"A": (1, 2), "B": (0, 0)}),
    ],
)
def test_required_minimums_can_be_infeasible_without_a_recommendation(extra):
    result = solve(**{**dict(bounds={"A": (1, 2), "B": (0, 2)}), **extra})
    assert result["status"] == result["solver_status"] == "infeasible"
    assert result["allocations"] == [] and result["benefit"] is None
    assert result["baseline"]["feasible"] is False
    assert "verification" not in result


def test_zero_budget_and_zero_additional_capacity_keep_feasible_do_nothing():
    result = solve(budget="0", resource_capacity="0")
    assert result["status"] == "feasible"
    assert all(a["quantity"] == 0 for a in result["allocations"])
    assert result["baseline"]["feasible"] is True
    assert result["unused_budget"] == result["resource_used"] == "0"


def test_exact_values_and_ties_follow_existing_cost_resource_lexical_order():
    rows = [("A", "0.1", "9007199254740993.01", "2"), ("B", "0.1", "9007199254740993.01", "1")]
    result = solve(
        rows,
        prerequisites=[],
        exclusions=[dict(first="A", second="B")],
        budget="0.2",
        quantum="0.1",
        resource_capacity="4",
    )
    assert [a["quantity"] for a in result["allocations"]] == [0, 2]
    assert result["benefit"] == "18014398509481986.02"
    assert result["cost"] == "0.2" and result["resource_used"] == "2"
    assert result == solve(
        list(reversed(rows)),
        prerequisites=[],
        exclusions=[dict(first="B", second="A")],
        budget="0.2",
        quantum="0.1",
        resource_capacity="4",
    )
    lexical = solve(
        [(name, "1", "1", None) for name in ["A", "B"]],
        prerequisites=[],
        exclusions=[dict(first="A", second="B")],
        budget="1",
    )
    assert [a["quantity"] for a in lexical["allocations"]] == [0, 1]


@pytest.mark.parametrize("two_resources", [False, True])
def test_selection_decisions_match_independent_fraction_oracle(two_resources):
    rng = random.Random(1610)
    for _ in range(60):
        rows = [
            (name, f"0.{rng.randint(1, 9)}", f"0.{rng.randint(0, 9)}", f"0.{rng.randint(0, 9)}")
            for name in ["A", "B", "C", "D"]
        ]
        lower = [rng.randint(0, 1) for _ in rows]
        bounds = {row[0]: (minimum, 2) for row, minimum in zip(rows, lower, strict=True)}
        requirements = [(0, 1)] + ([(1, 2)] if rng.choice([False, True]) else [])
        exclusions = [(0, 3)] if rng.choice([False, True]) else [(1, 3)]
        budget = f"{rng.randint(0, 3)}.{rng.randint(0, 9)}"
        capacity = f"{rng.randint(0, 3)}.{rng.randint(0, 9)}" if two_resources else None
        result = solve(
            rows,
            bounds=bounds,
            budget=budget,
            quantum="0.1",
            resource_capacity=capacity,
            prerequisites=[
                dict(candidate=rows[a][0], requires=rows[b][0]) for a, b in requirements
            ],
            exclusions=[dict(first=rows[a][0], second=rows[b][0]) for a, b in exclusions],
        )
        feasible = []
        for quantities in product(range(3), repeat=4):
            if any(q < minimum for q, minimum in zip(quantities, lower, strict=True)):
                continue
            selected = {index for index, q in enumerate(quantities) if q > 0}
            if any(a in selected and b not in selected for a, b in requirements):
                continue
            if any({a, b} <= selected for a, b in exclusions):
                continue
            cost, benefit, resource = tuple(
                sum(Fraction(row[i]) * q for row, q in zip(rows, quantities, strict=True))
                for i in (1, 2, 3)
            )
            if cost <= Fraction(budget) and (capacity is None or resource <= Fraction(capacity)):
                feasible.append((-benefit, cost, resource if two_resources else 0, quantities))
        if feasible:
            expected = min(feasible)
            assert result["solver_status"] == "optimal"
            assert Fraction(result["benefit"]) == -expected[0]
            assert Fraction(result["cost"]) == expected[1]
            assert tuple(a["quantity"] for a in result["allocations"]) == expected[3]
            if two_resources:
                assert Fraction(result["resource_used"]) == expected[2]
        else:
            assert result["solver_status"] == "infeasible"
            assert result["allocations"] == [] and result["benefit"] is None


@pytest.mark.parametrize(
    "prerequisites,exclusions",
    [
        ([], []),
        ([dict(candidate="A", requires="unknown")], []),
        ([dict(candidate="a", requires="B")], []),
        ([dict(candidate="A", requires="A")], []),
        ([dict(candidate="A", requires="B")] * 2, []),
        ([dict(candidate="A", requires="B"), dict(candidate="B", requires="A")], []),
        (
            [
                dict(candidate="A", requires="B"),
                dict(candidate="B", requires="C"),
                dict(candidate="C", requires="A"),
            ],
            [],
        ),
        ([], [dict(first="A", second="A")]),
        ([], [dict(first="A", second="B"), dict(first="B", second="A")]),
        ([], [dict(first="A", second="unknown")]),
        ([dict(candidate="A", requires="B", ignored=True)], []),
        ([dict(candidate="A", requires=True)], []),
        ([dict(candidate="A", requires="B")] * 41, []),
        (None, []),
    ],
)
def test_invalid_rule_shapes_names_duplicates_and_cycles_refuse(prerequisites, exclusions):
    with pytest.raises(IngestionError):
        selection_rules({"A", "B", "C"}, prerequisites, exclusions)


@pytest.mark.parametrize(
    "extra",
    [
        dict(quantum="0.3"),
        dict(budget="5001"),
        dict(assumptions_confirmed=False),
        dict(bounds={"A": (0, True), "B": (0, 2)}),
        dict(resource_capacity="-1"),
    ],
)
def test_existing_validation_is_not_weakened_by_selection_rules(extra):
    with pytest.raises(IngestionError):
        solve(**extra)


def test_search_cap_refuses_before_enumeration_but_accepts_exact_boundary():
    with pytest.raises(IngestionError, match="100,000"):
        solve(
            [(name, "1", "1", None) for name in "ABCDEF"],
            bounds={name: (0, 10) for name in "ABCDEF"},
            budget="1",
        )
    result = solve(
        [(name, "1", "1", None) for name in "ABCDE"],
        bounds={name: (0, 9) for name in "ABCDE"},
        budget="1",
    )
    assert result["status"] == "feasible" and result["benefit"] == "1"


@pytest.mark.parametrize("field", ["quantity", "cost", "resource", "rules", "identity", "minimum"])
def test_independent_checker_refuses_corrupted_solver_proposals(field):
    rows = [("A", "1", "10", "1"), ("B", "1", "0", "1")]
    result = copy.deepcopy(solve(rows, resource_capacity="2"))
    rules = copy.deepcopy(result["selection_rules"])
    if field == "quantity":
        result["allocations"][1]["quantity"] = 0
    elif field == "cost":
        result["cost"] = "0"
    elif field == "resource":
        result["resource_used"] = "0"
    elif field == "rules":
        result["selection_rules"]["prerequisites"] = []
    elif field == "identity":
        result["allocations"][1]["candidate"] = "A"
    else:
        result["allocations"][0]["minimum"] = 1
    with pytest.raises(IngestionError, match="independent checking"):
        verify_selection_result(rows, "2", {"A": (0, 2), "B": (0, 2)}, rules, result, "2")


def test_independent_checker_rejects_rule_violation_even_with_correct_totals():
    rows = [("A", "1", "10", None), ("B", "1", "0", None)]
    result = solve(rows, prerequisites=[], exclusions=[dict(first="A", second="B")])
    rules = selection_rules({"A", "B"}, [dict(candidate="A", requires="B")], [])
    result["selection_rules"] = rules
    assert result["allocations"][0]["quantity"] == 2
    with pytest.raises(IngestionError, match="independent checking"):
        verify_selection_result(rows, "2", {"A": (0, 2), "B": (0, 2)}, rules, result)
