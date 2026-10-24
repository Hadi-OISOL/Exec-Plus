"""Use case: Computes declared sales, quantity and cost scenarios from one source.

What it does: Validates a bounded row projection and calculates exact conditional
amounts without estimating demand, changing source rows or executing formulas.
"""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any, cast
from uuid import UUID, uuid4

from execplus.domain.decision_analysis import encoded, fail, number
from execplus.domain.models import QueryPlan, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.scenario_constraints import METHOD as CONSTRAINED_METHOD
from execplus.domain.scenario_constraints import apply_constraints, constraints, validate_units
from execplus.domain.scenario_simulation import simulate, validate_simulation
from execplus.domain.semantics import (
    DatasetView,
    MetricFilter,
    build_where,
    quote_identifier,
    validate_read_only,
)
from execplus.domain.studies import method_request, validated_method
from execplus.domain.understanding import governed_request, preferred_aggregation

METHOD = "source-unit-economics-v1"
MAX_ROWS = 10000
DRIVERS = ("price", "quantity", "variable_cost", "fixed_cost")
COLUMN_KEYS = ("quantity_column", "sales_column", "cost_column", "fixed_cost_column")
RANGE_METHOD = "vertex-interval-bounds-v1"


def is_source_scenario(raw: dict[str, Any]) -> bool:
    return raw.get("model") in {METHOD, CONSTRAINED_METHOD}


def source_columns(raw: dict[str, Any]) -> list[str]:
    columns = [raw.get(key) for key in COLUMN_KEYS[:3]]
    if raw.get("fixed_cost_column"):
        columns.append(raw["fixed_cost_column"])
    if any(not isinstance(value, str) or not value or len(value) > 200 for value in columns) or len(
        set(columns)
    ) != len(columns):
        fail("scenario_columns", "Choose separate confirmed quantity, sales and cost columns.")
    return cast(list[str], columns)


def _percent(value: object) -> Decimal:
    if not isinstance(value, str):
        fail("scenario_assumption", "Enter each percentage as an exact numerical string.")
    amount = number(value)
    if not Decimal(-100) <= amount <= Decimal(10000):
        fail("scenario_assumption", "Percentage changes must be between -100 and 10,000.")
    return amount


