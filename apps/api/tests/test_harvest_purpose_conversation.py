"""Exact Harvest purpose wording retains governed comparison and scope evidence."""

from uuid import UUID

import pytest
from sqlalchemy import select

from execplus.infrastructure.persistence import schema as s
from test_cohort_scope_boundaries import HARVEST_PURPOSE_QUESTION
from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask
from test_studies import prepare
from test_understanding import confirm, context


def setup_harvest(env):
    content = (
        b"Crop_Growth_Stage,Soil_Moisture,Crop_Type\n"
        + b"Harvest,20,Rice\n" * 10
        + b"Growing,30,Rice\n" * 5
        + b"Starting,50,Wheat\n" * 15
    )
    owner, _, wid, _, _, root = prepare(env, content, domain="research")
    current = context(env, owner, root)
    for column in current["definition"]["columns"]:
        if column["name"] == "Soil_Moisture":
            column["unit"] = "sensor units"
            column["currency"] = ""
    confirmed = confirm(env, owner, root, current)
    assert confirmed.status_code == 201, confirmed.text
    model = ScriptedModel(
        {
            "kind": "cohort_comparison",
            "target_column": "Crop_Growth_Stage",
            "target_value": "Harvest",
            "columns": ["Soil_Moisture"],
        }
    )
    env.runtime.intent_router.model = model
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    return owner, root, f"/workspaces/{wid}/threads/{tid}", model


def test_exact_harvest_question_compares_and_reopens_saved_evidence(integration):
    env = integration
    owner, root, path, model = setup_harvest(env)
    before = context(env, owner, root)
    result = ask(env, owner, path, HARVEST_PURPOSE_QUESTION)
    assert result["turn"]["status"] == "complete", result
    answer = result["answer"]
    assert answer["kind"] == "patterns"
    patterns = answer["patterns"]
    assert patterns["coverage"] == dict(
        source_rows=30, filtered_rows=30, target_rows=10, other_rows=20, missing_target_rows=0
    )
    metric = patterns["numeric"][0]
    assert metric["unit"] == "sensor units"
    assert metric["target_mean"] == "20"
    assert metric["other_mean"] == "45"
    assert metric["difference"] == "-25"
    assert patterns["limitations"]
    assert len(model.requests) == 1
    turn_id = result["turn"]["id"]
    with env.engine.connect() as conn:
        evidence = conn.execute(
            select(s.thread_turns.c.evidence).where(s.thread_turns.c.id == UUID(turn_id))
        ).scalar_one()
    assert evidence["patterns"]["result"]["numeric"] == patterns["numeric"]
    reopened = env.client.get(path + f"/turns/{turn_id}/answer", headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json() == {**answer, "model_route": "deterministic:cohort-comparison-v1"}
    assert len(model.requests) == 1  # Reopening replays retained evidence without a new model call.
    assert context(env, owner, root) == before


@pytest.mark.parametrize("restriction", [" in East", " from last 7 days", " excluding Rice"])
def test_exact_harvest_question_never_drops_an_extra_restriction(integration, restriction):
    env = integration
    owner, _, path, model = setup_harvest(env)
    result = ask(env, owner, path, HARVEST_PURPOSE_QUESTION + restriction)
    assert result["answer"] is None, result
    assert result["turn"]["status"] == "complete", result
    assert "adds another condition" in result["turn"]["message"]
    assert result["turn"]["clarification"] == {"choices": []}
    assert len(model.requests) == 1
