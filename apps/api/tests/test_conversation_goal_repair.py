"""Reproduce the menu loop without relying on a cooperative planner."""

import pytest
from sqlalchemy import select

from execplus.infrastructure.persistence import schema as s
from test_dataset_guidance import ask
from test_dataset_reading import READING, prepare


@pytest.mark.parametrize("question", ["hey there", "hello there!", "salam"])
def test_greeting_is_brief_and_never_calls_model_or_query(integration, question):
    env = integration
    owner, _, _, path, model = prepare(env)
    answer = ask(env, owner, path, question)["answer"]
    assert answer["message"].startswith("Hey!")
    assert len(answer["message"]) < 260
    assert "previous executed measure" not in answer["message"]
    assert not model.requests
    with env.engine.connect() as conn:
        assert conn.execute(select(s.query_executions)).first() is None


@pytest.mark.parametrize(
    "question",
    [
        "what can you do for me in this data?",
        "what can you do with this data?",
    ],
)
def test_capabilities_use_the_current_file_reading(integration, question):
    env = integration
    owner, _, _, path, model = prepare(env, READING)
    answer = ask(env, owner, path, question)["answer"]
    assert "sales value" in answer["message"]
    assert "start with a small question" not in answer["message"]
    assert question in model.requests[-1].messages[-1].content


def test_model_next_steps_is_read_for_the_actual_question(integration):
    env = integration
    owner, _, _, path, model = prepare(
        env, {"kind": "overview", "focus": "next_steps", "columns": []}, READING
    )
    answer = ask(env, owner, path, "Could you suggest useful things to investigate here?")["answer"]
    assert "sales value" in answer["message"]
    assert len(model.requests) == 2


@pytest.mark.parametrize("after_calculation", [False, True])
@pytest.mark.parametrize(
    "proposal",
    [
        {"kind": "overview", "focus": "next_steps", "columns": []},
        {
            "kind": "ambiguous",
            "message": "Choose a maximum",
            "options": [str(i) for i in range(11)],
        },
    ],
)
def test_ideal_conditions_ask_for_outcome_not_maximizing_inputs(
    integration, after_calculation, proposal
):
    env = integration
    numerical = {"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "sum"}}
    owner, _, _, path, model = prepare(env, *([numerical] if after_calculation else []), proposal)
    if after_calculation:
        assert ask(env, owner, path, "What is total revenue?")["answer"] is not None
    count = len(model.requests)
    reply = ask(
        env,
        owner,
        path,
        "can you help me finding the perfect crop conditions needed accordingly by this data?",
    )
    assert reply["answer"] is None
    assert "outcome" in reply["turn"]["message"].lower()
    assert "Higher measurements are not automatically better" in reply["turn"]["message"]
    assert len(model.requests) == count


def test_calculate_ideal_conditions_still_needs_an_outcome(integration):
    owner, _, _, path, model = prepare(integration)
    reply = ask(integration, owner, path, "Calculate the ideal crop conditions")
    assert reply["answer"] is None
    assert "outcome" in reply["turn"]["message"]
    assert not model.requests
