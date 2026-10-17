"""Verify declared scenario bounds against independent rational expectations."""

from copy import deepcopy
from decimal import localcontext
from fractions import Fraction

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.scenario_constraints import METHOD
from execplus.domain.source_scenarios import compare_source_scenarios
from test_source_scenarios import ROWS, plan, request


def constrained(**changes):
    return request(
        **{
            "model": METHOD,
            "constraints": [dict(field="remaining", operator="minimum", value="35", unit="USD")],
            **changes,
        }
    )


def test_limits_cover_baseline_simultaneous_changes_and_all_sensitivity_points():
    raw = constrained()
    before = deepcopy(raw)
    result = compare_source_scenarios(raw, ROWS)
    assert result["version"] == METHOD and raw == before
    assert result["baseline_constraints"][0]["status"] == "passed"
    assert result["alternatives"][0]["constraints"][0]["status"] == "passed"
    assert [p["constraints"][0]["status"] for p in result["sensitivity"]["points"]] == [
        "violated",
        "passed",
        "passed",
    ]
    for item in [result["baseline_constraints"][0], result["alternatives"][0]["constraints"][0]]:
        exact = item["exact_actual"]
        assert Fraction(int(exact["numerator"]), int(exact["denominator"])) == Fraction(
            item["actual"]
        )


def test_rounded_margin_never_decides_an_exact_boundary():
    limit = "33.33333333333333333333333333"
    raw = constrained(
        constraints=[dict(field="margin_percent", operator="maximum", value=limit, unit="%")]
    )
    result = compare_source_scenarios(raw, (("1", "3", "2", "0"),))
    checked = result["baseline_constraints"][0]
    assert checked["actual"] == limit and checked["status"] == "violated"
    assert checked["exact_actual"] == {"numerator": "100", "denominator": "3"}
    raw["constraints"][0]["operator"] = "minimum"
    assert (
        compare_source_scenarios(raw, (("1", "3", "2", "0"),))["baseline_constraints"][0]["status"]
        == "passed"
    )
    expected = compare_source_scenarios(constrained(), ROWS)
    with localcontext() as context:
        context.prec = 3
        assert compare_source_scenarios(constrained(), ROWS) == expected


@pytest.mark.parametrize("quantity", ["0", "-1"])
def test_zero_or_negative_revenue_leaves_margin_unavailable_without_clipping(quantity):
    raw = constrained(
        constraints=[dict(field="margin_percent", operator="minimum", value="0", unit="%")]
    )
    result = compare_source_scenarios(raw, ((quantity, "3", "2", "1"),))
    assert result["baseline"]["margin_percent"] is None
    assert Fraction(result["baseline"]["revenue"]) == Fraction(quantity) * 3
    checked = result["baseline_constraints"][0]
    assert checked["status"] == "unavailable" and checked["exact_actual"] is None
    # The historical method remains byte-for-byte semantically unchanged.
    old = compare_source_scenarios(request(), ((quantity, "3", "2", "1"),))
    if quantity == "-1":
        assert old["baseline"]["margin_percent"] is not None


@pytest.mark.parametrize(
    "limits",
    [
        [],
        [dict(field="unknown", operator="minimum", value="0", unit="USD")],
        [dict(field="quantity", operator="minimum", value=True, unit="items")],
        [dict(field="remaining", operator="minimum", value="0", unit="USD")] * 2,
        [
            dict(field="remaining", operator="minimum", value="2", unit="USD"),
            dict(field="remaining", operator="maximum", value="1", unit="USD"),
        ],
        [dict(field="remaining", operator="minimum", value="NaN", unit="USD")],
        [dict(field="remaining", operator="minimum", value="0", unit="USD", formula="eval")],
    ],
)
def test_invalid_or_conflicting_limits_are_refused(limits):
    with pytest.raises(IngestionError):
        compare_source_scenarios(constrained(constraints=limits), ROWS)


@pytest.mark.parametrize(
    "field,unit", [("quantity", "USD"), ("remaining", "EUR"), ("margin_percent", "USD")]
)
def test_units_are_checked_against_confirmed_source_mapping(field, unit):
    with pytest.raises(IngestionError, match="confirmed source unit"):
        plan(constrained(constraints=[dict(field=field, operator="minimum", value="0", unit=unit)]))


def test_constraints_cannot_be_silently_ignored_by_legacy_method():
    with pytest.raises(IngestionError):
        compare_source_scenarios(request(constraints=constrained()["constraints"]), ROWS)


def test_all_supported_amounts_have_exact_units_and_bounded_constraints():
    limits = [
        dict(
            field=field,
            operator="minimum",
            value="-1",
            unit="items" if field == "quantity" else "%" if field == "margin_percent" else "USD",
        )
        for field in (
            "quantity",
            "revenue",
            "variable_cost",
            "fixed_cost",
            "total_cost",
            "contribution",
            "remaining",
            "margin_percent",
        )
    ]
    plan(constrained(constraints=limits))
    result = compare_source_scenarios(constrained(constraints=limits), ROWS)
    assert len(result["baseline_constraints"]) == 8
    assert all(value["status"] == "passed" for value in result["baseline_constraints"])
