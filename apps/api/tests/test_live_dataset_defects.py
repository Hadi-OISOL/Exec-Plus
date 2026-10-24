"""Use case: Regression tests for defects found by live multi-dataset evaluation on October 22.

What it does: Replays the observed hosted-model plans through a scripted planner and the real
thread, router, query and receipt services, so each repaired response stays repaired.
"""

import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from execplus.application.services.insight_presentation import (
    build_insight_packet,
    display_number,
)
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.domain.analysis_guidance import analysis_guidance
from execplus.domain.conversation_requirements import (
    asks_derived_measure,
    is_contextual_reply,
    preserves_followup_scope,
)
from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.intent import CONTRADICTORY_FILTERS, route_response, with_time_grain
from execplus.domain.models import CalculationLineage, QueryResult
from execplus.domain.pattern_requests import pattern_filter_needs_clarification
from execplus.domain.response_synthesis import (
    RANKED_VERSION,
    render_selection,
    validate_saved_narrative,
)
from execplus.domain.semantics import FilterOperator, MetricFilter, build_where, dataset_view
from test_harness_context import query
from test_harness_context_integration import Planner, setup
from test_intent import view
from test_workspace_integration import dataset, identity, upload, workspace


def region(value):
    return {"column": "region", "operator": "ieq", "value": value}


def test_two_values_of_one_field_in_the_same_row_are_rejected_before_execution():
    contradictory = query(group_by=["region"], filters=[region("North"), region("South")])
    routed = route_response(json.dumps(contradictory), view())
    assert routed.validation_issue == CONTRADICTORY_FILTERS
    assert routed.options == ("region",)
    same = query(filters=[region("North"), region("north")])
    assert route_response(json.dumps(same), view()).request is not None
    rows = {
        "kind": "rows",
        "plan": {"columns": [], "filters": [region("North"), region("South")], "limit": 10},
    }
    assert route_response(json.dumps(rows), view()).validation_issue == CONTRADICTORY_FILTERS


@pytest.mark.asyncio
async def test_a_vs_b_contradiction_is_corrected_into_a_grouped_comparison(integration):
    contradictory = query(group_by=["region"], filters=[region("North"), region("South")])
    grouped = query(group_by=["region"])
    actor, wid, did, uid, model, threads = setup(integration, contradictory, grouped)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Compare revenue in North vs South")
    assert turn.status == "complete"
    result, lineage = answer
    assert lineage.filters == ()
    assert {row[0]: str(row[1]) for row in result.rows} == {
        "North": "150.000000000000",
        "South": "200.000000000000",
    }
    assert "can never match" in model.requests[1].messages[-1].content
    assert "filter-plan correction" in lineage.model_route


@pytest.mark.asyncio
async def test_repeated_contradiction_clarifies_with_working_grouped_choices(integration):
    contradictory = query(group_by=["region"], filters=[region("North"), region("South")])
    actor, wid, did, uid, _, threads = setup(integration, contradictory, contradictory)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Compare revenue in North vs South")
    assert answer is None
    assert turn.kind == "ambiguous"
    assert turn.query_id is None
    choices = turn.evidence["clarification"]["choices"]
    assert choices == [
        "What is the total of revenue by region?",
        "How many records are there by region?",
    ]
    answer, turn = await threads.ask(actor, wid, thread.id, choices[0])
    assert turn.status == "complete"
    assert turn.model_route == "deterministic:offered-question-v1"


def sales_view():
    return dataset_view(
        {
            "columns": [
                {"name": "region", "type": "text", "role": "dimension"},
                {"name": "product", "type": "text", "role": "dimension"},
                {"name": "age_band", "type": "text", "role": "dimension"},
                {"name": "revenue_usd", "type": "decimal", "role": "metric"},
                {"name": "readmitted_30d", "type": "integer", "role": "metric"},
            ]
        }
    )


def lineage(metric, aggregation, grouping=(), filters=()):
    return CalculationLineage(
        uuid4(), uuid4(), uuid4(), "Sales", 10, metric, aggregation, grouping, filters, "SELECT"
    )


@pytest.mark.parametrize(
    "question",
    [
        "break it down by age band",
        "split this by region",
        "show it by product",
        "when did they happen?",
    ],
)
def test_pronoun_follow_ups_keep_the_previous_result_context(question):
    assert is_contextual_reply(question, sales_view())


def test_regrouping_onto_a_named_field_with_the_old_group_as_a_filter_is_an_explicit_change():
    prior = lineage("revenue_usd", "sum", ("product",))
    plan = {
        "kind": "numerical",
        "plan": {
            "metric": "revenue_usd",
            "aggregation": "sum",
            "group_by": ["region"],
            "filters": [{"column": "product", "operator": "ieq", "value": "Laptop"}],
            "order": "desc",
        },
    }
    routed = route_response(json.dumps(plan), sales_view())
    question = "and which region sells the most laptops?"
    assert preserves_followup_scope(question, routed, prior, sales_view())
    count = route_response(
        json.dumps(
            {
                "kind": "numerical",
                "plan": {"metric": "*", "aggregation": "count", "group_by": ["age_band"]},
            }
        ),
        sales_view(),
    )
    prior = lineage("readmitted_30d", "avg")
    assert not preserves_followup_scope("break it down by age band", count, prior, sales_view())


