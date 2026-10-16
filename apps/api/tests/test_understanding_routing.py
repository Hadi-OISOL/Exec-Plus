"""Use case: Reproduces ordinary explanation questions being replaced by a generic menu.

What it does: Exercises semantic tool dispatch, unresolved work, private context,
freshness and the real durable-job model-call budget.
"""

import asyncio
import copy
import json
from uuid import UUID

import pytest
from sqlalchemy import select

from execplus.domain.conversation_requirements import request_requirements
from execplus.infrastructure.persistence import schema as s
from execplus.presentation.routes.analytics import get_intent_router_service
from execplus.presentation.routes.threads import get_thread_service
from test_agent_memory import memory_path, save
from test_conversation_jobs import job_path, process, submit
from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask, description
from test_dataset_reading import READING, prepare
from test_understanding import confirm, context
from test_unified_conversation import NUMERICAL, document
from test_workspace_integration import accept, identity, invite

OVERVIEW = {"kind": "overview", "columns": [], "focus": "orientation"}


@pytest.mark.parametrize(
    "question",
    [
        "what this data about?",
        "i want to know generally what this data is about",
        "Give me the big picture of this file",
        "Could you walk me through what these observations represent?",
        "Tell me the overall story behind this spreadsheet",
        "ye data kis bare mein hai",
    ],
)
def test_semantic_understanding_dispatches_to_reading_and_reopens_exactly(integration, question):
    env = integration
    owner, _, root, path, model = prepare(env, OVERVIEW, READING)
    before = context(env, owner, root)
    result = ask(env, owner, path, question)
    answer = result["answer"]
    assert answer is not None, result
    assert "sales value" in answer["message"] and "What would you like" not in answer["message"]
    assert answer["model_route"].endswith(":dataset-reading-v1")
    assert len(model.requests) == 2
    assert "Question: " + question in model.requests[0].messages[-1].content
    assert json.loads(model.requests[-1].messages[-1].content)["explanation_request"] == question
    assert (
        env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=owner).json()
        == answer
    )
    assert context(env, owner, root) == before
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None


def test_existing_whole_file_explanation_is_not_a_broad_analysis_goal(integration):
    owner, _, _, path, model = prepare(integration, READING)
    answer = ask(integration, owner, path, "What can you tell me about this data?")["answer"]
    assert "sales value" in answer["message"]
    assert len(model.requests) == 1


@pytest.mark.parametrize(
    "question",
    [
        "Count revenue",
        "How many records are there?",
        "What is the min revenue?",
        "What is the max revenue?",
        "What is the mean revenue?",
        "Calculate unknown_margin",
        "revenue > 10",
        "Explain the total revenue",
        "Show records for city Karachi",
        "Explain this file only for Karachi",
        "Give an overview excluding Karachi",
        "Tell me about this data since yesterday",
        "What does the policy say?",
        "Make a chart of revenue",
    ],
)
def test_overview_cannot_silently_replace_requested_work(integration, question):
    owner, _, _, path, model = prepare(integration, OVERVIEW)
    result = ask(integration, owner, path, question)
    assert result["answer"] is None, result
    assert result["turn"]["kind"] == "ambiguous"
    assert len(model.requests) == 1
    with integration.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None


@pytest.mark.parametrize(
    "question",
    [
        "What does attock_erp mean?",
        "Explain item_code",
        "What is this data about?",
        "What does category mean in this file?",
        "Explain the category in this file",
    ],
)
def test_definition_requests_do_not_require_a_calculation(question):
    assert not request_requirements(question, description().view).overview_conflicts


def test_new_understanding_supersedes_pending_calculation_but_metric_reply_keeps_it(integration):
    owner, _, _, path, model = prepare(
        integration, OVERVIEW, OVERVIEW, OVERVIEW, READING, NUMERICAL
    )
    pending = ask(integration, owner, path, "What is total revenue?")
    assert pending["answer"] is None
    retry = ask(integration, owner, path, "revenue")
    assert retry["answer"] is None
    assert '"original_question": "What is total revenue?"' in model.requests[1].messages[-1].content
    reading = ask(integration, owner, path, "i want to know generally what this data is about")
    assert "sales value" in reading["answer"]["message"]
    calculated = ask(integration, owner, path, "What is total revenue?")
    assert calculated["answer"]["value"] == "8.050000000000"
    assert len(model.requests) == 5


def test_new_understanding_uses_current_source_after_old_pending_task_becomes_stale(integration):
    owner, _, root, path, model = prepare(integration, OVERVIEW, OVERVIEW, READING)
    ask(integration, owner, path, "What is total revenue?")
    old = context(integration, owner, root)
    definition = copy.deepcopy(old["definition"])
    definition["description"] = "New current meaning."
    assert confirm(integration, owner, root, old, definition).status_code == 201
    result = ask(integration, owner, path, "what this data about?")
    assert "New current meaning" in result["answer"]["message"]
    assert "Pending clarification" not in model.requests[1].messages[-1].content


def test_reading_rechecks_source_after_semantic_classification(integration):
    env = integration

    class ChangingModel(ScriptedModel):
        async def complete(self, request):
            current = await asyncio.to_thread(context, env, owner, root)
            definition = copy.deepcopy(current["definition"])
            definition["description"] = "Changed while classifying."
            await asyncio.to_thread(confirm, env, owner, root, current, definition)
            return await super().complete(request)

    model = ChangingModel(OVERVIEW)
    owner, _, root, path, _ = prepare(env, primary=model)
    result = ask(env, owner, path, "what this data about?")
    assert result["answer"] is None and "changed" in result["turn"]["message"]
    assert len(model.requests) == 1


