"""Use case: Independently verifies declared multi-measure sales/cost scenarios.

What it does: Checks exact rational outcomes, complete populations, fixed units,
bounded sensitivity and successor compatibility without models or source writes.
"""

from copy import deepcopy
from dataclasses import replace
from decimal import localcontext
from fractions import Fraction
from random import Random
from uuid import uuid4

import pytest

from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.source_scenarios import (
    METHOD,
    compare_source_scenarios,
    compatible_source_successor,
    source_scenario_plan,
)
from execplus.domain.understanding import apply_definition, infer_definition
from execplus.infrastructure.query.validation import validated_query

ROWS = (("2", "10", "6", "3"), ("3", "20", "8", "4"))


def request(**changes):
    return {
        "kind": "scenario_comparison",
        "model": METHOD,
        "basis": "per_unit",
        "quantity_column": "quantity",
        "sales_column": "sales",
        "cost_column": "cost",
        "fixed_cost_column": "fixed",
        "filters": [],
        "assumptions_confirmed": True,
        "row_basis_confirmed": True,
        "alternatives": [
            dict(
                name="Changed mix", price="10", quantity="20", variable_cost="25", fixed_cost="100"
            )
        ],
        "sensitivity": dict(driver="price", percent_changes=["-10", "0", "10"]),
        **changes,
    }


def source():
    table = TableData(
        ("quantity", "sales", "cost", "fixed", "region"), tuple((*row, "North") for row in ROWS)
    )
    observed = profile(table)
    definition = infer_definition(observed)
    definition["grain"] = "order_item"
    for field in definition["columns"]:
        if field["name"] == "quantity":
            field["unit"] = "items"
        elif field["name"] != "region":
            field["currency"] = "USD"
    view = apply_definition(dataset_view(observed), definition)
    did = uuid4()
    return (
        WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({did})),
        did,
        table,
        view,
    )


def plan(raw=None, change=None):
    scope, did, table, view = source()
    if change:
        definition = deepcopy(view.definition)
        change(definition)
        view = apply_definition(dataset_view(profile(table)), definition)
    return source_scenario_plan(scope, did, view, table, raw or request())


def test_two_products_use_row_products_not_product_of_average_price_and_total_quantity():
    raw = request()
    original = deepcopy(raw)
    result = compare_source_scenarios(raw, ROWS)
    assert {key: Fraction(value) for key, value in result["baseline"].items()} == {
        "quantity": 5,
        "revenue": 80,
        "variable_cost": 36,
        "fixed_cost": 7,
        "total_cost": 43,
        "contribution": 44,
        "remaining": 37,
        "margin_percent": Fraction(185, 4),
    }
    alternative = result["alternatives"][0]
    expected = dict(
        quantity="6",
        revenue="105.6",
        variable_cost="54",
        fixed_cost="14",
        total_cost="68",
        contribution="51.6",
        remaining="37.6",
    )
    assert {key: Fraction(alternative["result"][key]) for key in expected} == {
        key: Fraction(value) for key, value in expected.items()
    }
    assert Fraction(alternative["difference"]["remaining"]) == Fraction(3, 5)
    assert result["sample_count"] == 2 and result["version"] == METHOD
    assert raw == original


def test_row_total_basis_matches_equivalent_per_unit_rows_without_dividing_prices():
    per_unit = compare_source_scenarios(request(), ROWS)
    totals = compare_source_scenarios(
        request(basis="row_totals"), (("2", "20", "12", "3"), ("3", "60", "24", "4"))
    )
    for key in ("baseline", "alternatives", "sensitivity"):
        assert totals[key] == per_unit[key]


def test_sensitivity_varies_one_explicit_driver_and_keeps_every_other_driver_at_baseline():
    result = compare_source_scenarios(request(), ROWS)
    sensitivity = result["sensitivity"]
    assert sensitivity["reference"] == "original_baseline_other_changes_zero"
    assert [Fraction(point["result"]["remaining"]) for point in sensitivity["points"]] == [
        29,
        37,
        45,
    ]
    assert all(Fraction(point["result"]["quantity"]) == 5 for point in sensitivity["points"])
    assert all(Fraction(point["result"]["fixed_cost"]) == 7 for point in sensitivity["points"])