@pytest.mark.parametrize(
    ("question", "columns", "clarify"),
    [
        ("Is humidity related to temperature?", (), False),
        ("Is humidity related to temperature?", ("humidity_pct", "temperature_c"), False),
        ("Is salary correlated with performance score?", (), False),
        ("Is humidity related to temperature in Lahore?", ("humidity_pct",), True),
    ],
)
def test_relationship_wording_is_not_mistaken_for_a_row_restriction(question, columns, clarify):
    assert pattern_filter_needs_clarification(question, columns) is clarify


@pytest.mark.parametrize(
    "question",
    ["Are there any unusual orders?", "Which sensor had abnormal temperature spikes?"],
)
def test_unusual_business_objects_open_the_automatic_scan(question):
    context = SimpleNamespace(view=sales_view(), state="inferred")
    _, actions = analysis_guidance(context, question)
    assert actions[0]["tool"] == "anomalies"


def test_comparing_two_fields_in_one_row_explains_the_limit_instead_of_a_value_error():
    inventory = dataset_view(
        {
            "columns": [
                {"name": "on_hand_units", "type": "integer", "role": "metric"},
                {"name": "reorder_point", "type": "integer", "role": "metric"},
            ]
        }
    )
    clause = MetricFilter("on_hand_units", FilterOperator.LT, "reorder_point")
    with pytest.raises(UnsupportedQuestionError, match="another field"):
        build_where(inventory, (clause,))


def city_totals(group="city"):
    line = CalculationLineage(
        uuid4(), uuid4(), uuid4(), "Urdu Sales", 180, "sales", "sum", (group,), (), "SELECT 1"
    )
    rows = (("Islamabad", Decimal("1724537")), ("Karachi", Decimal("2048855")))
    return QueryResult(line.query_id, (group, "__value"), rows, 180), line


def test_v3_names_the_leading_group_of_one_field_without_a_confirmed_unit():
    packet = build_insight_packet(city_totals(), version=RANKED_VERSION)
    saved = render_selection(packet)
    text = " ".join(segment["text"] for segment in saved["segments"])
    assert saved["version"] == "verified-narrative-v3"
    assert "city: Karachi has the highest total: 2,048,855" in text
    assert "No unit is confirmed for sales" in text
    assert validate_saved_narrative(packet, saved)
    legacy = build_insight_packet(city_totals())
    assert "common confirmed unit" in str(render_selection(legacy))
    assert not validate_saved_narrative(legacy, saved)


def test_v3_still_refuses_to_rank_groups_that_may_mix_units():
    data = city_totals("currency")
    assert "highest" not in str(
        render_selection(build_insight_packet(data, version=RANKED_VERSION))
    )
    per_row_unit = city_totals()
    flagged = build_insight_packet(
        per_row_unit,
        version=RANKED_VERSION,
        mixed_units=frozenset({str(per_row_unit[1].query_id)}),
    )
    assert "highest" not in str(render_selection(flagged))


def test_v3_display_rounds_half_up_while_v2_wording_is_unchanged():
    assert display_number(Decimal("0.265"), half_up=True) == "0.27"
    assert display_number(Decimal("0.265")) == "0.26"


def funnel_view():
    return dataset_view(
        {
            "columns": [
                {"name": "week_start", "type": "date", "role": "dimension"},
                {"name": "channel", "type": "text", "role": "dimension"},
                {"name": "clicks", "type": "integer", "role": "metric"},
                {"name": "purchases", "type": "integer", "role": "metric"},
                {"name": "spend_usd", "type": "decimal", "role": "metric"},
                {"name": "readmitted_30d", "type": "integer", "role": "metric"},
            ]
        }
    )


@pytest.mark.parametrize(
    ("question", "metric", "aggregation", "grouped"),
    [
        ("What is the conversion rate from clicks to purchases by channel?", "purchases", "sum", 1),
        ("Which channel has the lowest cost per purchase?", "spend_usd", "sum", 1),
        ("What is the overall defect rate?", "*", "count", 0),
        ("What is our net spend (clicks minus purchases)?", "spend_usd", "sum", 0),
    ],
)
def test_rates_ratios_and_differences_are_not_answered_by_one_aggregate(
    question, metric, aggregation, grouped
):
    assert asks_derived_measure(question, metric, aggregation, bool(grouped), funnel_view())


