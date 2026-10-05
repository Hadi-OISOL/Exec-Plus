"""Use case: Verifies evidence-led conversation without a manual configuration gate.

What it does: Exercises useful guidance, clarification continuation and safe model topic selection.
"""

import copy
import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from execplus.domain.guidance import DescriptionContext, explain_dataset, mentioned_columns
from execplus.domain.intent import route_response
from execplus.domain.models import QuestionKind
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel, prepare
from test_dataset_guidance import ask, setup
from test_understanding import confirm, context


def metadata_context():
    metadata = profile(
        TableData(
            ("CustomerID", "StockCode", "city", "revenue", "date"),
            (
                ("100", "1", "Karachi", "0.10", "2026-01-01"),
                ("200", "2", "Lahore", "", "2026-01-02"),
                ("300", "3", "Lahore", "bad", "2026-02-30"),
                ("400", "4", "Karachi", "0.20", "2026-01-03"),
                ("400", "4", "Karachi", "0.20", "2026-01-03"),
            ),
        )
    )
    return DescriptionContext("Example export", metadata, dataset_view(metadata), None, "inferred")


def test_quality_guidance_uses_actual_profile_counts_and_never_proposes_blind_cleaning():
    message, suggestions = explain_dataset(metadata_context(), (), focus="quality")
    assert "1 missing cells" in message
    assert "1 repeated rows" in message
    assert "revenue: 1 missing cells, 1 type conflicts" in message
    assert "date: 1 invalid dates" in message
    assert "Missing does not mean zero" in message
    assert "Repeated rows may be legitimate" in message
    assert "bad" not in message and "2026-02-30" not in message
    assert "Show the first 10 records" in suggestions
    assert not any("total" in prompt for prompt in suggestions)


def test_structure_guidance_handles_camelcase_identifier_names_without_changing_profile():
    ctx = metadata_context()
    assert ctx.view.column("CustomerID").role == "metric"
    assert mentioned_columns("what does customer id mean", ctx.view) == ("CustomerID",)
    message, suggestions = explain_dataset(ctx, (), focus="structure")
    assert "Possible record identifiers: CustomerID, StockCode" in message
    assert "2026-01-01 to 2026-01-03" in message
    assert "does not prove complete time coverage" in message
    assert not any("total of CustomerID" in question for question in suggestions)
    assert ctx.view.column("CustomerID").role == "metric"


@pytest.mark.parametrize("focus", ["invent_answer", {"text": "profit 999"}, [], 5])
def test_model_cannot_choose_an_unimplemented_guidance_topic(focus):
    response = route_response(
        json.dumps({"kind": "overview", "focus": focus}), metadata_context().view
    )
    assert response.kind == QuestionKind.UNSUPPORTED


def test_model_guidance_handles_natural_and_roman_urdu_phrasing_without_saving_meaning(integration):
    env = integration
    model = ScriptedModel(
        {
            "kind": "overview",
            "columns": ["attock_erp"],
            "focus": "orientation",
            "message": "There are 999999 cartons worth PKR",
        },
        {"kind": "overview", "focus": "quality", "message": "Everything is perfect"},
    )
    owner, _, root, path, _ = setup(env, model)
    current = context(env, owner, root)
    definition = copy.deepcopy(current["definition"])
    definition["columns"][3]["meaning"] = "Unreviewed branch quantity"
    assert confirm(env, owner, root, current, definition, state="inferred").status_code == 201
    first = ask(env, owner, path, "yeh attock_erp kis cheez ka column hai?")
    assert first["turn"]["status"] == "complete"
    assert "Unconfirmed draft" in first["answer"]["message"]
    assert "999999" not in first["answer"]["message"]
    second = ask(env, owner, path, "is file mein koi masla ya missing values hain?")
    assert "The profile found no missing cells" in second["answer"]["message"]
    assert "Everything is perfect" not in second["answer"]["message"]
    assert "PrivateItem" not in model.requests[-1].messages[-1].content
    assert "Roman Urdu" in model.requests[-1].messages[0].content
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.understandings)).all()) == 1
        assert connection.execute(select(s.query_executions)).first() is None
    query = env.client.post(
        root + "/query", headers=owner, json={"metric": "attock_erp", "aggregation": "sum"}
    )
    assert query.status_code == 422


def test_clarification_reply_preserves_original_operation_and_remains_retryable(integration):
    env = integration
    model = ScriptedModel(
        {"kind": "ambiguous", "message": "Which measure?", "options": ["revenue", "cost"]},
        {"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "avg"}},
    )
    owner, wid, root = prepare(
        env, model, content=b"city,revenue,cost\nKarachi,0.10,0.01\nLahore,0.20,0.02\n"
    )
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}"
    original = ask(env, owner, path, "What is the average amount?")
    assert original["turn"]["kind"] == "ambiguous"
    request_id = str(uuid4())
    answer = ask(env, owner, path, "revenue", request_id)
    assert answer["answer"]["value"] == "0.150000000000"
    prompt = model.requests[-1].messages[-1].content
    assert "What is the average amount?" in prompt and "Which measure?" in prompt
    assert '"latest_reply": "revenue"' in prompt
    assert ask(env, owner, path, "revenue", request_id)["answer"] == answer["answer"]
    assert len(model.requests) == 2


