"""Use case: Detects unusual numerical distributions and solves declared allocation decisions.

What it does: Provides versioned bounded methods with exact evidence and explicit assumptions.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, NoReturn
from uuid import UUID

from execplus.domain.ingestion import IngestionError

VERSION = "decision-analysis-v1"
METHODS = {
    "robust_distribution": "weighted-mad-iqr-v1",
    "bounded_allocation": "integer-budget-v1",
}


@dataclass(frozen=True)
class AnalysisRun:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    owner_id: UUID
    upload_id: UUID
    revision_id: UUID
    understanding_id: UUID
    name: str
    kind: str
    method_version: str
    request: dict[str, Any]
    evidence: dict[str, Any]
    result: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class AnalysisReview:
    id: UUID
    workspace_id: UUID
    run_id: UUID
    owner_id: UUID
    sequence: int
    target: str
    status: str
    note: str
    created_at: datetime


def fail(code: str, message: str) -> NoReturn:
    raise IngestionError(code, message, 422)


def number(value: object) -> Decimal:
    if isinstance(value, bool) or value is None or len(str(value)) > 200:
        fail("invalid_analysis_number", "Use finite bounded numerical values.")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        fail("invalid_analysis_number", "Use finite bounded numerical values.")
    if not result.is_finite() or result.copy_abs() >= Decimal("1e38"):
        fail("invalid_analysis_number", "Values must be finite and smaller than 1e38.")
    exponent = result.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -38:
        fail("invalid_analysis_number", "Use at most 38 decimal places.")
    return result


def encoded(value: Decimal) -> str:
    return format(value, "f")


def checksum(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def quantile(values: list[tuple[Decimal, int]], count: int, fraction: Decimal) -> Decimal:
    position = Decimal(count - 1) * fraction
    lower = int(position)
    weight = position - lower

    def at(index: int) -> Decimal:
        accumulated = 0
        for value, frequency in values:
            accumulated += frequency
            if index < accumulated:
                return value
        raise ValueError("Invalid weighted distribution")

    left = at(lower)
    return left if not weight else left + weight * (at(lower + 1) - left)


def detect_distribution(
    rows: list[tuple[object, object]], threshold: object = "3.5", materiality: object = "0"
) -> dict[str, Any]:
    limit, minimum = number(threshold), number(materiality)
    if not Decimal(3) <= limit <= Decimal(10) or minimum < 0:
        fail("invalid_detector", "Threshold must be 3-10 and materiality nonnegative.")
    if not rows or len(rows) > 1000:
        fail("analysis_size", "Use a measure with 1-1,000 distinct values.")
    merged: dict[Decimal, int] = {}
    for raw, frequency in rows:
        if type(frequency) is not int or not 1 <= frequency <= 200000:
            fail("invalid_distribution", "The distribution counts are invalid.")
        value = number(raw)
        merged[value] = merged.get(value, 0) + frequency
    values = sorted(merged.items())
    count = sum(merged.values())
    if not 8 <= count <= 200000:
        fail("insufficient_analysis_data", "Use 8-200,000 complete numerical records.")
    with localcontext() as context:
        context.prec = 128
        median = quantile(values, count, Decimal("0.5"))
        deviations: dict[Decimal, int] = {}
        for value, frequency in values:
            distance = abs(value - median)
            deviations[distance] = deviations.get(distance, 0) + frequency
        mad = quantile(sorted(deviations.items()), count, Decimal("0.5"))
        q1, q3 = (quantile(values, count, q) for q in (Decimal("0.25"), Decimal("0.75")))
        iqr = q3 - q1
        method = "mad" if mad else "iqr" if iqr else "constant_reference"
        lower, upper = q1 - limit * iqr, q3 + limit * iqr
        findings = []
        for value, frequency in values:
            distance = abs(value - median)
            score = Decimal("0.67448975") * distance / mad if mad else None
            unusual = score > limit if score is not None else value < lower or value > upper
            if unusual and distance >= minimum:
                findings.append(
                    dict(
                        id=hashlib.sha256(encoded(value).encode()).hexdigest()[:24],
                        value=encoded(value),
                        count=frequency,
                        absolute_difference=encoded(distance),
                        score=encoded(score) if score is not None else None,
                    )
                )
        return dict(
            version=VERSION,
            method_version=METHODS["robust_distribution"],
            method=method,
            sample_count=count,
            distinct_count=len(values),
            baseline=encoded(median),
            mad=encoded(mad),
            iqr=encoded(iqr),
            threshold=encoded(limit),
            materiality=encoded(minimum),
            findings=findings,
            flagged_records=sum(item["count"] for item in findings),
            limitations=[
                "Exploratory unusualness within this snapshot, not error, fraud or causal proof.",
                "Scores are not probabilities; "
                "the threshold has no calibrated false-alarm guarantee.",
                "Values are compared within the submitted filtered population, "
                "not across future periods.",
                "Zero MAD uses IQR fences; "
                "zero IQR uses the constant central reference without a score.",
            ],
        )


def allocate(
    rows: list[tuple[str, object, object]],
    budget: object,
    quantum: object,
    bounds: dict[str, tuple[int, int]],
    assumptions_confirmed: bool,
) -> dict[str, Any]:
    if assumptions_confirmed is not True:
        fail("decision_assumptions_required", "Confirm per-unit costs and linear benefits first.")
    if not 1 <= len(rows) <= 20 or len({row[0] for row in rows}) != len(rows):
        fail("invalid_candidates", "Use 1-20 uniquely identified candidate actions.")
    amount, step = number(budget), number(quantum)
    if amount < 0 or step <= 0:
        fail("invalid_budget", "Budget must be nonnegative and its quantum positive.")
    with localcontext() as context:
        context.prec = 128
        units = amount / step
        if units != units.to_integral_value() or units > 5000:
            fail("decision_budget_limit", "Budget must contain at most 5,000 exact quantum units.")
        total = int(units)
        if set(bounds) != {row[0] for row in rows}:
            fail("invalid_constraints", "Declare quantity bounds for every candidate exactly once.")
        candidates: list[tuple[str, Decimal, Decimal, int, int, int]] = []
        for label, raw_cost, raw_benefit in sorted(rows):
            cost, benefit = number(raw_cost), number(raw_benefit)
            minimum, maximum = bounds[label]
            if (
                not label
                or len(label) > 200
                or cost <= 0
                or benefit < 0
                or type(minimum) is not int
                or type(maximum) is not int
                or not 0 <= minimum <= maximum <= 10
            ):
                fail(
                    "invalid_constraints",
                    "Use positive costs, nonnegative benefits and quantities 0-10.",
                )
            candidate_units = cost / step
            if candidate_units != candidate_units.to_integral_value():
                fail(
                    "budget_quantum_mismatch",
                    "Every cost must be an exact multiple of the budget quantum.",
                )
            candidates.append((label, cost, benefit, int(candidate_units), minimum, maximum))
        work = (total + 1) * sum(c[5] - c[4] + 1 for c in candidates)
        if work > 1000000:
            fail("decision_work_limit", "Reduce the budget units, candidates or quantity ranges.")
        states: dict[int, tuple[Decimal, tuple[int, ...]]] = {0: (Decimal(0), ())}
        for _, _, benefit, cost_units, minimum, maximum in candidates:
            next_states: dict[int, tuple[Decimal, tuple[int, ...]]] = {}
            for spent, (gain, quantities) in states.items():
                for quantity in range(minimum, maximum + 1):
                    new_spent = spent + quantity * cost_units
                    if new_spent > total:
                        continue
                    candidate = (gain + quantity * benefit, (*quantities, quantity))
                    previous = next_states.get(new_spent)
                    if (
                        previous is None
                        or candidate[0] > previous[0]
                        or (candidate[0] == previous[0] and candidate[1] < previous[1])
                    ):
                        next_states[new_spent] = candidate
            states = next_states
        baseline_feasible = all(c[4] == 0 for c in candidates)
        base = dict(
            version=VERSION,
            method_version=METHODS["bounded_allocation"],
            status="feasible" if states else "infeasible",
            budget=encoded(amount),
            quantum=encoded(step),
            baseline=dict(cost="0", benefit="0", feasible=baseline_feasible),
            assumptions=[
                "Each candidate has fixed per-unit cost and additive linear per-unit benefit.",
                "Benefits and costs are user-confirmed decision assumptions, not causal estimates.",
            ],
            limitations=[
                "Optimal only for the declared single-budget integer allocation problem.",
                "No external action executes; human approval is a recorded decision only.",
            ],
        )
        if not states:
            return {
                **base,
                "allocations": [],
                "cost": None,
                "benefit": None,
                "reason": "Mandatory minimum quantities cannot fit the declared budget.",
            }
        spent, (gain, quantities) = min(
            states.items(), key=lambda item: (-item[1][0], item[0], item[1][1])
        )
        allocations = [
            dict(
                candidate=c[0],
                quantity=q,
                unit_cost=encoded(c[1]),
                unit_benefit=encoded(c[2]),
                cost=encoded(c[1] * q),
                benefit=encoded(c[2] * q),
                minimum=c[4],
                maximum=c[5],
            )
            for c, q in zip(candidates, quantities, strict=True)
        ]
        return {
            **base,
            "allocations": allocations,
            "cost": encoded(step * spent),
            "benefit": encoded(gain),
            "unused_budget": encoded(amount - step * spent),
            "optimality": "Exact optimum within the declared bounded model.",
            "tie_rule": "Highest benefit, then lowest cost, then lexical candidate quantities.",
        }
