"""Use case: Verifies the follow-up questions asked after any upload and how the answers are used.

What it does: Uploads fictional sales and city files, checks the questions are shaped by each
file's own columns, validates and privately saves answers, and shows they lead the suggested
questions, rebuild the dashboard around the chosen group and time view, reorder the analysts'
measures and reach the chat planner only as column names (never free text, filters or numbers).
"""

import json
from uuid import UUID, uuid4

from sqlalchemy import select

from execplus.application.services import auto_dashboards as service_module
from execplus.application.services.auto_dashboards import FOCUS_ROUTE
from execplus.domain.discovery import measure_candidates
from execplus.infrastructure.persistence import schema as s
from test_auto_dashboards import sales_csv
from test_auto_dashboards_integration import own_root
from test_dataset_guidance import ask
from test_unified_conversation import setup
from test_workspace_integration import accept, identity, invite, workspace


def focus_path(root):
    wid, uid = root.split("/")[2], root.split("/uploads/")[1]
    return f"/workspaces/{wid}/uploads/{uid}/dataset-focus"


def purpose(env, headers, root):
    wid, uid = root.split("/")[2], root.split("/uploads/")[1]
    response = env.client.get(f"/workspaces/{wid}/uploads/{uid}/dataset-purpose", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def sales(env):
    service_module._CACHE.clear()
    owner, user = identity(env, f"focus-{uuid4().hex[:8]}@example.test")
    wid = workspace(env, owner)
    return owner, user, wid, own_root(env, owner, wid, sales_csv().encode(), "sales.csv")


def test_questions_follow_the_file_and_answers_are_validated_and_private(integration):
    env = integration
    owner, _, wid, root = sales(env)
    follow = purpose(env, owner, root)["follow_up"]
    assert follow["version"] == "dataset-focus-v1" and follow["status"] == "pending"
    asked = {item["id"]: item for item in follow["questions"]}
    assert list(asked) == ["measure", "segment", "time", "decision", "relation"]
    assert {"amount", "quantity"} <= set(asked["measure"]["options"])
    assert {"region", "product"} <= set(asked["segment"]["options"])
    assert "customer_email" not in json.dumps(follow)
    assert asked["time"]["options"][2] == "Month by month"
    path = focus_path(root)
    for body in (
        {"answers": {"measure": "customer_email"}, "status": "completed"},
        {"answers": {"colour": "blue"}, "status": "completed"},
        {"answers": {"measure": "amount"}, "status": "maybe"},
        {"answers": {"decision": "x" * 121}, "status": "completed"},
    ):
        response = env.client.put(path, headers=owner, json=body)
        assert response.status_code == 422, response.text
    answers = {
        "measure": "quantity",
        "segment": "product",
        "time": "Week by week",
        "decision": "PrivateDecisionText",
    }
    saved = env.client.put(path, headers=owner, json={"answers": answers, "status": "completed"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["answers"] == answers and saved.json()["status"] == "completed"
    body = purpose(env, owner, root)
    assert body["follow_up"]["answers"] == answers
    assert body["suggested_questions"][0] == {
        "title": "Which product leads on quantity",
        "question": "Which product has the highest total quantity?",
    }
    member, member_user = identity(env, f"focus-member-{uuid4().hex[:8]}@example.test")
    accept(env, member, wid, invite(env, owner, wid, member_user.email).json()["id"])
    other = purpose(env, member, root)
    assert other["follow_up"]["answers"] == {}
    assert other["suggested_questions"][0]["question"] != body["suggested_questions"][0]["question"]
    skipped = env.client.put(path, headers=member, json={"answers": {}, "status": "skipped"})
    assert skipped.json()["status"] == "skipped"
    assert purpose(env, owner, root)["follow_up"]["answers"] == answers
    outsider, _ = identity(env, f"focus-outsider-{uuid4().hex[:8]}@example.test")
    assert env.client.put(
        path, headers=outsider, json={"answers": answers, "status": "completed"}
    ).status_code in {403, 404}


def test_answers_rebuild_the_dashboard_and_lead_the_analysts(integration):
    env = integration
    owner, user, _, root = sales(env)
    before = env.client.get(root + "/auto-dashboard", headers=owner).json()["dashboard"]
    assert "focus" not in before and before["selection"]["route"] != FOCUS_ROUTE
    again = env.client.get(root + "/auto-dashboard", headers=owner).json()["dashboard"]
    assert again["number"] == before["number"]
    answers = {"measure": "quantity", "segment": "product", "time": "Week by week"}
    env.client.put(
        focus_path(root), headers=owner, json={"answers": answers, "status": "completed"}
    )
    after = env.client.get(root + "/auto-dashboard", headers=owner).json()["dashboard"]
    assert after["number"] == before["number"] + 1
    assert after["selection"]["route"] == FOCUS_ROUTE
    assert len(after["focus"]) == 16 and "product" not in after["focus"]
    ids = [tile["id"] for tile in after["tiles"]]
    assert ids[0].startswith("volume:order_date:week")
    categories = [item for item in ids if item.startswith("category:")]
    assert categories[0] == "category:product"
    wid, did, uid = (UUID(root.split("/")[index]) for index in (2, 4, 6))
    context = env.runtime.analytics.describe(user, wid, did, uid)
    assert measure_candidates(context)[0] == "quantity"


def test_planner_gets_only_chosen_column_names_never_free_text_or_filters(integration):
    env = integration
    plan = {"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "sum"}}
    owner, _, root, path, model = setup(env, plan)
    follow = purpose(env, owner, root)["follow_up"]
    asked = {item["id"]: item for item in follow["questions"]}
    answers = {
        "measure": "revenue",
        "segment": asked["segment"]["options"][0],
        "decision": "PrivateDecisionText only Karachi 999999",
    }
    saved = env.client.put(
        focus_path(root), headers=owner, json={"answers": answers, "status": "completed"}
    )
    assert saved.status_code == 200, saved.text
    result = ask(env, owner, path, "Total revenue")
    assert result["answer"]["value"] == "8.050000000000"
    sent = str(model.requests[-1])
    assert "Columns and time view this user chose" in sent and '"measure": "revenue"' in sent
    assert "PrivateDecisionText" not in sent and "999999" not in sent
    with env.engine.connect() as connection:
        query = connection.execute(select(s.query_executions)).mappings().all()[-1]
    assert query["filters"] == []
