"""Use case: Recommends exact inventory reorder quantities from a confirmed demand history.

What it does: Derives average and spread of daily demand per item from dated quantities,
adds lead-time demand and service-level safety stock to each reorder point, orders the
whole units needed to reach that level, ranks items by days of cover and, when a budget
cannot fund every order, hands an exact integer problem to the bounded allocation solver
and independently checks the returned quantities.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from math import ceil
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.decision_analysis import checksum, encoded, fail, number
from execplus.domain.large_allocation import IntegerAllocation, SolverOutcome, exact_scale
from execplus.domain.models import QueryPlan, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import (
    DatasetView,
    MetricFilter,
    build_where,
    quote_identifier,
    validate_read_only,
)
from execplus.domain.studies import method_request, validated_method
from execplus.domain.understanding import governed_request, preferred_aggregation

METHOD = "inventory-reorder-v1"
VERSION = "inventory-reorder-v1"
SERVICE_LEVELS = {
    "0.90": Decimal("1.2815515655446004"),
    "0.95": Decimal("1.6448536269514722"),
    "0.975": Decimal("1.9599639845400536"),
    "0.99": Decimal("2.3263478740408408"),
}
ATTRIBUTES = ("stock", "reorder_point", "lead_time_days", "unit_cost")
COLUMNS = {
    "stock": "stock_column",
    "reorder_point": "reorder_point_column",
    "lead_time_days": "lead_time_column",
    "unit_cost": "unit_cost_column",
}
MAX_ROWS, MAX_ITEMS, MIN_DAYS = 10000, 50, 7
MAX_QUANTITY, MAX_LEAD_DAYS = 1_000_000, 365
DISPLAY = Decimal("0.000001")


@dataclass(frozen=True)
class ReorderItem:
    label: str
    stock: Decimal
    reorder_point: Decimal
    lead_time_days: int
    unit_cost: Decimal | None
    total_demand: Decimal
    mean: Fraction
    deviation: Decimal
    safety_stock: Decimal
    target: Decimal
    quantity: int
    cover: Fraction | None


@dataclass(frozen=True)
class PreparedReorder:
    items: tuple[ReorderItem, ...]
    window: tuple[str, str, int]
    budget: Decimal | None
    candidates: tuple[str, ...]
    weights: tuple[int, ...]
    problem: IntegerAllocation | None
    benefit_step: Fraction | None


def is_inventory_reorder(raw: dict[str, Any]) -> bool:
    return raw.get("kind") == "bounded_allocation" and raw.get("model") == METHOD


def _columns(raw: dict[str, Any]) -> list[str]:
    measures = [raw[COLUMNS[name]] for name in ATTRIBUTES if raw.get(COLUMNS[name])]
    return [raw["date_column"], raw["item_column"], raw["demand_column"], *measures]


def validate_reorder(raw: dict[str, Any]) -> None:
    if raw.get("assumptions_confirmed") is not True:
        fail(
            "decision_assumptions_required",
            "Confirm the demand history, lead times and service level are your assumptions.",
        )
    if raw.get("service_level") not in SERVICE_LEVELS:
        fail("reorder_service_level", "Choose a 90%, 95%, 97.5% or 99% service level.")
    columns = _columns(raw)
    if len(set(columns)) != len(columns):
        fail("distinct_columns_required", "Choose a different column for each reorder input.")
    items = raw.get("items")
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        fail("reorder_items", "List at most 50 items.")
    labels = [item.get("item") for item in items if isinstance(item, dict)]
    if len(labels) != len(items) or len(set(labels)) != len(labels):
        fail("reorder_items", "List each item once.")
    default = raw.get("default_lead_time_days")
    if default is not None and (type(default) is not int or not 1 <= default <= MAX_LEAD_DAYS):
        fail("reorder_lead_time", "Use a whole lead time from 1 to 365 days.")
    for name in ATTRIBUTES:
        if raw.get(COLUMNS[name]) and any(item.get(name) is not None for item in items):
            fail(
                "reorder_input_conflict",
                "Take each input either from a column or from typed item values, not both.",
            )
    if raw.get("lead_time_column") and default is not None:
        fail("reorder_input_conflict", "Use a lead-time column or a default lead time, not both.")
    for item in items:
        if not isinstance(item["item"], str) or not item["item"].strip():
            fail("reorder_items", "Name every listed item.")
        for name in ("stock", "reorder_point", "unit_cost"):
            if item.get(name) is not None:
                number(item[name])
        lead = item.get("lead_time_days")
        if lead is not None and (type(lead) is not int or not 1 <= lead <= MAX_LEAD_DAYS):
            fail("reorder_lead_time", "Use a whole lead time from 1 to 365 days.")
        if item.get("unit_cost") is not None and number(item["unit_cost"]) <= 0:
            fail("reorder_unit_cost", "Unit costs must be positive.")
    if raw.get("budget") is not None and number(raw["budget"]) < 0:
        fail("invalid_budget", "The budget must be zero or more.")


def reorder_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, table: TableData, raw: dict[str, Any]
) -> tuple[QueryPlan, dict[str, str]]:
    validate_reorder(raw)
    definition = view.definition or {}
    meanings = {column["name"]: column for column in definition.get("columns", [])}
    date_column, item_column = raw["date_column"], raw["item_column"]
    if not any(
        c.name == date_column and c.type == "date" and c.name in view.dimensions
        for c in view.columns
    ):
        fail("reorder_date_column", "Choose a confirmed complete date column for the history.")
    if meanings.get(item_column, {}).get("role") not in {"identifier", "dimension"}:
        fail("candidate_identity_required", "Choose a confirmed item identifier or category.")
    units: dict[str, str] = {}
    population: tuple[MetricFilter, ...] | None = None
    for name in _columns(raw)[2:]:
        method = validated_method(
            dict(
                kind="metric",
                column=name,
                aggregation=preferred_aggregation(view, name).value,
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
                "reorder_population_mismatch",
                "All reorder measures must use the same governed population filters.",
            )
        population = filters
        meaning = meanings[name]
        unit = meaning["currency"] or meaning["unit"]
        if not unit or meaning["unit_column"]:
            fail("fixed_unit_required", "Confirm a fixed unit for every reorder measure.")
        units[name] = unit
    demand_unit = units[raw["demand_column"]]
    if meanings[raw["demand_column"]]["currency"]:
        fail("reorder_demand_unit", "Demand needs a quantity unit, not a currency.")
    for key in ("stock_column", "reorder_point_column"):
        if raw.get(key) and units[raw[key]] != demand_unit:
            fail("reorder_unit_mismatch", "Stock and reorder point must use the demand unit.")
    if raw.get("lead_time_column") and units[raw["lead_time_column"]].lower() not in {
        "day",
        "days",
    }:
        fail("reorder_lead_time", "The lead-time column must be confirmed in days.")
    if raw.get("unit_cost_column") and not meanings[raw["unit_cost_column"]]["currency"]:
        fail("reorder_unit_cost", "The unit-cost column needs a confirmed currency.")
    if len(population or ()) > 20:
        fail("analysis_filter_limit", "Use at most twenty total governed filters.")
    where, params = build_where(view, population or ())
    sql = f'SELECT {", ".join(quote_identifier(name) for name in _columns(raw))} FROM "dataset"'
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (
        f" ORDER BY {quote_identifier(item_column)}, {quote_identifier(date_column)}"
        f" LIMIT {MAX_ROWS + 1}"
    )
    validate_read_only(sql)
    return QueryPlan(
        uuid4(), scope.workspace_id, did, "Inventory reorder history", sql, tuple(params)
    ), units


def _day(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    fail("reorder_dates", "Every history row needs a complete date.")


def _sqrt(value: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return value.sqrt()


def _decimal(value: Fraction) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return Decimal(value.numerator) / Decimal(value.denominator)


def _shown(value: Decimal | Fraction) -> str:
    amount = _decimal(value) if isinstance(value, Fraction) else value
    with localcontext() as context:
        context.prec = 60
        return encoded(amount.quantize(DISPLAY, rounding=ROUND_HALF_EVEN).normalize() + 0)


def _latest(rows: list[tuple[Any, ...]], index: int, name: str, label: str) -> Decimal | None:
    final = max(_day(row[0]) for row in rows)
    values = {row[index] for row in rows if _day(row[0]) == final}
    if len(values) != 1 or None in values:
        fail(
            "reorder_latest_value",
            f"{label} needs one complete {name} value on its latest date.",
        )
    return number(values.pop())


def prepare_reorder(raw: dict[str, Any], rows: tuple[tuple[Any, ...], ...]) -> PreparedReorder:
    validate_reorder(raw)
    if not rows:
        fail("reorder_history", "No history rows match this population.")
    if len(rows) > MAX_ROWS:
        fail("reorder_history", "Use at most 10,000 history rows; filter the population first.")
    days = [_day(row[0]) for row in rows]
    first, last = min(days), max(days)
    span = (last - first).days + 1
    if span < MIN_DAYS:
        fail("reorder_history", "Use a demand history covering at least seven calendar days.")
    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        if row[1] is None or not str(row[1]).strip():
            fail("candidate_identity_required", "Every history row needs an item identifier.")
        grouped.setdefault(str(row[1]), []).append(row)
    typed = {item["item"]: item for item in raw["items"]}
    if set(typed) - set(grouped):
        fail("reorder_items", "A listed item has no history in this population.")
    labels = sorted(typed) if typed else sorted(grouped)
    if len(labels) > MAX_ITEMS:
        fail("reorder_items", "Plan at most 50 items at once; list the items to include.")
    positions = {name: 3 + i for i, name in enumerate(n for n in ATTRIBUTES if raw.get(COLUMNS[n]))}
    level = SERVICE_LEVELS[raw["service_level"]]
    items = []
    for label in labels:
        history = grouped[label]
        values: dict[str, Decimal | None] = {}
        for name in ATTRIBUTES:
            if name in positions:
                values[name] = _latest(history, positions[name], raw[COLUMNS[name]], label)
            elif typed.get(label, {}).get(name) is not None:
                values[name] = number(typed[label][name])
            else:
                values[name] = None
        if values["lead_time_days"] is None and raw.get("default_lead_time_days"):
            values["lead_time_days"] = Decimal(raw["default_lead_time_days"])
        missing = [
            name for name in ("stock", "reorder_point", "lead_time_days") if values[name] is None
        ]
        if missing:
            fail("reorder_missing_input", f"{label} needs {', '.join(missing)}.")
        lead = values["lead_time_days"]
        assert lead is not None
        if lead != lead.to_integral_value() or not 1 <= lead <= MAX_LEAD_DAYS:
            fail("reorder_lead_time", f"{label} needs a whole lead time from 1 to 365 days.")
        if values["unit_cost"] is not None and values["unit_cost"] <= 0:
            fail("reorder_unit_cost", f"{label} needs a positive unit cost.")
        daily: dict[date, Fraction] = {}
        for row in history:
            if row[2] is not None:
                daily[_day(row[0])] = daily.get(_day(row[0]), Fraction(0)) + Fraction(
                    number(row[2])
                )
        total = sum(daily.values(), Fraction(0))
        if total < 0:
            fail("reorder_demand", f"{label} has negative net demand in this history.")
        mean = total / span
        variance = (
            sum(((value - mean) ** 2 for value in daily.values()), Fraction(0))
            + (span - len(daily)) * mean**2
        ) / (span - 1)
        deviation = _sqrt(_decimal(variance))
        days_lead = int(lead)
        with localcontext() as context:
            context.prec = 50
            safety = level * deviation * _sqrt(Decimal(days_lead))
        stock, point = values["stock"], values["reorder_point"]
        assert stock is not None and point is not None
        exact = Fraction(point) + mean * days_lead - Fraction(stock)
        with localcontext() as context:
            context.prec = 50
            target = Decimal(point) + _decimal(mean * days_lead) + safety
            needed = (
                ceil(exact)
                if safety == 0
                else int((_decimal(exact) + safety).to_integral_value(rounding=ROUND_CEILING))
            )
        quantity = max(0, needed) if stock <= point else 0
        if quantity > MAX_QUANTITY:
            fail("reorder_quantity_limit", f"{label} needs more than 1,000,000 units.")
        items.append(
            ReorderItem(
                label,
                stock,
                point,
                days_lead,
                values["unit_cost"],
                _decimal(total).normalize(),
                mean,
                deviation,
                safety,
                target,
                quantity,
                Fraction(stock) / mean if mean else None,
            )
        )
    ordered = tuple(sorted(items, key=lambda i: (i.cover is None, i.cover or Fraction(0), i.label)))
    budget = number(raw["budget"]) if raw.get("budget") is not None else None
    ordering = [item for item in ordered if item.quantity > 0]
    if budget is not None and any(item.unit_cost is None for item in ordering):
        fail("reorder_unit_cost", "Give a unit cost for every item to order within a budget.")
    full_cost = sum(
        ((item.unit_cost or Decimal(0)) * item.quantity for item in ordering), Decimal(0)
    )
    if budget is None or full_cost <= budget or not ordering:
        return PreparedReorder(
            ordered, (first.isoformat(), last.isoformat(), span), budget, (), (), None, None
        )
    covers = sorted({(i.cover is None, i.cover or Fraction(0)) for i in ordering}, reverse=True)
    weights = tuple(covers.index((i.cover is None, i.cover or Fraction(0))) + 1 for i in ordering)
    maxima = tuple(item.quantity for item in ordering)
    costs = tuple(item.unit_cost or Decimal(0) for item in ordering)
    benefits, step = exact_scale(
        tuple(cost * weight for cost, weight in zip(costs, weights, strict=True)), maxima
    )
    resources, _ = exact_scale((*costs, budget), (*maxima, 0))
    problem = IntegerAllocation(
        benefits,
        (resources[:-1],),
        (resources[-1],),
        tuple(0 for _ in ordering),
        maxima,
        (),
        (),
    )
    return PreparedReorder(
        ordered,
        (first.isoformat(), last.isoformat(), span),
        budget,
        tuple(item.label for item in ordering),
        weights,
        problem,
        step,
    )


def checked_reorder(prepared: PreparedReorder, outcome: SolverOutcome | None) -> dict[str, Any]:
    funded = {item.label: item.quantity for item in prepared.items}
    solver_evidence = None
    status, funding = "feasible", "complete"
    if prepared.problem is not None:
        if outcome is None or outcome.status not in {"OPTIMAL", "FEASIBLE", "UNKNOWN"}:
            fail("allocation_solver_evidence", "The allocation solver returned invalid evidence.")
        solver_evidence = dict(
            version="bounded-cp-sat-v1",
            solver="OR-Tools CP-SAT",
            solver_version="9.15.6755",
            problem_checksum=checksum(asdict(prepared.problem)),
            **{
                **asdict(outcome),
                "quantities": list(outcome.quantities) if outcome.quantities is not None else None,
            },
        )
        if outcome.status == "UNKNOWN":
            if outcome.quantities is not None or outcome.objective is not None:
                fail("allocation_solver_evidence", "The solver returned inconsistent evidence.")
            status, funding = "unknown", "unresolved"
            funded = dict.fromkeys(funded, 0)
        else:
            quantities = outcome.quantities
            if (
                quantities is None
                or len(quantities) != len(prepared.candidates)
                or any(
                    type(q) is not int or not 0 <= q <= cap
                    for q, cap in zip(quantities, prepared.problem.maximum, strict=True)
                )
            ):
                fail(
                    "allocation_solver_evidence", "The proposed quantities fail independent checks."
                )
            funded = dict.fromkeys(funded, 0) | dict(
                zip(prepared.candidates, quantities, strict=True)
            )
            costs = {item.label: item.unit_cost or Decimal(0) for item in prepared.items}
            weights = dict(zip(prepared.candidates, prepared.weights, strict=True))
            assert prepared.budget is not None and prepared.benefit_step is not None
            spent = sum((costs[label] * q for label, q in funded.items()), Decimal(0))
            weighted = sum(
                (costs[label] * weights[label] * funded[label] for label in prepared.candidates),
                Decimal(0),
            )
            if spent > prepared.budget:
                fail("allocation_solver_evidence", "The proposed quantities exceed the budget.")
            if (
                type(outcome.objective) is not int
                or Fraction(weighted) != outcome.objective * prepared.benefit_step
            ):
                fail("allocation_solver_evidence", "The objective differs from exact arithmetic.")
            funding = "budget_limited"
    rows = []
    for rank, item in enumerate(prepared.items, 1):
        ordered = funded[item.label]
        reaches = Decimal(item.stock) + ordered
        if ordered > 0 and not (reaches >= item.target > reaches - 1) and funding == "complete":
            fail("reorder_verification", "A reorder quantity is not the smallest whole amount.")
        rows.append(
            dict(
                rank=rank,
                candidate=item.label,
                stock=encoded(item.stock),
                reorder_point=encoded(item.reorder_point),
                lead_time_days=item.lead_time_days,
                total_demand=encoded(item.total_demand),
                mean_daily_demand=_shown(item.mean),
                daily_demand_deviation=_shown(item.deviation),
                lead_time_demand=_shown(item.mean * item.lead_time_days),
                safety_stock=_shown(item.safety_stock),
                target_level=_shown(item.target),
                days_of_cover=_shown(item.cover) if item.cover is not None else None,
                below_reorder_point=item.stock <= item.reorder_point,
                recommended_quantity=item.quantity,
                quantity=ordered,
                unit_cost=encoded(item.unit_cost) if item.unit_cost is not None else None,
                cost=encoded(item.unit_cost * ordered) if item.unit_cost is not None else None,
                urgency_weight=dict(zip(prepared.candidates, prepared.weights, strict=True)).get(
                    item.label
                ),
            )
        )
    costs_known = all(row["cost"] is not None for row in rows if row["quantity"])
    total_cost = (
        encoded(sum((Decimal(str(row["cost"])) for row in rows if row["quantity"]), Decimal(0)))
        if costs_known
        else None
    )
    first, last, span = prepared.window
    return dict(
        version=VERSION,
        method_version=METHOD,
        status=status,
        funding=funding,
        reason={
            "complete": "Every recommended quantity is included.",
            "budget_limited": (
                "The budget cannot fund every recommended quantity; the solver chose whole "
                "quantities within it, favouring items with fewer days of cover."
            ),
            "unresolved": "The bounded search found no usable selection. No order is recommended.",
        }[funding],
        history=dict(start=first, end=last, calendar_days=span),
        budget=encoded(prepared.budget) if prepared.budget is not None else None,
        cost=total_cost,
        unused_budget=encoded(prepared.budget - Decimal(total_cost))
        if prepared.budget is not None and total_cost is not None
        else None,
        items_to_order=sum(1 for row in rows if row["quantity"]),
        allocations=rows,
        verification=dict(
            quantities="passed",
            minimal_whole_units="passed" if funding == "complete" else "not_applicable",
            budget="passed"
            if prepared.budget is not None and status == "feasible"
            else "not_applicable",
            objective="passed" if funding == "budget_limited" else "not_applicable",
        ),
        solver_evidence=solver_evidence,
        assumptions=[
            "Average daily demand is total demand over every calendar day from the first to "
            "the last history date; days without rows count as zero demand.",
            "Safety stock = service-level z times sample standard deviation of daily demand times "
            "√(lead time in days), assuming roughly normal, independent daily demand.",
            "Target level = reorder point + average daily demand times lead time + safety stock. "
            "An item at or below its reorder point orders the smallest whole quantity that "
            "reaches the target; other items order nothing.",
            "Stock, reorder point, lead time and unit cost are taken as given; open orders, "
            "minimum order sizes and supplier pack sizes are not considered.",
            *(
                [
                    "Under a budget the solver maximises spend weighted by urgency: the item "
                    "group with the fewest days of cover has the largest weight. It is a stated "
                    "priority rule, not a cost of running out."
                ]
                if funding != "complete"
                else []
            ),
        ],
        limitations=[
            "A recommendation is not an order; no purchase is placed.",
            "Displayed demand, deviation, safety stock, target and cover values are rounded to "
            "six decimal places; quantities use full precision.",
            "Service levels are cycle service levels under the normal-demand assumption, "
            "not guaranteed fill rates.",
        ],
    )


def reopen_reorder(prepared: PreparedReorder, retained: dict[str, Any]) -> dict[str, Any]:
    evidence = retained.get("solver_evidence")
    if evidence is None:
        return checked_reorder(prepared, None)
    quantities = evidence["quantities"]
    return checked_reorder(
        prepared,
        SolverOutcome(
            evidence["status"],
            tuple(quantities) if quantities is not None else None,
            evidence["objective"],
            evidence["termination"],
        ),
    )