def test_forget_during_classification_is_respected_before_reading(integration):
    env = integration

    class ForgettingModel(ScriptedModel):
        async def complete(self, request):
            if not self.requests:
                response = await asyncio.to_thread(
                    env.client.delete, memory_path(wid) + "?expected_version=1", headers=owner
                )
                assert response.status_code == 200
            return await super().complete(request)

    model = ForgettingModel(OVERVIEW, READING)
    owner, wid, _, path, _ = prepare(env, primary=model)
    assert save(env, owner, wid).status_code == 200
    result = ask(env, owner, path, "what this data about?")
    assert result["answer"] is not None
    assert "PrivateRetailRole" not in json.dumps(
        [request.messages for request in model.requests], default=str
    )
    assert json.loads(model.requests[-1].messages[-1].content)["personal_memory"] == {}


@pytest.mark.parametrize("corrected", [True, False])
def test_semantic_reading_correction_fits_actual_three_call_job_budget(integration, corrected):
    env = integration
    invalid = {**READING, "summary": "UntrustedBadProse 99999."}
    owner, _, _, path, model = prepare(env, OVERVIEW, invalid, READING if corrected else invalid)
    router = env.client.app.dependency_overrides[get_intent_router_service]()
    selector = ScriptedModel({"route": "overview", "columns": []})
    router.selector = selector
    env.runtime.jobs.threads = env.client.app.dependency_overrides[get_thread_service]()
    job = submit(env, owner, path, "what this data about?")
    assert process(env) == {"processed": 1}
    assert env.client.get(job_path(job), headers=owner).json()["status"] == "succeeded"
    result = env.client.get(job_path(job) + "/result", headers=owner).json()
    assert len(model.requests) == 3 and not selector.requests
    assert (":dataset-reading-v1" in result["answer"]["model_route"]) == corrected
    assert "99999" not in result["answer"]["message"]
    assert "UntrustedBadProse" not in "\n".join(
        message.content for message in model.requests[-1].messages
    )
    with env.engine.connect() as connection:
        plan = connection.execute(
            select(s.jobs.c.plan).where(s.jobs.c.id == UUID(job["id"]))
        ).scalar_one()
        assert plan["value"]["steps"][0]["operation"] == "inspect_profile"
        assert connection.execute(select(s.query_executions)).first() is None


def test_semantic_reading_remains_owner_private(integration):
    owner, wid, _, path, model = prepare(integration, OVERVIEW, READING)
    result = ask(integration, owner, path, "what this data about?")
    member, user = identity(integration, "semantic-reading-member@example.test")
    accept(integration, member, wid, invite(integration, owner, wid, user.email).json()["id"])
    assert integration.client.get(path, headers=member).status_code == 404
    assert (
        integration.client.get(
            path + f"/turns/{result['turn']['id']}/answer", headers=member
        ).status_code
        == 404
    )
    assert len(model.requests) == 2


@pytest.mark.parametrize("followup", ["make it simpler", "i dont understand", "tell me more"])
def test_explanation_repair_reuses_only_the_source_checked_previous_explanation(
    integration, followup
):
    owner, _, _, path, model = prepare(integration, OVERVIEW, READING, READING)
    first = ask(integration, owner, path, "what this data about?")
    repaired = ask(integration, owner, path, followup)
    assert "sales value" in repaired["answer"]["message"]
    prompt = json.loads(model.requests[-1].messages[-1].content)
    assert prompt["previous_explanation_to_rephrase"] == first["answer"]["message"][:3500]
    assert prompt["explanation_request"] == followup
    assert "reading_context_digest" not in json.dumps(repaired)


@pytest.mark.parametrize("changed", ["memory", "goal", "notes", "historical"])
def test_rephrasing_does_not_reintroduce_outdated_private_context(integration, changed):
    env = integration
    owner, wid, root, path, model = prepare(env, READING, READING)
    assert save(env, owner, wid).status_code == 200
    first = ask(env, owner, path, "Help me understand this data")
    if changed == "memory":
        assert (
            env.client.delete(memory_path(wid) + "?expected_version=1", headers=owner).status_code
            == 200
        )
    elif changed == "goal":
        assert (
            env.client.post(
                root.split("/uploads/")[0] + "/preferences",
                headers=owner,
                json={"domain_hint": "auto", "goal": "A revised private goal"},
            ).status_code
            == 200
        )
    elif changed == "notes":
        document(
            env, owner, root, "New saved note.", f"data-reading-{root.split('/')[-1][:8]}.md", False
        )
    else:
        with env.engine.begin() as connection:
            evidence = connection.execute(
                select(s.thread_turns.c.evidence).where(
                    s.thread_turns.c.id == UUID(first["turn"]["id"])
                )
            ).scalar_one()
            del evidence["guide"]["reading_context_digest"]
            connection.execute(
                s.thread_turns.update()
                .where(s.thread_turns.c.id == UUID(first["turn"]["id"]))
                .values(evidence=evidence)
            )
    repaired = ask(env, owner, path, "make it simpler")
    assert repaired["answer"] is not None
    prompt = json.loads(model.requests[-1].messages[-1].content)
    assert "previous_explanation_to_rephrase" not in prompt
    if changed == "memory":
        assert "PrivateRetailRole" not in json.dumps(prompt)


def test_explanation_repair_cannot_reuse_changed_source(integration):
    owner, _, root, path, model = prepare(integration, READING)
    ask(integration, owner, path, "Help me understand this data")
    current = context(integration, owner, root)
    assert confirm(integration, owner, root, current, current["definition"]).status_code == 201
    result = ask(integration, owner, path, "make it simpler")
    assert result["answer"] is None and "changed" in result["turn"]["message"]
    assert len(model.requests) == 1
