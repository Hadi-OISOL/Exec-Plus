"""Use case: Independently checks multi-period scheduled allocations.

What it does: Compares real CP-SAT schedules with an exhaustive decimal oracle,
refuses forged periods and verifies saved replay through the governed API.
"""

import random
from decimal import Decimal
from fractions import Fraction
from itertools import product

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.large_allocation import SCHEDULE_METHOD, SolverOutcome
from execplus.domain.scheduled_allocation import (
    ScheduleOutcome,
    checked_schedule,
    prepare_schedule,
    reopen_schedule,
)
from execplus.infrastructure.allocation.cp_sat import CpSatAllocationSolver
from test_large_allocation_integration import create, endpoint, fixture

ROWS = (
    ("A", "0.03", "0.07", "0.2"),
    ("B", "0.05", "0.11", "0.1"),
    ("C", "0.04", "0.06", "0.3"),
)


def request(period_budgets, precedence=(), **changes):
    return dict(
        kind="bounded_allocation",
        model=SCHEDULE_METHOD,
        cost_column="cost",
        benefit_column="benefit",
        budget=changes.pop("budget", "0.2"),
        maximum_quantity=changes.pop("maximum_quantity", 2),
        bounds=[],
        resources=[dict(column="hours", capacity=changes.pop("hours", "1"))],
        assumptions_confirmed=True,
        prerequisites=[],
        exclusions=[],
        schedule=dict(
            period_budgets=list(period_budgets),
            precedence=[dict(candidate=a, after=b) for a, b in precedence],
        ),
        **changes,
    )


def oracle(raw, rows):
    budgets = [Decimal(v) for v in raw["schedule"]["period_budgets"]]
    after = [(r["candidate"], r["after"]) for r in raw["schedule"]["precedence"]]
    labels = [row[0] for row in rows]
    best = None
    for quantities in product(range(raw["maximum_quantity"] + 1), repeat=len(rows)):
        if sum(Decimal(r[1]) * q for r, q in zip(rows, quantities, strict=True)) > Decimal(
            raw["budget"]
        ):
            continue
        if sum(Decimal(r[3]) * q for r, q in zip(rows, quantities, strict=True)) > Decimal(
            raw["resources"][0]["capacity"]
        ):
            continue
        selected = [i for i, q in enumerate(quantities) if q]
        for chosen in product(range(len(budgets)), repeat=len(selected)):
            start = dict(zip((labels[i] for i in selected), chosen, strict=True))
            if any(
                later in start and (earlier not in start or start[earlier] >= start[later])
                for later, earlier in after
            ):
                continue
            spent = [Decimal(0)] * len(budgets)
            for i, period in zip(selected, chosen, strict=True):
                spent[period] += Decimal(rows[i][1]) * quantities[i]
            if any(s > b for s, b in zip(spent, budgets, strict=True)):
                continue
            value = sum(Decimal(r[2]) * q for r, q in zip(rows, quantities, strict=True))
            best = value if best is None or value > best else best
    return best


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", range(8))
async def test_real_solver_matches_exhaustive_schedule_oracle(seed):
    rng = random.Random(seed)
    budgets = [rng.choice(["0", "0.03", "0.05", "0.08", "0.1"]) for _ in range(rng.choice([2, 3]))]
    pairs = [("B", "A"), ("C", "B"), ("C", "A"), ("A", "C")]
    precedence = rng.sample(pairs[:3], rng.randint(0, 2))
    raw = request(budgets, precedence, budget=rng.choice(["0.1", "0.2"]))
    scheduled = prepare_schedule(raw, ROWS)
    outcome = await CpSatAllocationSolver().solve_schedule(scheduled.integers)
    result = checked_schedule(scheduled, outcome)
    assert result["solver_status"] == "optimal"
    assert Decimal(result["benefit"]) == oracle(raw, ROWS)
    assert result["verification"]["precedence"] == "passed"
    assert reopen_schedule(scheduled, result) == result


@pytest.mark.asyncio
async def test_precedence_forces_a_later_period_and_period_budgets_split_work():
    raw = request(["0.05", "0.05"], [("B", "A")], maximum_quantity=1)
    scheduled = prepare_schedule(raw, ROWS)
    result = checked_schedule(
        scheduled, await CpSatAllocationSolver().solve_schedule(scheduled.integers)
    )
    periods = {row["candidate"]: row["period"] for row in result["allocations"]}
    assert periods["B"] == 2 and periods["A"] == 1
    assert Decimal(result["benefit"]) == Decimal("0.18") == oracle(raw, ROWS)
    assert [p["used"] for p in result["schedule"]["periods"]] == ["0.03", "0.05"]


def forged(quantities, periods, objective):
    return ScheduleOutcome(SolverOutcome("FEASIBLE", quantities, objective), periods)


@pytest.mark.parametrize(
    "outcome",
    [
        forged((1, 1, 0), (1, 0, None), None),
        forged((1, 1, 0), (0, None, None), None),
        forged((2, 0, 0), (0, None, None), None),
        forged((1, 0, 0), None, None),
        forged((1, 0, 0), (5, None, None), None),
    ],
)
def test_forged_periods_are_independently_rejected(outcome):
    scheduled = prepare_schedule(request(["0.05", "0.05"], [("B", "A")]), ROWS)
    benefit = sum(Fraction(r[2]) * q for r, q in zip(ROWS, outcome.outcome.quantities, strict=True))
    fixed = ScheduleOutcome(
        SolverOutcome(
            "FEASIBLE",
            outcome.outcome.quantities,
            int(benefit / scheduled.problem.benefit_step),
        ),
        outcome.periods,
    )
    with pytest.raises(IngestionError):
        checked_schedule(scheduled, fixed)


@pytest.mark.parametrize(
    "change",
    [
        dict(schedule=dict(period_budgets=["1"], precedence=[])),
        dict(schedule=dict(period_budgets=["1", "-1"], precedence=[])),
        dict(schedule=dict(period_budgets=["1", "1"], precedence=[dict(candidate="A", after="A")])),
        dict(schedule=dict(period_budgets=["1", "1"], precedence=[dict(candidate="A", after="Z")])),
        dict(schedule=None),
    ],
)
def test_invalid_schedule_declarations_refused(change):
    with pytest.raises(IngestionError):
        prepare_schedule({**request(["1", "1"]), **change}, ROWS)


def test_scheduled_allocation_api_replays_and_keeps_legacy_requests(integration, monkeypatch):
    env = integration
    owner, _, _, _, _, root = fixture(env)
    response = create(
        env,
        owner,
        root,
        model=SCHEDULE_METHOD,
        maximum_quantity=1,
        schedule=dict(period_budgets=["0.05", "0.05"], precedence=[dict(candidate="B", after="A")]),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert body["run"]["method_version"] == SCHEDULE_METHOD
    assert {r["candidate"]: r["period"] for r in result["allocations"]} == {"A": 1, "B": 2}
    assert Decimal(result["benefit"]) == Decimal("0.18")

    class NoSearch:
        async def solve_schedule(self, problem):
            raise AssertionError("Reopening must not rerun bounded search")

    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", NoSearch())
    assert env.client.get(endpoint(root, body), headers=owner).json()["run"] == body["run"]
    monkeypatch.undo()
    legacy = create(env, owner, root)
    assert legacy.status_code == 201, legacy.text
    assert "schedule" not in legacy.json()["run"]["request"]
    assert legacy.json()["run"]["method_version"] == "cp-sat-integer-allocation-v1"
    mismatched = create(env, owner, root, schedule=dict(period_budgets=["1", "1"]))
    assert mismatched.status_code == 422, mismatched.text
