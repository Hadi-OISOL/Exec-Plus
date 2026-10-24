"""Use case: Regression tests for the run-4 PARTIAL answers (rates, labels, spending, ties).

What it does: Checks one-step rates/net values against pandas/Decimal, measure and category value
matching, average-first score choices, label-variant flags, debit-only spending and named ties,
using pure functions and scripted-planner replays through the real thread/query/receipt services.
"""

import io
from decimal import Decimal
from uuid import uuid4

import pandas as pd
import pytest

from execplus.application.conversation import EvidenceAnswer
from execplus.application.services.insight_presentation import build_insight_packet
from execplus.domain.conversation_requirements import spending_filter
from execplus.domain.derived_measures import (
    DERIVED_ROUTE,
    DerivedChoices,
    DerivedRequest,
    combine,
    derived_request,
    measures_for,
)
from execplus.domain.label_matching import label_variants, match_label, variants_note
from execplus.domain.models import CalculationLineage, QueryResult
from execplus.domain.offline_planner import offline_plan, working_choices
from execplus.domain.response_synthesis import NAMED_VERSION, RANKED_VERSION
from execplus.domain.semantics import AggregationKind, FilterOperator, MetricFilter, MetricRequest
from execplus.presentation.routes.analytics import numerical_answer_body
from test_choice_relevance_per_day import (
    FUNNEL,
    LEDGER,
    LEDGER_VALUES,
    PLANTS,
    _ledger_csv,
    _setup,
    _view,
)

CHANNELS = {"channel": ("Email", "Search", "Social")}


def _sum(frame: pd.DataFrame, column: str, by: str | None = None):
    total = lambda values: sum(map(Decimal, values), Decimal(0))  # noqa: E731
    return frame.groupby(by)[column].apply(total) if by else total(frame[column])


@pytest.mark.parametrize(
    ("question", "view", "values", "operation", "left", "right", "group", "order"),
    [
        (
            "What is the conversion rate from clicks to purchases by channel?",
            FUNNEL,
            CHANNELS,
            "ratio",
            "purchases",
            "clicks",
            "channel",
            None,
        ),
        (
            "Which channel has the lowest cost per purchase?",
            FUNNEL,
            CHANNELS,
            "ratio",
            "spend_usd",
            "purchases",
            "channel",
            "asc",
        ),
        (
            "What is our net income (credits minus debits)?",
            LEDGER,
            LEDGER_VALUES,
            "difference",
            "amount_pkr",
            "amount_pkr",
            None,
            None,
        ),
        (
            "What is metric_01_defects as a percentage of metric_01_output?",
            PLANTS,
            {},
            "ratio",
            "metric_01_defects",
            "metric_01_output",
            None,
            None,
        ),
    ],
)
def test_live_rate_and_net_questions_plan_both_components(
    question, view, values, operation, left, right, group, order
):
    request = derived_request(question, view, values)
    assert isinstance(request, DerivedRequest)
    assert request.operation == operation and request.order == order
    assert (request.left.metric, request.right.metric) == (left, right)
    assert request.left.group_by == request.right.group_by == ((group,) if group else ())
    assert request.left.aggregation == request.right.aggregation == AggregationKind.SUM


def test_net_income_filters_each_entry_type_and_keeps_the_currency():
    question = "What is our net income (credits \u2212 debits)?"
    request = derived_request(question, LEDGER, LEDGER_VALUES)
    assert request.left.filters == (MetricFilter("entry_type", FilterOperator.IEQ, "credit"),)
    assert request.right.filters == (MetricFilter("entry_type", FilterOperator.IEQ, "debit"),)
    assert request.unit == "PKR" and request.name == "net"


def test_ambiguous_rate_offers_choices_that_each_plan_a_rate():
    choices = derived_request("What is the overall defect rate?", PLANTS)
    assert isinstance(choices, DerivedChoices)
    assert choices.choices[0] == "What is metric_01_defects as a percentage of metric_01_output?"
    planned = [derived_request(item, PLANTS) for item in choices.choices]
    assert all(isinstance(item, DerivedRequest) for item in planned)


