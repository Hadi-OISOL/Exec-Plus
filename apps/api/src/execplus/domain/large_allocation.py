"""Use case: Defines exact, bounded multi-resource integer allocation evidence.

What it does: Scales declared decimals without rounding and independently checks solver quantities.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import reduce
from math import gcd, lcm
from typing import Any

from execplus.domain.allocation_constraints import selection_rules
from execplus.domain.decision_analysis import checksum, encoded, fail, number

METHOD = "cp-sat-integer-allocation-v1"
SENSITIVITY_METHOD = "cp-sat-capacity-sensitivity-v2"
SCHEDULE_METHOD = "cp-sat-scheduled-allocation-v1"
VERSION = "multi-resource-allocation-v1"
INTEGER_LIMIT = 2**53 - 1


@dataclass(frozen=True)
class IntegerAllocation:
    benefits: tuple[int, ...]
    resources: tuple[tuple[int, ...], ...]
    capacities: tuple[int, ...]
    minimum: tuple[int, ...]
    maximum: tuple[int, ...]
    requires: tuple[tuple[int, int], ...]
    excludes: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class SolverOutcome:
    status: str
    quantities: tuple[int, ...] | None
    objective: int | None
    termination: str = "solver_completed"


@dataclass(frozen=True)
class AllocationCandidate:
    label: str
    benefit: Decimal
    resources: tuple[Decimal, ...]
    minimum: int
    maximum: int


@dataclass(frozen=True)
class AllocationProblem:
    candidates: tuple[AllocationCandidate, ...]
    resource_names: tuple[str, ...]
    capacities: tuple[Decimal, ...]
    rules: dict[str, list[dict[str, str]]]
    integers: IntegerAllocation
    benefit_step: Fraction
    resource_steps: tuple[Fraction, ...]


def is_large_allocation(raw: dict[str, Any]) -> bool:
    return raw.get("kind") == "bounded_allocation" and raw.get("model") in {
        METHOD,
        SENSITIVITY_METHOD,
        SCHEDULE_METHOD,
    }


def exact_scale(
    values: tuple[Decimal, ...], maxima: tuple[int, ...]
) -> tuple[tuple[int, ...], Fraction]:
    fractions = tuple(Fraction(value) for value in values)
    denominator = lcm(*(value.denominator for value in fractions))
    scaled = tuple(value.numerator * (denominator // value.denominator) for value in fractions)
    divisor = reduce(gcd, scaled) or 1
    integers = tuple(value // divisor for value in scaled)
    if (
        any(value < 0 or value > INTEGER_LIMIT for value in integers)
        or sum(value * maximum for value, maximum in zip(integers, maxima, strict=True))
        > INTEGER_LIMIT
    ):
        fail(
            "allocation_integer_limit",
            "These exact decimal scales exceed the bounded integer solver. "
            "Use a smaller quantity range or separately prepared units; no values were rounded.",
        )
    return integers, Fraction(divisor, denominator)


def prepare_allocation(raw: dict[str, Any], rows: tuple[tuple[Any, ...], ...]) -> AllocationProblem:
    if raw.get("assumptions_confirmed") is not True:
        fail(
            "decision_assumptions_required",
            "Confirm fixed per-unit resources and additive benefits.",
        )
    if not 1 <= len(rows) <= 50:
        fail("invalid_candidates", "Use 1-50 complete, uniquely identified action rows.")
    extras = raw.get("resources", [])
    if not isinstance(extras, list) or len(extras) > 3:
        fail("invalid_constraints", "Use the budget and at most three additional resources.")
    resource_names = (raw["cost_column"], *(item["column"] for item in extras))
    capacities = tuple(number(value) for value in [raw["budget"], *(r["capacity"] for r in extras)])
    if any(value < 0 for value in capacities):
        fail("invalid_budget", "Every resource capacity must be nonnegative.")
    default = raw["maximum_quantity"]
    if type(default) is not int or not 0 <= default <= 100:
        fail("invalid_constraints", "Use whole quantities from 0 through 100.")
    supplied = raw.get("bounds", [])
    bounds = {item["candidate"]: (item["minimum"], item["maximum"]) for item in supplied}
    if len(bounds) != len(supplied):
        fail("invalid_constraints", "Declare each action bound once.")
    candidates = []
    labels: set[str] = set()
    for row in rows:
        if len(row) != 3 + len(extras) or row[0] is None:
            fail("invalid_candidates", "Every action needs an identifier and complete measures.")
        label = str(row[0])
        if not label.strip() or len(label) > 200 or label in labels:
            fail("invalid_candidates", "Use a unique, nonempty identifier for each action row.")
        labels.add(label)
        cost, benefit = number(row[1]), number(row[2])
        resources = (cost, *(number(value) for value in row[3:]))
        lower, upper = bounds.get(label, (0, default))
        if (
            cost <= 0
            or benefit < 0
            or any(value < 0 for value in resources)
            or type(lower) is not int
            or type(upper) is not int
            or not 0 <= lower <= upper <= 100
        ):
            fail(
                "invalid_constraints",
                "Use positive costs, nonnegative benefits/resources and quantities 0-100.",
            )
        candidates.append(AllocationCandidate(label, benefit, resources, lower, upper))
    if set(bounds) - labels:
        fail("invalid_constraints", "Quantity bounds reference an unknown action.")
    ordered = tuple(sorted(candidates, key=lambda candidate: candidate.label))
    minimum, maximum = tuple(c.minimum for c in ordered), tuple(c.maximum for c in ordered)
    benefits, benefit_step = exact_scale(tuple(c.benefit for c in ordered), maximum)
    scaled_resources, resource_steps, scaled_capacities = [], [], []
    for index, capacity in enumerate(capacities):
        integers, step = exact_scale(
            (*[c.resources[index] for c in ordered], capacity), (*maximum, 0)
        )
        scaled_resources.append(integers[:-1])
        scaled_capacities.append(integers[-1])
        resource_steps.append(step)
    rules = (
        selection_rules(labels, raw.get("prerequisites", []), raw.get("exclusions", []))
        if raw.get("prerequisites") or raw.get("exclusions")
        else {"prerequisites": [], "exclusions": []}
    )
    indexes = {c.label: index for index, c in enumerate(ordered)}
    problem_integers = IntegerAllocation(
        benefits,
        tuple(scaled_resources),
        tuple(scaled_capacities),
        minimum,
        maximum,
        tuple((indexes[r["candidate"]], indexes[r["requires"]]) for r in rules["prerequisites"]),
        tuple((indexes[r["first"]], indexes[r["second"]]) for r in rules["exclusions"]),
    )
    return AllocationProblem(
        ordered,
        resource_names,
        capacities,
        rules,
        problem_integers,
        benefit_step,
        tuple(resource_steps),
    )


def checked_allocation(problem: AllocationProblem, outcome: SolverOutcome) -> dict[str, Any]:
    if outcome.status not in {
        "OPTIMAL",
        "FEASIBLE",
        "INFEASIBLE",
        "UNKNOWN",
    } or outcome.termination not in {"solver_completed", "hard_wall_limit"}:
        fail("allocation_solver_evidence", "The allocation solver returned invalid evidence.")
    has_solution = outcome.status in {"OPTIMAL", "FEASIBLE"}
    if (not has_solution and (outcome.quantities is not None or outcome.objective is not None)) or (
        outcome.termination == "hard_wall_limit" and outcome.status != "UNKNOWN"
    ):
        fail("allocation_solver_evidence", "The allocation solver returned inconsistent evidence.")
    quantities = outcome.quantities
    allocations: list[dict[str, Any]] = []
    cost: Decimal | None = None
    benefit: Decimal | None = None
    used: list[Decimal] | None = None
    with localcontext() as context:
        context.prec = 256
        if has_solution:
            if (
                quantities is None
                or len(quantities) != len(problem.candidates)
                or any(
                    type(q) is not int or not c.minimum <= q <= c.maximum
                    for c, q in zip(problem.candidates, quantities, strict=True)
                )
            ):
                fail(
                    "allocation_solver_evidence", "The proposed quantities fail independent checks."
                )
            selected = {
                c.label for c, q in zip(problem.candidates, quantities, strict=True) if q > 0
            }
            if any(
                r["candidate"] in selected and r["requires"] not in selected
                for r in problem.rules["prerequisites"]
            ) or any(
                r["first"] in selected and r["second"] in selected
                for r in problem.rules["exclusions"]
            ):
                fail(
                    "allocation_solver_evidence", "The proposed selection violates declared rules."
                )
            used = [
                sum(
                    (
                        c.resources[index] * q
                        for c, q in zip(problem.candidates, quantities, strict=True)
                    ),
                    Decimal(0),
                )
                for index in range(len(problem.capacities))
            ]
            if any(
                value > capacity for value, capacity in zip(used, problem.capacities, strict=True)
            ):
                fail(
                    "allocation_solver_evidence", "The proposed quantities exceed resource limits."
                )
            benefit = sum(
                (c.benefit * q for c, q in zip(problem.candidates, quantities, strict=True)),
                Decimal(0),
            )
            if (
                type(outcome.objective) is not int
                or Fraction(benefit) != outcome.objective * problem.benefit_step
            ):
                fail(
                    "allocation_solver_evidence",
                    "The objective differs from exact source arithmetic.",
                )
            cost = used[0]
            allocations = [
                dict(
                    candidate=c.label,
                    quantity=q,
                    minimum=c.minimum,
                    maximum=c.maximum,
                    unit_cost=encoded(c.resources[0]),
                    unit_benefit=encoded(c.benefit),
                    cost=encoded(c.resources[0] * q),
                    benefit=encoded(c.benefit * q),
                    resources=[
                        dict(column=name, per_unit=encoded(value), used=encoded(value * q))
                        for name, value in zip(problem.resource_names, c.resources, strict=True)
                    ],
                )
                for c, q in zip(problem.candidates, quantities, strict=True)
            ]
        resource_totals = [
            dict(
                column=name,
                capacity=encoded(capacity),
                used=encoded(used[index]) if used is not None else None,
                unused=encoded(capacity - used[index]) if used is not None else None,
            )
            for index, (name, capacity) in enumerate(
                zip(problem.resource_names, problem.capacities, strict=True)
            )
        ]
        reason = {
            "OPTIMAL": "The solver proved maximum benefit within the declared integer model.",
            "FEASIBLE": "A checked feasible selection was found; maximum benefit was not proved.",
            "INFEASIBLE": "The solver proved no selection meets all declared limits and rules.",
            "UNKNOWN": (
                "The bounded search returned no proven outcome or usable selection. "
                "No action is recommended."
            ),
        }[outcome.status]
        return dict(
            version=VERSION,
            method_version=METHOD,
            status="feasible" if has_solution else outcome.status.lower(),
            solver_status=outcome.status.lower(),
            reason=reason,
            budget=encoded(problem.capacities[0]),
            cost=encoded(cost) if cost is not None else None,
            benefit=encoded(benefit) if benefit is not None else None,
            unused_budget=encoded(problem.capacities[0] - cost) if cost is not None else None,
            baseline=dict(
                cost="0", benefit="0", feasible=all(c.minimum == 0 for c in problem.candidates)
            ),
            resources=resource_totals,
            selection_rules=problem.rules,
            allocations=allocations,
            verification=dict(
                quantities="passed",
                resources="passed",
                selection_rules="passed",
                objective="passed",
            )
            if has_solution
            else None,
            solver_evidence=dict(
                version="bounded-cp-sat-v1",
                solver="OR-Tools CP-SAT",
                solver_version="9.15.6755",
                problem_checksum=checksum(asdict(problem.integers)),
                **{
                    **asdict(outcome),
                    "quantities": list(outcome.quantities)
                    if outcome.quantities is not None
                    else None,
                },
            ),
            assumptions=[
                "Each source row describes one unique action with fixed per-unit resources "
                "and additive benefits.",
                "Selecting an action means a positive integer quantity; "
                "prerequisites need at least one unit.",
                "Declared benefit is an input assumption, not an estimated causal effect.",
            ],
            limitations=[
                "At most 50 actions, four resources, quantities 0-100 and 40 rules of each kind.",
                "One solver worker, 1.5 seconds solver wall time, 0.25 deterministic seconds, "
                "4 seconds process wall time and 768 MiB address-space limit.",
                "A feasible result is independently checked, "
                "but only solver status optimal proves the model optimum.",
                "Tied optima have no promised cost or lexical tie-break; "
                "a timed search can return a different feasible selection when run again.",
                "Saved reopening verifies original source evidence and retained quantities; "
                "it does not rerun the time-bounded search.",
                "No external action executes; human approval is a recorded decision only.",
            ],
        )


def reopen_allocation(problem: AllocationProblem, retained: dict[str, Any]) -> dict[str, Any]:
    return checked_allocation(problem, retained_outcome(retained))


def retained_outcome(retained: dict[str, Any]) -> SolverOutcome:
    evidence = retained["solver_evidence"]
    quantities = evidence["quantities"]
    return SolverOutcome(
        evidence["status"],
        tuple(quantities) if quantities is not None else None,
        evidence["objective"],
        evidence["termination"],
    )
