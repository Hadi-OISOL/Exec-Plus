"""Use case: Extends private analysis with group baselines and a second resource limit.

What it does: Preserves legacy methods while bounding coverage and exact exhaustive decisions.
"""

from decimal import Decimal, localcontext
from itertools import product
from math import prod
from typing import Any

from execplus.domain.decision_analysis import (
    allocate,
    checksum,
    detect_distribution,
    encoded,
    fail,
    number,
)

SEGMENT_METHOD = "segmented-mad-iqr-v1"
RESOURCE_METHOD = "two-resource-enumeration-v1"


def detect_segments(
    rows: list[tuple[object, object, object]],
    threshold: object,
    materiality: object,
    minimum_support: int,
) -> dict[str, Any]:
    limit, minimum = number(threshold), number(materiality)
    if not Decimal(3) <= limit <= Decimal(10) or minimum < 0:
        fail("invalid_detector", "Threshold must be 3-10 and materiality nonnegative.")
    if type(minimum_support) is not int or not 8 <= minimum_support <= 1000:
        fail("invalid_segment_support", "Require 8-1,000 complete records per group.")
    if not 1 <= len(rows) <= 1000:
        fail("analysis_size", "Use at most 1,000 distinct group/value pairs.")
    grouped: dict[str | None, list[tuple[object, int]]] = {}
    total = 0
    for label, value, frequency in rows:
        if label is not None and (not isinstance(label, str) or len(label) > 200):
            fail("invalid_segment", "Use text groups of at most 200 characters.")
        if type(frequency) is not int or not 1 <= frequency <= 200000:
            fail("invalid_distribution", "The distribution counts are invalid.")
        if value is not None:
            number(value)
        grouped.setdefault(label, []).append((value, frequency))
        total += frequency
    if len(grouped) > 32 or total > 200000:
        fail("analysis_size", "Use at most 32 groups and 200,000 records.")
    groups: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    covered = 0
    for label in sorted(grouped, key=lambda value: (value is not None, value or "")):
        values = grouped[label]
        complete = [(value, frequency) for value, frequency in values if value is not None]
        count = sum(frequency for _, frequency in complete)
        group: dict[str, Any] = dict(
            segment=label,
            sample_count=count,
            missing_records=sum(frequency for value, frequency in values if value is None),
            status="missing_group"
            if label is None or not label.strip()
            else "insufficient_support"
            if count < minimum_support
            else "evaluated",
        )
        if group["status"] == "evaluated":
            result = detect_distribution(
                [(value, frequency) for value, frequency in complete], threshold, materiality
            )
            covered += count
            group.update(
                {
                    key: result[key]
                    for key in ("baseline", "mad", "iqr", "method", "flagged_records")
                }
            )
            findings.extend(
                {
                    **finding,
                    "segment": label,
                    "id": checksum(dict(segment=label, finding=finding["id"]))[:24],
                }
                for finding in result["findings"]
            )
        groups.append(group)
    return dict(
        version="segmented-analysis-v1",
        method_version=SEGMENT_METHOD,
        method="within_group",
        baseline=None,
        sample_count=total,
        covered_records=covered,
        excluded_records=total - covered,
        minimum_support=minimum_support,
        threshold=encoded(limit),
        materiality=encoded(minimum),
        groups=groups,
        findings=findings,
        flagged_records=sum(finding["count"] for finding in findings),
        limitations=[
            "Each eligible group has its own weighted median and MAD/IQR baseline.",
            "Missing groups, missing measures and undersized groups are not evaluated; "
            "there is no fallback to the whole population.",
            "Exploratory findings are not confirmed errors, fraud or causal effects.",
            "Scores are not probabilities; multiple groups have no calibrated false-alarm rate.",
            "This snapshot method does not detect seasonality, drift or multivariate anomalies.",
        ],
    )


def allocate_resources(
    rows: list[tuple[str, object, object, object]],
    budget: object,
    quantum: object,
    bounds: dict[str, tuple[int, int]],
    assumptions_confirmed: bool,
    resource_capacity: object,
) -> dict[str, Any]:
    capacity = number(resource_capacity)
    if capacity < 0:
        fail("invalid_resource_capacity", "The additional resource limit must be nonnegative.")
    base = allocate(
        [(r[0], r[1], r[2]) for r in rows], budget, quantum, bounds, assumptions_confirmed
    )
    candidates = [
        (label, number(cost), number(benefit), number(resource))
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
    best: tuple[Decimal, Decimal, Decimal, tuple[int, ...]] | None = None
    amount = number(budget)
    with localcontext() as ctx:
        ctx.prec = 128
        for quantities in product(*ranges):
            cost = sum(
                (row[1] * q for row, q in zip(candidates, quantities, strict=True)), Decimal(0)
            )
            resource = sum(
                (row[3] * q for row, q in zip(candidates, quantities, strict=True)), Decimal(0)
            )
            if cost > amount or resource > capacity:
                continue
            benefit = sum(
                (row[2] * q for row, q in zip(candidates, quantities, strict=True)), Decimal(0)
            )
            candidate = (-benefit, cost, resource, quantities)
            if best is None or candidate < best:
                best = candidate
        result: dict[str, Any] = dict(
            version="resource-allocation-v1",
            method_version=RESOURCE_METHOD,
            status="feasible" if best is not None else "infeasible",
            solver_status="optimal" if best is not None else "infeasible",
            budget=base["budget"],
            quantum=base["quantum"],
            baseline={**base["baseline"], "resource": "0"},
            resource_capacity=encoded(capacity),
            resource_used=None,
            unused_resource=None,
            cost=None,
            benefit=None,
            allocations=[],
            assumptions=[
                *base["assumptions"],
                "The second resource has fixed additive per-unit use.",
            ],
            limitations=[
                "Exact optimum only for this declared two-resource integer model.",
                "At most 100,000 combinations; no causal effects or external actions are inferred.",
            ],
            tie_rule="Highest benefit, lowest cost, lowest resource use, then lexical quantities.",
        )
        if best is None:
            result["reason"] = "Mandatory quantities cannot fit both declared resource limits."
            return result
        negative_gain, cost, resource, quantities = best
        result.update(
            cost=encoded(cost),
            benefit=encoded(-negative_gain),
            unused_budget=encoded(amount - cost),
            resource_used=encoded(resource),
            unused_resource=encoded(capacity - resource),
            optimality="Exact optimum within the declared bounded model.",
            allocations=[
                dict(
                    candidate=row[0],
                    quantity=q,
                    unit_cost=encoded(row[1]),
                    unit_benefit=encoded(row[2]),
                    unit_resource=encoded(row[3]),
                    cost=encoded(row[1] * q),
                    benefit=encoded(row[2] * q),
                    resource=encoded(row[3] * q),
                    minimum=bounds[row[0]][0],
                    maximum=bounds[row[0]][1],
                )
                for row, q in zip(candidates, quantities, strict=True)
            ],
        )
        return result
