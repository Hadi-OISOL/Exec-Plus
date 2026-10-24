"""Use case: Regression tests for live defects D13 (next steps), D20 (row products), D21 (weekdays).

What it does: Replays the real failing questions through a scripted planner and the real thread,
router, query and receipt services, and checks every number against independent pandas/Decimal.
"""

import io
import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pandas as pd
import pytest

from execplus.application.services.intent_router import (
    NEXT_STEPS_ROUTE,
    DatasetGuide,
    IntentRouterService,
)
from execplus.application.services.threads import ThreadService
from execplus.domain.conversation_requirements import asks_for_next_steps, product_choices
from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.insights import next_steps
from execplus.domain.intent import route_response, with_product, with_time_grain
from execplus.domain.models import WorkspaceScope
from execplus.domain.semantics import (
    AggregationKind,
    DatasetView,
    MetricRequest,
    SemanticColumn,
    plan_query,
)
from execplus.domain.understanding import product_unit
from execplus.infrastructure.query.validation import validated_query
from test_harness_context_integration import Planner
from test_workspace_integration import dataset, identity, upload, workspace

DID = UUID(int=7)


def _view(*columns: tuple[str, str, str]) -> DatasetView:
    entries = tuple(SemanticColumn(name, kind, role) for name, kind, role in columns)
    return DatasetView(
        entries,
        frozenset(c.name for c in entries if c.role == "metric"),
        frozenset(c.name for c in entries if c.role == "dimension"),
    )


RESTAURANT_VIEW = _view(
    ("order_date", "date", "dimension"),
    ("branch", "text", "dimension"),
    ("orders", "integer", "metric"),
    ("revenue", "decimal", "metric"),
)
INVENTORY_VIEW = _view(
    ("sku", "text", "dimension"),
    ("warehouse", "text", "dimension"),
    ("on_hand_units", "integer", "metric"),
    ("unit_cost", "decimal", "metric"),
    ("unit_price", "decimal", "metric"),
)


def _scope() -> WorkspaceScope:
    return WorkspaceScope(UUID(int=1), UUID(int=2), frozenset({"owner"}), frozenset({DID}))


def _plan(view: DatasetView, **changes):
    request = MetricRequest(**{"metric": "orders", "aggregation": AggregationKind.SUM, **changes})
    return plan_query(_scope(), DID, view, request, row_limit=1000)


def _routed(plan: dict, view: DatasetView, question: str):
    return with_product(
        question, with_time_grain(question, route_response(json.dumps(plan), view), view), view
    )


def _numerical(**plan):
    return {
        "kind": "numerical",
        "plan": {"aggregation": "sum", "group_by": [], "filters": [], **plan},
    }


def _restaurant_csv() -> bytes:
    lines = ["order_date,branch,orders,revenue"]
    start = date(2025, 3, 3)
    for offset in range(28):
        day = start + timedelta(days=offset)
        for index, branch in enumerate(("Clifton", "Gulshan")):
            orders = 90 + (offset * 7) % 13 + index * 5 + (35 if day.isoweekday() >= 6 else 0)
            lines.append(f"{day.isoformat()},{branch},{orders},{orders * 1250}.50")
    return ("\n".join(lines) + "\n").encode()


def _inventory_csv() -> bytes:
    rows = [
        ("SKU-1", "North", 120, "12.50", "19.99"),
        ("SKU-2", "North", 40, "3.333", "5.25"),
        ("SKU-3", "South", 75, "100.10", "149.00"),
        ("SKU-4", "South", 0, "7.00", "9.00"),
        ("SKU-5", "East", 310, "0.125", "0.40"),
        ("SKU-6", "East", 18, "2500.00", "3100.00"),
    ]
    body = "sku,warehouse,on_hand_units,unit_cost,unit_price\n"
    return (body + "\n".join(",".join(map(str, row)) for row in rows) + "\n").encode()


