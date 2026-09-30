"""Use case: Verifies hybrid planning and conversational record exploration.

What it does: Checks bounded plans, fallback, permissions, exact values and replay on real data.
"""

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.bootstrap import build_selection_model
from execplus.config import Settings
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.evidence import result_evidence
from execplus.domain.intent import route_response
from execplus.domain.models import ModelTier, QueryResult, QuestionKind
from execplus.presentation.routes.analytics import get_intent_router_service
from execplus.presentation.routes.threads import get_thread_service
from test_intent import view
from test_workspace_integration import dataset, identity, upload, workspace


class ScriptedModel:
    def __init__(self, *responses, provider="planner"):
        self.responses = list(responses)
        self.requests = []
        self.provider = provider

    async def complete(self, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return ModelResponse(json.dumps(response), "test-model", self.provider)


@pytest.mark.parametrize(
    "plan",
    [
        {"columns": ["missing"]},
        {"columns": ["region", "region"]},
        {"columns": "region"},
        {"columns": [1]},
        {"limit": 1001},
        {"limit": 0},
        {"limit": True},
        {"limit": "10"},
        {"sql": "DROP TABLE dataset"},
        {"filters": [{"column": "secret", "operator": "eq", "value": "x"}]},
        {"filters": [{"column": "region", "operator": "raw", "value": "x"}]},
    ],
)
def test_untrusted_record_plans_cannot_bypass_the_grammar(plan):
    assert route_response(json.dumps({"kind": "rows", "plan": plan}), view()).kind == (
        QuestionKind.UNSUPPORTED
    )


def test_model_prose_is_ignored_for_dataset_guidance():
    response = route_response('{"kind":"overview","message":"Revenue is 999999"}', view())
    assert response.kind == QuestionKind.OVERVIEW
    assert not response.message


def test_additive_match_counts_preserve_historical_result_checksums():
    old_result = QueryResult(uuid4(), ("city",), (("Karachi",),), 10)
    current_result = replace(old_result, matched_records=3)
    assert result_evidence(old_result)["checksum"] == result_evidence(current_result)["checksum"]


def test_selection_configuration_requires_complete_pair_and_hides_secret():
    with pytest.raises(ValueError, match="both a base URL and model"):
        Settings(_env_file=None, llm_selection_model="helper")
    settings = Settings(
        _env_file=None,
        llm_mode="local",
        llm_small_model="planner",
        llm_large_model="planner",
        llm_selection_base_url="http://helper/v1",
        llm_selection_model="helper",
        llm_selection_api_key="private-secret",
    )
    assert "private-secret" not in repr(settings)
    assert build_selection_model(settings) is not None
    assert build_selection_model(Settings(_env_file=None, llm_mode="disabled")) is None


def prepare(env, primary, selector=None, content=None):
    owner, _ = identity(env, "explorer@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    content = content or (
        b"city,customer,revenue\nKarachi,PrivateCustomerA,0.10\n"
        b"Lahore,PrivateCustomerB,7.75\nKARACHI,PrivateCustomerC,0.20\n"
    )
    result = upload(env, owner, wid, did, content, "cities.csv", "text/csv")
    assert result.status_code == 201
    uid = result.json()["id"]
    router = IntentRouterService(primary, env.runtime.analytics, selector)
    env.client.app.dependency_overrides[get_intent_router_service] = lambda: router
    threads = ThreadService(env.runtime.threads.uow, router)
    env.client.app.dependency_overrides[get_thread_service] = lambda: threads
    return owner, wid, f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"


def record_plan(limit=100):
    return {
        "kind": "rows",
        "plan": {
            "columns": [],
            "limit": limit,
            "filters": [
                {"column": "city", "operator": "ieq", "value": "karachi"},
            ],
        },
    }


def test_hybrid_city_records_are_scoped_bounded_exact_and_replayable(integration):
    env = integration
    primary = ScriptedModel(record_plan(1))
    selector = ScriptedModel({"route": "rows", "columns": ["city"]}, provider="selector")
    owner, wid, root = prepare(env, primary, selector)
    result = env.client.post(
        f"{root}/ask", headers=owner, json={"question": "show all records of karachi"}
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert len(body["rows"]) == 1
    assert body["records_analyzed"] == 3
    assert body["matched_records"] == 2
    assert body["rows"][0][2] == "0.100000000000"
    assert body["lineage"]["model_route"] == "selector:test-model -> planner:test-model"
    assert "LOWER" in body["lineage"]["sql"]
    assert "karachi" not in body["lineage"]["sql"]
    assert selector.requests[0].tier == ModelTier.SMALL
    assert primary.requests[0].tier == ModelTier.LARGE
    assert "Selection hint" in primary.requests[0].messages[-1].content
    assert all(
        "PrivateCustomer" not in message.content
        for request in selector.requests + primary.requests
        for message in request.messages
    )
    replay = env.client.post(
        f"/workspaces/{wid}/queries/{body['lineage']['query_id']}/replay", headers=owner
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["rows"] == body["rows"]
    outsider, _ = identity(env, "outside-explorer@example.test")
    blocked = env.client.post(f"{root}/ask", headers=outsider, json={"question": "show records"})
    assert blocked.status_code in {403, 404}
    assert len(primary.requests) == len(selector.requests) == 1


@pytest.mark.parametrize(
    "selection",
    [
        {"route": "rows", "columns": ["secret_column"]},
        ProviderUnavailableError("Provider unavailable"),
        {"route": "overview", "columns": []},
    ],
)
def test_invalid_unavailable_or_wrong_helper_does_not_override_primary(integration, selection):
    primary = ScriptedModel(record_plan())
    helper = ScriptedModel(selection)
    owner, _, root = prepare(integration, primary, helper)
    result = integration.client.post(
        f"{root}/ask", headers=owner, json={"question": "show Karachi records"}
    )
    assert result.status_code == 200, result.text
    assert len(result.json()["rows"]) == 2


def test_thread_can_greet_show_rows_and_follow_up_with_exact_total(integration):
    env = integration
    primary = ScriptedModel(
        {"kind": "overview", "message": "Invented revenue: 999999"},
        record_plan(),
        {
            "kind": "numerical",
            "plan": {
                "metric": "revenue",
                "aggregation": "sum",
                "filters": [{"column": "city", "operator": "ieq", "value": "karachi"}],
            },
        },
    )
    owner, wid, root = prepare(env, primary)
    thread = env.client.post(f"{root}/threads", headers=owner).json()["id"]
    endpoint = f"/workspaces/{wid}/threads/{thread}/ask"
    greeting = env.client.post(endpoint, headers=owner, json={"question": "Hi, how can you help?"})
    assert greeting.status_code == 200, greeting.text
    assert greeting.json()["turn"]["kind"] == "overview"
    assert greeting.json()["turn"]["model_route"] == "planner:test-model"
    assert "999999" not in greeting.text
    assert "revenue" in greeting.json()["answer"]["message"]
    records = env.client.post(endpoint, headers=owner, json={"question": "Show Karachi records"})
    assert records.json()["turn"]["kind"] == "rows"
    answer = env.client.post(endpoint, headers=owner, json={"question": "Their total revenue?"})
    assert answer.json()["answer"]["value"] == "0.300000000000"
    assert "city ieq 'karachi'" in primary.requests[-1].messages[-1].content
    assert "PrivateCustomer" not in primary.requests[-1].messages[-1].content


def test_record_queries_work_for_text_only_files_and_bind_injection(integration):
    primary = ScriptedModel(
        {
            "kind": "rows",
            "plan": {
                "filters": [
                    {"column": "city", "operator": "ieq", "value": "Karachi' OR 1=1 --"},
                ]
            },
        }
    )
    owner, _, root = prepare(integration, primary, content=b"city,customer\nKarachi,A\nLahore,B\n")
    result = integration.client.post(
        f"{root}/ask", headers=owner, json={"question": "show records"}
    )
    assert result.status_code == 200, result.text
    assert result.json()["rows"] == []
    assert result.json()["matched_records"] == 0
    assert "OR 1" not in result.json()["lineage"]["sql"]
