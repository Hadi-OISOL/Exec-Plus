"""Use case: Solves bounded allocations with explicit action-selection rules.

What it does: Enumerates exact quantities and independently checks every proposed selection.
"""

from decimal import Decimal, localcontext
from itertools import product
from math import prod
from typing import Any

from execplus.domain.decision_analysis import allocate, encoded, fail, number

RULE_METHOD = "selection-rules-enumeration-v1"


def selection_rules(
    labels: set[str], prerequisites: object, exclusions: object
) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for name, raw, keys in (
        ("prerequisites", prerequisites, ("candidate", "requires")),
        ("exclusions", exclusions, ("first", "second")),
    ):
        if not isinstance(raw, list) or len(raw) > 40:
            fail("invalid_selection_rules", "Use at most 40 rules of each kind.")
        seen: set[tuple[str, str]] = set()
        for entry in raw:
            if not isinstance(entry, dict) or set(entry) != set(keys):
                fail("invalid_selection_rules", "Each selection rule needs two named actions.")
            first, second = entry[keys[0]], entry[keys[1]]
            if (
                not isinstance(first, str)
                or not isinstance(second, str)
                or first not in labels
                or second not in labels
                or first == second
            ):
                fail(
                    "invalid_selection_rules",
                    "Each rule must name two different actions in the selected source.",
                )
            edge = (first, second) if name == "prerequisites" or first < second else (second, first)
            if edge in seen:
                fail("invalid_selection_rules", "Declare each selection rule only once.")
            seen.add(edge)
        result[name] = [dict(zip(keys, edge, strict=True)) for edge in sorted(seen)]
    if not any(result.values()):
        fail("invalid_selection_rules", "Declare at least one prerequisite or exclusion.")
    graph: dict[str, list[str]] = {label: [] for label in labels}
    for rule in result["prerequisites"]:
        graph[rule["candidate"]].append(rule["requires"])
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(label: str) -> None:
        if label in visiting:
            fail(
                "cyclic_selection_rules",
                "Prerequisites cannot form a loop. These are selection rules, not a schedule.",
            )
        if label in visited:
            return
        visiting.add(label)
        for required in graph[label]:
            visit(required)
        visiting.remove(label)
        visited.add(label)

    for label in sorted(labels):
        visit(label)
    return result


def verify_selection_result(
    rows: list[tuple[str, object, object, object | None]],
    budget: object,
    bounds: dict[str, tuple[int, int]],
    rules: dict[str, list[dict[str, str]]],
    result: dict[str, Any],
    resource_capacity: object | None = None,
) -> None:
    """Recalculate a selected result from original inputs, separately from enumeration."""
    invalid = "The proposed quantities failed independent checking; no recommendation was saved."
    if result.get("selection_rules") != rules or result.get("method_version") != RULE_METHOD:
        fail("allocation_verification_failed", invalid)
    if result.get("status") == "infeasible":
        if result.get("allocations") != [] or any(
            result.get(key) is not None for key in ("cost", "benefit", "resource_used")
        ):
            fail("allocation_verification_failed", invalid)
        return
    entries = result.get("allocations", [])
    if result.get("status") != "feasible" or len(entries) != len(rows):
        fail("allocation_verification_failed", invalid)
    expected = {row[0]: row for row in rows}
    quantities: dict[str, int] = {}
    with localcontext() as context:
        context.prec = 128
        total_cost = total_benefit = total_resource = Decimal(0)
        for entry in entries:
            label, quantity = entry.get("candidate"), entry.get("quantity")
            if (
                label not in expected
                or label in quantities
                or type(quantity) is not int
                or not bounds[label][0] <= quantity <= bounds[label][1]
            ):
                fail("allocation_verification_failed", invalid)
            quantities[label] = quantity
            _, raw_cost, raw_benefit, raw_resource = expected[label]
            cost, benefit = number(raw_cost), number(raw_benefit)
            per_entry = dict(
                unit_cost=encoded(cost),
                unit_benefit=encoded(benefit),
                cost=encoded(cost * quantity),
                benefit=encoded(benefit * quantity),
                minimum=bounds[label][0],
                maximum=bounds[label][1],
            )
            total_cost += cost * quantity
            total_benefit += benefit * quantity
            if resource_capacity is not None:
                resource = number(raw_resource)
                total_resource += resource * quantity
                per_entry.update(
                    unit_resource=encoded(resource), resource=encoded(resource * quantity)
                )
            if any(entry.get(key) != value for key, value in per_entry.items()):
                fail("allocation_verification_failed", invalid)
        for rule in rules["prerequisites"]:
            if quantities[rule["candidate"]] > 0 and quantities[rule["requires"]] < 1:
                fail("allocation_verification_failed", invalid)
        for rule in rules["exclusions"]:
            if quantities[rule["first"]] > 0 and quantities[rule["second"]] > 0:
                fail("allocation_verification_failed", invalid)
        amount = number(budget)
        totals = dict(
            budget=encoded(amount),
            cost=encoded(total_cost),
            benefit=encoded(total_benefit),
            unused_budget=encoded(amount - total_cost),
        )
        if total_cost > amount:
            fail("allocation_verification_failed", invalid)
        if resource_capacity is not None:
            capacity = number(resource_capacity)
            if total_resource > capacity:
                fail("allocation_verification_failed", invalid)
            totals.update(
                resource_capacity=encoded(capacity),
                resource_used=encoded(total_resource),
                unused_resource=encoded(capacity - total_resource),
            )
        if any(result.get(key) != value for key, value in totals.items()):
            fail("allocation_verification_failed", invalid)