@pytest.mark.parametrize(
    "question",
    [
        "What is the 30-day readmission rate?",
        "What is the conversion rate by channel?",
        "cost per purchase for Email",
        "cost per purchase in 2024",
        "What is the average temperature per sensor?",
        "Total spend by channel",
        "What is the revenue per day?",
    ],
)
def test_unknown_parts_or_extra_conditions_keep_the_previous_behaviour(question):
    view = _view(
        ("week_start", "date", "dimension"),
        ("channel", "text", "dimension"),
        ("clicks", "integer", "metric"),
        ("purchases", "integer", "metric"),
        ("spend_usd", "decimal", "metric"),
        ("readmitted_30d", "integer", "metric"),
    )
    assert derived_request(question, view, CHANNELS) is None


def test_subtracting_measures_with_different_currencies_is_refused():
    view = _view(("revenue_usd", "decimal", "metric"), ("cost_pkr", "decimal", "metric"))
    with pytest.raises(Exception, match="different units"):
        derived_request("revenue minus cost", view)


def test_combine_is_exact_ranks_and_reports_divide_by_zero():
    spec = DerivedRequest(
        "ratio",
        "cost per purchase",
        MetricRequest("spend_usd", AggregationKind.SUM, ("channel",)),
        MetricRequest("purchases", AggregationKind.SUM, ("channel",)),
        order="asc",
        unit="USD",
    ).spec()
    left = [("Email", Decimal("10.00")), ("Search", Decimal("900.50")), ("Print", Decimal("5"))]
    right = [("Email", 3), ("Search", 7), ("Print", 0)]
    result = combine(spec, left, right, "channel")
    assert result["rows"] == [
        ["Email", "3.333333", "10.00", "3"],
        ["Search", "128.642857", "900.50", "7"],
        ["Print", None, "5", "0"],
    ]
    assert result["formula"] == "cost per purchase = spend_usd ÷ purchases"
    assert "Lowest first: Email: 3.33 USD" in result["message"]
    assert "not defined because purchases is 0" in result["message"]


def test_combine_difference_and_percent_match_decimal_arithmetic():
    spec = DerivedRequest(
        "difference",
        "net",
        MetricRequest("amount", AggregationKind.SUM),
        MetricRequest("amount", AggregationKind.SUM),
    ).spec()
    result = combine(spec, [(None, Decimal("975525.51"))], [(None, Decimal("2805395.19"))], None)
    assert result["rows"] == [["-1829869.68", "975525.51", "2805395.19"]]
    percent = dict(spec, operation="ratio", percent=True)
    assert combine(percent, [(None, 2979)], [(None, 107500)], None)["rows"][0][0] == "2.7712"


@pytest.mark.parametrize(
    ("asked", "expected"),
    [("revenue", ["revenue_usd"]), ("sales", ["sales_amount"]), ("cost", ["spend_usd"])],
)
def test_measure_words_match_column_tokens_prefixes_and_synonyms(asked, expected):
    view = _view(
        ("revenue_usd", "decimal", "metric"),
        ("sales_amount", "decimal", "metric"),
        ("spend_usd", "decimal", "metric"),
    )
    assert measures_for(asked, view) == expected


def test_offline_plans_match_measures_named_without_their_unit_suffix():
    view = _view(
        ("region", "text", "dimension"),
        ("revenue_usd", "decimal", "metric"),
        ("units", "integer", "metric"),
    )
    plan = offline_plan("total revenue by region", view)
    assert plan is not None and plan.request.metric == "revenue_usd"
    sales = _view(("store", "text", "dimension"), ("sales_amount", "decimal", "metric"))
    assert offline_plan("total sales by store", sales).request.metric == "sales_amount"


