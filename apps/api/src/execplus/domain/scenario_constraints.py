"""Check explicit scenario limits using exact amounts and rational margins.

These checks describe declared limits, not operational feasibility or probability.
"""

from fractions import Fraction
from typing import Any

from execplus.domain.decision_analysis import encoded, fail, number

METHOD = "source-unit-economics-constrained-v2"
FIELDS = frozenset(
    {
        "quantity",
        "revenue",
        "variable_cost",
        "fixed_cost",
        "total_cost",
        "contribution",
        "remaining",
        "margin_percent",
    }
)


def constraints(raw: dict[str, Any]) -> list[dict[str, str]]:
    declared = raw.get("constraints")
    if not isinstance(declared, list) or not 1 <= len(declared) <= 12:
        fail("scenario_constraints", "Declare one to twelve minimum or maximum limits.")
    limits = []
    bounds: dict[str, dict[str, Fraction]] = {}
    for item in declared:
        if (
            not isinstance(item, dict)
            or set(item) != {"field", "operator", "value", "unit"}
            or not isinstance(item["field"], str)
            or item["field"] not in FIELDS
            or not isinstance(item["operator"], str)
            or item["operator"] not in {"minimum", "maximum"}
            or not isinstance(item["value"], str)
            or not isinstance(item["unit"], str)
            or not item["unit"].strip()
            or len(item["unit"]) > 100
        ):
            fail(
                "scenario_constraints",
                "Choose a supported amount, exact limit and its confirmed unit.",
            )
        value = number(item["value"])
        by_field = bounds.setdefault(item["field"], {})
        if item["operator"] in by_field:
            fail("scenario_constraints", "Declare each minimum or maximum only once per amount.")
        by_field[item["operator"]] = Fraction(value)
        limits.append({**item, "value": encoded(value)})
    if any(
        "minimum" in values and "maximum" in values and values["minimum"] > values["maximum"]
        for values in bounds.values()
    ):
        fail("scenario_constraints", "A minimum cannot exceed the maximum for that amount.")
    return limits


def validate_units(raw: dict[str, Any], units: dict[str, str]) -> None:
    for item in constraints(raw):
        expected = (
            "%"
            if item["field"] == "margin_percent"
            else units[
                raw["quantity_column"] if item["field"] == "quantity" else raw["sales_column"]
            ]
        )
        if item["unit"] != expected:
            fail(
                "scenario_constraint_unit", "Use the confirmed source unit for each scenario limit."
            )


def check(amounts: dict[str, Any], limits: list[dict[str, str]]) -> list[dict[str, Any]]:
    checks = []
    for limit in limits:
        field = limit["field"]
        value = (
            Fraction(amounts["remaining"]) / Fraction(amounts["revenue"]) * 100
            if field == "margin_percent" and Fraction(amounts["revenue"]) > 0
            else None
            if field == "margin_percent"
            else Fraction(amounts[field])
        )
        threshold = Fraction(limit["value"])
        passed = value is not None and (
            value >= threshold if limit["operator"] == "minimum" else value <= threshold
        )
        checks.append(
            {
                **limit,
                "status": "unavailable" if value is None else "passed" if passed else "violated",
                "actual": amounts[field],
                "exact_actual": {
                    "numerator": str(value.numerator),
                    "denominator": str(value.denominator),
                }
                if value is not None
                else None,
                "reason": "Margin requires positive revenue; "
                "zero or negative revenue has no eligible margin."
                if value is None
                else "Compared with the declared limit using exact arithmetic.",
            }
        )
    return checks


def apply_constraints(raw: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    limits = constraints(raw)
    result["version"] = result["method_version"] = METHOD
    amounts = [result["baseline"], *(entry["result"] for entry in result["alternatives"])]
    if result["sensitivity"]:
        amounts.extend(entry["result"] for entry in result["sensitivity"]["points"])
    for value in amounts:
        if Fraction(value["revenue"]) <= 0:
            value["margin_percent"] = None
    result["constraints"] = limits
    result["baseline_constraints"] = check(result["baseline"], limits)
    for alternative in result["alternatives"]:
        alternative["constraints"] = check(alternative["result"], limits)
    if result["sensitivity"]:
        for point in result["sensitivity"]["points"]:
            point["constraints"] = check(point["result"], limits)
    result["limitations"].extend(
        [
            "Passing declared limits is not proof of operational feasibility "
            "or an optimal decision.",
            "Margin limits use the exact rational remaining/revenue ratio, "
            "not its rounded display; "
            "margin is unavailable when revenue is zero or negative.",
            "Named alternatives and sensitivity ranges are user assumptions, not probabilities.",
        ]
    )
    return result