def _retail_csv() -> bytes:
    lines = ["order_date,region,product,units,revenue"]
    regions = ("North", "North", "North", "South", "South", "East", "West")
    for index in range(70):
        region = regions[index % len(regions)]
        units = 3 + (index * 5) % 11 + (25 if index == 41 else 0)
        price = {"North": "20.00", "South": "18.50", "East": "25.00", "West": "15.00"}[region]
        day = date(2025, 1, 1) + timedelta(days=index)
        product = ("Tea", "Coffee", "Juice")[index % 3]
        lines.append(f"{day},{region},{product},{units},{Decimal(price) * units}")
    return ("\n".join(lines) + "\n").encode()


def _setup(env, content: bytes, name: str, *plans, email="nextsteps@example.test"):
    headers, actor = identity(env, email)
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    response = upload(env, headers, wid, did, content, name, "text/csv")
    assert response.status_code == 201, response.text
    model = Planner(*plans)
    router = IntentRouterService(
        model,
        env.runtime.analytics,
        patterns=env.runtime.intent_router.patterns,
        context_enabled=True,
        orchestration_enabled=True,
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    return actor, UUID(wid), UUID(did), UUID(response.json()["id"]), model, threads


def _frame(content: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(content), dtype=str)


# D21: weekday and weekend calendar groups.


def test_weekday_and_weekend_groups_compile_to_bound_iso_day_sql():
    weekday = _plan(RESTAURANT_VIEW, group_by=("order_date",), period="weekday")
    assert weekday.sql.startswith('SELECT STRFTIME("order_date", ?) AS "order_date"')
    assert weekday.params == ("%u %A",)
    weekend = _plan(RESTAURANT_VIEW, group_by=("order_date",), period="weekend")
    assert 'CASE WHEN ISODOW("order_date") >= ? THEN ? ELSE ? END' in weekend.sql
    assert weekend.params == (6, "weekend", "weekday")
    for plan in (weekday, weekend):
        validated_query(plan.sql, {"dataset"}, len(plan.params))
    month = _plan(RESTAURANT_VIEW, group_by=("order_date",), period="month")
    assert month.sql == (
        'SELECT CAST(DATE_TRUNC(?, "order_date") AS DATE) AS "order_date", '
        'SUM("orders") AS "__value" FROM "dataset" GROUP BY ALL ORDER BY "order_date" LIMIT 1000'
    )


@pytest.mark.parametrize(
    "sql",
    [
        'SELECT STRFTIME("d", \'%A\') AS "d", SUM("x") AS v FROM "dataset" GROUP BY ALL LIMIT 5',
        'SELECT CASE WHEN ISODOW("d") >= 6 THEN ? ELSE ? END AS "d", SUM("x") AS v '
        'FROM "dataset" GROUP BY ALL LIMIT 5',
        'SELECT CASE WHEN "x" >= ? THEN ? ELSE ? END AS "d", SUM("x") AS v '
        'FROM "dataset" GROUP BY ALL LIMIT 5',
        'SELECT ISODOW("d") AS "d", SUM("x") AS v FROM "dataset" GROUP BY ALL LIMIT 5',
        'SELECT "a" * "b" AS v FROM "dataset" LIMIT 5',
        'SELECT SUM("a" * ?) AS v FROM "dataset" LIMIT 5',
    ],
)
def test_execution_boundary_rejects_unbound_or_misplaced_calendar_and_product_forms(sql):
    from execplus.domain.errors import UnsafeQueryError

    with pytest.raises(UnsafeQueryError):
        validated_query(sql, {"dataset"}, sql.count("?"))


@pytest.mark.parametrize(
    ("question", "plan", "period"),
    [
        (
            "Do weekends get more orders than weekdays?",
            _numerical(metric="orders", group_by=["order_date"], period="week"),
            "weekend",
        ),
        ("weekday vs weekend sales", _numerical(metric="revenue"), "weekend"),
        (
            "Which day of the week is busiest?",
            _numerical(metric="orders", group_by=["order_date"], order="desc"),
            "weekday",
        ),
        ("Are Mondays slower than Fridays?", _numerical(metric="orders"), "weekday"),
        (
            "Which month had the most orders on mondays?",
            _numerical(metric="orders", group_by=["order_date"], period="month"),
            "month",
        ),
    ],
)
def test_day_of_week_questions_select_the_iso_weekday_grouping(question, plan, period):
    routed = _routed(plan, RESTAURANT_VIEW, question)
    assert routed.request.period == period
    assert "order_date" in routed.request.group_by


@pytest.mark.asyncio
async def test_weekend_and_weekday_answers_match_pandas_and_replay(integration):
    content = _restaurant_csv()
    observed_week_plan = _numerical(
        metric="orders", aggregation="avg", group_by=["order_date"], period="week"
    )
    busiest = _numerical(metric="orders", group_by=["order_date"], order="desc")
    actor, wid, did, uid, _, threads = _setup(
        integration,
        content,
        "restaurant_daily.csv",
        observed_week_plan,
        busiest,
        _numerical(metric="orders", group_by=["order_date"], order="asc"),
    )
    frame = _frame(content)
    frame["orders"] = frame["orders"].map(Decimal)
    days = pd.to_datetime(frame["order_date"])
    frame["part"] = days.dt.dayofweek.map(lambda d: "weekend" if d >= 5 else "weekday")
    frame["dow"] = days.dt.dayofweek.map(lambda d: f"{d + 1} {date(2025, 3, 3 + d):%A}")
    thread = await threads.start_thread(actor, wid, did, uid)

    answer, turn = await threads.ask(
        actor, wid, thread.id, "Do weekends get more orders than weekdays?"
    )
    assert turn.status == "complete"
    result, lineage = answer
    expected = {
        part: sum(group, Decimal(0)) / len(group) for part, group in frame.groupby("part")["orders"]
    }
    assert {row[0]: row[1] for row in result.rows} == {
        part: value.quantize(Decimal("1e-12")) for part, value in expected.items()
    }
    replayed, _ = await integration.runtime.analytics.replay(actor, wid, lineage.query_id)
    assert replayed.rows == result.rows

    answer, turn = await threads.ask(actor, wid, thread.id, "Which day of the week is busiest?")
    (per_day, per_day_lineage), (result, lineage) = answer.data, answer.additional_data[0]
    totals = frame.groupby("dow")["orders"].apply(lambda s: sum(s, Decimal(0)))
    day_counts = frame.groupby("dow")["order_date"].nunique()
    averages = {
        key: (totals[key] / day_counts[key]).quantize(Decimal("1e-12")) for key in totals.index
    }
    assert [(row[0], row[1]) for row in per_day.rows] == sorted(
        averages.items(), key=lambda item: (-item[1], item[0])
    )
    assert "COUNT(DISTINCT" in per_day_lineage.sql
    assert [(row[0], row[1]) for row in result.rows] == sorted(
        totals.items(), key=lambda item: (-item[1], item[0])
    )
    assert result.rows[0][0] == totals.idxmax()
    for item in (per_day, result):
        replayed, _ = await integration.runtime.analytics.replay(actor, wid, item.query_id)
        assert replayed.rows == item.rows

    answer, turn = await threads.ask(actor, wid, thread.id, "and the lowest?")
    result, lineage = answer.additional_data[0]
    assert "STRFTIME(" in lineage.sql
    assert result.rows[0] == (totals.idxmin(), totals.min())


# D20: row-level products such as inventory value.


def test_product_compiles_inside_the_aggregate_and_old_plans_are_unchanged():
    old = plan_query(
        _scope(),
        DID,
        INVENTORY_VIEW,
        MetricRequest("on_hand_units", AggregationKind.SUM, ("warehouse",)),
        row_limit=100,
    )
    assert old.sql == (
        'SELECT "warehouse", SUM("on_hand_units") AS "__value" FROM "dataset" '
        'GROUP BY "warehouse" ORDER BY "warehouse" LIMIT 100'
    )
    product = plan_query(
        _scope(),
        DID,
        INVENTORY_VIEW,
        MetricRequest("on_hand_units", AggregationKind.SUM, ("warehouse",), times="unit_cost"),
        row_limit=100,
    )
    assert 'SUM("on_hand_units" * "unit_cost")' in product.sql
    validated_query(product.sql, {"dataset"}, 0)
    for aggregation, times in ((AggregationKind.MAX, "unit_cost"), (AggregationKind.SUM, "sku")):
        with pytest.raises(UnsupportedQuestionError):
            plan_query(
                _scope(),
                DID,
                INVENTORY_VIEW,
                MetricRequest("on_hand_units", aggregation, times=times),
                row_limit=100,
            )
    bad = route_response(
        json.dumps(_numerical(metric="on_hand_units", aggregation="count", times="unit_cost")),
        INVENTORY_VIEW,
    )
    assert bad.request is None


def test_product_units_keep_one_currency_and_refuse_money_times_money():
    assert product_unit(None, "on_hand_units", "unit_cost_pkr") == "PKR"
    assert product_unit(None, "on_hand_units", "unit_cost") == ""
    with pytest.raises(UnsupportedQuestionError, match="different currencies"):
        product_unit(None, "price_usd", "cost_pkr")
    with pytest.raises(UnsupportedQuestionError, match="both money"):
        product_unit(None, "price_pkr", "cost_pkr")
    definition = {
        "columns": [
            {"name": "qty", "unit": "kg", "currency": ""},
            {"name": "rate", "unit": "", "currency": "EUR"},
        ]
    }
    assert product_unit(definition, "qty", "rate") == "EUR"


def test_a_named_value_offers_the_product_and_an_explicit_product_is_applied():
    observed = _numerical(metric="on_hand_units", group_by=["warehouse"])
    question = "Total inventory value by warehouse"
    routed = _routed(observed, INVENTORY_VIEW, question)
    assert routed.request.times is None
    assert product_choices(question, routed.request, INVENTORY_VIEW) == (
        "What is the total of on_hand_units * unit_cost by warehouse?",
        "What is the total of on_hand_units * unit_price by warehouse?",
        "What is the total of on_hand_units by warehouse?",
    )
    assert product_choices("Total units by warehouse", routed.request, INVENTORY_VIEW) == ()
    chosen = _routed(observed, INVENTORY_VIEW, "What is the total of on_hand_units * unit_cost?")
    assert (chosen.request.metric, chosen.request.times) == ("on_hand_units", "unit_cost")
    reversed_ = _routed(
        _numerical(metric="unit_price"), INVENTORY_VIEW, "revenue = on_hand_units times unit_price"
    )
    assert (reversed_.request.metric, reversed_.request.times) == ("on_hand_units", "unit_price")


@pytest.mark.asyncio
async def test_inventory_value_clarifies_then_sums_the_exact_row_products(integration):
    content = _inventory_csv()
    observed = _numerical(metric="on_hand_units", group_by=["warehouse"])
    direct = _numerical(metric="on_hand_units", aggregation="avg", times="unit_price")
    actor, wid, did, uid, _, threads = _setup(
        integration,
        content,
        "inventory.csv",
        observed,
        _numerical(metric="on_hand_units", group_by=["sku"], times="unit_cost"),
        direct,
    )
    frame = _frame(content)
    values = {
        warehouse: sum(
            (
                Decimal(units) * Decimal(cost)
                for units, cost in zip(g.on_hand_units, g.unit_cost, strict=True)
            ),
            Decimal(0),
        )
        for warehouse, g in frame.groupby("warehouse")
    }
    thread = await threads.start_thread(actor, wid, did, uid)

    answer, turn = await threads.ask(actor, wid, thread.id, "Total inventory value by warehouse")
    assert answer is None and turn.kind == "ambiguous" and turn.query_id is None
    choices = turn.evidence["clarification"]["choices"]
    assert choices[0] == "What is the total of on_hand_units * unit_cost by warehouse?"
    assert choices[-1] == "What is the total of on_hand_units by warehouse?"

    answer, turn = await threads.ask(actor, wid, thread.id, choices[0])
    assert turn.status == "complete"
    assert turn.model_route == "deterministic:offered-question-v1"
    result, lineage = answer
    assert {row[0]: row[1] for row in result.rows} == values
    assert lineage.metric == "on_hand_units * unit_cost"
    replayed, _ = await integration.runtime.analytics.replay(actor, wid, lineage.query_id)
    assert replayed.rows == result.rows

    answer, turn = await threads.ask(actor, wid, thread.id, "and by sku?")
    assert turn.status == "complete"
    result, lineage = answer
    assert {row[0]: row[1] for row in result.rows} == {
        sku: Decimal(units) * Decimal(cost)
        for sku, units, cost in zip(frame.sku, frame.on_hand_units, frame.unit_cost, strict=True)
    }

    answer, turn = await threads.ask(
        actor, wid, thread.id, "What is the average sales value per item on hand?"
    )
    expected = sum(
        (
            Decimal(u) * Decimal(p)
            for u, p in zip(frame.on_hand_units, frame.unit_price, strict=True)
        ),
        Decimal(0),
    ) / len(frame)
    assert answer.value == expected.quantize(Decimal("1e-12"))


# D13: grounded next steps.


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What should I do to grow sales?", True),
        ("what should HR focus on?", True),
        ("batao kya karna chahiye?", True),
        ("How can we increase revenue?", True),
        ("What should I ask?", False),
        ("What should I reorder first?", False),
        ("Total revenue by region", False),
    ],
)
def test_open_advice_questions_are_recognized(question, expected):
    assert asks_for_next_steps(question) is expected


