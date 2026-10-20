"""Use case: Reproduces saved answers being ignored across chat and analysis tools.

What it does: Checks context reuse, private evidence, remaining questions and forecast handoffs.
"""

import copy
from uuid import uuid4

from test_conversational_explorer import ScriptedModel, prepare
from test_dataset_guidance import ask, setup
from test_forecast_integration import daily
from test_understanding import confirm, context
from test_unified_conversation import document
from test_unified_conversation import setup as knowledge_setup
from test_workspace_integration import accept, identity, invite


def saved(env, owner, root):
    current = context(env, owner, root)
    definition = copy.deepcopy(current["definition"])
    definition["description"] = "Field observations used to compare irrigation conditions."
    definition["grain"] = "record"
    for column in definition["columns"]:
        column["meaning"] = "Reviewed " + column["name"]
        if column["role"] == "metric":
            column["unit"] = "units"
    assert confirm(env, owner, root, current, definition).status_code == 201
    return definition


def test_orientation_uses_saved_description_and_does_not_repeat_row_review(integration):
    owner, _, root, path, _ = setup(integration)
    definition = saved(integration, owner, root)
    result = ask(integration, owner, path, "Help me understand my data")["answer"]
    assert definition["description"] in result["message"]
    assert "Reviewed attock_erp" in result["message"]
    assert "what one row represents still need review" not in result["message"]


def test_missing_only_reading_preserves_existing_answers_without_model(integration):
    env = integration
    owner, _, root, _, model = setup(env)
    definition = saved(env, owner, root)
    current = context(env, owner, root)
    definition["columns"][-1]["unit"] = ""
    assert confirm(env, owner, root, current, definition).status_code == 201
    before = context(env, owner, root)
    reading = env.client.post(root + "/data-brief?review_missing=true", headers=owner).json()
    assert reading["review_mode"] == "missing"
    assert len(reading["columns"]) == 1
    assert reading["columns"][0]["meaning"] == "Reviewed attock_erp_value"
    assert reading["definition"] == before["definition"]
    assert context(env, owner, root) == before
    assert not model.requests
    definition["columns"][-1]["unit"] = "kg"
    assert confirm(env, owner, root, before, definition).status_code == 201
    assert env.client.post(root + "/data-brief?review_missing=true", headers=owner).json()[
        "already_confirmed"
    ]


def test_chat_and_forecast_share_no_date_reason_and_preserve_history(integration):
    env = integration
    owner, wid, root, path, model = setup(env)
    saved(env, owner, root)
    options = env.client.get(root + "/forecasts/options", headers=owner).json()
    assert [item["code"] for item in options["blockers"]] == ["date"]
    result = ask(env, owner, path, "Forecast attock_erp")
    answer = result["answer"]
    assert options["blockers"][0]["message"] in answer["message"]
    assert answer["guidance"]["actions"][0]["tool"] == "patterns"
    assert answer["guidance"]["actions"][1]["scenario_mode"] == "daily_change"
    assert not model.requests
    turn_id = result["turn"]["id"]
    restored = env.client.get(path + f"/turns/{turn_id}/answer", headers=owner)
    assert restored.status_code == 200
    assert restored.json() == answer
    assert env.client.get(path.replace(str(wid), str(uuid4())), headers=owner).status_code == 404


def test_date_forecast_and_other_tools_receive_explicit_measure(integration):
    env = integration
    model = ScriptedModel()
    owner, wid, root = prepare(env, model, content=daily())
    saved(env, owner, root)
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}"
    for question, tool in [
        ("Forecast amount", "forecasts"),
        ("Find anomalies in amount", "anomalies"),
        ("Compare scenarios for amount", "scenarios"),
        ("Set up budget allocation for amount", "allocations"),
    ]:
        answer = ask(env, owner, path, question)["answer"]
        action = answer["guidance"]["actions"][0]
        assert action["tool"] == tool and action["metric"] == "amount"
    assert not model.requests
    assert env.client.get(root + "/forecasts/options", headers=owner).json()["blockers"] == []


