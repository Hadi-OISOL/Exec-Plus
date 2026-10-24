"""Use case: Verifies seeded triangular Monte Carlo scenarios against analytic answers.

What it does: Compares simulated percentiles and target shares with closed-form
triangular results, recomputes draws with separate float/Fraction code and replays
the stored seed through the governed API while plain scenarios stay unchanged.
"""

import random
from decimal import Decimal
from fractions import Fraction
from math import sqrt

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.scenario_simulation import triangular
from execplus.domain.source_scenarios import compare_source_scenarios
from test_source_scenarios import ROWS, request
from test_source_scenarios_integration import create, endpoint, fixture

REVENUE, COSTS = 80, 43


def simulation(drivers=None, **changes):
    return (
        dict(
            drivers=drivers or dict(price=dict(low="-10", likely="0", high="20")),
            draws=10000,
            seed=7,
            target=dict(field="remaining", direction="above", value="40"),
        )
        | changes
    )


def triangular_quantile(q, low, likely, high):
    if q < (likely - low) / (high - low):
        return low + sqrt(q * (high - low) * (likely - low))
    return high - sqrt((1 - q) * (high - low) * (high - likely))


def test_one_driver_simulation_matches_closed_form_triangular_answers():
    result = compare_source_scenarios(request(simulation=simulation()), ROWS)["simulation"]
    assert result["method"] == "triangular-monte-carlo-v1" and result["seed"] == 7
    remaining = result["percentiles"]["remaining"]
    for name, q in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9)):
        expected = REVENUE * (1 + triangular_quantile(q, -10, 0, 20) / 100) - COSTS
        assert abs(float(remaining[name]) - expected) < 0.4, name
    analytic = (20 - 3.75) ** 2 / (30 * 20)
    probability = result["target_probability"]
    error = sqrt(analytic * (1 - analytic) / 10000)
    assert abs(float(probability["share"]) - analytic) < 4 * error
    assert abs(float(probability["monte_carlo_standard_error"]) - error) < 0.001
    assert result["percentiles"]["variable_cost"]["p10"] == "36"


def test_draws_match_an_independent_float_and_fraction_recomputation():
    drivers = dict(
        price=dict(low="-10", likely="5", high="20"),
        quantity=dict(low="-30", likely="-5", high="10"),
    )
    value = simulation(drivers, draws=1000, seed=11)
    result = compare_source_scenarios(request(simulation=value), ROWS)["simulation"]
    rng = random.Random(11)
    outcomes = []
    for _ in range(1000):
        p = round(triangular_quantile(rng.random(), -10, 5, 20), 6)
        q = round(triangular_quantile(rng.random(), -30, -5, 10), 6)
        price, quantity = Fraction(str(p)), Fraction(str(q))
        revenue = REVENUE * (1 + price / 100) * (1 + quantity / 100)
        outcomes.append(revenue - 36 * (1 + quantity / 100) - 7)
    ordered = sorted(outcomes)
    for name, rank in (("p10", 100), ("p50", 500), ("p90", 900)):
        assert abs(
            Fraction(result["percentiles"]["remaining"][name]) - ordered[rank - 1]
        ) < Fraction(1, 10**9)
    assert result["target_probability"]["draws_beating"] == sum(o > 40 for o in outcomes)


def test_seed_replays_identically_and_plain_scenarios_are_unchanged():
    first = compare_source_scenarios(request(simulation=simulation()), ROWS)
    assert compare_source_scenarios(request(simulation=simulation()), ROWS) == first
    other = compare_source_scenarios(request(simulation=simulation(seed=8)), ROWS)
    assert other["simulation"] != first["simulation"]
    plain = compare_source_scenarios(request(), ROWS)
    assert "simulation" not in plain
    assert {key: value for key, value in first.items() if key != "simulation"} == plain


def test_triangular_draws_stay_within_bounds_and_degenerate_modes_work():
    for low, likely, high in ((-5, -5, 5), (-5, 5, 5), (0, 1, 2)):
        for uniform in (0.0, 0.25, 0.5, 0.999999):
            value = triangular(uniform, Decimal(low), Decimal(likely), Decimal(high))
            assert Decimal(low) <= value <= Decimal(high)
            assert abs(float(value) - triangular_quantile(uniform, low, likely, high)) < 1e-6


@pytest.mark.parametrize(
    "value",
    [
        simulation(dict(price=dict(low="0", likely="-1", high="5"))),
        simulation(dict(price=dict(low="5", likely="5", high="5"))),
        simulation(dict(margin=dict(low="0", likely="1", high="2"))),
        simulation(draws=999),
        simulation(seed=-1),
        simulation(target=dict(field="profit", direction="above", value="1")),
    ],
)
def test_invalid_simulations_are_refused(value):
    with pytest.raises(IngestionError):
        compare_source_scenarios(request(simulation=value), ROWS)


def test_simulation_saves_seed_and_reopens_identically(integration):
    env = integration
    headers, *_, root = fixture(env)
    response = create(
        env,
        headers,
        root,
        simulation=dict(
            drivers=dict(price=dict(low="-10", likely="0", high="20")),
            draws=2000,
            target=dict(field="remaining", direction="above", value="40"),
        ),
    )
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    assert run["request"]["simulation"]["seed"] == 20261024
    assert run["result"]["simulation"]["draws"] == 2000
    reopened = env.client.get(endpoint(root, response.json()), headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == run
    plain = create(env, headers, root)
    assert plain.status_code == 201, plain.text
    assert "simulation" not in plain.json()["run"]["request"]
    assert "simulation" not in plain.json()["run"]["result"]
    bad = create(
        env,
        headers,
        root,
        simulation=dict(drivers=dict(price=dict(low="5", likely="9", high="1"))),
    )
    assert bad.status_code == 422, bad.text
