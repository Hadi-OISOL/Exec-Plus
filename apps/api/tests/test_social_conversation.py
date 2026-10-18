"""Model-selected social talk stays conversational and cannot replace data work."""

import asyncio
import copy
import json

import pytest
from sqlalchemy import select

from execplus.application.contracts import ModelResponse
from execplus.domain.intent import route_response
from execplus.domain.models import QuestionKind
from execplus.infrastructure.persistence import schema as s
from test_dataset_guidance import ask, description
from test_dataset_reading import prepare
from test_understanding import confirm, context
from test_workspace_integration import identity

SOCIAL = {
    "kind": "overview",
    "focus": "conversation",
    "columns": [],
    "message": "I'm here and ready to help. How are you doing?",
}


@pytest.mark.parametrize(
    "question,message",
    [
        ("how are you?", "I'm here and ready to help. How are you doing?"),
        ("hello", "Hi! What would you like to talk about?"),
        ("thanks", "You're welcome!"),
        ("Hope you're doing alright today!", "Hey, thanks for checking in! What's on your mind?"),
        ("That was really helpful, appreciate you", "You're welcome! Glad that helped."),
        (
            "This feels frustrating and impersonal",
            "That sounds frustrating. Let's slow down a little.",
        ),
        ("kya haal hain dost?", "Main yahan hoon, madad ke liye tayyar. Aap sunao?"),
    ],
)
def test_social_intent_uses_the_model_reply_without_dataset_lecture(integration, question, message):
    env = integration
    owner, _, _, path, model = prepare(env, {**SOCIAL, "message": message})
    result = ask(env, owner, path, question)
    answer = result["answer"]
    assert answer["message"] == message
    assert answer["guidance"]["focus"] == "conversation"
    assert answer["guidance"]["suggestions"] == []
    assert len(model.requests) == 1
    assert question in model.requests[0].messages[-1].content
    assert "social conversation" in model.requests[0].messages[0].content
    restored = env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=owner)
    assert restored.json() == answer
    outsider, _ = identity(env, "social-outsider@example.test")
    assert env.client.get(path, headers=outsider).status_code == 404
    assert env.client.get(
        path + f"/turns/{result['turn']['id']}/answer", headers=outsider
    ).status_code == 404
    with env.engine.connect() as conn:
        assert conn.execute(select(s.query_executions)).first() is None


@pytest.mark.parametrize(
    "question",
    [
        "Hi, how are you? What is the total revenue?",
        "Thanks, now show the maximum revenue by city",
        "This is frustrating. Calculate average revenue",
    ],
)
def test_social_proposal_cannot_swallow_mixed_analytical_request(integration, question):
    owner, _, _, path, model = prepare(integration, SOCIAL)
    result = ask(integration, owner, path, question)
    assert result["answer"] is None
    assert result["turn"]["kind"] == "ambiguous"
    assert result["turn"]["message"] != SOCIAL["message"]
    assert len(model.requests) == 1


def test_greeting_preamble_still_executes_typed_calculation(integration):
    proposal = {"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "sum"}}
    owner, _, _, path, model = prepare(integration, proposal)
    result = ask(integration, owner, path, "Hey, how's it going? What is total revenue?")
    assert result["turn"]["kind"] == "numerical"
    assert result["answer"] is not None
    assert len(model.requests) == 1
    with integration.engine.connect() as conn:
        assert conn.execute(select(s.query_executions)).first() is not None


@pytest.mark.parametrize(
    "change",
    [
        {"columns": ["attock_erp"]},
        {"message": "Revenue is 123."},
        {"message": "Go to https://example.test"},
        {"message": "<script>alert('x')</script>"},
        {"message": "a" * 401},
        {"message": ""},
        {"message": ["hello"]},
        {"message": "Hello\nfriend"},
        {"source": "invented"},
    ],
)
def test_invalid_social_payload_does_not_become_an_answer(change):
    result = route_response(json.dumps({**SOCIAL, **change}), description().view)
    assert result.kind == QuestionKind.UNSUPPORTED


@pytest.mark.parametrize("format", ["pdf", "xlsx", "csv"])
def test_social_reply_is_not_exported_as_an_analysis_report(integration, format):
    owner, _, _, path, _ = prepare(integration, SOCIAL)
    result = ask(integration, owner, path, "how are you?")
    response = integration.client.get(
        path + f"/turns/{result['turn']['id']}/export.{format}", headers=owner
    )
    assert response.status_code == 422, response.text
    assert "conversational reply" in response.json()["error"]["message"]
    with integration.engine.connect() as conn:
        assert conn.execute(
            select(s.audit_events).where(
                s.audit_events.c.action.in_(["pdf.exported", "result.exported"])
            )
        ).first() is None


def test_social_reply_rechecks_source_version_after_model_call(integration):
    env = integration

    class ChangingModel:
        async def complete(self, request):
            current = await asyncio.to_thread(context, env, owner, root)
            definition = copy.deepcopy(current["definition"])
            definition["description"] = "Updated synthetic sales definition"
            saved = await asyncio.to_thread(confirm, env, owner, root, current, definition)
            assert saved.status_code == 201
            return ModelResponse(json.dumps(SOCIAL), "test-model", "planner")

    owner, _, root, path, _ = prepare(env, primary=ChangingModel())
    result = ask(env, owner, path, "how are you?")
    assert result["answer"] is None
    assert "changed" in result["turn"]["message"]


@pytest.mark.parametrize(
    "message",
    [
        "The attock ERP value doubled because demand improved.",
        "I saved your preferences.",
        "Your confidential goal is to cut payroll.",
        "I have just analyzed the dataset.",
        "I remember your previous request.",
        "The data shows a clear improvement.",
    ],
)
def test_social_parser_refuses_source_claims_and_pretend_actions(message):
    result = route_response(json.dumps({**SOCIAL, "message": message}), description().view)
    assert result.kind == QuestionKind.UNSUPPORTED


def test_claimed_action_in_social_reply_is_not_published(integration):
    owner, _, _, path, _ = prepare(integration, {**SOCIAL, "message": "I saved your preferences."})
    result = ask(integration, owner, path, "how are you?")
    assert result["answer"] is None
    assert result["turn"]["status"] != "complete"
    assert "I saved" not in result["turn"]["message"]
