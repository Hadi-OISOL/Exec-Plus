"""Use case: Verifies the answer reviewer that cross-checks a plan before a reply is published.

What it does: Covers unsupported reply numbers, wrong-column repair, missing-condition
clarification, the optional model check and the fixed review codes saved with each turn.
"""

import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.domain.answer_review import (
    allowed_numbers,
    parse_model_review,
    plan_issue,
    unsupported_numbers,
)
from execplus.domain.intent import route_response
from execplus.domain.semantics import AggregationKind, dataset_view
from test_goal_ranking import LEADS_CSV, leads_view
from test_workspace_integration import identity, upload, workspace

VIEW = leads_view()


def plan(**body):
    return route_response(json.dumps({"kind": "numerical", "plan": body}), VIEW)


class Model:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        return ModelResponse(self.replies.pop(0), "fake-model", "fake")


def test_numbers_must_come_from_the_result_or_the_question():
    allowed = allowed_numbers(Decimal("1250.5"), "intent_score", ("Lahore", 18), 48)
    assert unsupported_numbers("The total is 1,250.5 across 48 leads.", allowed) == ()
    assert unsupported_numbers("Lahore has 18 leads, about 1.25 thousand.", allowed) == ()
    assert unsupported_numbers("The total is 1,999.", allowed) == ("1,999",)
    assert unsupported_numbers("Lahore holds 37.5% of leads.", allowed_numbers(18, 30)) == ()
    assert unsupported_numbers("Lahore holds 90% of leads.", allowed_numbers(18, 30)) == ("90%",)


def test_correct_plan_passes_and_wrong_column_is_repaired_once():
    question = "What is the average fit_score by source?"
    good = plan(metric="fit_score", aggregation="avg", group_by=["source"])
    assert plan_issue(question, good, VIEW) == ("", good)
    wrong = plan(metric="intent_score", aggregation="avg", group_by=["source"])
    issue, repaired = plan_issue(question, wrong, VIEW)
    assert issue == "wrong_column" and repaired.request.metric == "fit_score"
    assert plan_issue(question, repaired, VIEW)[0] == ""
    both = "Compare the average fit_score and total_score by source"
    assert plan_issue(both, wrong, VIEW) == ("wrong_column", wrong)


def test_missing_conditions_and_question_type_are_caught():
    whole = plan(metric="intent_score", aggregation="avg")
    assert plan_issue("Average intent_score above 7?", whole, VIEW)[0] == "missing_filter"
    dated = dataset_view(
        {
            "columns": [
                {"name": "intent_score", "type": "integer", "role": "metric"},
                {"name": "posted_at", "type": "date", "role": "dimension"},
            ]
        }
    )
    yearly = route_response(
        json.dumps({"kind": "numerical", "plan": {"metric": "intent_score", "aggregation": "avg"}}),
        dated,
    )
    assert plan_issue("Average intent_score in 2025?", yearly, dated)[0] == "missing_filter"
    assert plan_issue("Average intent_score for source LinkedIn", whole, VIEW)[0] == (
        "missing_filter"
    )
    total = plan(metric="intent_score", aggregation="count")
    issue, repaired = plan_issue("What is the average intent_score?", total, VIEW)
    assert issue == "wrong_operation" and repaired.request.aggregation == AggregationKind.AVG
    grouped = plan(metric="intent_score", aggregation="avg", group_by=["source"])
    issue, repaired = plan_issue("Which source has the lowest intent_score?", grouped, VIEW)
    assert issue == "wrong_operation" and repaired.request.order == "asc"


def test_model_review_reply_is_strict():
    assert parse_model_review('{"verdict":"ok"}', VIEW) == ("", None)
    issue, alternative = parse_model_review(
        json.dumps(
            {
                "verdict": "flag",
                "issue": "wrong_column",
                "plan": {
                    "kind": "numerical",
                    "plan": {"metric": "fit_score", "aggregation": "avg", "group_by": []},
                },
            }
        ),
        VIEW,
    )
    assert issue == "wrong_column" and alternative.request.metric == "fit_score"
    for bad in ('{"verdict":"ok","value":3}', '{"verdict":"flag","issue":"cause"}', "[]"):
        with pytest.raises(ValueError):
            parse_model_review(bad, VIEW)


