"""Use case: Proves multi-turn threads resolve follow-ups from structured references.

What it does: Swaps in a fake language model that only answers a follow-up
correctly when it receives the prior turn's structured plan, proving continuity
comes from stored lineage rather than raw prompt text.
"""

import json

from execplus.application.contracts import ModelResponse
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.presentation.routes.analytics import get_intent_router_service
from execplus.presentation.routes.threads import get_thread_service
from test_analytics_integration import uploaded_dataset
from test_workspace_integration import identity, workspace


class ContextAwareFakeModel:
    """Replies 'region' only once a prior-turn structured context is present."""

    async def complete(self, request: object) -> ModelResponse:
        user_message = request.messages[-1].content  # type: ignore[attr-defined]
        if "Previous turn" in user_message:
            plan = {
                "kind": "numerical",
                "plan": {"metric": "revenue", "aggregation": "sum", "group_by": ["region"]},
            }
        else:
            plan = {"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "sum"}}
        return ModelResponse(content=json.dumps(plan), model="fake-model", provider="fake")


def _wire_fake_thread_service(env):
    analytics = env.runtime.analytics
    intent_router = IntentRouterService(ContextAwareFakeModel(), analytics)
    env.client.app.dependency_overrides[get_intent_router_service] = lambda: intent_router
    fake_threads = ThreadService(env.runtime.threads.uow, intent_router)
    env.client.app.dependency_overrides[get_thread_service] = lambda: fake_threads
    return fake_threads


def test_thread_follow_up_uses_prior_turns_structured_lineage_not_raw_text(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    _wire_fake_thread_service(env)

    created = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/threads", headers=owner
    )
    assert created.status_code == 201, created.text
    thread_id = created.json()["id"]

    first = env.client.post(
        f"/workspaces/{wid}/threads/{thread_id}/ask",
        headers=owner,
        json={"question": "What is total revenue?"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["turn"]["kind"] == "numerical"
    assert first.json()["answer"]["lineage"]["grouping"] == []

    follow_up = env.client.post(
        f"/workspaces/{wid}/threads/{thread_id}/ask",
        headers=owner,
        json={"question": "and by region?"},
    )
    assert follow_up.status_code == 200, follow_up.text
    assert follow_up.json()["answer"]["lineage"]["grouping"] == ["region"]


def test_get_thread_returns_all_recorded_turns(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    _wire_fake_thread_service(env)

    created = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/threads", headers=owner
    )
    thread_id = created.json()["id"]
    env.client.post(
        f"/workspaces/{wid}/threads/{thread_id}/ask",
        headers=owner,
        json={"question": "What is total revenue?"},
    )
    env.client.post(
        f"/workspaces/{wid}/threads/{thread_id}/ask",
        headers=owner,
        json={"question": "and by region?"},
    )

    response = env.client.get(f"/workspaces/{wid}/threads/{thread_id}", headers=owner)

    assert response.status_code == 200, response.text
    assert len(response.json()["turns"]) == 2


def test_thread_across_workspaces_is_not_found(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    outsider, _ = identity(env, "outsider@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    created = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/threads", headers=owner
    )
    thread_id = created.json()["id"]
    other_wid = workspace(env, outsider)

    response = env.client.get(f"/workspaces/{other_wid}/threads/{thread_id}", headers=outsider)

    assert response.status_code == 404
