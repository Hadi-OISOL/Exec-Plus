"""Use case: Compares explicit hypothetical changes to a governed numerical baseline.

What it does: Calculates bounded immutable alternatives without rewriting source data.
"""

from decimal import Decimal, localcontext
from typing import Any

from execplus.domain.decision_analysis import encoded, fail, number

METHOD = "aggregate-scenarios-v1"


def alternatives(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 5:
        fail("scenario_limit", "Declare one to five alternatives.")
    result = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"name", "operation", "value"}:
            fail("invalid_scenario", "Use a named replacement or percentage change.")
        name = item["name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or "\x00" in name:
            fail("invalid_scenario", "Use a nonempty alternative name of up to 100 characters.")
        if not isinstance(item["operation"], str) or item["operation"] not in {
            "replace",
            "percent_change",
        }:
            fail("invalid_scenario", "Choose replacement or percentage change.")
        if not isinstance(item["value"], str):
            fail("invalid_scenario", "Declare scenario amounts as exact numerical strings.")
        amount = number(item["value"])
        if item["operation"] == "percent_change" and abs(amount) > Decimal("10000"):
            fail("invalid_scenario", "Percentage changes must be between -10,000 and 10,000.")
        result.append(dict(name=name.strip(), operation=item["operation"], value=encoded(amount)))
    if len({item["name"].casefold() for item in result}) != len(result):
        fail("invalid_scenario", "Use distinct alternative names.")
    return result


def compare_scenarios(raw: dict[str, Any], rows: tuple[tuple[Any, ...], ...]) -> dict[str, Any]:
    if raw.get("assumptions_confirmed") is not True:
        fail("scenario_assumptions_required", "Confirm these are hypothetical aggregate changes.")
    if raw.get("aggregation") not in {"sum", "avg"}:
        fail("invalid_scenario", "Scenarios support eligible sums and averages only.")
    declared = alternatives(raw.get("alternatives"))
    if len(rows) != 1 or len(rows[0]) != 3:
        fail("invalid_scenario_evidence", "A complete baseline and coverage counts are required.")
    baseline, present, count = rows[0]
    if type(present) is not int or type(count) is not int or not 0 < count <= 200000:
        fail("scenario_coverage", "Use one to 200,000 eligible complete source records.")
    if present != count or baseline is None:
        fail("scenario_coverage", "Correct missing measures before comparing scenarios.")
    base = number(baseline)
    results = []
    with localcontext() as ctx:
        ctx.prec = 192
        for item in declared:
            amount = number(item["value"])
            value = amount if item["operation"] == "replace" else base * (1 + amount / 100)
            if abs(value) >= Decimal("1e38"):
                fail(
                    "scenario_range", "The hypothetical output exceeds supported numerical bounds."
                )
            difference = value - base
            ctx.prec = 28
            percentage = difference / abs(base) * 100 if base else None
            ctx.prec = 192
            results.append(
                dict(
                    **item,
                    result=encoded(value),
                    difference=encoded(difference),
                    percentage_difference=encoded(percentage) if percentage is not None else None,
                )
            )
    return dict(
        version="scenario-comparison-v1",
        method_version=METHOD,
        baseline=encoded(base),
        sample_count=count,
        metric=raw["metric"],
        aggregation=raw["aggregation"],
        alternatives=results,
        parent_run_id=raw.get("parent_run_id"),
        limitations=[
            "Hypothetical aggregate changes are conditional estimates, "
            "not forecasts or causal effects.",
            "Original records, source meaning and past comparisons remain unchanged.",
            "Percentage difference uses the absolute baseline; "
            "it is unavailable for zero baselines.",
            "Percentage differences use 28 significant digits; "
            "amounts and absolute changes remain exact.",
            "This method does not model demand, multiple drivers, uncertainty or external actions.",
        ],
    )
