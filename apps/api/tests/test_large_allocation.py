"""Use case: Independently checks larger allocations and exact decimal scaling.

What it does: Uses exhaustive small oracles, resource boundaries and forged-solver refusals.
"""

import json
import random
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.large_allocation import (
    METHOD,
    SolverOutcome,
    checked_allocation,
    exact_scale,
    prepare_allocation,
    reopen_allocation,
)
from execplus.infrastructure.allocation.cp_sat import CpSatAllocationSolver


def request(**changes):
    return dict(
        kind="bounded_allocation",
        model=METHOD,
        cost_column="cost",
        benefit_column="benefit",
        budget="0.11",
        maximum_quantity=2,
        bounds=[],
        resources=[dict(column="hours", capacity="0.5")],
        assumptions_confirmed=True,
        prerequisites=[],
        exclusions=[],
        **changes,
    )


ROWS = (("A", "0.03", "0.07", "0.2"), ("B", "0.05", "0.11", "0.1"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "capacity,expected,benefit,cost,hours",
    [
        ("0.5", [2, 1], "0.25", "0.11", "0.5"),
        ("0.4", [0, 2], "0.22", "0.10", "0.2"),
    ],
)
async def test_independent_decimal_expected_values(capacity, expected, benefit, cost, hours):
    raw = request()
    raw["resources"][0]["capacity"] = capacity
    problem = prepare_allocation(raw, ROWS)
    outcome = await CpSatAllocationSolver().solve(problem.integers)
    result = checked_allocation(problem, outcome)
    assert result["solver_status"] == "optimal"
    assert [row["quantity"] for row in result["allocations"]] == expected
    assert result["benefit"] == benefit and result["cost"] == cost
    assert result["resources"][1]["used"] == hours
    retained = json.loads(json.dumps(result))
    assert reopen_allocation(problem, retained) == retained


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", range(20))
async def test_real_solver_against_independent_small_exhaustive_oracle(seed):
    rng = random.Random(seed)
    size, dimensions = rng.randint(2, 6), rng.randint(1, 4)
    rows = tuple(
        (
            chr(65 + i),
            rng.randint(1, 7),
            rng.randint(0, 11),
            *(rng.randint(0, 5) for _ in range(dimensions - 1)),
        )
        for i in range(size)
    )
    capacities = [rng.randint(3, 19) for _ in range(dimensions)]
    raw = request()
    raw.update(
        budget=str(capacities[0]),
        resources=[dict(column=f"r{i}", capacity=str(capacities[i])) for i in range(1, dimensions)],
    )
    if seed % 2:
        raw["prerequisites"] = [dict(candidate="B", requires="A")]
    if seed % 3 == 0:
        raw["exclusions"] = [dict(first="A", second="B")]
    if seed % 4 == 0:
        raw["bounds"] = [dict(candidate="B", minimum=1, maximum=2)]
    feasible = []
    for quantities in product(range(3), repeat=size):
        if raw["bounds"] and quantities[1] < 1:
            continue
        if raw["prerequisites"] and quantities[1] and not quantities[0]:
            continue
        if raw["exclusions"] and quantities[0] and quantities[1]:
            continue
        consumed = [
            sum(
                q * row[1 if index == 0 else index + 2]
                for q, row in zip(quantities, rows, strict=True)
            )
            for index in range(dimensions)
        ]
        if all(value <= capacity for value, capacity in zip(consumed, capacities, strict=True)):
            feasible.append(sum(q * row[2] for q, row in zip(quantities, rows, strict=True)))
    problem = prepare_allocation(raw, rows)
    result = checked_allocation(problem, await CpSatAllocationSolver().solve(problem.integers))
    if feasible:
        assert result["solver_status"] == "optimal"
        assert Decimal(result["benefit"]) == max(feasible)
    else:
        assert result["solver_status"] == "infeasible"
        assert result["benefit"] is None and result["allocations"] == []


def test_exact_scaling_retains_38_decimal_places_and_ignores_caller_context():
    with localcontext() as context:
        context.prec = 3
        integers, step = exact_scale((Decimal("1e-38"), Decimal("3e-38")), (100, 100))
    assert integers == (1, 3) and step == Fraction(1, 10**38)
    with pytest.raises(IngestionError, match="exact decimal scales"):
        exact_scale((Decimal("9007199254740993"), Decimal(1)), (1, 1))


@pytest.mark.parametrize(
    "change",
    [
        {"assumptions_confirmed": False},
        {"maximum_quantity": 101},
        {"maximum_quantity": True},
        {"budget": "-1"},
        {"resources": [dict(column="r", capacity="1")] * 4},
        {"bounds": [dict(candidate="missing", minimum=0, maximum=1)]},
        {"bounds": [dict(candidate="A", minimum=2, maximum=1)]},
        {"prerequisites": [dict(candidate="A", requires="B"), dict(candidate="B", requires="A")]},
    ],
)
def test_invalid_declarations_refused(change):
    raw = request()
    raw.update(change)
    with pytest.raises(IngestionError):
        prepare_allocation(raw, ROWS)


@pytest.mark.parametrize(
    "rows",
    [
        (),
        ROWS * 26,
        (ROWS[0], ROWS[0]),
        ((None, 1, 2, 3),),
        ((" ", 1, 2, 3),),
        (("A", None, 2, 3),),
        (("A", 1, -2, 3),),
        (("A", 0, 2, 3),),
        (("A", 1, 2, -3),),
    ],
)
def test_incomplete_or_invalid_population_refused(rows):
    with pytest.raises(IngestionError):
        prepare_allocation(request(), rows)


@pytest.mark.parametrize(
    "outcome",
    [
        SolverOutcome("WRONG", None, None),
        SolverOutcome("UNKNOWN", (0, 0), 0),
        SolverOutcome("OPTIMAL", None, None),
        SolverOutcome("OPTIMAL", (True, 1), 18),
        SolverOutcome("OPTIMAL", (2, 2), 36),
        SolverOutcome("OPTIMAL", (2, 1), 99),
        SolverOutcome("OPTIMAL", (2, 1), 25, "hard_wall_limit"),
    ],
)
def test_forged_solver_values_are_independently_rejected(outcome):
    with pytest.raises(IngestionError):
        checked_allocation(prepare_allocation(request(), ROWS), outcome)


def test_feasible_is_not_labelled_optimal_and_unknown_does_not_invent_actions():
    problem = prepare_allocation(request(), ROWS)
    result = checked_allocation(problem, SolverOutcome("FEASIBLE", (0, 1), 11))
    assert result["status"] == "feasible" and result["solver_status"] == "feasible"
    assert "not proved" in result["reason"]
    result = checked_allocation(problem, SolverOutcome("UNKNOWN", None, None, "hard_wall_limit"))
    assert (
        result["status"] == "unknown" and result["allocations"] == [] and result["benefit"] is None
    )


def test_rule_verifier_checks_prerequisites_and_exclusions_independently():
    raw = request()
    raw["prerequisites"] = [dict(candidate="B", requires="A")]
    with pytest.raises(IngestionError):
        checked_allocation(prepare_allocation(raw, ROWS), SolverOutcome("FEASIBLE", (0, 1), 11))
    raw["prerequisites"] = []
    raw["exclusions"] = [dict(first="A", second="B")]
    with pytest.raises(IngestionError):
        checked_allocation(prepare_allocation(raw, ROWS), SolverOutcome("FEASIBLE", (2, 1), 25))


@pytest.mark.asyncio
async def test_fifty_actions_four_resources_and_zero_benefits_have_valid_bounded_output():
    raw = request()
    raw.update(budget="100", resources=[dict(column=f"r{i}", capacity="100") for i in range(3)])
    rows = tuple((f"Action{i:02}", 1, 0, 1, 1, 1) for i in range(50))
    problem = prepare_allocation(raw, rows)
    result = checked_allocation(problem, await CpSatAllocationSolver().solve(problem.integers))
    assert result["solver_status"] == "optimal" and result["benefit"] == "0"
    assert len(result["allocations"]) == 50 and len(result["resources"]) == 4


def test_portable_chart_keeps_saved_unit_and_essential_assumption_status_visible():
    from execplus.application.services.analysis_report_documents import build_analysis_report
    from test_analysis_report_documents import NOW, decision, table

    raw = request()
    result = checked_allocation(
        prepare_allocation(raw, ROWS), SolverOutcome("FEASIBLE", (2, 1), 25)
    )
    record = decision(result, raw)
    record["run"]["evidence"]["units"] = {"cost": "USD", "benefit": "USD", "hours": "hours"}
    content = build_analysis_report("allocation", record, NOW)
    assert content.charts[0].y_label == "benefit (USD)"
    assert "not proved" in content.charts[0].notes[0]
    assert "not proven real-world effects" in content.charts[0].notes[1]
    assert len(content.charts[0].notes) == 3
    resources = table(content, "Every declared resource limit and exact use")
    assert resources.rows == (("cost", "0.11", "0.11", "0.00"), ("hours", "0.5", "0.5", "0.0"))
    assert len(table(content, "Per-action resource contributions").rows) == 4
