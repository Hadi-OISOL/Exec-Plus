"""Use case: Verifies meaning-first readings use authorized context without inventing results.

What it does: Checks model boundaries, private notes, missing inputs, source races and saved replay.
"""

import asyncio
import copy
import json

import pytest
from sqlalchemy import select

from execplus.application.contracts import ModelResponse
from execplus.domain.dataset_reading import parse_reading
from execplus.domain.errors import ProviderUnavailableError
from execplus.infrastructure.persistence import schema as s
from execplus.presentation.routes.analytics import get_intent_router_service
from test_context_reuse import saved
from test_dataset_guidance import ask, description
from test_understanding import confirm, context
from test_unified_conversation import document, setup
from test_workspace_integration import accept, identity, invite

READING = {
    "summary": "These records connect sales value with the city where the sale was recorded.",
    "connections": [
        {
            "columns": ["city", "revenue"],
            "meaning": "Location and sales value allow comparisons between cities.",
        }
    ],
    "explore": [{"metric": "revenue", "group_by": "city"}],
}


def prepare(env, *replies, primary=None):
    owner, wid, root, path, model = setup(env, *replies, primary=primary)
    router = env.client.app.dependency_overrides[get_intent_router_service]()
    router.interpretation_enabled = True
    saved(env, owner, root)
    return owner, wid, root, path, model


def test_reading_uses_saved_meaning_notes_goal_and_retains_private_replay(integration):
    env = integration
    owner, wid, root, path, model = prepare(env, READING, READING)
    document(
        env,
        owner,
        root,
        "PrivateReadingContext: revenue refers to collected sales.",
        f"data-reading-{root.split('/')[-1][:8]}.md",
        False,
    )
    env.client.post(
        root.split("/uploads/")[0] + "/preferences",
        headers=owner,
        json={"domain_hint": "auto", "goal": "PrivateGoal: compare cities"},
    )
    result = ask(env, owner, path, "Help me understand this data")
    answer = result["answer"]
    assert "What this data is about" in answer["message"]
    assert "sales value" in answer["message"]
    assert "What is the average of revenue by city?" in answer["guidance"]["suggestions"]
    assert "Field observations" in answer["message"]
    assert "no date column" in answer["message"]
    prompt = model.requests[-1].messages[-1].content
    assert "PrivateReadingContext" in prompt and "PrivateGoal" in prompt
    assert "PrivateCustomerA" not in prompt and "8.05" not in answer["message"]
    restored = env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=owner)
    assert restored.json() == answer
    member, user = identity(env, "reading-member@example.test")
    accept(env, member, wid, invite(env, owner, wid, user.email).json()["id"])
    assert env.client.get(path, headers=member).status_code == 404
    tid = env.client.post(root + "/threads", headers=member).json()["id"]
    ask(env, member, f"/workspaces/{wid}/threads/{tid}", "Help me understand this data")
    prompt = model.requests[-1].messages[-1].content
    assert "PrivateReadingContext" not in prompt and "PrivateGoal" not in prompt
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None


def test_reading_asks_only_the_missing_unit_before_suggesting_calculation(integration):
    env = integration
    owner, _, root, path, _ = prepare(env, READING)
    current = context(env, owner, root)
    definition = copy.deepcopy(current["definition"])
    next(c for c in definition["columns"] if c["name"] == "revenue")["unit"] = ""
    assert confirm(env, owner, root, current, definition).status_code == 201
    answer = ask(env, owner, path, "Help me understand this data")["answer"]
    assert "What unit is revenue recorded in?" in answer["message"]
    assert "What does revenue measure?" not in answer["message"]
    assert "What does a single row" not in answer["message"]
    assert answer["guidance"]["actions"] == [
        {"tool": "prepare", "label": "Complete missing details"}
    ]
    assert not any("average" in item for item in answer["guidance"]["suggestions"])
    assert context(env, owner, root)["definition"] == definition