def test_random_fixtures_match_an_independent_exact_fraction_calculator():
    rng = Random(5701)
    for _ in range(25):
        rows = tuple(tuple(str(rng.randint(1, 90) / 10) for _ in range(4)) for _ in range(6))
        changes = {
            key: str(rng.randint(-90, 300))
            for key in ("price", "quantity", "variable_cost", "fixed_cost")
        }
        raw = request(alternatives=[dict(name="Independent", **changes)], sensitivity=None)
        result = compare_source_scenarios(raw, rows)["alternatives"][0]["result"]
        source_values = [tuple(Fraction(cell) for cell in row) for row in rows]
        p, q, c, f = (
            1
            + Fraction(
                changes[key],
            )
            / 100
            for key in ("price", "quantity", "variable_cost", "fixed_cost")
        )
        revenue = sum(row[0] * row[1] for row in source_values) * p * q
        variable = sum(row[0] * row[2] for row in source_values) * c * q
        fixed = sum(row[3] for row in source_values) * f
        assert Fraction(result["revenue"]) == revenue
        assert Fraction(result["variable_cost"]) == variable
        assert Fraction(result["remaining"]) == revenue - variable - fixed


def test_zero_revenue_has_no_margin_and_negative_outputs_are_not_clipped():
    result = compare_source_scenarios(request(), (("0", "10", "6", "3"),))
    assert result["baseline"]["margin_percent"] is None
    assert Fraction(result["baseline"]["remaining"]) == -3
    assert Fraction(result["alternatives"][0]["result"]["remaining"]) == -6
    signed = compare_source_scenarios(request(), (("-2", "10", "6", "0"),))
    assert Fraction(signed["baseline"]["revenue"]) == -20
    assert Fraction(signed["baseline"]["remaining"]) == -8
    assert signed["warnings"] and "Signed" in signed["warnings"][0]


def test_high_precision_and_caller_context_do_not_change_exact_amounts():
    raw = request(
        alternatives=[
            dict(
                name="Precise",
                price="0.00000000000000000000000000000000000001",
                quantity="-1",
                variable_cost="0",
                fixed_cost="0",
            )
        ],
        sensitivity=None,
    )
    rows = (
        (
            "0.12345678901234567890123456789012345678",
            "9007199254740993.12345678901234567890123456789012345678",
            "0.2",
            "0.01",
        ),
    )
    result = compare_source_scenarios(raw, rows)
    with localcontext() as ctx:
        ctx.prec = 4
        assert compare_source_scenarios(raw, rows) == result
    expected = (
        Fraction(rows[0][0])
        * Fraction(rows[0][1])
        * (1 + Fraction(raw["alternatives"][0]["price"]) / 100)
        * Fraction(99, 100)
    )
    assert Fraction(result["alternatives"][0]["result"]["revenue"]) == expected


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (("1", "2", "3"),),
        (("1", None, "3", "0"),),
        (("1", "NaN", "3", "0"),),
        ((True, "2", "3", "0"),),
        (("1", "2", "3", "0"),) * 10001,
    ],
)
def test_incomplete_or_oversized_populations_are_refused_not_sampled(rows):
    with pytest.raises(IngestionError):
        compare_source_scenarios(request(), rows)


def test_maximum_population_and_sensitivity_are_bounded_and_complete():
    raw = request(
        sensitivity=dict(driver="quantity", percent_changes=[str(i) for i in range(-10, 11)])
    )
    result = compare_source_scenarios(raw, (("1", "2", "1", "0"),) * 10000)
    assert result["sample_count"] == 10000
    assert Fraction(result["baseline"]["remaining"]) == 10000
    assert len(result["sensitivity"]["points"]) == 21
    with pytest.raises(IngestionError):
        compare_source_scenarios(
            request(
                sensitivity=dict(driver="quantity", percent_changes=[str(i) for i in range(22)])
            ),
            ROWS,
        )