def test_score_measures_are_offered_as_an_average_first():
    survey = _view(
        ("channel", "text", "dimension"),
        ("nps_score", "integer", "metric"),
        ("orders", "integer", "metric"),
    )
    choices = working_choices(
        "which channel should we fix first?", survey, "Compare NPS by channel nps_score channel"
    )
    assert choices[0] == "What is the average of nps_score by channel?"
    assert working_choices("total orders by channel", survey)[0].startswith("What is the total")


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("laptops", "Laptop"),
        ("LAPTOP", "Laptop"),
        ("  laptop ", "Laptop"),
        ("Labtop", "Laptop"),
        ("monitors", "Monitor"),
        ("accessories", "Accessory"),
    ],
)
def test_typed_values_resolve_to_the_recorded_label(typed, expected):
    assert match_label(typed, ["Laptop", "Monitor", "Accessory", "Phone"]) == (expected, ())


def test_values_matching_nothing_return_the_closest_labels():
    label, closest = match_label("tablets", ["Laptop", "Monitor", "Tablet PC", "Phone"])
    assert label is None and closest[0] == "Tablet PC" and len(closest) == 3


def test_case_and_space_variants_are_found_and_described_without_merging():
    values = ["Store 1", " store 1 ", "Store 2", "Store 1", None]
    assert label_variants(values) == [("Store 1", " store 1 ")]
    note = variants_note(("store", "sales"), [(v or "", "1") for v in values], ("store",))
    assert "'Store 1' and ' store 1 '" in note
    assert "Trim surrounding whitespace" in note and "Nothing is merged" in note


def test_spending_on_a_debit_credit_ledger_uses_debits_only():
    request = MetricRequest("amount_pkr", AggregationKind.SUM, ("posting_date",), period="month")
    spent = spending_filter(
        "How did monthly spending change over the year?", request, LEDGER_VALUES
    )
    assert spent.filters == (MetricFilter("entry_type", FilterOperator.IEQ, "debit"),)
    grouped = MetricRequest("amount_pkr", AggregationKind.SUM, ("entry_type",))
    assert spending_filter("spending by entry type", grouped, LEDGER_VALUES) is None
    assert spending_filter("Total spend by channel", request, CHANNELS) is None
    assert spending_filter("monthly revenue", request, LEDGER_VALUES) is None


def _extremum(names: tuple[str, ...]):
    query_id = uuid4()
    sql = (
        'SELECT "plant_id", "metric_05_defects" FROM "dataset" WHERE "metric_05_defects" = '
        '(SELECT MAX("metric_05_defects") FROM "dataset")'
    )
    lineage = CalculationLineage(
        query_id, uuid4(), uuid4(), "Plants", 100, "*", "rows", (), (), sql
    )
    rows = tuple((name, 30) for name in names)
    return QueryResult(query_id, ("plant_id", "metric_05_defects"), rows, 100), lineage


def test_v4_narrative_names_tied_records_and_v3_wording_is_unchanged():
    answer = _extremum(("P004", "P078", "P097"))
    named = [s.variants[0] for s in build_insight_packet(answer, version=NAMED_VERSION).statements]
    assert "P004, P078 and P097 share the highest metric 05 defects: 30." in named
    v3 = build_insight_packet(answer, version=RANKED_VERSION)
    ranked = [s.variants[0] for s in v3.statements]
    assert "I found 3 returned records. Open the table to inspect their fields." in ranked


def _funnel_csv() -> bytes:
    lines = ["week_start,channel,clicks,purchases,spend_usd"]
    data = {"Email": (400, 20, "55.10"), "Search": (900, 30, "310.75"), "Print": (50, 0, "80")}
    for week in range(4):
        for channel, (clicks, purchases, spend) in data.items():
            lines.append(
                f"2025-01-{6 + 7 * week:02d},{channel},{clicks + week * 13},"
                f"{purchases + (week if purchases else 0)},{Decimal(spend) + week}"
            )
    return ("\n".join(lines) + "\n").encode()


