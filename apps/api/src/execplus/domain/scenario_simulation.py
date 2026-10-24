"""Use case: Simulates declared low/likely/high driver ranges through the exact scenario formula.

What it does: Draws seeded independent triangular percentage changes, evaluates each draw
with the existing source scenario arithmetic and reports nearest-rank percentiles and the
share of draws beating a declared target. The stored seed makes replay identical.
"""

import random
from collections.abc import Callable
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from execplus.domain.decision_analysis import encoded, fail, number

METHOD = "triangular-monte-carlo-v1"
DRIVERS = ("price", "quantity", "variable_cost", "fixed_cost")
FIELDS = (
    "quantity",
    "revenue",
    "variable_cost",
    "fixed_cost",
    "total_cost",
    "contribution",
    "remaining",
    "margin_percent",
)
MIN_DRAWS, MAX_DRAWS = 1000, 10000
MAX_SEED = 2**32 - 1
PERCENTILES = (10, 50, 90)
DRAW_PLACES = Decimal("0.000001")

Outcome = Callable[[dict[str, Any]], dict[str, str | None]]


def _percent(value: object) -> Decimal:
    if not isinstance(value, str):
        fail("scenario_simulation", "Enter each percentage as an exact numerical string.")
    amount = number(value)
    if not Decimal(-100) <= amount <= Decimal(10000):
        fail("scenario_simulation", "Percentage changes must be between -100 and 10,000.")
    return amount


def validate_simulation(raw: dict[str, Any]) -> None:
    simulation = raw.get("simulation")
    if simulation is None:
        return
    if not isinstance(simulation, dict) or set(simulation) != {
        "drivers",
        "draws",
        "seed",
        "target",
    }:
        fail("scenario_simulation", "Declare drivers, draw count, seed and an optional target.")
    drivers = simulation["drivers"]
    if not isinstance(drivers, dict) or not 1 <= len(drivers) <= 4 or set(drivers) - set(DRIVERS):
        fail("scenario_simulation", "Choose one to four drivers with low, likely and high values.")
    for driver, bounds in drivers.items():
        if not isinstance(bounds, dict) or set(bounds) != {"low", "likely", "high"}:
            fail("scenario_simulation", "Declare low, likely and high percentage changes.")
        low, likely, high = (_percent(bounds[key]) for key in ("low", "likely", "high"))
        if not (low <= likely <= high and low < high):
            fail("scenario_simulation", "Use low ≤ likely ≤ high with low below high.")
        if driver == "fixed_cost" and not raw.get("fixed_cost_column"):
            fail("scenario_fixed_cost", "Choose a source fixed-cost column before varying it.")
    if type(simulation["draws"]) is not int or not MIN_DRAWS <= simulation["draws"] <= MAX_DRAWS:
        fail("scenario_simulation", "Use 1,000 to 10,000 simulation draws.")
    if type(simulation["seed"]) is not int or not 0 <= simulation["seed"] <= MAX_SEED:
        fail("scenario_simulation", "Use a whole-number seed from 0 to 4,294,967,295.")
    target = simulation["target"]
    if target is not None and (
        not isinstance(target, dict)
        or set(target) != {"field", "direction", "value"}
        or target["field"] not in FIELDS
        or target["direction"] not in {"above", "below"}
    ):
        fail("scenario_simulation", "Choose a known outcome, a direction and a target value.")
    if target is not None:
        number(target["value"])


def triangular(uniform: float, low: Decimal, likely: Decimal, high: Decimal) -> Decimal:
    """Inverse triangular CDF evaluated in Decimal so replay never depends on library code."""
    with localcontext() as context:
        context.prec, context.rounding = 50, ROUND_HALF_EVEN
        u, width = Decimal(uniform), high - low
        if u * width < likely - low:
            value = low + (u * width * (likely - low)).sqrt()
        else:
            value = high - ((1 - u) * width * (high - likely)).sqrt()
        return min(max(value.quantize(DRAW_PLACES), low), high)


def _rank(values: list[Decimal], percentile: int) -> Decimal:
    return values[(percentile * len(values) + 99) // 100 - 1]


def simulate(raw: dict[str, Any], outcome: Outcome) -> dict[str, Any]:
    validate_simulation(raw)
    simulation = raw["simulation"]
    declared = {key: simulation["drivers"][key] for key in DRIVERS if key in simulation["drivers"]}
    bounds = {
        key: tuple(_percent(value[name]) for name in ("low", "likely", "high"))
        for key, value in declared.items()
    }
    rng = random.Random(simulation["seed"])
    collected: dict[str, list[Decimal] | None] = {field: [] for field in FIELDS}
    for _ in range(simulation["draws"]):
        changes = dict.fromkeys(DRIVERS, "0") | {
            key: encoded(triangular(rng.random(), *values)) for key, values in bounds.items()
        }
        result = outcome(changes)
        for field in FIELDS:
            values = collected[field]
            if values is not None:
                if result[field] is None:
                    collected[field] = None
                else:
                    values.append(Decimal(str(result[field])))
    summary: dict[str, Any] = {}
    for field, values in collected.items():
        if values is None:
            summary[field] = None
            continue
        ordered = sorted(values)
        summary[field] = {f"p{p}": encoded(_rank(ordered, p)) for p in PERCENTILES} | dict(
            minimum=encoded(ordered[0]), maximum=encoded(ordered[-1])
        )
    target = simulation["target"]
    probability = None
    if target is not None:
        values = collected[target["field"]]
        if values is not None:
            limit = number(target["value"])
            hits = sum(
                value > limit if target["direction"] == "above" else value < limit
                for value in values
            )
            with localcontext() as context:
                context.prec = 28
                share = Decimal(hits) / Decimal(len(values))
                error = (share * (1 - share) / Decimal(len(values))).sqrt()
            probability = dict(
                field=target["field"],
                direction=target["direction"],
                value=encoded(limit),
                draws_beating=hits,
                share=encoded(share),
                monte_carlo_standard_error=encoded(error),
            )
    return dict(
        method=METHOD,
        label="Simulation under the stated assumptions, not a forecast or guarantee.",
        reference="original_baseline_other_changes_zero",
        seed=simulation["seed"],
        draws=simulation["draws"],
        drivers={
            key: dict(zip(("low", "likely", "high"), map(encoded, values), strict=True))
            for key, values in bounds.items()
        },
        percentiles=summary,
        target_probability=probability,
        percentile_rule="nearest rank over all draws",
        assumptions=[
            "Each listed driver follows its own triangular low/likely/high range.",
            "Drivers are drawn independently; real drivers can move together.",
            "Unlisted drivers stay at zero change from the original baseline.",
            "Each draw runs the same exact scenario arithmetic as the alternatives.",
        ],
        limitations=[
            "Shares are frequencies among seeded draws, not calibrated probabilities "
            "of real outcomes; they inherit every assumption above.",
            "Sampled percentages are rounded to six decimal places before evaluation.",
            "Margin percentiles are unavailable when any draw has zero revenue.",
        ],
    )
