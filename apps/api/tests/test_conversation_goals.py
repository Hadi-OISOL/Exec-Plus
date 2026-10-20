"""Use case: Reproduces generic replies instead of useful goal clarification.

What it does: Tests source-bound choices, continuation, stale context and planner
fallback without model arithmetic.
"""

import copy
import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from execplus.domain.guidance import goal_choices, needs_goal_clarification
from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask, description, setup
from test_understanding import confirm, context


@pytest.mark.parametrize("question", ["analyze my data", "show me insights", "find patterns", "??"])
def test_broad_goals_require_a_specific_next_step(question):
    assert needs_goal_clarification(question)
    assert not needs_goal_clarification("What does attock_erp mean?")
    assert not needs_goal_clarification("What is the total attock_erp?")
    assert not needs_goal_clarification("??", ("attock_erp",))
    choices = goal_choices(description())
    assert "What is the average of attock_erp_value?" in choices
    assert "Show the first 10 records" in choices
    assert not any("item_code" in choice and "total" in choice for choice in choices)


def test_goal_reply_preserves_original_context(
    integration,
):
    env = integration
    model = ScriptedModel(
        {"kind": "numerical", "plan": {"metric": "attock_erp", "aggregation": "sum"}}
    )
    owner, wid, _, path, _ = setup(env, model)
    first = ask(env, owner, path, "analyze my data")
    assert first["turn"]["kind"] == "ambiguous" and first["answer"] is None
    choices = first["turn"]["clarification"]["choices"]
    assert "What is the average of attock_erp_value?" in choices
    assert "What would you like to find" in first["turn"]["message"]
    assert not model.requests
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None
    repeat = ask(env, owner, path, "??")
    assert (
        repeat["turn"]["kind"] == "ambiguous"
        and repeat["turn"]["clarification"] == first["turn"]["clarification"]
    )
    answer = ask(env, owner, path, "What's the total of attock_erp?")
    assert answer["answer"]["value"] == 5
    planner = model.requests[-1].messages[-1].content
    assert '"original_question": "analyze my data"' in planner
    assert "PrivateItem" not in planner
    historical = env.client.get(path, headers=owner).json()
    assert historical["turns"][0]["clarification"]["choices"] == choices
    assert env.client.get(path.replace(str(wid), str(uuid4())), headers=owner).status_code == 404


@pytest.mark.parametrize("columns", [[], ["attock_erp"]])
def test_misrouted_calculation_clarifies_without_querying(integration, columns):
    model = ScriptedModel({"kind": "overview", "columns": columns})
    owner, _, _, path, _ = setup(integration, model)
    result = ask(integration, owner, path, "What's the total attock_erp?")
    assert result["turn"]["kind"] == "ambiguous" and result["answer"] is None
    assert result["turn"]["clarification"]["choices"] == ["attock_erp"]
    assert "including any filters" in result["turn"]["message"]
    with integration.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None


def test_unknown_question_cannot_receive_empty_generic_model_overview(integration):
    model = ScriptedModel({"kind": "overview"})
    owner, _, _, path, _ = setup(integration, model)
    result = ask(integration, owner, path, "Can you work out the thing I need?")
    assert result["turn"]["kind"] == "ambiguous"
    assert result["answer"] is None
    assert "attock_erp" in json.dumps(result["turn"]["clarification"])


def test_explicit_quality_choice_changes_goal_without_confirmation_or_model(integration):
    owner, _, root, path, model = setup(integration)
    original = context(integration, owner, root)
    ask(integration, owner, path, "show me insights")
    quality = ask(integration, owner, path, "Check data quality")
    assert quality["answer"]["guidance"]
    assert "The profile found no missing cells" in quality["answer"]["message"]
    assert not model.requests
    assert context(integration, owner, root) == original


def test_source_change_blocks_even_a_deterministic_clarification_choice(integration):
    owner, _, root, path, model = setup(integration)
    ask(integration, owner, path, "analyze my data")
    current = context(integration, owner, root)
    definition = copy.deepcopy(current["definition"])
    assert (
        confirm(integration, owner, root, current, definition, state="needs_review").status_code
        == 201
    )
    reply = ask(integration, owner, path, "Check data quality")
    assert reply["turn"]["kind"] == "ambiguous" and reply["answer"] is None
    assert "changed while clarifying" in reply["turn"]["message"]
    assert not model.requests


def test_misrouted_filtered_calculation_keeps_filter_context_after_measure_choice(integration):
    model = ScriptedModel(
        {"kind": "overview"},
        {
            "kind": "numerical",
            "plan": {
                "metric": "attock_erp",
                "aggregation": "sum",
                "filters": [{"column": "category", "operator": "eq", "value": "Parts"}],
            },
        },
    )
    owner, _, _, path, _ = setup(integration, model)
    first = ask(integration, owner, path, "What is the total attock_erp for category Parts?")
    assert first["turn"]["clarification"]["choices"] == ["attock_erp"]
    result = ask(integration, owner, path, "attock_erp")
    assert result["answer"]["value"] == 5
    assert "category eq" in result["answer"]["lineage"]["filters"][0]
    assert "category Parts" in model.requests[-1].messages[-1].content
