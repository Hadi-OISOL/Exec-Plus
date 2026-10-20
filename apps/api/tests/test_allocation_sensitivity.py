"""Check capacity alternatives with independent exact enumeration and retained evidence."""

from copy import deepcopy
from fractions import Fraction
from itertools import product

import pytest

from execplus.domain.allocation_sensitivity import (
    checked_sensitivity,
    infeasibility_reasons,
    prepare_sensitivity,
    reopen_sensitivity,
)
from execplus.domain.ingestion import IngestionError
from execplus.domain.large_allocation import SENSITIVITY_METHOD, SolverOutcome, prepare_allocation
from execplus.infrastructure.allocation.cp_sat import CpSatAllocationSolver
from test_large_allocation import ROWS, request


def compared(**changes):
    raw = request()
    raw.update(
        model=SENSITIVITY_METHOD,
        capacity_sensitivity=dict(
            column="cost", unit="USD", capacities=["0.03", "0.08", "0.11", "0.13", "0.16"]
        ),
    )
    raw.update(changes)
    return raw


@pytest.mark.asyncio
async def test_every_capacity_matches_independent_fraction_enumeration_and_reopens_without_search():
    raw = compared()
    original = deepcopy(raw)
    problems = prepare_sensitivity(raw, ROWS)
    solver = CpSatAllocationSolver()
    outcomes = tuple([await solver.solve(p.integers) for p in problems])
    result = checked_sensitivity(raw, problems, outcomes)
    assert len(problems) == 6 and raw == original
    assert result["capacity_sensitivity"]["approval_scope"] == "original_baseline_only"
    for variant in result["capacity_sensitivity"]["variants"]:
        capacity = Fraction(variant["capacity"])
        benefits = []
        for quantities in product(range(3), repeat=2):
            cost = sum(Fraction(r[1]) * q for r, q in zip(ROWS, quantities, strict=True))
            hours = sum(Fraction(r[3]) * q for r, q in zip(ROWS, quantities, strict=True))
            if cost <= capacity and hours <= Fraction("0.5"):
                benefits.append(
                    sum(Fraction(r[2]) * q for r, q in zip(ROWS, quantities, strict=True))
                )
        value = variant["result"]
        assert value["solver_status"] == "optimal" and Fraction(value["benefit"]) == max(benefits)
        assert Fraction(variant["difference"]["benefit"]) == max(benefits) - Fraction(
            result["benefit"]
        )
    assert reopen_sensitivity(raw, ROWS, result) == result
    forged = deepcopy(result)
    forged["capacity_sensitivity"]["variants"][0][
        "solver_evidence"
    ] = {}  # Unused placement must not be accepted as retained equality.
    assert reopen_sensitivity(raw, ROWS, forged) != forged
    forged = deepcopy(result)
    forged["capacity_sensitivity"]["variants"][0]["result"]["solver_evidence"]["quantities"] = [
        2,
        2,
    ]
    with pytest.raises(IngestionError):
        reopen_sensitivity(raw, ROWS, forged)


@pytest.mark.parametrize(
    "value",
    [
        None,
        dict(column="missing", unit="USD", capacities=["1", "2"]),
        dict(column="cost", unit="USD", capacities=["1"]),
        dict(column="cost", unit="USD", capacities=["1", "1.0"]),
        dict(column="cost", unit="USD", capacities=["2", "1"]),
        dict(column="cost", unit="USD", capacities=["-1", "2"]),
        dict(column="cost", unit="USD", capacities=["1", "2", "3", "4", "5", "6"]),
    ],
)
def test_invalid_capacity_lists_are_refused(value):
    with pytest.raises(IngestionError):
        prepare_sensitivity(compared(capacity_sensitivity=value), ROWS)


def test_each_capacity_must_fit_exact_solver_integer_bounds():
    with pytest.raises(IngestionError, match="exact decimal scales"):
        prepare_sensitivity(
            compared(
                capacity_sensitivity=dict(
                    column="cost",
                    unit="USD",
                    capacities=["0.00000000000000000000000000000000000001", "0.11"],
                )
            ),
            ROWS,
        )


def test_mandatory_prerequisite_closure_proves_resource_and_exclusion_conflicts():
    raw = request()
    raw.update(
        budget="0.01",
        bounds=[dict(candidate="B", minimum=1, maximum=2)],
        prerequisites=[dict(candidate="B", requires="A")],
        exclusions=[dict(first="A", second="B")],
    )
    reasons = infeasibility_reasons(prepare_allocation(raw, ROWS))
    shortage = next(
        reason for reason in reasons if reason["code"] == "mandatory_resource_exceeds_capacity"
    )
    assert shortage["column"] == "cost" and Fraction(shortage["minimum_required"]) == Fraction(
        "0.08"
    )
    assert Fraction(shortage["shortfall"]) == Fraction("0.07")
    assert shortage["forced_quantities"] == {"A": 1, "B": 1}
    assert any(reason["code"] == "mandatory_actions_excluded" for reason in reasons)
    raw["bounds"].append(dict(candidate="A", minimum=0, maximum=0))
    assert any(
        reason["code"] == "required_action_unavailable"
        for reason in infeasibility_reasons(prepare_allocation(raw, ROWS))
    )


def test_unknown_and_feasible_only_variants_keep_actual_status_without_invented_differences():
    raw = compared(
        capacity_sensitivity=dict(column="cost", unit="USD", capacities=["0.03", "0.08"])
    )
    problems = prepare_sensitivity(raw, ROWS)
    result = checked_sensitivity(
        raw,
        problems,
        (
            SolverOutcome("UNKNOWN", None, None, "hard_wall_limit"),
            SolverOutcome("FEASIBLE", (1, 0), 7),
            SolverOutcome("INFEASIBLE", None, None),
        ),
    )
    variants = result["capacity_sensitivity"]["variants"]
    assert result["benefit"] is None and all(v["difference"] is None for v in variants)
    assert variants[0]["result"]["solver_status"] == "feasible"
    assert "not proved" in variants[0]["result"]["reason"]
    assert variants[1]["result"]["infeasibility"][0]["proof_kind"] == "solver_result"
    assert reopen_sensitivity(raw, ROWS, result) == result