@pytest.mark.asyncio
async def test_conversion_and_cost_rates_are_computed_exactly_and_replay(integration):
    content = _funnel_csv()
    actor, wid, did, uid, model, threads = _setup(
        integration, content, "marketing_funnel.csv", email="derived-funnel@example.test"
    )
    frame = pd.read_csv(io.BytesIO(content), dtype=str)
    clicks, purchases = _sum(frame, "clicks", "channel"), _sum(frame, "purchases", "channel")
    spend = _sum(frame, "spend_usd", "channel")
    thread = await threads.start_thread(actor, wid, did, uid)

    answer, turn = await threads.ask(
        actor, wid, thread.id, "What is the conversion rate from clicks to purchases by channel?"
    )
    assert isinstance(answer, EvidenceAnswer) and turn.status == "complete"
    assert turn.model_route == DERIVED_ROUTE and not model.requests
    rates = {row[0]: row[1] for row in answer.derived["rows"]}
    for channel in clicks.index:
        expected = (purchases[channel] / clicks[channel] * 100).quantize(Decimal("0.0001"))
        assert Decimal(rates[channel]) == expected
    assert len(turn.evidence["data_steps"]) == 1
    assert turn.evidence["derived"]["version"] == "derived-v1"
    restored = await threads.resolve(actor, wid, thread.id, turn.id)
    assert restored.derived == answer.derived
    body = numerical_answer_body(answer)
    assert body["derived"]["formula"] == "conversion rate = purchases ÷ clicks \u00d7 100"
    assert body["message"].startswith("conversion rate = purchases ÷ clicks \u00d7 100 by channel.")

    answer, turn = await threads.ask(
        actor, wid, thread.id, "Which channel has the lowest cost per purchase?"
    )
    rows = answer.derived["rows"]
    assert [row[0] for row in rows] == ["Email", "Search", "Print"]
    for channel, value, *_ in rows[:2]:
        expected = (spend[channel] / purchases[channel]).quantize(Decimal("0.000001"))
        assert Decimal(value) == expected
    assert rows[2][1] is None and "not defined because purchases is 0" in answer.derived["message"]
    assert not model.requests


@pytest.mark.asyncio
async def test_net_income_is_credits_minus_debits_with_both_receipts(integration):
    content = _ledger_csv()
    actor, wid, did, uid, model, threads = _setup(
        integration, content, "finance_ledger.csv", email="derived-ledger@example.test"
    )
    frame = pd.read_csv(io.BytesIO(content), dtype=str)
    by_type = _sum(frame, "amount_pkr", "entry_type")
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(
        actor, wid, thread.id, "What is our net income (credits minus debits)?"
    )
    assert answer.data.value == by_type["credit"]
    assert answer.additional_data[0].value == by_type["debit"]
    assert Decimal(answer.derived["rows"][0][0]) == by_type["credit"] - by_type["debit"]
    assert answer.derived["unit"] == "PKR" and not model.requests
    restored = await threads.resolve(actor, wid, thread.id, turn.id)
    assert restored.derived["rows"] == answer.derived["rows"]


MONTHLY = {
    "kind": "numerical",
    "plan": {
        "metric": "amount_pkr",
        "aggregation": "sum",
        "group_by": ["posting_date"],
        "filters": [],
        "period": "month",
    },
}


@pytest.mark.asyncio
async def test_monthly_spending_on_a_ledger_sums_debits_only(integration):
    content = _ledger_csv()
    actor, wid, did, uid, _, threads = _setup(
        integration, content, "finance_ledger.csv", MONTHLY, email="spend-ledger@example.test"
    )
    frame = pd.read_csv(io.BytesIO(content), dtype=str)
    debits = frame[frame["entry_type"] == "debit"].copy()
    debits["month"] = debits["posting_date"].str[:7]
    expected = _sum(debits, "amount_pkr", "month")
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, _ = await threads.ask(
        actor, wid, thread.id, "How did monthly spending change over the year?"
    )
    result, lineage = answer
    assert lineage.filters == ("entry_type = debit",) or "debit" in " ".join(lineage.filters)
    assert {str(row[0])[:7]: row[1] for row in result.rows} == dict(expected.items())


