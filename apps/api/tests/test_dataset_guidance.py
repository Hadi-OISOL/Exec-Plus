"""Use case: Reproduces column-meaning and dataset-orientation conversation failures.

What it does: Verifies bounded guidance, honest uncertainty, private context and immutable evidence.
"""

import copy
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from execplus.domain.guidance import DescriptionContext, explain_dataset, guidance_selection
from execplus.domain.intent import route_response
from execplus.domain.models import QuestionKind
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel, prepare
from test_understanding import confirm, context
from test_workspace_integration import accept, identity, invite

CONTENT = (
    b"item_code,item_description,category,attock_erp,attock_erp_value\n"
    b"A1,PrivateItem,Parts,2,5.25\nA2,OtherItem,Parts,3,8.75\n"
)


def description():
    data = TableData(
        ("item_code", "attock_erp", "attock_erp_value"),
        (("A1", "2", "5.25"), ("A2", "3", "8.75")),
    )
    metadata = profile(data)
    return DescriptionContext(
        "Fictional export", metadata, dataset_view(metadata), None, "inferred"
    )


@pytest.mark.parametrize(
    "question",
    [
        "what is this attock erp means",
        "what does attock_erp means",
        "What does attock ERP mean?",
        "Explain attock_erp",
        "Describe ATTOCK_ERP",
        "What is attock_erp?",
    ],
)
def test_column_meaning_is_selected_from_real_names(question):
    assert guidance_selection(question, description().view) == ("attock_erp",)


def test_longest_column_name_does_not_accidentally_select_its_prefix():
    assert guidance_selection("what does attock_erp_value mean?", description().view) == (
        "attock_erp_value",
    )


@pytest.mark.parametrize(
    "question",
    [
        "What is the total attock_erp?",
        "What is the mean attock_erp?",
        "Why did attock_erp fall?",
        "Calculate attock_erp",
        "Show attock_erp records",
        "According to the policy what does attock_erp mean?",
    ],
)
def test_guidance_does_not_swallow_calculations_causality_or_document_requests(question):
    assert guidance_selection(question, description().view) is None


@pytest.mark.parametrize("columns", [["unknown"], "attock_erp", [1], ["attock_erp"] * 2])
def test_model_column_selection_cannot_invent_or_duplicate_fields(columns):
    intent = route_response(
        json.dumps({"kind": "overview", "columns": columns}), description().view
    )
    assert intent.kind == QuestionKind.UNSUPPORTED


def test_tentative_meaning_and_followup_do_not_assert_units_or_repeat_a_menu():
    ctx = description()
    message, suggestions = explain_dataset(ctx, ("attock_erp",))
    assert "Enterprise Resource Planning" in message
    assert "Tentative interpretation" in message and "attock_erp_value" in message
    assert "PKR" not in message and "PrivateItem" not in message
    assert "stock quantity, sales quantity, or something else" in message
    assert "What does attock_erp_value mean?" in suggestions
    simple, _ = explain_dataset(ctx, ("attock_erp",), simplify=True)
    assert simple != message and "In plain words" in simple and "attock_erp" in simple


def test_common_terms_are_helpful_but_not_mistaken_for_confirmed_file_definitions():
    metadata = profile(TableData(("revenue",), (("1",),)))
    ctx = DescriptionContext("Fictional sales", metadata, dataset_view(metadata), None, "inferred")
    message, _ = explain_dataset(ctx, ("revenue",))
    assert "income earned from sales" in message
    assert "not a confirmed file definition" in message
    assert "Confirmed workspace definition" not in message


def setup(env, model=None):
    model = model or ScriptedModel()
    owner, wid, root = prepare(env, model, content=CONTENT)
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    return owner, wid, root, f"/workspaces/{wid}/threads/{tid}", model