def validate_source_scenario(raw: dict[str, Any]) -> None:
    if not is_source_scenario(raw) or raw.get("basis") not in {"per_unit", "row_totals"}:
        fail("scenario_model", "Choose a registered sales and cost model.")
    if raw["model"] == CONSTRAINED_METHOD:
        constraints(raw)
    elif raw.get("constraints"):
        fail("scenario_constraints", "Use the constrained method when declaring scenario limits.")
    source_columns(raw)
    if raw.get("assumptions_confirmed") is not True or raw.get("row_basis_confirmed") is not True:
        fail(
            "scenario_assumptions_required",
            "Confirm the row basis, cost interpretation and hypothetical changes.",
        )
    values = raw.get("alternatives")
    if not isinstance(values, list) or not 1 <= len(values) <= 5:
        fail("scenario_limit", "Declare one to five alternatives.")
    names = []
    for item in values:
        if not isinstance(item, dict) or set(item) != {"name", *DRIVERS}:
            fail("scenario_assumption", "Declare all four driver changes explicitly.")
        name = item["name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or "\x00" in name:
            fail("scenario_assumption", "Use a nonempty name of at most 100 characters.")
        names.append(name.strip().casefold())
        for driver in DRIVERS:
            value = _percent(item[driver])
            if driver == "fixed_cost" and value and not raw.get("fixed_cost_column"):
                fail("scenario_fixed_cost", "Choose a source fixed-cost column before changing it.")
    if len(set(names)) != len(names):
        fail("scenario_assumption", "Use distinct alternative names.")
    sensitivity = raw.get("sensitivity")
    if sensitivity is not None:
        if (
            not isinstance(sensitivity, dict)
            or set(sensitivity) != {"driver", "percent_changes"}
            or sensitivity["driver"] not in DRIVERS
            or not isinstance(sensitivity["percent_changes"], list)
            or not 2 <= len(sensitivity["percent_changes"]) <= 21
        ):
            fail("scenario_sensitivity", "Choose one driver and two to twenty-one percentages.")
        amounts = [_percent(value) for value in sensitivity["percent_changes"]]
        if len(set(amounts)) != len(amounts) or amounts != sorted(amounts):
            fail("scenario_sensitivity", "Use distinct increasing sensitivity percentages.")
        if sensitivity["driver"] == "fixed_cost" and not raw.get("fixed_cost_column"):
            fail("scenario_fixed_cost", "Choose a source fixed-cost column before varying it.")
    ranges = raw.get("ranges")
    if ranges is not None:
        if not isinstance(ranges, dict) or not 1 <= len(ranges) <= 4 or set(ranges) - set(DRIVERS):
            fail("scenario_range", "Choose one to four drivers with low and high changes.")
        for driver, bounds in ranges.items():
            if not isinstance(bounds, dict) or set(bounds) != {"low", "high"}:
                fail("scenario_range", "Declare both a low and a high percentage change.")
            if not _percent(bounds["low"]) < _percent(bounds["high"]):
                fail("scenario_range", "Each low change must be below its high change.")
            if driver == "fixed_cost" and not raw.get("fixed_cost_column"):
                fail("scenario_fixed_cost", "Choose a source fixed-cost column before varying it.")
    validate_simulation(raw)


def source_scenario_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, table: TableData, raw: dict[str, Any]
) -> tuple[QueryPlan, dict[str, str]]:
    validate_source_scenario(raw)
    definition = view.definition or {}
    if definition.get("grain") not in {"record", "order", "order_item", "other"}:
        fail(
            "scenario_row_basis",
            "Confirm additive transaction or non-overlapping period rows first; "
            "stock snapshots and unknown row meanings are not supported.",
        )
    columns = source_columns(raw)
    units: dict[str, str] = {}
    money = set()
    population: tuple[MetricFilter, ...] | None = None
    for name in columns:
        additive = raw["basis"] == "row_totals" or name in {
            raw["quantity_column"],
            raw.get("fixed_cost_column"),
        }
        method = validated_method(
            dict(
                kind="metric",
                column=name,
                aggregation="sum" if additive else preferred_aggregation(view, name).value,
                filters=raw["filters"],
                group_by=[],
                order=[],
            ),
            view,
        )
        request = governed_request(view, table, method_request(method))
        filters = tuple(dict.fromkeys(request.filters))
        if population is not None and set(filters) != set(population):
            fail(
                "scenario_population_mismatch",
                "All selected measures must use the same governed population filters.",
            )
        population = filters
        meaning = next(item for item in definition["columns"] if item["name"] == name)
        unit = meaning["currency"] or meaning["unit"]
        if not unit or meaning["unit_column"]:
            fail("fixed_unit_required", "Confirm a fixed unit for every selected measure.")
        if name == raw["quantity_column"]:
            if meaning["currency"]:
                fail("scenario_quantity_unit", "Quantity needs a non-currency unit.")
        else:
            if not meaning["currency"]:
                fail("scenario_currency", "Confirm a currency code for every sales/cost field.")
            money.add(meaning["currency"])
        units[name] = unit
    if len(money) != 1:
        fail("scenario_currency", "Sales and costs must use the same fixed currency.")
    if raw["model"] == CONSTRAINED_METHOD:
        validate_units(raw, units)
    if len(population or ()) > 20:
        fail("analysis_filter_limit", "Use at most twenty total governed filters.")
    where, params = build_where(view, population or ())
    fields = ", ".join(quote_identifier(column) for column in columns)
    sql = f'SELECT {fields} FROM "dataset"'
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {fields} LIMIT {MAX_ROWS + 1}"
    validate_read_only(sql)
    return QueryPlan(
        uuid4(), scope.workspace_id, did, "Declared source sales/cost scenario", sql, tuple(params)
    ), units