def _sales_csv() -> bytes:
    lines = ["region,product,revenue_usd"]
    for index in range(24):
        region = ("North", "South", "East")[index % 3]
        product = ("Laptop", "Monitor", "Phone", "Laptop")[index % 4]
        lines.append(f"{region},{product},{Decimal(100 + index * 17) / 4}")
    return ("\n".join(lines) + "\n").encode()


def _by_region(value: str) -> dict:
    return {
        "kind": "numerical",
        "plan": {
            "metric": "revenue_usd",
            "aggregation": "sum",
            "group_by": ["region"],
            "filters": [{"column": "product", "operator": "ieq", "value": value}],
            "order": "desc",
        },
    }


@pytest.mark.asyncio
async def test_plural_value_resolves_and_unknown_value_clarifies_with_real_labels(integration):
    content = _sales_csv()
    actor, wid, did, uid, _, threads = _setup(
        integration,
        content,
        "retail_sales.csv",
        _by_region("laptops"),
        _by_region("tablets"),
        email="labels-sales@example.test",
    )
    frame = pd.read_csv(io.BytesIO(content), dtype=str)
    expected = _sum(frame[frame["product"] == "Laptop"], "revenue_usd", "region")
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, _ = await threads.ask(actor, wid, thread.id, "Which region sells the most laptops?")
    result, lineage = answer
    assert {row[0]: row[1] for row in result.rows} == dict(expected.items())
    assert any("Laptop" in item for item in lineage.filters)

    answer, turn = await threads.ask(actor, wid, thread.id, "Which region sells the most tablets?")
    assert answer is None and turn.kind == "ambiguous"
    clarification = turn.evidence["clarification"]
    assert "No product value matches 'tablets'" in clarification["message"]
    assert clarification["choices"][0].startswith("Which region sells the most ")
    assert all("tablets" not in choice for choice in clarification["choices"])


CONTRADICTORY = {
    "kind": "numerical",
    "plan": {
        "metric": "*",
        "aggregation": "count",
        "group_by": [],
        "filters": [
            {"column": "region", "operator": "ieq", "value": "North"},
            {"column": "region", "operator": "ieq", "value": "South"},
        ],
    },
}


@pytest.mark.asyncio
async def test_north_vs_south_offers_the_revenue_comparison_named_without_its_suffix(integration):
    actor, wid, did, uid, _, threads = _setup(
        integration,
        _sales_csv(),
        "retail_sales.csv",
        CONTRADICTORY,
        CONTRADICTORY,
        email="contradiction-sales@example.test",
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    _, turn = await threads.ask(actor, wid, thread.id, "Compare revenue in North vs South")
    choices = turn.evidence["clarification"]["choices"]
    assert choices[0] == "What is the total of revenue_usd by region?"


QUALITY = {"kind": "overview", "columns": [], "focus": "quality"}


def _messy_csv() -> bytes:
    rows = ["Store 1,10.50", " store 1 ,4", "Store 2,7", "Store 1,1.25", "STORE 2,2"]
    return ("store,sales_amount\n" + "\n".join(rows) + "\n").encode()


@pytest.mark.asyncio
async def test_quality_answer_flags_label_variants_with_the_cleaning_step(integration):
    actor, wid, did, uid, _, threads = _setup(
        integration, _messy_csv(), "messy_store_sales.csv", QUALITY, email="messy@example.test"
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Is this data clean?")
    assert turn.status == "complete"
    assert "'Store 1' and ' store 1 '" in answer.message
    assert "'Store 2' and 'STORE 2'" in answer.message
    assert "Trim surrounding whitespace" in answer.message
