"""Compare explicit resource capacities with retained, independently checked solutions.

At most six bounded searches share one authorized source projection. Reopening
rechecks their retained outcomes and never repeats time-limited optimization.
"""

from decimal import Decimal, localcontext
from typing import Any

from execplus.domain.decision_analysis import encoded, fail, number
from execplus.domain.large_allocation import (
    SENSITIVITY_METHOD,
    AllocationProblem,
    SolverOutcome,
    checked_allocation,
    prepare_allocation,
    retained_outcome,
)

VERSION = "multi-resource-allocation-v2"


def sensitivity(raw: dict[str, Any]) -> dict[str, Any]:
    value = raw.get("capacity_sensitivity")
    if (
        raw.get("model") != SENSITIVITY_METHOD
        or not isinstance(value, dict)
        or set(value) != {"column", "unit", "capacities"}
        or not isinstance(value["column"], str)
        or not isinstance(value["unit"], str)
        or not value["unit"].strip()
        or len(value["unit"]) > 100
        or value["column"]
        not in [raw["cost_column"], *(v["column"] for v in raw.get("resources", []))]
        or not isinstance(value["capacities"], list)
        or not 2 <= len(value["capacities"]) <= 5
        or any(not isinstance(v, str) for v in value["capacities"])
    ):
        fail(
            "allocation_sensitivity",
            "Choose one declared resource, its unit and two to five capacities.",
        )
    values = [number(v) for v in value["capacities"]]
    if any(v < 0 for v in values) or len(set(values)) != len(values) or values != sorted(values):
        fail("allocation_sensitivity", "Use distinct increasing nonnegative capacities.")
    return {**value, "capacities": [encoded(v) for v in values]}


def prepare_sensitivity(
    raw: dict[str, Any], rows: tuple[tuple[Any, ...], ...]
) -> tuple[AllocationProblem, ...]:
    declared = sensitivity(raw)
    problems = [prepare_allocation(raw, rows)]
    for capacity in declared["capacities"]:
        candidate = {**raw, "resources": [dict(v) for v in raw.get("resources", [])]}
        if declared["column"] == raw["cost_column"]:
            candidate["budget"] = capacity
        else:
            for resource in candidate["resources"]:
                if resource["column"] == declared["column"]:
                    resource["capacity"] = capacity
        problems.append(prepare_allocation(candidate, rows))
    return tuple(problems)


def infeasibility_reasons(problem: AllocationProblem) -> list[dict[str, Any]]:
    forced = {c.label: c.minimum for c in problem.candidates}
    changed = True
    while changed:
        changed = False
        for rule in problem.rules["prerequisites"]:
            if forced[rule["candidate"]] > 0 and not forced[rule["requires"]]:
                forced[rule["requires"]] = 1
                changed = True
    reasons: list[dict[str, Any]] = []
    for candidate in problem.candidates:
        if forced[candidate.label] > candidate.maximum:
            reasons.append(
                dict(
                    code="required_action_unavailable",
                    candidate=candidate.label,
                    required_minimum=forced[candidate.label],
                    maximum=candidate.maximum,
                    proof="Mandatory quantities and their prerequisite closure "
                    "exceed this action's maximum.",
                )
            )
    for rule in problem.rules["exclusions"]:
        if forced[rule["first"]] and forced[rule["second"]]:
            reasons.append(
                dict(
                    code="mandatory_actions_excluded",
                    **rule,
                    proof="Both excluded actions are required by minimum quantities "
                    "or prerequisite closure.",
                )
            )
    with localcontext() as context:
        context.prec = 256
        for index, (name, capacity) in enumerate(
            zip(problem.resource_names, problem.capacities, strict=True)
        ):
            used = sum(
                (c.resources[index] * forced[c.label] for c in problem.candidates), Decimal(0)
            )
            if used > capacity:
                reasons.append(
                    dict(
                        code="mandatory_resource_exceeds_capacity",
                        column=name,
                        minimum_required=encoded(used),
                        capacity=encoded(capacity),
                        shortfall=encoded(used - capacity),
                        proof="Nonnegative resources consumed by mandatory quantities "
                        "and prerequisite closure exceed this capacity.",
                    )
                )
    return [
        {**reason, "proof_kind": "exact_constraint", "forced_quantities": forced}
        for reason in reasons
    ]


def _checked(problem: AllocationProblem, outcome: SolverOutcome) -> dict[str, Any]:
    value = checked_allocation(problem, outcome)
    value["infeasibility"] = (
        (
            infeasibility_reasons(problem)
            or [
                dict(
                    code="joint_model_infeasible",
                    proof_kind="solver_result",
                    proof="The solver reports the complete model infeasible. "
                    "No independent minimal conflict or relaxation is claimed.",
                )
            ]
        )
        if outcome.status == "INFEASIBLE"
        else []
    )
    return value


def checked_sensitivity(
    raw: dict[str, Any],
    problems: tuple[AllocationProblem, ...],
    outcomes: tuple[SolverOutcome, ...],
) -> dict[str, Any]:
    declared = sensitivity(raw)
    if len(problems) != len(outcomes) or len(problems) != len(declared["capacities"]) + 1:
        fail(
            "allocation_solver_evidence",
            "Every declared capacity needs its own retained solver evidence.",
        )
    baseline = _checked(problems[0], outcomes[0])
    variants = []
    for capacity, problem, outcome in zip(
        declared["capacities"], problems[1:], outcomes[1:], strict=True
    ):
        value = _checked(problem, outcome)
        with localcontext() as context:
            context.prec = 256
            difference = (
                {
                    field: encoded(Decimal(value[field]) - Decimal(baseline[field]))
                    for field in ("benefit", "cost")
                }
                if baseline["status"] == value["status"] == "feasible"
                else None
            )
        variants.append(dict(capacity=capacity, result=value, difference=difference))
    baseline.update(
        version=VERSION,
        method_version=SENSITIVITY_METHOD,
        capacity_sensitivity=dict(
            column=declared["column"],
            unit=declared["unit"],
            baseline_capacity=encoded(
                problems[0].capacities[problems[0].resource_names.index(declared["column"])]
            ),
            variants=variants,
            approval_scope="original_baseline_only",
        ),
    )
    baseline["limitations"].extend(
        [
            "At most six sequential bounded solves: one original model "
            "and two to five declared capacity alternatives.",
            "Differences compare independently checked selections; "
            "feasible-only results do not establish optimal sensitivity.",
            "Only the original capacity model can receive this result's approval. "
            "Save a separate model to review an alternative.",
            "Alternative capacities are explicit hypothetical assumptions, "
            "not estimated probabilities or causal uplift.",
        ]
    )
    return baseline


def reopen_sensitivity(
    raw: dict[str, Any], rows: tuple[tuple[Any, ...], ...], retained: dict[str, Any]
) -> dict[str, Any]:
    variants = retained["capacity_sensitivity"]["variants"]
    outcomes = (retained_outcome(retained), *(retained_outcome(v["result"]) for v in variants))
    return checked_sensitivity(raw, prepare_sensitivity(raw, rows), outcomes)
