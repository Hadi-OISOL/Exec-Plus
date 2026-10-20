"""Use case: Prevents old tasks from leaking through a new private conversation task.

What it does: Exercises persisted context boundaries, follow-ups and saved choices
against the real thread service while keeping the model response deterministic.
"""

from inspect import signature

import pytest

from execplus.presentation.routes.threads import get_thread_service
from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask, setup


@pytest.mark.parametrize(
    "new_question",
    [
        "Help me understand this data",
        "What does attock_erp mean?",
        "Show me a diagram of the fields in this data",
    ],
)
def test_new_task_prevents_resurrecting_an_older_measure_after_thanks(integration, new_question):
    env = integration
    model = ScriptedModel(
        {"kind": "numerical", "plan": {"metric": "attock_erp", "aggregation": "sum"}},
        {"kind": "ambiguous", "message": "Which measure should I compare by category?"},
    )
    owner, _, root, path, _ = setup(env, model)
    before = env.client.get(root + "/understanding", headers=owner).json()
    numeric = ask(env, owner, path, "What is the total attock_erp?")
    assert numeric["answer"]["value"] == 5
    new_task = ask(env, owner, path, new_question)
    assert new_task["answer"] is not None
    ask(env, owner, path, "thank you")
    followup = ask(env, owner, path, "and by category?")
    assert followup["turn"]["kind"] == "ambiguous"
    planner = model.requests[-1].messages[-1].content
    assert "Previous turn:" not in planner
    assert "Previous document search" not in planner
    assert len(model.requests) == 2
    assert env.client.get(root + "/understanding", headers=owner).json() == before
    replay = env.client.get(path + "/turns/" + numeric["turn"]["id"] + "/answer", headers=owner)
    assert replay.status_code == 200 and replay.json() == numeric["answer"]


def test_a_new_calculation_after_orientation_becomes_the_followup_context(integration):
    env = integration
    model = ScriptedModel(
        {"kind": "numerical", "plan": {"metric": "attock_erp", "aggregation": "avg"}},
        {
            "kind": "numerical",
            "plan": {"metric": "attock_erp", "aggregation": "avg", "group_by": ["category"]},
        },
    )
    owner, _, _, path, _ = setup(env, model)
    assert ask(env, owner, path, "Help me understand this data")["answer"] is not None
    assert ask(env, owner, path, "What is the average attock_erp?")["answer"] is not None
    ask(env, owner, path, "thank you")
    grouped = ask(env, owner, path, "and by category?")
    assert grouped["answer"]["lineage"]["grouping"] == ["category"]
    assert "Previous turn: avg of attock_erp" in model.requests[-1].messages[-1].content


def test_saved_clarification_choices_survive_into_the_next_router_call(integration):
    env = integration
    model = ScriptedModel(
        {"kind": "numerical", "plan": {"metric": "attock_erp", "aggregation": "sum"}}
    )
    owner, _, _, path, _ = setup(env, model)
    first = ask(env, owner, path, "analyze my data")
    choices = first["turn"]["clarification"]["choices"]
    service = env.client.app.dependency_overrides[get_thread_service]()
    original = service.intent_router.ask
    received = []

    async def capture(*args, **kwargs):
        received.append(signature(original).bind(*args, **kwargs).arguments["prior_clarification"])
        return await original(*args, **kwargs)

    service.intent_router.ask = capture
    answer = ask(env, owner, path, "What is the total of attock_erp?")
    assert answer["answer"]["value"] == 5
    assert received[0].choices == tuple(choices)