def compatible_source_successor(
    previous: dict[str, Any],
    previous_definition: dict[str, Any] | None,
    previous_units: dict[str, str],
    raw: dict[str, Any],
    definition: dict[str, Any] | None,
    units: dict[str, str],
) -> bool:
    if (previous.get("model"), raw.get("model")) not in {
        (METHOD, METHOD),
        (METHOD, CONSTRAINED_METHOD),
        (CONSTRAINED_METHOD, CONSTRAINED_METHOD),
    } or any(previous.get(key) != raw.get(key) for key in ("basis", "filters", *COLUMN_KEYS)):
        return False
    old, new = previous_definition or {}, definition or {}
    names = set(source_columns(raw))
    return (
        previous_units == units
        and old.get("grain") == new.get("grain")
        and [item for item in old.get("columns", []) if item["name"] in names]
        == [item for item in new.get("columns", []) if item["name"] in names]
        and [item for item in old.get("metrics", []) if item["column"] in names]
        == [item for item in new.get("metrics", []) if item["column"] in names]
    )


def _amounts(
    quantity: Decimal, revenue: Decimal, variable: Decimal, fixed: Decimal
) -> dict[str, str | None]:
    values = dict(
        quantity=quantity,
        revenue=revenue,
        variable_cost=variable,
        fixed_cost=fixed,
        total_cost=variable + fixed,
        contribution=revenue - variable,
        remaining=revenue - variable - fixed,
    )
    if any(value.copy_abs() >= Decimal("1e38") for value in values.values()):
        fail("scenario_range", "A scenario amount exceeds the supported range below 1e38.")
    with localcontext() as ctx:
        ctx.prec = 28
        margin = encoded(values["remaining"] / revenue * 100) if revenue else None
    return {**{key: encoded(value) for key, value in values.items()}, "margin_percent": margin}


