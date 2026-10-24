"""Use case: Verifies seeded triangular Monte Carlo scenarios against analytic answers.

What it does: Compares simulated percentiles and target shares with closed-form
triangular results, recomputes draws with separate float/Fraction code and replays
the stored seed through the governed API while plain scenarios stay unchanged.
Correlated drivers are checked against the analytic Gaussian-copula rank correlation
and an independent NumPy/SciPy copula.
"""

import random
from decimal import Decimal
from fractions import Fraction
from math import asin, pi, sqrt

import numpy as np
import pytest
from scipy.stats import norm, spearmanr, triang

from execplus.domain.ingestion import IngestionError
from execplus.domain.scenario_simulation import FIELDS, simulate, triangular
from execplus.domain.source_scenarios import compare_source_scenarios
from test_result_exports import download_text
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


PRICE_QUANTITY = dict(
    price=dict(low="-10", likely="5", high="20"),
    quantity=dict(low="-30", likely="-5", high="10"),
)


def correlated(value="0.8", drivers=None, **changes):
    return simulation(
        drivers or PRICE_QUANTITY,
        correlations=[dict(first="price", second="quantity", value=value)],
        **changes,
    )


def sampled_changes(value):
    drawn = []

    def outcome(changes):
        drawn.append(changes)
        return dict.fromkeys(FIELDS, "0")

    simulate(dict(simulation=value), outcome)
    return drawn


@pytest.mark.parametrize("r", [0.7, -0.5, 0.9])
def test_copula_rank_correlation_and_marginals_match_analytic_values(r):
    drawn = sampled_changes(correlated(str(r)))
    price = [float(item["price"]) for item in drawn]
    quantity = [float(item["quantity"]) for item in drawn]
    assert abs(spearmanr(price, quantity).statistic - 6 / pi * asin(r / 2)) < 0.03
    assert abs(sum(price) / len(price) - 5) < 0.3
    assert abs(sum(quantity) / len(quantity) - (-25 / 3)) < 0.3
    assert min(price) >= -10 and max(price) <= 20


def test_correlated_percentiles_match_an_independent_scipy_copula():
    result = compare_source_scenarios(request(simulation=correlated()), ROWS)["simulation"]
    assert result["method"] == "triangular-gaussian-copula-v1"
    assert result["correlations"] == [dict(first="price", second="quantity", value="0.8")]
    assert any("Gaussian copula" in item for item in result["assumptions"])
    generator = np.random.default_rng(99)
    normals = (
        generator.standard_normal((400000, 2))
        @ np.linalg.cholesky(np.array([[1, 0.8], [0.8, 1]])).T
    )
    uniforms = norm.cdf(normals)
    price = triang.ppf(uniforms[:, 0], 0.5, loc=-10, scale=30)
    quantity = triang.ppf(uniforms[:, 1], 25 / 40, loc=-30, scale=40)
    remaining = REVENUE * (1 + price / 100) * (1 + quantity / 100) - 36 * (1 + quantity / 100) - 7
    for name, q in (("p10", 10), ("p50", 50), ("p90", 90)):
        expected = np.percentile(remaining, q)
        assert abs(float(result["percentiles"]["remaining"][name]) - expected) < 0.4, name
    independent = compare_source_scenarios(request(simulation=simulation(PRICE_QUANTITY)), ROWS)[
        "simulation"
    ]
    assert independent["method"] == "triangular-monte-carlo-v1"
    remaining_result = result["percentiles"]["remaining"]
    remaining_independent = independent["percentiles"]["remaining"]
    spread = float(remaining_result["p90"]) - float(remaining_result["p10"])
    narrower = float(remaining_independent["p90"]) - float(remaining_independent["p10"])
    assert spread > narrower + 2
    assert compare_source_scenarios(request(simulation=correlated()), ROWS)["simulation"] == result


@pytest.mark.parametrize(
    "value",
    [
        correlated("0.95"),
        correlated("-0.91"),
        correlated("abc"),
        simulation(
            PRICE_QUANTITY,
            correlations=[dict(first="price", second="price", value="0.5")],
        ),
        simulation(
            PRICE_QUANTITY,
            correlations=[dict(first="price", second="variable_cost", value="0.5")],
        ),
        simulation(
            PRICE_QUANTITY,
            correlations=[
                dict(first="price", second="quantity", value="0.5"),
                dict(first="quantity", second="price", value="0.4"),
            ],
        ),
        simulation(
            PRICE_QUANTITY | dict(variable_cost=dict(low="-5", likely="0", high="5")),
            correlations=[
                dict(first="price", second="quantity", value="-0.9"),
                dict(first="price", second="variable_cost", value="-0.9"),
                dict(first="quantity", second="variable_cost", value="-0.9"),
            ],
        ),
        simulation(PRICE_QUANTITY, correlations=[]),
    ],
)
def test_invalid_correlations_are_refused(value):
    with pytest.raises(IngestionError):
        compare_source_scenarios(request(simulation=value), ROWS)


def test_correlated_simulation_is_recorded_and_reopens_identically(integration):
    env = integration
    headers, *_, root = fixture(env)
    response = create(env, headers, root, simulation=correlated(draws=2000, seed=5))
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    assert run["request"]["simulation"]["correlations"][0]["value"] == "0.8"
    assert run["result"]["simulation"]["method"] == "triangular-gaussian-copula-v1"
    reopened = env.client.get(endpoint(root, response.json()), headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == run
    plain = create(env, headers, root, simulation=simulation(PRICE_QUANTITY, draws=1000))
    assert plain.status_code == 201, plain.text
    assert "correlations" not in plain.json()["run"]["request"]["simulation"]
    assert "correlations" not in plain.json()["run"]["result"]["simulation"]
    bad = create(env, headers, root, simulation=correlated("0.99"))
    assert bad.status_code == 422, bad.text


@pytest.mark.parametrize("format", ["pdf", "xlsx"])
def test_simulation_percentiles_probability_and_assumptions_are_exported(integration, format):
    env = integration
    headers, *_, root = fixture(env)
    response = create(env, headers, root, simulation=correlated(draws=1000, seed=3))
    assert response.status_code == 201, response.text
    body = response.json()
    simulated = body["run"]["result"]["simulation"]
    path = (
        root.split("/uploads/")[0] + f"/analyses/{body['run']['id']}/export.{format}?kind=scenario"
    )
    exported = " ".join(download_text(env.client.get(path, headers=headers), format).split())
    remaining = simulated["percentiles"]["remaining"]
    probability = simulated["target_probability"]
    for text in (
        "nearest rank over all draws",
        remaining["p10"],
        remaining["p50"],
        remaining["p90"],
        probability["share"],
        probability["monte_carlo_standard_error"],
        "triangular-gaussian-copula-v1",
        "quantity",
        "0.8",
        simulated["assumptions"][0],
        simulated["limitations"][0],
    ):
        assert text in exported, text
    assert "seed" in exported and str(simulated["seed"]) in exported
    plain = create(env, headers, root)
    plain_path = (
        root.split("/uploads/")[0]
        + f"/analyses/{plain.json()['run']['id']}/export.{format}?kind=scenario"
    )
    assert "nearest rank over all draws" not in download_text(
        env.client.get(plain_path, headers=headers), format
    )