@pytest.mark.parametrize(
    "response",
    [
        ProviderUnavailableError("private-provider-credential"),
        {**READING, "summary": "Revenue is 999999."},
        {**READING, "connections": [{"columns": ["unknown"], "meaning": "Unseen field"}]},
        {**READING, "explore": [{"metric": "revenue", "group_by": "unknown"}]},
        {**READING, "query": "SELECT * FROM secrets"},
    ],
)
def test_invalid_or_unavailable_reading_falls_back_without_calculations(integration, response):
    owner, _, _, path, model = prepare(integration, response, response)
    answer = ask(integration, owner, path, "Help me understand this data")["answer"]
    assert "The AI explanation" in answer["message"]
    assert "Your file is still available" in answer["message"]
    assert "999999" not in answer["message"] and "private-provider" not in answer["message"]
    assert answer["model_route"] == "deterministic:dataset-guidance-v1"
    assert len(model.requests) == (1 if isinstance(response, Exception) else 2)


def test_invalid_reading_gets_one_correction_using_only_authorized_context(integration):
    invalid = {**READING, "summary": "SecretBadReply: revenue is 999999."}
    owner, _, _, path, model = prepare(integration, invalid, READING)
    answer = ask(integration, owner, path, "Help me understand this data")["answer"]
    assert "sales value" in answer["message"]
    assert "The AI explanation" not in answer["message"]
    assert "999999" not in answer["message"]
    assert len(model.requests) == 2
    retry_prompt = "\n".join(message.content for message in model.requests[-1].messages)
    assert "SecretBadReply" not in retry_prompt
    assert "Field observations" in retry_prompt
    with integration.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None


def test_changed_notes_during_correction_cannot_publish_old_context(integration):
    env = integration

    class ChangingModel:
        calls = 0

        async def complete(self, request):
            self.calls += 1
            if self.calls == 1:
                return ModelResponse("malformed", "test", "planner")
            await asyncio.to_thread(
                document,
                env,
                owner,
                root,
                "Changed during correction.",
                f"data-reading-{root.split('/')[-1][:8]}.md",
                False,
            )
            return ModelResponse(json.dumps(READING), "test", "planner")

    primary = ChangingModel()
    owner, _, root, path, _ = prepare(env, primary=primary)
    result = ask(env, owner, path, "Help me understand this data")
    assert primary.calls == 2
    assert result["answer"] is None
    assert "changed while I was reading" in result["turn"]["message"]


def test_changed_context_after_invalid_reading_prevents_second_model_call(integration):
    env = integration

    class ChangingModel:
        calls = 0

        async def complete(self, request):
            self.calls += 1
            await asyncio.to_thread(
                document,
                env,
                owner,
                root,
                "Changed before another model call.",
                f"data-reading-{root.split('/')[-1][:8]}.md",
                False,
            )
            return ModelResponse("invalid", "test", "planner")

    primary = ChangingModel()
    owner, _, root, path, _ = prepare(env, primary=primary)
    result = ask(env, owner, path, "Help me understand this data")
    assert primary.calls == 1
    assert result["answer"] is None
    assert "changed while I was reading" in result["turn"]["message"]


def test_changed_context_during_reading_is_not_published(integration):
    env = integration

    class ChangingModel:
        async def complete(self, request):
            await asyncio.to_thread(
                document,
                env,
                owner,
                root,
                "A newer note.",
                f"data-reading-{root.split('/')[-1][:8]}.md",
                False,
            )
            return ModelResponse(json.dumps(READING), "test", "planner")

    owner, _, root, path, _ = prepare(env, primary=ChangingModel())
    result = ask(env, owner, path, "Help me understand this data")
    assert result["answer"] is None
    assert "changed while I was reading" in result["turn"]["message"]


def test_reading_cannot_name_unknown_columns_or_hide_numerical_claims_in_text():
    ctx = description()
    reading = {
        "summary": "Inventory records.",
        "connections": [{"columns": ["attock_erp"], "meaning": "Recorded inventory measure."}],
        "explore": [],
    }
    assert parse_reading(json.dumps(reading), ctx)["summary"] == "Inventory records."
    assert parse_reading("```json\n" + json.dumps(reading) + "\n```", ctx) == reading
    for text in ["Revenue is 700.", "<script>alert()</script>", "See https://example.test"]:
        with pytest.raises(ValueError):
            parse_reading(json.dumps({**reading, "summary": text}), ctx)