def compare_source_scenarios(
    raw: dict[str, Any], rows: tuple[tuple[Any, ...], ...]
) -> dict[str, Any]:
    validate_source_scenario(raw)
    if not 1 <= len(rows) <= MAX_ROWS:
        fail("scenario_coverage", "Use one to 10,000 complete matching records; no sample is used.")
    width = len(source_columns(raw))
    values = []
    for row in rows:
        if len(row) != width or any(value is None for value in row):
            fail("scenario_coverage", "Every selected input must be present on every matched row.")
        values.append(tuple(number(value) for value in row))
    with localcontext() as ctx:
        ctx.prec, ctx.rounding = 256, ROUND_HALF_EVEN
        quantity = revenue = variable = fixed = Decimal(0)
        for row in values:
            q, sales, cost = row[:3]
            if raw["basis"] == "row_totals" and not q and (sales or cost):
                fail(
                    "scenario_row_basis", "Rows with sales or variable cost need nonzero quantity."
                )
            quantity += q
            revenue += q * sales if raw["basis"] == "per_unit" else sales
            variable += q * cost if raw["basis"] == "per_unit" else cost
            fixed += row[3] if width == 4 else 0
        baseline = _amounts(quantity, revenue, variable, fixed)

        def outcome(changes: dict[str, Any]) -> dict[str, str | None]:
            factors = {key: 1 + _percent(changes[key]) / 100 for key in DRIVERS}
            return _amounts(
                quantity * factors["quantity"],
                revenue * factors["price"] * factors["quantity"],
                variable * factors["variable_cost"] * factors["quantity"],
                fixed * factors["fixed_cost"],
            )

        alternatives = []
        for item in raw["alternatives"]:
            result = outcome(item)
            difference = {
                key: encoded(Decimal(str(result[key])) - Decimal(str(baseline[key])))
                for key in baseline
                if key != "margin_percent"
            }
            alternatives.append(
                dict(
                    name=item["name"].strip(),
                    assumptions={key: encoded(_percent(item[key])) for key in DRIVERS},
                    result=result,
                    difference=difference,
                )
            )
        sensitivity = None
        if raw.get("sensitivity"):
            declared = raw["sensitivity"]
            sensitivity = dict(
                driver=declared["driver"],
                points=[
                    dict(
                        percent_change=encoded(_percent(value)),
                        result=outcome({**dict.fromkeys(DRIVERS, "0"), declared["driver"]: value}),
                    )
                    for value in declared["percent_changes"]
                ],
                reference="original_baseline_other_changes_zero",
            )
        ranges = None
        if raw.get("ranges"):
            declared_ranges = {key: raw["ranges"][key] for key in DRIVERS if key in raw["ranges"]}
            corners = [
                (
                    {key: "0" for key in DRIVERS}
                    | {
                        key: bounds["high" if index >> bit & 1 else "low"]
                        for bit, (key, bounds) in enumerate(declared_ranges.items())
                    },
                )
                for index in range(2 ** len(declared_ranges))
            ]
            evaluated = [(changes, outcome(changes)) for (changes,) in corners]
            bounds_by_key: dict[str, Any] = {}
            for key in baseline:
                known = [(Decimal(str(r[key])), c) for c, r in evaluated if r[key] is not None]
                if len(known) != len(evaluated):
                    bounds_by_key[key] = None
                    continue
                low = min(known, key=lambda item: item[0])
                high = max(known, key=lambda item: item[0])
                bounds_by_key[key] = dict(
                    low=encoded(low[0]),
                    high=encoded(high[0]),
                    low_assumptions={k: encoded(_percent(low[1][k])) for k in declared_ranges},
                    high_assumptions={k: encoded(_percent(high[1][k])) for k in declared_ranges},
                )
            ranges = dict(
                method=RANGE_METHOD,
                reference="original_baseline_other_changes_zero",
                drivers={
                    key: dict(low=encoded(_percent(v["low"])), high=encoded(_percent(v["high"])))
                    for key, v in declared_ranges.items()
                },
                corners_evaluated=len(evaluated),
                bounds=bounds_by_key,
                limitation=(
                    "Bounds evaluate every low/high combination exactly; each outcome is "
                    "monotone in every driver, so extremes occur at these corners. "
                    "They are declared ranges, not probabilities or forecasts. "
                    "Margin bounds are unavailable when any combination has zero revenue."
                ),
            )
        simulation = simulate(raw, outcome) if raw.get("simulation") else None
    comparison = dict(
        version=METHOD,
        method_version=METHOD,
        basis=raw["basis"],
        sample_count=len(rows),
        baseline=baseline,
        alternatives=alternatives,
        sensitivity=sensitivity,
        **({"ranges": ranges} if ranges else {}),
        **({"simulation": simulation} if simulation else {}),
        parent_run_id=raw.get("parent_run_id"),
        warnings=[
            "Signed source inputs are retained, including returns or credits; "
            "check that their declared row meaning is appropriate."
        ]
        if any(value < 0 for row in values for value in row)
        else [],
        assumptions=[
            "Every row contributes once; included periods do not overlap "
            "and fixed costs are allocated once.",
            "Price and variable cost are per one declared quantity unit, "
            "or row totals of those same flows.",
            "All rows keep the same mix. The declared quantity change independently "
            "scales sales and variable costs.",
            "Included fixed costs change only by their explicit percentage, not with quantity.",
        ],
        limitations=[
            "These are conditional arithmetic outcomes, not forecasts or inferred causal effects.",
            "No demand response, capacity limits, tax, financing, omitted costs "
            "or uncertainty is inferred.",
            "Remaining amount and margin include only the selected costs; "
            "they are not audited net profit.",
            "Percentage scaling can produce fractional quantities; "
            "no integer rounding or operational feasibility model is applied.",
            "Sensitivity changes one driver around the original baseline "
            "while every other change is zero.",
            "Negative outcomes are preserved. Margin is unavailable at zero revenue; "
            "ratios use 28 significant digits.",
            "Amounts use 256-digit Decimal arithmetic; input values stay below 1e38 "
            "with at most 38 decimal places.",
            "Original rows, definitions and previous saved scenarios remain unchanged.",
        ],
    )
    return apply_constraints(raw, comparison) if raw["model"] == CONSTRAINED_METHOD else comparison
