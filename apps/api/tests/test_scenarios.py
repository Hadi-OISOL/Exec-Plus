"""Use case: Independently checks conditional scenario arithmetic and eligibility.

What it does: Covers exact amounts, negative/zero baselines and bounded invalid inputs.
"""

from decimal import Decimal, localcontext

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.scenarios import compare_scenarios


def raw(**extra):
    return dict(
        metric="amount",
        aggregation="sum",
        assumptions_confirmed=True,
        alternatives=[dict(name="Increase", operation="percent_change", value="10")],
        **extra,
    )


@pytest.mark.parametrize(
    "baseline",
    ["0", "-0.30", "0.30", "9007199254740993.10", "0.00000000000000000000000000000000000001"],
)
def test_scenario_percentages_match_independent_decimal(baseline):
    result = compare_scenarios(raw(), ((baseline, 2, 2),))
    value = result["alternatives"][0]
    with localcontext() as ctx:
        ctx.prec = 192
        expected = Decimal(baseline) * Decimal("1.10")
        assert Decimal(value["result"]) == expected
        assert Decimal(value["difference"]) == expected - Decimal(baseline)
    assert (value["percentage_difference"] is None) == (Decimal(baseline) == 0)


def test_replacement_preserves_exact_negative_value_and_zero_limit():
    request = raw()
    request["alternatives"] = [dict(name="Replace", operation="replace", value="-0.20")]
    result = compare_scenarios(request, (("0", 1, 1),))
    assert result["alternatives"][0]["result"] == "-0.20"
    assert result["alternatives"][0]["difference"] == "-0.20"
    assert result["alternatives"][0]["percentage_difference"] is None


@pytest.mark.parametrize(
    "alternatives",
    [
        [],
        [dict(name="x", operation="replace", value="1")] * 6,
        [dict(name="x", operation="python", value="1")],
        [dict(name="x", operation="replace", value=1)],
        [dict(name="x", operation="percent_change", value="10001")],
        [dict(name="x", operation="replace", value="NaN")],
        [dict(name="x", operation="replace", value="1e38")],
        [
            dict(name="x", operation="replace", value="1"),
            dict(name=" X ", operation="replace", value="2"),
        ],
        [dict(name="", operation="replace", value="1")],
    ],
)
def test_unsafe_or_unbounded_scenarios_refuse(alternatives):
    request = raw()
    request["alternatives"] = alternatives
    with pytest.raises(IngestionError):
        compare_scenarios(request, (("1", 1, 1),))


@pytest.mark.parametrize(
    "rows",
    [((None, 0, 0),), (("1", 1, 2),), (("1", True, 1),), (("1", 200001, 200001),), (), (("1", 1),)],
)
def test_incomplete_evidence_refuses(rows):
    with pytest.raises(IngestionError):
        compare_scenarios(raw(), rows)


def test_percentage_overflow_refuses_without_rounding():
    with pytest.raises(IngestionError):
        compare_scenarios(raw(), (("99999999999999999999999999999999999999", 1, 1),))


@pytest.mark.parametrize("key,value", [("assumptions_confirmed", False), ("aggregation", "count")])
def test_unsupported_assumptions_refuse(key, value):
    request = raw()
    request[key] = value
    with pytest.raises(IngestionError):
        compare_scenarios(request, (("1", 1, 1),))
