"""Use case: Regression tests for live defects D26 (irrelevant choices), D21 (per-day), D12, D19.

What it does: Replays the October 23 live questions through deterministic choice ranking and a
scripted planner with the real thread, router, query and receipt services, and checks every
offered choice plans and every number matches independent pandas/Decimal results.
"""

import io
import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pandas as pd
import pytest

from execplus.application.conversation import EvidenceAnswer
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.response_synthesis import build_fact_packet
from execplus.application.services.threads import ThreadService
from execplus.domain.answer_presentation import decimal_text
from execplus.domain.errors import UnsafeQueryError
from execplus.domain.intent import (
    canonical_question,
    per_day_request,
    route_response,
    with_extremum,
)
from execplus.domain.models import QuestionKind
from execplus.domain.offline_planner import working_choices
from execplus.domain.semantics import dataset_view
from execplus.infrastructure.query.validation import validated_query
from execplus.presentation.routes.analytics import numerical_answer_body
from test_harness_context_integration import Planner
from test_workspace_integration import dataset, identity, upload, workspace


def _view(*columns):
    return dataset_view(
        {
            "columns": [
                {"name": name, "type": kind, "role": role, "semantic_tags": list(tags)}
                for name, kind, role, *tags in columns
            ]
        }
    )


LEDGER = _view(
    ("entry_id", "integer", "dimension", "identifier"),
    ("posting_date", "date", "dimension"),
    ("account", "text", "dimension"),
    ("entry_type", "text", "dimension"),
    ("amount_pkr", "decimal", "metric"),
    ("cost_center", "text", "dimension"),
)
LEDGER_VALUES = {
    "account": ("Rent", "Salaries", "Sales Income"),
    "entry_type": ("credit", "debit"),
    "cost_center": ("HQ", "Lahore", "Karachi"),
}
FUNNEL = _view(
    ("week_start", "date", "dimension"),
    ("channel", "text", "dimension"),
    ("impressions", "integer", "metric"),
    ("clicks", "integer", "metric"),
    ("signups", "integer", "metric"),
    ("purchases", "integer", "metric"),
    ("spend_usd", "decimal", "metric"),
)
PLANTS = _view(
    ("plant_id", "text", "dimension", "identifier"),
    ("country", "text", "dimension"),
    *(
        column
        for index in range(1, 31)
        for column in (
            (f"metric_{index:02d}_output", "integer", "metric"),
            (f"metric_{index:02d}_defects", "integer", "metric"),
        )
    ),
)
SENSORS = _view(
    ("timestamp", "date", "dimension"),
    ("sensor_id", "text", "dimension", "identifier"),
    ("temperature_c", "decimal", "metric"),
    ("humidity_pct", "decimal", "metric"),
    ("power_w", "decimal", "metric"),
)

RELEVANCE = [
    (
        "What is our net income (credits minus debits)?",
        LEDGER,
        "",
        ["What is the total of amount_pkr by entry_type?"],
    ),
    (
        "What is the conversion rate from clicks to purchases by channel?",
        FUNNEL,
        "",
        ["What is the total of clicks by channel?", "What is the total of purchases by channel?"],
    ),
    (
        "Which channel has the lowest cost per purchase?",
        FUNNEL,
        "",
        [
            "What is the total of spend_usd by channel?",
            "What is the total of purchases by channel?",
        ],
    ),
    (
        "What is the overall defect rate?",
        PLANTS,
        "",
        ["What is the total of metric_01_defects?", "What is the total of metric_01_output?"],
    ),
    (
        "when did they happen?",
        SENSORS,
        "Which sensor had abnormal temperature spikes?",
        ["Which timestamp has the highest maximum temperature_c?"],
    ),
]


@pytest.mark.parametrize(("question", "view", "context", "leading"), RELEVANCE)
def test_offered_choices_follow_the_question_and_all_plan(question, view, context, leading):
    choices = working_choices(question, view, context, LEDGER_VALUES)
    assert list(choices[: len(leading)]) == leading
    assert 1 <= len(choices) <= 3
    for choice in choices:
        planned = canonical_question(choice, view)
        assert planned is not None and planned.kind != QuestionKind.UNSUPPORTED