def ask(env, owner, path, question, request_id=None):
    response = env.client.post(
        path + "/ask",
        headers=owner,
        json={"question": question, "request_id": request_id or str(uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_reported_conversation_has_meaning_context_help_and_no_model_or_query(integration):
    env = integration
    owner, _, _, path, model = setup(env)
    first = ask(env, owner, path, "what is this attock erp means")
    assert first["turn"]["status"] == "complete"
    assert first["answer"]["guidance"]["columns"] == ["attock_erp"]
    second = ask(env, owner, path, "what does attock_erp means")
    assert "Enterprise Resource Planning" in second["answer"]["message"]
    followup = ask(env, owner, path, "??")
    assert "In plain words" in followup["answer"]["message"]
    assert followup["answer"]["guidance"]["columns"] == ["attock_erp"]
    value = ask(env, owner, path, "and the value column?")
    assert value["answer"]["guidance"]["columns"] == ["attock_erp_value"]
    help_answer = ask(env, owner, path, "hello can you please help me with understanding my data")
    text = help_answer["answer"]["message"]
    assert "2 rows and 5 columns" in text and "item_code" in text
    assert "Repeated measure/value pairs" in text and "PrivateItem" not in text
    assert not model.requests
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None
        assert connection.execute(select(s.understandings)).first() is None


def test_confirmed_meaning_overrides_inference_and_old_answer_stays_versioned(integration):
    env = integration
    owner, _, root, path, _ = setup(env)
    current = context(env, owner, root)
    definition = copy.deepcopy(current["definition"])
    column = next(c for c in definition["columns"] if c["name"] == "attock_erp")
    column.update(meaning="Approved order quantity for the Attock branch", unit="cartons")
    saved = confirm(env, owner, root, current, definition)
    assert saved.status_code == 201, saved.text
    request_id = str(uuid4())
    first = ask(env, owner, path, "what does attock_erp mean?", request_id)
    text = first["answer"]["message"]
    assert "Confirmed workspace definition" in text and "Approved order quantity" in text
    assert "Unit: cartons" in text and "Tentative interpretation" not in text
    changed = context(env, owner, root)
    definition["columns"][3]["meaning"] = "Updated definition"
    assert confirm(env, owner, root, changed, definition).status_code == 201
    stale = ask(env, owner, path, "??")
    assert stale["turn"]["kind"] == "ambiguous"
    retry = ask(env, owner, path, "what does attock_erp mean?", request_id)
    assert retry["answer"] == first["answer"]
    fresh = ask(env, owner, path, "what does attock_erp mean?")
    assert "Updated definition" in fresh["answer"]["message"]
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.understandings)).all()) == 2


@pytest.mark.parametrize("state", ["inferred", "rejected", "needs_review"])
def test_unconfirmed_definitions_can_be_explained_without_enabling_calculation(integration, state):
    env = integration
    owner, _, root, path, _ = setup(env)
    current = context(env, owner, root)
    definition = copy.deepcopy(current["definition"])
    definition["columns"][3]["meaning"] = "Unreviewed interpretation"
    assert confirm(env, owner, root, current, definition, state=state).status_code == 201
    response = ask(env, owner, path, "what does attock_erp mean?")
    assert response["turn"]["status"] == "complete"
    assert "Confirmed workspace definition" not in response["answer"]["message"]
    assert ("Unconfirmed draft" in response["answer"]["message"]) == (state == "inferred")
    query = env.client.post(
        root + "/query", headers=owner, json={"metric": "attock_erp", "aggregation": "sum"}
    )
    assert query.status_code == 422


def test_guidance_history_is_private_and_missing_source_bytes_prevent_reopening(integration):
    env = integration
    owner, wid, root, path, _ = setup(env)
    response = ask(env, owner, path, "what does attock_erp mean?")
    answer_path = path + "/turns/" + response["turn"]["id"] + "/answer"
    outsider, _ = identity(env, "other-guidance@example.test")
    invitation = invite(env, owner, wid, "other-guidance@example.test").json()
    assert accept(env, outsider, wid, invitation["id"]).status_code == 200
    assert env.client.get(answer_path, headers=outsider).status_code == 404
    member, _ = identity(env, "foreign-guidance@example.test")
    assert (
        env.client.post(
            root + "/ask", headers=member, json={"question": "Explain attock_erp"}
        ).status_code
        == 404
    )
    with env.runtime.analytics.uow() as repo:
        stored = repo.upload(
            UUID(wid), UUID(root.split("/datasets/")[1].split("/")[0]), UUID(root.rsplit("/", 1)[1])
        )
    env.runtime.analytics.storage.delete(stored)
    missing = env.client.get(answer_path, headers=owner)
    assert missing.status_code == 503
    history = env.client.get(path, headers=owner).json()
    assert history["turns"][0]["message"] is None


def test_model_selected_explanation_ignores_invented_prose_and_calculations_still_work(integration):
    env = integration
    model = ScriptedModel(
        {"kind": "overview", "columns": ["attock_erp"], "message": "Stock is 999999 PKR"},
        {"kind": "numerical", "plan": {"metric": "attock_erp", "aggregation": "sum"}},
    )
    owner, _, _, path, _ = setup(env, model)
    result = ask(env, owner, path, "Could you walk me through that ERP field?")
    assert result["answer"]["guidance"]["columns"] == ["attock_erp"]
    assert "999999" not in result["answer"]["message"]
    total = ask(env, owner, path, "What is its total?")
    assert total["answer"]["value"] == 5
    assert "Previous column explanation" in model.requests[-1].messages[-1].content
    assert "PrivateItem" not in model.requests[-1].messages[-1].content


def test_unknown_column_gets_clarification_instead_of_a_document_answer(integration):
    env = integration
    owner, _, _, path, model = setup(env)
    response = ask(env, owner, path, "what does missing_branch mean?")
    assert response["turn"]["kind"] == "ambiguous"
    assert "Which column" in response["turn"]["message"]
    assert not model.requests