async def thread(env, model, review_model=False):
    headers, actor = identity(env, f"{uuid4().hex[:8]}@example.test")
    wid = workspace(env, headers)
    did = env.client.post(
        f"/workspaces/{wid}/datasets", headers=headers, json={"name": "Leads"}
    ).json()["id"]
    response = upload(env, headers, wid, did, LEADS_CSV, "leads.csv", "text/csv")
    assert response.status_code == 201, response.text
    router = IntentRouterService(model, env.runtime.analytics, review_model_enabled=review_model)
    threads = ThreadService(env.runtime.threads.uow, router)
    started = await threads.start_thread(actor, UUID(wid), UUID(did), UUID(response.json()["id"]))
    return actor, UUID(wid), threads, started, headers


@pytest.mark.asyncio
async def test_offered_question_passes_without_any_model_call(integration):
    model = Model()
    actor, wid, threads, started, headers = await thread(integration, model)
    answer, turn = await threads.ask(
        actor, wid, started.id, "What is the average of intent_score by source?"
    )
    assert turn.status == "complete" and answer is not None
    assert turn.evidence["review"] == "passed"
    assert model.requests == []
    listed = integration.client.get(
        f"/workspaces/{wid}/threads/{started.id}", headers=headers
    ).json()
    assert listed["turns"][-1]["review"] == "passed"


@pytest.mark.asyncio
async def test_wrong_column_plan_is_replanned_and_recorded(integration):
    reply = json.dumps(
        {
            "kind": "numerical",
            "plan": {"metric": "intent_score", "aggregation": "avg", "group_by": []},
        }
    )
    model = Model(reply)
    actor, wid, threads, started, _ = await thread(integration, model)
    answer, turn = await threads.ask(actor, wid, started.id, "how good is the fit_score overall")
    assert turn.evidence["review"] == "replanned:wrong_column"
    assert answer.lineage.metric == "fit_score" and str(answer.value) == "7.333333333333"
    assert "(review: wrong_column)" in turn.model_route
    assert len(model.requests) == 1


@pytest.mark.asyncio
async def test_dropped_condition_becomes_a_clarification_with_choices(integration):
    reply = json.dumps(
        {
            "kind": "numerical",
            "plan": {"metric": "intent_score", "aggregation": "avg", "group_by": []},
        }
    )
    actor, wid, threads, started, _ = await thread(integration, Model(reply))
    answer, turn = await threads.ask(
        actor, wid, started.id, "tell me the intent_score for leads in the Remote location"
    )
    assert answer is None and turn.kind == "ambiguous"
    assert turn.evidence["review"] == "clarified:missing_filter"
    assert turn.message.startswith("I checked my plan against your question")
    assert turn.evidence["clarification"]["choices"]


@pytest.mark.asyncio
async def test_optional_model_check_can_flag_and_ok_costs_one_call(integration):
    reply = json.dumps(
        {
            "kind": "numerical",
            "plan": {"metric": "intent_score", "aggregation": "avg", "group_by": []},
        }
    )
    flag = json.dumps({"verdict": "flag", "issue": "question_not_answered", "plan": None})
    model = Model(reply, flag)
    actor, wid, threads, started, _ = await thread(integration, model, review_model=True)
    answer, turn = await threads.ask(actor, wid, started.id, "how keen are these leads")
    assert answer is None and turn.evidence["review"] == "clarified:question_not_answered"
    assert len(model.requests) == 2
    assert "Lahore" not in model.requests[1].messages[1].content
    model = Model(reply, '{"verdict":"ok"}')
    actor, wid, threads, started, _ = await thread(integration, model, review_model=True)
    answer, turn = await threads.ask(actor, wid, started.id, "how keen are these leads")
    assert turn.evidence["review"] == "passed" and len(model.requests) == 2


@pytest.mark.asyncio
async def test_reply_wording_with_a_foreign_number_is_dropped(integration, monkeypatch):
    actor, wid, threads, started, _ = await thread(integration, Model())

    async def narrative(*_):
        segment = dict(statement_id="s1", text="The average is 999.", evidence_ids=[], kind="x")
        return {"narrative": {"version": "v", "mode": "selected", "segments": [segment]}}

    threads.response_synthesis = object()
    monkeypatch.setattr(threads, "_narrative", narrative)
    answer, turn = await threads.ask(
        actor, wid, started.id, "What is the average of intent_score by source?"
    )
    assert answer is not None and "narrative" not in turn.evidence
    assert turn.evidence["review"] == "fallback:unsupported_number"