def test_grouping_is_kept_and_unrelated_generic_choices_are_dropped():
    choices = working_choices(
        "What is the conversion rate from clicks to purchases by channel?", FUNNEL
    )
    assert all("by channel" in choice for choice in choices)
    assert not any("relate" in choice for choice in choices)
    sensors = working_choices(
        "when did they happen?", SENSORS, "Which sensor had abnormal temperature spikes?"
    )
    assert all("temperature_c" in choice for choice in sensors)


def test_without_any_named_field_the_generic_working_questions_remain():
    assert working_choices("Where should I move budget?", FUNNEL)


def _setup(env, content: bytes, name: str, *plans, email: str):
    headers, actor = identity(env, email)
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    response = upload(env, headers, wid, did, content, name, "text/csv")
    assert response.status_code == 201, response.text
    model = Planner(*plans)
    router = IntentRouterService(
        model, env.runtime.analytics, context_enabled=True, orchestration_enabled=True
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    return actor, UUID(wid), UUID(did), UUID(response.json()["id"]), model, threads


def _ledger_csv() -> bytes:
    lines = ["entry_id,posting_date,account,entry_type,amount_pkr,cost_center"]
    accounts = ("Rent", "Salaries", "Sales Income", "Consulting Income", "Travel")
    for index in range(40):
        account = accounts[index % len(accounts)]
        kind = "credit" if "Income" in account else "debit"
        amount = Decimal(200 + (index * 137) % 900) + Decimal(index % 7) / 4
        day = date(2025, 1, 1) + timedelta(days=index * 3)
        lines.append(f"{index + 1},{day},{account},{kind},{amount},{('HQ', 'Lahore')[index % 2]}")
    return ("\n".join(lines) + "\n").encode()


UNUSABLE = {"kind": "ambiguous", "message": "Net income needs two parts.", "options": []}


@pytest.mark.asyncio
async def test_net_income_offers_the_entry_type_totals_and_the_click_matches_pandas(integration):
    content = _ledger_csv()
    actor, wid, did, uid, model, threads = _setup(
        integration, content, "finance_ledger.csv", UNUSABLE, email="ledger@example.test"
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "What is our net income?")
    assert answer is None and turn.kind == "ambiguous"
    choices = turn.evidence["clarification"]["choices"]
    assert "What is the total of amount_pkr?" in choices
    answer, turn = await threads.ask(
        actor, wid, thread.id, "What is the total of amount_pkr by entry_type?"
    )
    assert turn.model_route == "deterministic:offered-question-v1"
    result, _ = answer
    frame = pd.read_csv(io.BytesIO(content), dtype=str)
    expected = frame.groupby("entry_type")["amount_pkr"].apply(
        lambda values: sum(map(Decimal, values), Decimal(0))
    )
    assert {row[0]: Decimal(row[1]) for row in result.rows} == dict(expected.items())
    assert len(model.requests) == 1


def _funnel_csv() -> bytes:
    lines = ["week_start,channel,impressions,clicks,purchases,spend_usd"]
    rates = {"Google Ads": "0.012", "Facebook": "0.008", "Email": "0.001", "Organic": "0"}
    for week in range(6):
        for offset, (channel, rate) in enumerate(rates.items()):
            impressions = 20000 + week * 1500 + offset * 3700
            clicks = impressions // (25 + offset)
            purchases = clicks // (9 + week)
            spend = (Decimal(impressions) * Decimal(rate)).quantize(Decimal("0.01"))
            day = date(2025, 1, 6) + timedelta(weeks=week)
            lines.append(f"{day},{channel},{impressions},{clicks},{purchases},{spend}")
    return ("\n".join(lines) + "\n").encode()


@pytest.mark.asyncio
async def test_cost_per_purchase_offers_both_components_by_channel(integration):
    content = _funnel_csv()
    actor, wid, did, uid, _, threads = _setup(
        integration, content, "marketing_funnel.csv", email="funnel@example.test"
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(
        actor, wid, thread.id, "Which channel has the lowest cost per purchase?"
    )
    assert turn.model_route == "deterministic:derived-measure-v1"
    frame = pd.read_csv(io.BytesIO(content), dtype=str)
    for data, column in zip(
        (answer.data, answer.additional_data[0]), ("spend_usd", "purchases"), strict=True
    ):
        result, _ = data
        expected = frame.groupby("channel")[column].apply(
            lambda values: sum(map(Decimal, values), Decimal(0))
        )
        assert {row[0]: Decimal(row[1]) for row in result.rows} == dict(expected.items())
        organic = next(row[1] for row in result.rows if row[0] == "Organic")
        if column == "spend_usd":
            assert decimal_text(organic) == "0"
    assert answer.derived["rows"][0][:2] == ["Organic", "0"]


def _restaurant_csv() -> bytes:
    lines = ["date,branch,orders"]
    start = date(2025, 1, 1)
    for offset in range(38):
        day = start + timedelta(days=offset)
        if offset % 9 == 4:
            continue
        branches = ("Gulberg", "DHA") if offset % 3 == 0 else ("Gulberg",)
        for index, branch in enumerate(branches):
            orders = 40 + (offset * 11) % 50 + index * 7 + (30 if day.isoweekday() >= 6 else 0)
            lines.append(f"{day.isoformat()},{branch},{orders}")
    return ("\n".join(lines) + "\n").encode()


def _numerical(**plan):
    return {"kind": "numerical", "plan": {"group_by": [], "filters": [], **plan}}


WEEKEND_SUM = _numerical(metric="orders", aggregation="sum", group_by=["date"], period="weekend")


@pytest.mark.asyncio
async def test_weekend_comparison_leads_with_the_exact_average_per_calendar_day(integration):
    content = _restaurant_csv()
    actor, wid, did, uid, _, threads = _setup(
        integration,
        content,
        "restaurant_daily.csv",
        WEEKEND_SUM,
        WEEKEND_SUM,
        email="restaurant@example.test",
    )
    frame = pd.read_csv(io.BytesIO(content), dtype=str)
    frame["orders"] = frame["orders"].map(Decimal)
    frame["part"] = pd.to_datetime(frame["date"]).dt.dayofweek.map(
        lambda day: "weekend" if day >= 5 else "weekday"
    )
    totals = frame.groupby("part")["orders"].apply(lambda values: sum(values, Decimal(0)))
    days = frame.groupby("part")["date"].nunique()
    per_day = {
        part: (totals[part] / days[part]).quantize(Decimal("1e-12")) for part in totals.index
    }
    per_record = {part: totals[part] / (frame["part"] == part).sum() for part in totals.index}
    assert per_day != per_record
    thread = await threads.start_thread(actor, wid, did, uid)

    answer, turn = await threads.ask(
        actor, wid, thread.id, "Do weekends get more orders than weekdays?"
    )
    assert turn.status == "complete" and isinstance(answer, EvidenceAnswer)
    (headline, lineage), (total_rows, total_lineage) = answer.data, answer.additional_data[0]
    assert {row[0]: row[1] for row in headline.rows} == per_day
    assert {row[0]: row[1] for row in total_rows.rows} == dict(totals.items())
    assert per_day["weekend"] > per_day["weekday"] and totals["weekday"] > totals["weekend"]
    assert lineage.metric == "orders per calendar day" and lineage.aggregation == "avg"
    assert 'COUNT(DISTINCT CAST("date" AS DATE))' in lineage.sql
    assert "COUNT(DISTINCT" not in total_lineage.sql
    body = numerical_answer_body(answer)
    assert "average per calendar day" in body["message"]
    restored = await threads.resolve(actor, wid, thread.id, turn.id)
    assert restored.data[0].rows == headline.rows
    assert restored.additional_data[0][0].rows == total_rows.rows
    replayed, _ = await integration.runtime.analytics.replay(actor, wid, lineage.query_id)
    assert replayed.rows == headline.rows

    answer, turn = await threads.ask(
        actor, wid, thread.id, "What are the total orders on weekdays and weekends?"
    )
    result, lineage = answer
    assert {row[0]: row[1] for row in result.rows} == dict(totals.items())
    assert "COUNT(DISTINCT" not in lineage.sql


def test_per_day_applies_only_to_compared_sums_split_by_day_of_week():
    view = _view(("date", "date", "dimension"), ("orders", "integer", "metric"))

    def request(question, **plan):
        return per_day_request(question, route_response(_json(plan), view).request)

    weekend = {"metric": "orders", "aggregation": "sum", "group_by": ["date"], "period": "weekend"}
    assert request("Do weekends get more orders than weekdays?", **weekend).per_day
    assert request("Orders by weekday and weekend", **weekend) is None
    assert request("Total orders weekends vs weekdays", **weekend) is None
    assert request("weekends vs weekdays", **{**weekend, "aggregation": "avg"}) is None
    assert request("weekends vs weekdays", **{**weekend, "period": "month"}) is None


def _json(plan):
    return json.dumps(_numerical(**plan))


PER_DAY_SQL = (
    'SELECT CASE WHEN ISODOW("date") >= ? THEN ? ELSE ? END AS "date", SUM("orders") AS '
    '"__value", COUNT(DISTINCT CAST("date" AS DATE)) AS "__days" FROM "dataset" GROUP BY ALL '
    'ORDER BY "date" LIMIT 100'
)


@pytest.mark.parametrize(
    "sql",
    [
        PER_DAY_SQL.replace('CAST("date" AS DATE)', '"orders"'),
        PER_DAY_SQL.replace('"__days"', '"__other"'),
        PER_DAY_SQL.replace('SUM("orders")', 'AVG("orders")'),
        PER_DAY_SQL.replace(" GROUP BY ALL", ""),
        PER_DAY_SQL.replace('"__days" FROM', '"__days", COUNT(DISTINCT "orders") AS "x" FROM'),
    ],
)
def test_execution_boundary_accepts_only_the_calendar_day_count(sql):
    assert validated_query(PER_DAY_SQL, {"dataset"}, 3) is not None
    with pytest.raises(UnsafeQueryError):
        validated_query(sql, {"dataset"}, 3)


def _plants_csv() -> bytes:
    lines = ["plant_id,country,metric_05_output,metric_05_defects"]
    defects = [12, 30, 7, 30, 19, 30, 3, 25, 11, 29]
    for index, value in enumerate(defects):
        lines.append(f"P{index:03d},{('PK', 'AE')[index % 2]},{500 + index},{value}")
    return ("\n".join(lines) + "\n").encode()


@pytest.mark.asyncio
async def test_highest_value_names_every_tied_record(integration):
    top_five = {
        "kind": "rows",
        "plan": {
            "columns": [],
            "filters": [],
            "order_by": {"column": "metric_05_defects", "direction": "desc"},
            "limit": 5,
        },
    }
    content = _plants_csv()
    actor, wid, did, uid, _, threads = _setup(
        integration, content, "wide_plants.csv", top_five, email="plants@example.test"
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, _ = await threads.ask(
        actor, wid, thread.id, "Which plant has the highest metric_05_defects?"
    )
    result, lineage = answer
    frame = pd.read_csv(io.BytesIO(content))
    leaders = frame[frame["metric_05_defects"] == frame["metric_05_defects"].max()]
    assert sorted(row[0] for row in result.rows) == sorted(leaders["plant_id"])
    assert "(SELECT MAX(" in lineage.sql
    texts = [text for item in build_fact_packet(answer).statements for text in item.variants]
    assert '3 record(s) share the highest value; "plant_id": P001, P003, P005.' in texts


def test_extremum_is_kept_for_explicit_top_lists():
    view = _view(("plant_id", "text", "dimension"), ("defects", "integer", "metric"))
    plan = {
        "kind": "rows",
        "plan": {
            "columns": [],
            "filters": [],
            "order_by": {"column": "defects", "direction": "asc"},
            "limit": 5,
        },
    }
    routed = route_response(json.dumps(plan), view)
    single = with_extremum("Which plant has the lowest defects?", routed, view)
    assert single.rows.extremum.direction == "min" and single.rows.order_by is None
    assert with_extremum("Top 5 plants with the lowest defects", routed, view) == routed
    assert with_extremum("Which plants have the lowest defects?", routed, view) == routed


def test_zero_and_tiny_decimals_display_without_scientific_notation():
    assert decimal_text(Decimal("0E-12")) == "0"
    assert decimal_text(Decimal("-0E-12")) == "0"
    assert decimal_text(Decimal("4672.611100000000")) == "4672.611100000000"
    assert decimal_text(Decimal("1.00000E-7")) == "0.000000100000"
    assert decimal_text(Decimal("1E+3")) == "1000"
