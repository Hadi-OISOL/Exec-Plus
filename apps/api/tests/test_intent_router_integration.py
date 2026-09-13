"""Use case: Proves NL question routing and grounded summaries against real infrastructure.

What it does: Swaps in a fake language model (no billed provider required) to prove
only numerical intents execute, hallucinated columns are rejected, and an ungrounded
summary is refused, all through the real HTTP surface.
"""

import json

from execplus.application.contracts import ModelResponse
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.summaries import SummaryService
from execplus.presentation.routes.analytics import get_intent_router_service, get_summary_service
from test_analytics_integration import uploaded_dataset
from test_workspace_integration import identity, workspace


class FakeLanguageModel:
    def __init__(self, content: str) -> None:
        self.content = content

    async def complete(self, request: object) -> ModelResponse:
        return ModelResponse(content=self.content, model="fake-model", provider="fake")


def ask(env, headers, wid, did, uid, question):
    return env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/ask",
        headers=headers,
        json={"question": question},
    )


def summary(env, headers, wid, did, uid):
    return env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/dashboard/summary",
        headers=headers,
        json={"filters": []},
    )


def _override_model(env, service_cls, getter, fake_model):
    if service_cls is IntentRouterService:
        env.client.app.dependency_overrides[getter] = lambda: IntentRouterService(
            fake_model, env.runtime.analytics
        )
    else:
        env.client.app.dependency_overrides[getter] = lambda: SummaryService(fake_model)


def test_ask_executes_only_for_a_numerical_response(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    fake = FakeLanguageModel(
        json.dumps({"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "sum"}})
    )
    _override_model(env, IntentRouterService, get_intent_router_service, fake)

    response = ask(env, owner, wid, did, uid, "What is total revenue?")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["value"] == 350.0
    assert body["lineage"]["metric"] == "revenue"
    assert body["lineage"]["model_route"] == "fake:fake-model"


def test_ask_rejects_a_hallucinated_column_before_executing(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    fake = FakeLanguageModel(
        json.dumps({"kind": "numerical", "plan": {"metric": "profit_margin", "aggregation": "sum"}})
    )
    _override_model(env, IntentRouterService, get_intent_router_service, fake)

    response = ask(env, owner, wid, did, uid, "What is our profit margin?")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_question"


def test_ask_returns_clarification_for_ambiguous_response(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    fake = FakeLanguageModel(
        json.dumps(
            {"kind": "ambiguous", "message": "Which amount?", "options": ["revenue", "cost"]}
        )
    )
    _override_model(env, IntentRouterService, get_intent_router_service, fake)

    response = ask(env, owner, wid, did, uid, "What is the amount?")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "clarification_required"


def test_suggested_questions_endpoint_needs_no_model(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/suggested-questions", headers=owner
    )

    assert response.status_code == 200, response.text
    assert any("revenue" in question.lower() for question in response.json())


def test_dashboard_summary_accepts_a_grounded_narrative(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    fake = FakeLanguageModel("Total revenue reached 350.")
    _override_model(env, SummaryService, get_summary_service, fake)

    response = summary(env, owner, wid, did, uid)

    assert response.status_code == 200, response.text
    assert response.json()["summary"] == "Total revenue reached 350."


def test_dashboard_summary_rejects_an_ungrounded_number(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    fake = FakeLanguageModel("Total revenue reached 999999, a huge increase.")
    _override_model(env, SummaryService, get_summary_service, fake)

    response = summary(env, owner, wid, did, uid)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