def test_owner_goal_and_authorized_notes_reach_planner_without_leaking(integration):
    env = integration
    plan = {"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "sum"}}
    owner, wid, root, path, model = knowledge_setup(env, plan, plan)
    saved(env, owner, root)
    dataset_root = root.split("/uploads/")[0]
    response = env.client.post(
        dataset_root + "/preferences",
        headers=owner,
        json={"domain_hint": "auto", "goal": "Total revenue for the PrivateHarvestPlan"},
    )
    assert response.status_code in {200, 201}, response.text
    document(
        env,
        owner,
        root,
        "Revenue here is the crop sale value. PrivateHarvestNote.",
        f"data-reading-{root.split('/')[-1][:8]}.md",
        False,
    )
    result = ask(env, owner, path, "Analyze my data")
    assert result["answer"]["value"] == "8.050000000000"
    prompt = model.requests[-1].messages[-1].content
    assert "PrivateHarvestPlan" in prompt and "PrivateHarvestNote" in prompt
    assert "Field observations" in prompt
    member, user = identity(env, "context-member@example.test")
    accept(env, member, wid, invite(env, owner, wid, user.email).json()["id"])
    tid = env.client.post(root + "/threads", headers=member).json()["id"]
    ask(env, member, f"/workspaces/{wid}/threads/{tid}", "What is total revenue?")
    prompt = model.requests[-1].messages[-1].content
    assert "PrivateHarvestPlan" not in prompt and "PrivateHarvestNote" not in prompt


def test_other_upload_reading_notes_are_not_used_for_current_planning(integration):
    env = integration
    plan = {"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "sum"}}
    owner, _, root, path, model = knowledge_setup(env, plan)
    saved(env, owner, root)
    document(env, owner, root, "Revenue: OtherUploadSecret.", "data-reading-ffffffff.md", False)
    ask(env, owner, path, "Total revenue")
    assert "OtherUploadSecret" not in model.requests[-1].messages[-1].content


def test_corrupt_reading_context_fails_without_leaking_storage_details(integration, monkeypatch):
    from execplus.domain.ingestion import IngestionError

    env = integration
    owner, _, root, path, model = knowledge_setup(env)
    document(
        env, owner, root, "Revenue notes.", f"data-reading-{root.split('/')[-1][:8]}.md", False
    )

    def fail(_):
        raise IngestionError("source_unavailable", "private-secret-storage", 503)

    monkeypatch.setattr(env.runtime.knowledge.storage, "read_document", fail)
    result = ask(env, owner, path, "Total revenue")
    assert result["answer"] is None
    assert "private-secret-storage" not in str(result)
    assert not model.requests


def test_tool_words_do_not_swallow_ordinary_calculation_or_document_requests():
    from execplus.domain.analysis_guidance import analysis_guidance
    from test_dataset_guidance import description

    for question in [
        "What is the total forecast?",
        "List scenario records",
        "According to the policy, what is the forecast?",
    ]:
        assert analysis_guidance(description(), question) is None


def test_changed_upload_schema_keeps_existing_answers_but_requires_review(integration):
    from test_workspace_integration import upload

    env = integration
    owner, wid, root, _, _ = setup(env)
    saved(env, owner, root)
    did = root.split("/datasets/")[1].split("/")[0]
    response = upload(
        env, owner, wid, did, b"attock_erp,new_measure\n1,2\n", "changed.csv", "text/csv"
    )
    assert response.status_code == 201
    next_root = root.rsplit("/", 1)[0] + "/" + response.json()["id"]
    result = env.client.post(next_root + "/data-brief?review_missing=true", headers=owner)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["state"] == "needs_review" and not body["already_confirmed"]
    columns = {column["name"]: column for column in body["definition"]["columns"]}
    assert set(columns) == {"attock_erp", "new_measure"}
    assert columns["attock_erp"]["meaning"] == "Reviewed attock_erp"


def test_named_measure_without_unit_does_not_fall_back_to_another_measure(integration):
    env = integration
    owner, _, root, path, model = setup(env)
    definition = saved(env, owner, root)
    current = context(env, owner, root)
    definition["columns"][-1]["unit"] = ""
    assert confirm(env, owner, root, current, definition).status_code == 201
    result = ask(env, owner, path, "Find anomalies in attock_erp_value")["answer"]
    action = result["guidance"]["actions"][0]
    assert action["tool"] == "anomalies" and action["metric"] == "attock_erp_value"
    assert not model.requests