def allocate_selection_rules(
    rows: list[tuple[str, object, object, object | None]],
    budget: object,
    quantum: object,
    bounds: dict[str, tuple[int, int]],
    assumptions_confirmed: bool,
    prerequisites: object,
    exclusions: object,
    resource_capacity: object | None = None,
) -> dict[str, Any]:
    # Retain the existing validation and work bounds before adding rule constraints.
    base = allocate(
        [(r[0], r[1], r[2]) for r in rows], budget, quantum, bounds, assumptions_confirmed
    )
    rules = selection_rules({row[0] for row in rows}, prerequisites, exclusions)
    capacity = None if resource_capacity is None else number(resource_capacity)
    if capacity is not None and capacity < 0:
        fail("invalid_resource_capacity", "The additional resource limit must be nonnegative.")
    candidates = [
        (
            label,
            number(cost),
            number(benefit),
            number(resource) if capacity is not None else Decimal(0),
        )
        for label, cost, benefit, resource in sorted(rows)
    ]
    if any(row[3] < 0 for row in candidates):
        fail("invalid_resource_cost", "Per-unit resource use must be nonnegative.")
    ranges = [range(bounds[row[0]][0], bounds[row[0]][1] + 1) for row in candidates]
    if prod(len(values) for values in ranges) > 100000:
        fail(
            "decision_work_limit",
            "Reduce quantities or candidates to at most 100,000 combinations.",
        )
    indexes = {row[0]: index for index, row in enumerate(candidates)}
    required = [(indexes[r["candidate"]], indexes[r["requires"]]) for r in rules["prerequisites"]]
    excluded = [(indexes[r["first"]], indexes[r["second"]]) for r in rules["exclusions"]]
    best: tuple[Decimal, Decimal, Decimal, tuple[int, ...]] | None = None
    amount = number(budget)
    with localcontext() as context:
        context.prec = 128
        for quantities in product(*ranges):
            if any(quantities[a] and not quantities[b] for a, b in required) or any(
                quantities[a] and quantities[b] for a, b in excluded
            ):
                continue
            cost = sum(
                (row[1] * q for row, q in zip(candidates, quantities, strict=True)), Decimal(0)
            )
            benefit = sum(
                (row[2] * q for row, q in zip(candidates, quantities, strict=True)), Decimal(0)
            )
            resource = sum(
                (row[3] * q for row, q in zip(candidates, quantities, strict=True)), Decimal(0)
            )
            if cost > amount or (capacity is not None and resource > capacity):
                continue
            candidate = (-benefit, cost, resource, quantities)
            if best is None or candidate < best:
                best = candidate
        result: dict[str, Any] = dict(
            version="selection-allocation-v1",
            method_version=RULE_METHOD,
            status="feasible" if best is not None else "infeasible",
            solver_status="optimal" if best is not None else "infeasible",
            budget=base["budget"],
            quantum=base["quantum"],
            baseline=base["baseline"],
            selection_rules=rules,
            cost=None,
            benefit=None,
            allocations=[],
            assumptions=[
                *base["assumptions"],
                "Selecting an action means a positive quantity; "
                "its prerequisites need at least one unit.",
                "Excluded actions cannot both have a positive quantity.",
            ],
            limitations=[
                "Exact optimum only within the declared bounded allocation and selection rules.",
                "At most 100,000 combinations; "
                "prerequisites are not timing or scheduling constraints.",
                "No causal effects or external actions are inferred; approval is a record only.",
            ],
            tie_rule="Highest benefit, lowest cost, "
            + ("lowest resource use, " if capacity is not None else "")
            + "then lexical candidate quantities.",
        )
        if capacity is not None:
            result.update(
                resource_capacity=encoded(capacity),
                resource_used=None,
                unused_resource=None,
                baseline={**base["baseline"], "resource": "0"},
            )
            result["assumptions"].append("The second resource has fixed additive per-unit use.")
        if best is None:
            result["reason"] = (
                "No quantities satisfy all declared bounds, resource limits and selection rules."
            )
        else:
            negative_gain, cost, resource, quantities = best
            result.update(
                cost=encoded(cost),
                benefit=encoded(-negative_gain),
                unused_budget=encoded(amount - cost),
                optimality="Exact optimum within the declared bounded model.",
                allocations=[
                    dict(
                        candidate=row[0],
                        quantity=q,
                        unit_cost=encoded(row[1]),
                        unit_benefit=encoded(row[2]),
                        cost=encoded(row[1] * q),
                        benefit=encoded(row[2] * q),
                        minimum=bounds[row[0]][0],
                        maximum=bounds[row[0]][1],
                        **(
                            dict(unit_resource=encoded(row[3]), resource=encoded(row[3] * q))
                            if capacity is not None
                            else {}
                        ),
                    )
                    for row, q in zip(candidates, quantities, strict=True)
                ],
            )
            if capacity is not None:
                result.update(
                    resource_used=encoded(resource), unused_resource=encoded(capacity - resource)
                )
        verify_selection_result(rows, budget, bounds, rules, result, resource_capacity)
        if best is not None:
            result["verification"] = dict(
                quantities="passed", resources="passed", selection_rules="passed"
            )
        return result
