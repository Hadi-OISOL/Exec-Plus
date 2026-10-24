"""Use case: Simulates declared low/likely/high driver ranges through the exact scenario formula.

What it does: Draws seeded triangular percentage changes, independently or through an
optional Gaussian copula with declared pairwise correlations, evaluates each draw with the
existing source scenario arithmetic and reports nearest-rank percentiles and the share of
draws beating a declared target. The stored seed makes replay identical.
"""

import random
from collections.abc import Callable
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from statistics import NormalDist
from typing import Any

from execplus.domain.decision_analysis import encoded, fail, number

METHOD = "triangular-monte-carlo-v1"
COPULA_METHOD = "triangular-gaussian-copula-v1"
MAX_CORRELATION = Decimal("0.9")
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
    if not isinstance(simulation, dict) or set(simulation) - {"correlations"} != {
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
    if "correlations" in simulation:
        _cholesky(_matrix(simulation))


def _matrix(simulation: dict[str, Any]) -> list[list[float]]:
    keys = [key for key in DRIVERS if key in simulation["drivers"]]
    pairs = simulation["correlations"]
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 6:
        fail("scenario_correlation", "Declare one to six driver correlations.")
    matrix = [[float(i == j) for j in range(len(keys))] for i in range(len(keys))]
    seen: set[frozenset[str]] = set()
    for pair in pairs:
        if (
            not isinstance(pair, dict)
            or set(pair) != {"first", "second", "value"}
            or not all(isinstance(item, str) for item in pair.values())
        ):
            fail("scenario_correlation", "Declare two drivers and a correlation for each pair.")
        names = frozenset((pair["first"], pair["second"]))
        if len(names) != 2 or not names <= set(keys) or names in seen:
            fail("scenario_correlation", "Correlate two different simulated drivers once each.")
        seen.add(names)
        value = number(pair["value"])
        if not -MAX_CORRELATION <= value <= MAX_CORRELATION:
            fail("scenario_correlation", "Correlations must be between -0.9 and 0.9.")
        i, j = keys.index(pair["first"]), keys.index(pair["second"])
        matrix[i][j] = matrix[j][i] = float(value)
    return matrix


def _cholesky(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    lower = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1):
            total = matrix[i][j] - sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                if total <= 1e-9:
                    fail(
                        "scenario_correlation",
                        "These correlations cannot hold together; weaken or change one pair.",
                    )
                lower[i][i] = total**0.5
            else:
                lower[i][j] = total / lower[j][j]
    return lower


def _uniforms(rng: random.Random, lower: list[list[float]] | None, size: int) -> list[float]:
    if lower is None:
        return [rng.random() for _ in range(size)]
    normal = NormalDist()
    z = [normal.inv_cdf(min(max(rng.random(), 1e-12), 1 - 1e-12)) for _ in range(size)]
    return [normal.cdf(sum(row[k] * z[k] for k in range(i + 1))) for i, row in enumerate(lower)]


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
    correlated = "correlations" in simulation
    lower = _cholesky(_matrix(simulation)) if correlated else None
    collected: dict[str, list[Decimal] | None] = {field: [] for field in FIELDS}
    for _ in range(simulation["draws"]):
        uniforms = _uniforms(rng, lower, len(bounds))
        changes = dict.fromkeys(DRIVERS, "0") | {
            key: encoded(triangular(uniform, *values))
            for uniform, (key, values) in zip(uniforms, bounds.items(), strict=True)
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
    dependence = (
        [
            "Declared driver pairs move together through a Gaussian copula: each driver keeps "
            "its triangular range while normal scores share the stated correlations.",
            "Undeclared driver pairs are uncorrelated.",
        ]
        if correlated
        else ["Drivers are drawn independently; real drivers can move together."]
    )
    return dict(
        method=COPULA_METHOD if correlated else METHOD,
        label="Simulation under the stated assumptions, not a forecast or guarantee.",
        reference="original_baseline_other_changes_zero",
        seed=simulation["seed"],
        draws=simulation["draws"],
        drivers={
            key: dict(zip(("low", "likely", "high"), map(encoded, values), strict=True))
            for key, values in bounds.items()
        },
        **(
            {
                "correlations": [
                    dict(first=p["first"], second=p["second"], value=encoded(number(p["value"])))
                    for p in simulation["correlations"]
                ]
            }
            if correlated
            else {}
        ),
        percentiles=summary,
        target_probability=probability,
        percentile_rule="nearest rank over all draws",
        assumptions=[
            "Each listed driver follows its own triangular low/likely/high range.",
            *dependence,
            "Unlisted drivers stay at zero change from the original baseline.",
            "Each draw runs the same exact scenario arithmetic as the alternatives.",
        ],
        limitations=[
            "Shares are frequencies among seeded draws, not calibrated probabilities "
            "of real outcomes; they inherit every assumption above.",
            "Sampled percentages are rounded to six decimal places before evaluation.",
            "Margin percentiles are unavailable when any draw has zero revenue.",
            *(
                [
                    "Correlations apply to normal scores; the drivers' own rank correlation "
                    "is 6/π·asin(r/2), slightly below r."
                ]
                if correlated
                else []
            ),
        ],
    )