def _card(analyst, card_id, summary, *actions):
    return {"analyst": analyst, "id": card_id, "summary": summary, "actions": list(actions)}


def test_next_steps_prefer_named_measures_and_carry_a_follow_up_question():
    ask = {"kind": "ask", "payload": {"type": "ask", "question": "Compare average units by region"}}
    cards = [
        _card("quality", "quality:file", "All 10 rows passed basic checks.", ask),
        _card("segment", "segment:units:region", "North averages 9 units.", ask),
        _card(
            "outlier",
            "outlier:revenue",
            "2 revenue values are unusual.",
            {"kind": "investigate_outliers", "payload": {"type": "anomalies", "metric": "revenue"}},
        ),
    ]
    steps = next_steps(cards, focus=("units",))
    assert steps == [
        ("Look into the gap between groups: North averages 9 units.", ask["payload"]["question"]),
        (
            "Review the unusual values: 2 revenue values are unusual.",
            "Show the 10 records with the highest revenue",
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question", ["What should I do to grow sales?", "batao kya karna chahiye?"]
)
async def test_what_should_i_do_returns_grounded_clickable_next_steps(integration, question):
    content = _retail_csv()
    actor, wid, did, uid, model, threads = _setup(integration, content, "retail_sales.csv")
    frame = _frame(content)
    thread = await threads.start_thread(actor, wid, did, uid)

    answer, turn = await threads.ask(actor, wid, thread.id, question)

    assert turn.status == "complete"
    assert model.requests == []
    assert isinstance(answer, DatasetGuide)
    assert answer.model_route == NEXT_STEPS_ROUTE
    assert answer.focus == "next_steps"
    assert 3 <= len(answer.suggestions) <= 5
    assert "not proof of what causes" in answer.message
    frame["revenue"] = frame["revenue"].map(Decimal)
    counts = frame["region"].value_counts()
    leader = counts.idxmax()
    assert f"{leader} is the largest region group with {counts.max()} of {len(frame)} rows" in (
        answer.message
    )
    means = frame.groupby("region")["revenue"].apply(lambda s: sum(s, Decimal(0)) / len(s))
    high, low = means.idxmax(), means.idxmin()
    gap = (means[high] - means[low]).quantize(Decimal("0.01"))
    assert f"{high} has the highest average revenue" in answer.message
    assert f"{gap} more than {low}" in answer.message
    rho = frame["revenue"].astype(float).corr(frame["units"].astype(float), method="spearman")
    assert f"rank score {rho:.3f}" in answer.message
    assert "Compare average revenue by region" in answer.suggestions
    assert "Show the 10 records with the highest revenue" in answer.suggestions

    followed, followed_turn = await threads.ask(
        actor, wid, thread.id, "Compare average revenue by region"
    )
    assert followed_turn.model_route == "deterministic:offered-question-v1"
    result, _ = followed
    assert {row[0]: row[1] for row in result.rows} == {
        region: value.quantize(Decimal("1e-12")) for region, value in means.items()
    }
    assert model.requests == []
