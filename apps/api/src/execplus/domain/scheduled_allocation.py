"""Use case: Defines exact multi-period scheduling evidence for bounded allocations.

What it does: Adds per-period budgets and strict start-order precedence to the
multi-resource model, then independently checks solver periods with exact decimals.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from typing import Any

from execplus.domain.decision_analysis import checksum, encoded, fail, number
from execplus.domain.large_allocation import (
    SCHEDULE_METHOD,
    AllocationProblem,
    IntegerAllocation,
    SolverOutcome,
    checked_allocation,
    exact_scale,
    prepare_allocation,
    retained_outcome,
)

SCHEDULE_VERSION = "scheduled-allocation-v1"
MAX_PERIODS = 12
MAX_PRECEDENCE = 40


@dataclass(frozen=True)
class ScheduledInteger:
    base: IntegerAllocation
    period_costs: tuple[int, ...]
    period_capacities: tuple[int, ...]
    after: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ScheduleOutcome:
    outcome: SolverOutcome
    periods: tuple[int | None, ...] | None


@dataclass(frozen=True)
class ScheduledProblem:
    problem: AllocationProblem
    period_budgets: tuple[Decimal, ...]
    precedence: tuple[dict[str, str], ...]
    integers: ScheduledInteger


def prepare_schedule(raw: dict[str, Any], rows: tuple[tuple[Any, ...], ...]) -> ScheduledProblem:
    schedule = raw.get("schedule")
    if not isinstance(schedule, dict) or set(schedule) != {"period_budgets", "precedence"}:
        fail("invalid_schedule", "Declare per-period budgets and precedence rules.")
    budgets = schedule["period_budgets"]
    if not isinstance(budgets, list) or not 2 <= len(budgets) <= MAX_PERIODS:
        fail("invalid_schedule", f"Use 2-{MAX_PERIODS} periods, each with a budget.")
    period_budgets = tuple(number(value) for value in budgets)
    if any(value < 0 for value in period_budgets):
        fail("invalid_schedule", "Every period budget must be nonnegative.")
    problem = prepare_allocation(raw, rows)
    labels = [candidate.label for candidate in problem.candidates]
    rules = schedule["precedence"]
    if not isinstance(rules, list) or len(rules) > MAX_PRECEDENCE:
        fail("invalid_schedule", f"Use at most {MAX_PRECEDENCE} precedence rules.")
    pairs = []
    for rule in rules:
        if (
            not isinstance(rule, dict)
            or set(rule) != {"candidate", "after"}
            or rule["candidate"] not in labels
            or rule["after"] not in labels
            or rule["candidate"] == rule["after"]
        ):
            fail("invalid_schedule", "Precedence must name two different known actions.")
        pairs.append((rule["candidate"], rule["after"]))
    if len(set(pairs)) != len(pairs):
        fail("invalid_schedule", "Declare each precedence rule once.")
    maximum = problem.integers.maximum
    costs, _ = exact_scale(
        (*(c.resources[0] for c in problem.candidates), *period_budgets),
        (*maximum, *(0 for _ in period_budgets)),
    )
    ordered = tuple(dict(candidate=a, after=b) for a, b in sorted(pairs))
    return ScheduledProblem(
        problem,
        period_budgets,
        ordered,
        ScheduledInteger(
            problem.integers,
            costs[: len(labels)],
            costs[len(labels) :],
            tuple((labels.index(r["candidate"]), labels.index(r["after"])) for r in ordered),
        ),
    )


def checked_schedule(scheduled: ScheduledProblem, result: ScheduleOutcome) -> dict[str, Any]:
    problem, outcome, periods = scheduled.problem, result.outcome, result.periods
    base = checked_allocation(problem, outcome)
    count = len(scheduled.period_budgets)
    used: list[Decimal] | None = None
    if outcome.quantities is None:
        if periods is not None:
            fail("allocation_solver_evidence", "Periods were returned without a selection.")
    else:
        if (
            periods is None
            or len(periods) != len(outcome.quantities)
            or any(
                (q > 0) != (p is not None)
                or (p is not None and (type(p) is not int or not 0 <= p < count))
                for q, p in zip(outcome.quantities, periods, strict=True)
            )
        ):
            fail("allocation_solver_evidence", "Each selected action needs exactly one period.")
        start = {
            c.label: -1 if p is None else p
            for c, p in zip(problem.candidates, periods, strict=True)
        }
        if any(
            start[rule["candidate"]] >= 0
            and not 0 <= start[rule["after"]] < start[rule["candidate"]]
            for rule in scheduled.precedence
        ):
            fail("allocation_solver_evidence", "The proposed periods violate declared precedence.")
        with localcontext() as context:
            context.prec = 256
            used = [
                sum(
                    (
                        c.resources[0] * q
                        for c, q, p in zip(
                            problem.candidates, outcome.quantities, periods, strict=True
                        )
                        if p == index
                    ),
                    Decimal(0),
                )
                for index in range(count)
            ]
            if any(value > cap for value, cap in zip(used, scheduled.period_budgets, strict=True)):
                fail("allocation_solver_evidence", "The proposed periods exceed a period budget.")
        for row, period in zip(base["allocations"], periods, strict=True):
            row["period"] = period + 1 if period is not None else None
    with localcontext() as context:
        context.prec = 256
        periods_view = [
            dict(
                period=index + 1,
                budget=encoded(cap),
                used=encoded(used[index]) if used is not None else None,
                unused=encoded(cap - used[index]) if used is not None else None,
            )
            for index, cap in enumerate(scheduled.period_budgets)
        ]
    evidence = base["solver_evidence"]
    evidence.update(
        version="bounded-cp-sat-schedule-v1",
        problem_checksum=checksum(asdict(scheduled.integers)),
        periods=list(periods) if periods is not None else None,
    )
    if base["verification"] is not None:
        base["verification"].update(period_budgets="passed", precedence="passed")
    base.update(
        version=SCHEDULE_VERSION,
        method_version=SCHEDULE_METHOD,
        schedule=dict(periods=periods_view, precedence=list(scheduled.precedence)),
        assumptions=[
            *base["assumptions"],
            "Each selected action starts and spends its whole cost within one declared period.",
            "Precedence means the later action starts in a strictly later period than the "
            "earlier action, which must also be selected.",
        ],
        limitations=[
            *base["limitations"],
            f"At most {MAX_PERIODS} periods and {MAX_PRECEDENCE} precedence rules; "
            "durations longer than one period, carry-over budgets and calendars are not modelled.",
        ],
    )
    return base


def reopen_schedule(scheduled: ScheduledProblem, retained: dict[str, Any]) -> dict[str, Any]:
    periods = retained["solver_evidence"]["periods"]
    return checked_schedule(
        scheduled,
        ScheduleOutcome(
            retained_outcome(retained), tuple(periods) if periods is not None else None
        ),
    )