def test_source_change_prevents_reusing_pending_clarification(integration):
    env = integration
    model = ScriptedModel({"kind": "ambiguous", "message": "Which measure?", "options": []})
    owner, _, root, path, _ = setup(env, model)
    assert ask(env, owner, path, "What is the average amount?")["turn"]["kind"] == "ambiguous"
    current = context(env, owner, root)
    assert confirm(env, owner, root, current).status_code == 201
    followup = ask(env, owner, path, "attock_erp")
    assert followup["turn"]["kind"] == "ambiguous"
    assert "changed while clarifying" in followup["turn"]["message"]
    assert len(model.requests) == 1


def test_gratitude_keeps_executed_context_for_later_breakdown(integration):
    env = integration
    model = ScriptedModel(
        {"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "sum"}},
        {
            "kind": "numerical",
            "plan": {"metric": "revenue", "aggregation": "sum", "group_by": ["city"]},
        },
    )
    owner, wid, root = prepare(env, model)
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}"
    first = ask(env, owner, path, "What is the total revenue?")
    assert first["answer"]["value"] == "8.050000000000"
    thanks = ask(env, owner, path, "thank you")
    assert thanks["answer"]["message"].startswith("You're welcome")
    answer = ask(env, owner, path, "and by city?")
    assert answer["turn"]["status"] == "complete"
    assert "Previous turn: sum of revenue" in model.requests[-1].messages[-1].content
    assert len(model.requests) == 2


def test_help_suggests_queries_that_need_no_manual_definition_confirmation(integration):
    env = integration
    owner, _, _, path, model = setup(env)
    answer = ask(env, owner, path, "what should i ask")
    assert "What is the total of attock_erp?" in answer["answer"]["guidance"]["suggestions"]
    assert not model.requests


def test_column_quality_topic_answers_only_selected_column_facts():
    message, _ = explain_dataset(metadata_context(), ("revenue",), focus="quality")
    assert "revenue: 1 missing cells, 1 numeric/boolean type conflicts" in message
    assert "2 distinct present values" not in message
    assert "date:" not in message
    assert "No source values have been changed" in message


def test_suggestions_group_mixed_currency_and_average_prices_instead_of_identifiers():
    metadata = profile(
        TableData(
            ("CustomerID", "UnitPrice", "currency", "city"),
            (("100", "2.25", "PKR", "Karachi"), ("200", "1.05", "USD", "Lahore")),
        )
    )
    ctx = DescriptionContext("Public fixture", metadata, dataset_view(metadata), None, "inferred")
    _, suggestions = explain_dataset(ctx, ())
    assert "What is the average of UnitPrice by currency?" in suggestions
    assert "Show the average of UnitPrice by currency, city" in suggestions
    assert not any("total of CustomerID" in suggestion for suggestion in suggestions)


def test_date_component_and_timestamp_warnings_explain_profiler_limits_without_retyping():
    metadata = profile(
        TableData(
            ("day", "InvoiceDate", "amount"),
            (("7", "12/1/2024 08:26", "1.25"), ("8", "12/2/2024 09:01", "2.50")),
        )
    )
    original = copy.deepcopy(metadata)
    ctx = DescriptionContext("Public export", metadata, dataset_view(metadata), None, "inferred")
    message, _ = explain_dataset(ctx, (), focus="quality")
    assert "day-of-month component" in message
    assert "do not by themselves prove the source is wrong" in message
    assert "InvoiceDate has a date-like label but is profiled as text" in message
    assert "not reinterpreted" in message
    assert metadata == original


def test_second_clarification_does_not_forget_original_average_request(integration):
    env = integration
    model = ScriptedModel(
        {"kind": "ambiguous", "message": "Which amount?", "options": ["salary", "cost"]},
        {"kind": "numerical", "plan": {"metric": "base_salary", "aggregation": "avg"}},
    )
    owner, wid, root = prepare(
        env, model, content=b"base_salary,total_salary,cost\n10,12,3\n20,22,4\n"
    )
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}"
    assert ask(env, owner, path, "What is the average amount?")["turn"]["kind"] == "ambiguous"
    assert ask(env, owner, path, "salary")["turn"]["kind"] == "ambiguous"
    result = ask(env, owner, path, "base_salary")
    assert result["answer"]["value"] == "15.000000000000"
    assert "What is the average amount?" in model.requests[-1].messages[-1].content
    assert len(model.requests) == 2