@pytest.mark.parametrize(
    "changes",
    [
        dict(assumptions_confirmed=False),
        dict(row_basis_confirmed=1),
        dict(model="arbitrary"),
        dict(basis="predict_demand"),
        dict(quantity_column="sales"),
        dict(alternatives=[]),
        dict(
            alternatives=[
                dict(name="Bad", price="-101", quantity="0", variable_cost="0", fixed_cost="0")
            ]
        ),
        dict(
            alternatives=[
                dict(name="Bad", price=10, quantity="0", variable_cost="0", fixed_cost="0")
            ]
        ),
        dict(sensitivity=dict(driver="price", percent_changes=["0", "0.00"])),
        dict(sensitivity=dict(driver="price", percent_changes=["10", "0"])),
        dict(sensitivity=dict(driver="python", percent_changes=["0", "10"])),
    ],
)
def test_explicit_scope_and_finite_driver_validation(changes):
    with pytest.raises(IngestionError):
        compare_source_scenarios(request(**changes), ROWS)


def test_undeclared_fixed_cost_is_zero_and_cannot_receive_a_fake_change():
    raw = request(
        fixed_cost_column=None,
        alternatives=[
            dict(name="Sales", price="10", quantity="0", variable_cost="0", fixed_cost="0")
        ],
    )
    result = compare_source_scenarios(raw, tuple(row[:3] for row in ROWS))
    assert result["baseline"]["fixed_cost"] == "0"
    assert Fraction(result["baseline"]["remaining"]) == 44
    raw["alternatives"][0]["fixed_cost"] = "10"
    with pytest.raises(IngestionError, match="fixed-cost"):
        compare_source_scenarios(raw, tuple(row[:3] for row in ROWS))


def test_nonzero_row_totals_with_zero_quantity_do_not_imply_an_infinite_unit_price():
    with pytest.raises(IngestionError, match="nonzero quantity"):
        compare_source_scenarios(request(basis="row_totals"), (("0", "10", "2", "1"),))


def test_output_overflow_is_refused_and_no_float_conversion_occurs():
    with pytest.raises(IngestionError, match="range"):
        compare_source_scenarios(request(), (("1e20", "1e20", "1", "0"),))


def test_projection_is_bounded_read_only_and_preserves_same_population_and_units():
    raw = request(filters=[dict(column="region", operator="eq", value="North")])
    query, units = plan(raw)
    assert (
        query.sql
        == 'SELECT "quantity", "sales", "cost", "fixed" FROM "dataset" WHERE "region" = ? '
        'ORDER BY "quantity", "sales", "cost", "fixed" LIMIT 10001'
    )
    assert query.params == ("North",)
    assert units == {"quantity": "items", "sales": "USD", "cost": "USD", "fixed": "USD"}
    validated_query(query.sql, {"dataset"}, len(query.params))


@pytest.mark.parametrize(
    "name,field,value",
    [
        ("cost", "currency", "EUR"),
        ("sales", "currency", ""),
        ("quantity", "currency", "USD"),
        ("cost", "unit_column", "region"),
        ("quantity", "unit", ""),
    ],
)
def test_mixed_currency_missing_units_and_variable_units_are_refused(name, field, value):
    def change(definition):
        next(item for item in definition["columns"] if item["name"] == name)[field] = value

    with pytest.raises((IngestionError, UnsupportedQuestionError)):
        plan(change=change)


@pytest.mark.parametrize("grain", ["unknown", "inventory_snapshot", "customer", "survey_response"])
def test_non_additive_or_unconfirmed_grain_is_refused(grain):
    with pytest.raises(IngestionError, match="row"):
        plan(change=lambda definition: definition.update(grain=grain))


def test_distinct_governed_populations_are_not_silently_intersected():
    def change(definition):
        definition["metrics"] = [
            dict(
                name="North sales",
                column="sales",
                aggregation="sum",
                filters=[dict(column="region", operator="eq", value="North")],
            )
        ]

    with pytest.raises(IngestionError, match="same governed population"):
        plan(change=change)
    query, _ = plan(request(filters=[dict(column="region", operator="eq", value="North")]), change)
    assert query.params == ("North",)


