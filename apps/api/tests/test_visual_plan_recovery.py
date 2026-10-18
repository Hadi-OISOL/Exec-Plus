"""A chart presentation request can recover from a mistaken structural tool choice."""

from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask
from test_studies import prepare


def test_stage_rainfall_chart_repairs_structural_proposal(integration):
    env = integration
    content = b"Crop_Growth_Stage,Rainfall_mm\nHarvest,20\nHarvest,40\nFlowering,10\nFlowering,30\n"
    owner, _, wid, _, _, root = prepare(env, content, domain="research")
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    model = ScriptedModel(
        {"kind": "diagram", "columns": ["Crop_Growth_Stage", "Rainfall_mm"]},
        {
            "kind": "numerical",
            "plan": {
                "metric": "Rainfall_mm",
                "aggregation": "avg",
                "group_by": ["Crop_Growth_Stage"],
                "filters": [],
            },
        },
    )
    env.runtime.intent_router.model = model
    result = ask(
        env,
        owner,
        f"/workspaces/{wid}/threads/{tid}",
        "can you draw me a diagram of how crop growth is related to rainfall",
    )
    assert result["answer"] is not None, result
    assert result["turn"]["query_id"] is not None
    assert len(model.requests) == 2
    assert "maps field membership only" in model.requests[1].messages[-1].content


def test_outcome_column_choice_does_not_silently_choose_a_stage(integration):
    env = integration
    content = (
        b"stage_type,stage,reading\nRice,Ready,20\nWheat,Ready,40\n"
        b"Rice,Growing,10\nWheat,Growing,30\n"
    )
    owner, _, wid, _, _, root = prepare(env, content, domain="research")
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    env.runtime.intent_router.context_enabled = True
    model = ScriptedModel(
        {
            "kind": "ambiguous",
            "message": "Which field describes the outcome?",
            "options": ["stage", "reading"],
        },
        {
            "kind": "cohort_comparison",
            "target_column": "stage",
            "target_value": "Ready",
            "columns": ["reading"],
        },
    )
    env.runtime.intent_router.model = model
    path = f"/workspaces/{wid}/threads/{tid}"
    first = ask(env, owner, path, "Which factor affects the outcome most?")
    assert first["turn"]["kind"] == "ambiguous"
    second = ask(env, owner, path, "stage")
    assert second["answer"] is None
    assert "Which recorded value" in second["turn"]["message"]
    assert second["turn"]["query_id"] is None
    assert set(second["turn"]["clarification"]["choices"]) == {"Ready", "Growing"}
