"""Exercise bounded English routing without external model or network calls."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from execplus.application.services.intent_router import IntentRouterService
from execplus.domain.conversation_requirements import (
    compound_covers_request,
    is_contextual_reply,
    request_requirements,
)
from execplus.domain.intent import route_response
from execplus.domain.profiling import TableData
from execplus.domain.semantics import dataset_view
from test_harness_context import query
from test_harness_context_integration import setup
from test_intent import view


@pytest.mark.parametrize(
    "question",
    [
        "Explain the revenue totals",
        "Describe revenue averages",
        "Explain revenue counts",
    ],
)
def test_plural_operations_preserve_calculation_requirement(question):
    assert request_requirements(question, view()).calculation


def test_bare_last_year_is_a_contextual_reply():
    assert is_contextual_reply("Last year?", view())


def test_extremum_and_count_compound_covers_both_record_and_numerical_measures():
    intent = route_response(
        json.dumps(
            {
                "kind": "compound",
                "steps": [
                    {
                        "kind": "rows",
                        "plan": {
                            "columns": [],
                            "filters": [],
                            "limit": 100,
                            "extremum": {"column": "revenue", "direction": "max"},
                        },
                    },
                    query("count", metric="*"),
                ],
            }
        ),
        view(),
    )
    assert compound_covers_request(
        "Show highest revenue records and count all records", intent, view()
    )
    assert not compound_covers_request(
        "Show highest revenue records and average revenue", intent, view()
    )


class CategorySnapshot:
    def __init__(self, selected_view, table):
        self.view = selected_view
        self.table = table

    def descriptive_snapshot(self, *args):
        return SimpleNamespace(view=self.view), self.table, None


@pytest.mark.asyncio
async def test_observed_question_label_grounds_only_matching_visible_category_values():
    selected_view = dataset_view(
        {
            "columns": [
                {"name": "region", "type": "text", "role": "dimension"},
                {"name": "customer_id", "type": "text", "role": "identifier"},
                {"name": "revenue", "type": "decimal", "role": "metric"},
            ]
        }
    )
    table = TableData(
        ("region", "customer_id", "hidden_field", "revenue"),
        (
            ("West", "PrivateCustomer", "PrivateSecret", "10"),
            ("PrivateUnrelatedRegion", "PrivateCustomer2", "PrivateSecret2", "20"),
        ),
    )
    router = IntentRouterService(None, CategorySnapshot(selected_view, table), context_enabled=True)
    text, choices = await router._category_context(
        None,
        uuid4(),
        uuid4(),
        uuid4(),
        "Why do West records differ?",
        selected_view,
    )
    assert choices == ("West",)
    assert '"column": "region"' in text
    assert "PrivateUnrelatedRegion" not in text
    assert "PrivateCustomer" not in text
    assert "PrivateSecret" not in text
    text, choices = await router._category_context(
        None,
        uuid4(),
        uuid4(),
        uuid4(),
        "Why do Midwest records differ?",
        selected_view,
    )
    assert text == "" and choices == ()


@pytest.mark.asyncio
async def test_cross_category_label_grounding_keeps_low_cardinality_bound():
    selected_view = view()
    table = TableData(
        ("region", "sale_date", "revenue"),
        tuple(
            ("West" if index == 0 else f"Region{index}", "2025-01-01", "1") for index in range(13)
        ),
    )
    router = IntentRouterService(None, CategorySnapshot(selected_view, table), context_enabled=True)
    text, choices = await router._category_context(
        None,
        uuid4(),
        uuid4(),
        uuid4(),
        "Why do West records differ?",
        selected_view,
    )
    assert text == "" and choices == ()


@pytest.mark.asyncio
async def test_plural_total_reaches_planner_and_executes_instead_of_column_overview(integration):
    actor, wid, did, uid, model, threads = setup(integration, query())
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Explain the revenue totals")
    assert turn.kind == "numerical"
    assert str(answer.value) == "350.000000000000"
    assert len(model.requests) == 1


@pytest.mark.asyncio
async def test_last_year_keeps_previous_metric_scope_and_supplies_utc_calendar(integration):
    year = datetime.now(timezone.utc).year - 1
    period = [
        {"column": "sale_date", "operator": "gte", "value": f"{year}-01-01"},
        {"column": "sale_date", "operator": "lt", "value": f"{year + 1}-01-01"},
    ]
    actor, wid, did, uid, model, threads = setup(
        integration, query("count"), query("count", filters=period)
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    _, first = await threads.ask(actor, wid, thread.id, "count revenue values")
    _, turn = await threads.ask(actor, wid, thread.id, "Last year?")
    assert turn.kind == "numerical"
    prompt = model.requests[-1].messages[-1].content
    assert str(first.query_id) in prompt
    assert "Previous turn: count of revenue" in prompt
    assert "Calendar reference (UTC): " + datetime.now(timezone.utc).date().isoformat() in prompt
    assert "changes only the prior calculation's calendar period" in prompt


@pytest.mark.asyncio
async def test_bare_temporal_reply_without_referent_clarifies_before_planner(integration):
    actor, wid, did, uid, model, threads = setup(integration)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Last year?")
    assert answer is None and turn.kind == "ambiguous"
    assert "Which calculation" in turn.message
    assert not model.requests


@pytest.mark.asyncio
async def test_extremum_records_and_count_complete_with_distinct_receipts(integration):
    compound = {
        "kind": "compound",
        "steps": [
            {
                "kind": "rows",
                "plan": {
                    "columns": [],
                    "filters": [],
                    "limit": 100,
                    "extremum": {"column": "revenue", "direction": "max"},
                },
            },
            query("count", metric="*"),
        ],
    }
    actor, wid, did, uid, _, threads = setup(integration, compound)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(
        actor,
        wid,
        thread.id,
        "Show highest revenue records and count all records",
    )
    assert turn.status == "complete"
    assert answer.data[0].rows[0][0] == "South"
    assert answer.additional_data[0].value == 3
    assert str(turn.query_id) != turn.evidence["data_steps"][0]["query_id"]


@pytest.mark.parametrize("correct", [True, False])
def test_explicit_compound_clauses_keep_metric_operation_pairs(correct):
    selected_view = dataset_view(
        {
            "columns": [
                {"name": "revenue", "type": "decimal", "role": "metric"},
                {"name": "cost", "type": "decimal", "role": "metric"},
            ]
        }
    )
    steps = (
        [query("sum", metric="revenue"), query("avg", metric="cost")]
        if correct
        else [
            query("avg", metric="revenue"),
            query("sum", metric="cost"),
        ]
    )
    intent = route_response(json.dumps({"kind": "compound", "steps": steps}), selected_view)
    assert (
        compound_covers_request("total revenue and average cost", intent, selected_view) is correct
    )


def test_returned_columns_never_count_as_a_performed_calculation():
    selected_view = dataset_view(
        {
            "columns": [
                {"name": "revenue", "type": "decimal", "role": "metric"},
                {"name": "cost", "type": "decimal", "role": "metric"},
            ]
        }
    )
    intent = route_response(
        json.dumps(
            {
                "kind": "compound",
                "steps": [
                    {
                        "kind": "rows",
                        "plan": {
                            "columns": ["revenue"],
                            "filters": [],
                            "limit": 100,
                            "extremum": {"column": "cost", "direction": "max"},
                        },
                    },
                    query("min", metric="revenue"),
                ],
            }
        ),
        selected_view,
    )
    assert not compound_covers_request("maximum revenue and minimum cost", intent, selected_view)


@pytest.mark.asyncio
async def test_common_short_category_labels_are_not_grounded_from_ordinary_words():
    selected_view = dataset_view(
        {
            "columns": [
                {"name": "region", "type": "text", "role": "dimension"},
                {"name": "status", "type": "text", "role": "dimension"},
            ]
        }
    )
    table = TableData(("region", "status"), (("US", "No"), ("IN", "The")))
    router = IntentRouterService(None, CategorySnapshot(selected_view, table), context_enabled=True)
    text, choices = await router._category_context(
        None,
        uuid4(),
        uuid4(),
        uuid4(),
        "Show us totals",
        selected_view,
    )
    assert text == "" and choices == ()
    text, choices = await router._category_context(
        None,
        uuid4(),
        uuid4(),
        uuid4(),
        "Show region US",
        selected_view,
    )
    assert "US" in choices
    assert '"values_complete": true' in text


@pytest.mark.asyncio
async def test_question_matched_category_packet_marks_its_values_as_incomplete():
    selected_view = view()
    table = TableData(
        ("region", "sale_date", "revenue"),
        (
            ("West", "2025-01-01", "10"),
            ("East", "2025-01-01", "20"),
        ),
    )
    router = IntentRouterService(None, CategorySnapshot(selected_view, table), context_enabled=True)
    text, choices = await router._category_context(
        None,
        uuid4(),
        uuid4(),
        uuid4(),
        "Why do West records differ?",
        selected_view,
    )
    assert choices == ("West",)
    assert '"values_complete": false' in text
    assert "other labels may exist" in text
    assert "East" not in text