@pytest.mark.parametrize(
    ("question", "metric", "aggregation", "grouped"),
    [
        ("What is the 30-day readmission rate?", "readmitted_30d", "avg", 0),
        ("What percentage of rows are from each channel?", "*", "count", 1),
        ("Total spend by channel", "spend_usd", "sum", 1),
        ("Average clicks per channel", "clicks", "avg", 1),
        ("How many purchases per week?", "purchases", "sum", 1),
    ],
)
def test_ordinary_grouping_shares_and_flag_averages_still_run(
    question, metric, aggregation, grouped
):
    assert not asks_derived_measure(question, metric, aggregation, bool(grouped), funnel_view())


@pytest.mark.asyncio
async def test_difference_question_never_publishes_one_side_as_the_answer(integration):
    north_only = query(filters=[region("North")])
    actor, wid, did, uid, _, threads = setup(integration, north_only)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(
        actor, wid, thread.id, "What is the net revenue, North minus South?"
    )
    assert answer.data.value == Decimal("150.000000000000")
    assert answer.additional_data[0].value == Decimal("200.000000000000")
    assert answer.derived["rows"] == [["-50.000000000000", "150.000000000000", "200.000000000000"]]
    assert turn.model_route == "deterministic:derived-measure-v1"


MONTHLY_CSV = (
    b"region,sale_date,revenue\n"
    b"North,2026-01-05,10.25\n"
    b"South,2026-01-20,20.00\n"
    b"North,2026-02-03,5.50\n"
    b"South,2026-03-15,40.00\n"
    b"North,2026-03-31,1.00\n"
)


def monthly_setup(env, *plans):
    headers, actor = identity(env, "months@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    response = upload(env, headers, wid, did, MONTHLY_CSV, "months.csv", "text/csv")
    assert response.status_code == 201, response.text
    model = Planner(*plans)
    router = IntentRouterService(
        model, env.runtime.analytics, context_enabled=True, orchestration_enabled=True
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    return actor, UUID(wid), UUID(did), UUID(response.json()["id"]), model, threads


def by_date(**changes):
    return query(group_by=["sale_date"], **changes)


@pytest.mark.parametrize(
    ("question", "plan", "period", "order"),
    [
        ("Show the monthly revenue trend", by_date(order="asc"), "month", None),
        ("How did revenue change over the year?", by_date(order="asc"), None, None),
        ("How did monthly revenue change over the year?", by_date(order="asc"), "month", None),
        ("Hiring trend by year", by_date(order="asc"), "year", None),
        ("Weekly visit trend", by_date(), "week", None),
        ("Which month had the highest revenue?", by_date(order="desc", limit=1), "month", "desc"),
        ("Revenue by day", by_date(), None, None),
        ("Daily revenue for last month", by_date(), None, None),
        ("Top 3 days by revenue", by_date(order="desc", limit=3), None, "desc"),
    ],
)
def test_explicit_calendar_grain_and_trend_order_are_applied(question, plan, period, order):
    routed = with_time_grain(question, route_response(json.dumps(plan), view()), view())
    assert routed.request.period == period
    assert routed.request.order == order


def test_period_is_validated_and_rendered_as_a_bound_calendar_group():
    routed = route_response(json.dumps(by_date(period="month")), view())
    assert routed.request.period == "month"
    bad = route_response(json.dumps(query(group_by=["region"], period="month")), view())
    assert bad.request is None
    assert route_response(json.dumps(by_date(period="hour")), view()).request is None


@pytest.mark.asyncio
async def test_monthly_trend_and_top_month_are_exact_calendar_totals_with_replay(integration):
    actor, wid, did, uid, model, threads = monthly_setup(
        integration, by_date(order="asc"), by_date(order="desc", limit=1), by_date(order="asc")
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Show the monthly revenue trend")
    assert turn.status == "complete"
    result, lineage = answer
    assert [(row[0].isoformat(), str(row[1])) for row in result.rows] == [
        ("2026-01-01", "30.250000000000"),
        ("2026-02-01", "5.500000000000"),
        ("2026-03-01", "41.000000000000"),
    ]
    assert "DATE_TRUNC(?" in lineage.sql and 'ORDER BY "__value"' not in lineage.sql
    replayed, _ = await integration.runtime.analytics.replay(actor, wid, lineage.query_id)
    assert replayed.rows == result.rows
    answer, turn = await threads.ask(actor, wid, thread.id, "Which month had the highest revenue?")
    result, _ = answer
    assert [(row[0].isoformat(), str(row[1])) for row in result.rows] == [
        ("2026-03-01", "41.000000000000")
    ]
    answer, turn = await threads.ask(actor, wid, thread.id, "and the lowest?")
    assert turn.status == "complete"
    result, lineage = answer
    assert "DATE_TRUNC(?" in lineage.sql
    assert "per month" in model.requests[-1].messages[-1].content