def test_successors_preserve_mapping_grain_units_filters_and_selected_meanings():
    _, _, _, view = source()
    _, units = plan()
    raw = request()
    assert compatible_source_successor(raw, view.definition, units, raw, view.definition, units)
    changed = request(basis="row_totals")
    assert not compatible_source_successor(
        raw, view.definition, units, changed, view.definition, units
    )
    definition = deepcopy(view.definition)
    definition["columns"][0]["meaning"] = "A new interpretation"
    assert not compatible_source_successor(raw, view.definition, units, raw, definition, units)
    replacement = replace(view, metrics=view.metrics - {"sales"})
    scope, did, table, _ = source()
    with pytest.raises(UnsupportedQuestionError):
        source_scenario_plan(scope, did, replacement, table, raw)


def oracle_outcome(p, q, c, f):
    p, q, c, f = (1 + Fraction(v) / 100 for v in (p, q, c, f))
    revenue, variable, fixed = 80 * p * q, 36 * q * c, 7 * f
    remaining = revenue - variable - fixed
    return dict(
        quantity=5 * q,
        revenue=revenue,
        variable_cost=variable,
        fixed_cost=fixed,
        total_cost=variable + fixed,
        contribution=revenue - variable,
        remaining=remaining,
        margin_percent=remaining / revenue * 100,
    )


def test_declared_ranges_give_exact_bounds_that_contain_every_interior_combination():
    ranges = dict(
        price=dict(low="-10", high="20"),
        quantity=dict(low="-50", high="10"),
        fixed_cost=dict(low="0", high="50"),
    )
    result = compare_source_scenarios(request(ranges=ranges), ROWS)
    value = result["ranges"]
    assert value["method"] == "vertex-interval-bounds-v1" and value["corners_evaluated"] == 8
    grid = [
        oracle_outcome(p, q, 0, f)
        for p in range(-10, 21, 5)
        for q in range(-50, 11, 10)
        for f in range(0, 51, 25)
    ]
    for key, bounds in value["bounds"].items():
        low, high = min(g[key] for g in grid), max(g[key] for g in grid)
        if key == "margin_percent":
            assert abs(Fraction(bounds["low"]) - low) < Fraction(1, 10**20)
            assert abs(Fraction(bounds["high"]) - high) < Fraction(1, 10**20)
        else:
            assert (Fraction(bounds["low"]), Fraction(bounds["high"])) == (low, high)
    remaining = value["bounds"]["remaining"]
    assert (Fraction(remaining["low"]), Fraction(remaining["high"])) == (Fraction(15, 2), 59)
    assert remaining["high_assumptions"] == dict(price="20", quantity="10", fixed_cost="0")
    assert remaining["low_assumptions"] == dict(price="-10", quantity="-50", fixed_cost="50")
    without = compare_source_scenarios(request(), ROWS)
    assert "ranges" not in without
    assert {k: v for k, v in result.items() if k != "ranges"} == without


def test_ranges_are_validated_and_zero_revenue_margin_bounds_stay_unavailable():
    zero = compare_source_scenarios(request(ranges=dict(price=dict(low="-100", high="0"))), ROWS)[
        "ranges"
    ]["bounds"]
    assert zero["margin_percent"] is None and zero["revenue"]["low"] == "0"
    for ranges in (
        {},
        dict(price=dict(low="5", high="5")),
        dict(price=dict(low="-101", high="0")),
        dict(margin=dict(low="0", high="1")),
        dict(price=dict(low="0")),
    ):
        with pytest.raises(IngestionError):
            compare_source_scenarios(request(ranges=ranges), ROWS)
    plain = dict(name="Flat", price="0", quantity="0", variable_cost="0", fixed_cost="0")
    raw = request(fixed_cost_column=None, alternatives=[plain], sensitivity=None)
    assert "ranges" not in compare_source_scenarios(raw, tuple(row[:3] for row in ROWS))
    with pytest.raises(IngestionError, match="fixed-cost column before varying"):
        compare_source_scenarios(
            {**raw, "ranges": dict(fixed_cost=dict(low="0", high="1"))},
            tuple(row[:3] for row in ROWS),
        )
