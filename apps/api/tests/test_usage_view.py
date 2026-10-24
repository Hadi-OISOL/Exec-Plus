"""Use case: Verifies the owner Usage view and staff usage ranking for feature 14.

What it does: Checks exact daily counts from stored admissions/uploads, near and
reached notices, and owner/admin/staff/member permission boundaries.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from execplus.application.services.plans import admit
from execplus.domain.plans import DEMO, usage_notices, usage_state
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from test_studies import add_member, prepare
from test_workspace_integration import identity, workspace


def operator(env):
    headers, staff = identity(env, f"usage-staff-{uuid4().hex}@example.test")
    env.runtime.operations.change_staff(
        staff.email, "admin", confirmed_user_id=staff.id, identity_checked=True
    )
    return headers, staff


def assign(env, staff, wid, **limits):
    key = "usage-" + uuid4().hex[:12]
    env.runtime.plans.configure(staff, key, "Synthetic usage allowance", {**DEMO, **limits}, 0)
    before = env.runtime.plans.assigned(staff, UUID(wid))
    start = datetime.now(timezone.utc) - timedelta(days=10)
    env.runtime.plans.assign(
        staff, UUID(wid), key, before["version"] if before else 0, start, start + timedelta(days=30)
    )


def consume(env, actor, wid, kind, count):
    for _ in range(count):
        with SQLUnitOfWork(env.engine)() as repo:
            assert admit(repo, actor, UUID(wid), kind, uuid4(), {"synthetic": kind})


def test_usage_state_thresholds_and_notices_name_what_still_works():
    assert [usage_state(u, 10) for u in (0, 7, 8, 9, 10, 12)] == [
        "ok",
        "ok",
        "near",
        "near",
        "reached",
        "reached",
    ]
    assert usage_state(5, None) == "ok" and usage_state(None, 5) == "ok"
    assert usage_state(0, 0) == "reached"
    notices = usage_notices(
        {
            "exports": {"used": 4, "limit": 5},
            "forecasts": {"used": 2, "limit": 2},
            "processing": {"used": 1, "limit": 100},
            "file_bytes": {"used": 0, "limit": 0},
        }
    )
    assert [(n["kind"], n["state"]) for n in notices] == [
        ("exports", "near"),
        ("forecasts", "reached"),
    ]
    assert "4 of 5 exports" in notices[0]["message"]
    assert "still open" in notices[1]["message"]


def test_usage_view_counts_exact_daily_history_and_flags_limits(integration):
    env = integration
    headers, actor, wid, _, _, _ = prepare(env)
    _, staff = operator(env)
    assign(env, staff, wid, exports=5, forecasts=2, processing=1000)
    consume(env, actor, wid, "exports", 4)
    consume(env, actor, wid, "forecasts", 2)
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    old = datetime.now(timezone.utc) - timedelta(days=40)
    with env.engine.begin() as connection:
        for when, kind in (
            (three_days_ago, "processing"),
            (three_days_ago, "processing"),
            (old, "exports"),
        ):
            connection.execute(
                s.plan_admissions.insert().values(
                    workspace_id=UUID(wid),
                    actor_id=actor.id,
                    kind=kind,
                    request_id=uuid4(),
                    input_hash="0" * 64,
                    assignment_id=None,
                    quantity=1,
                    created_at=when,
                )
            )
    response = env.client.get(f"/workspaces/{wid}/usage", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["allowances"]["exports"] == {
        "limit": 5,
        "used": 4,
        "remaining": 1,
        "basis": "period_operations",
        "state": "near",
    }
    assert body["allowances"]["forecasts"]["state"] == "reached"
    assert body["allowances"]["processing"]["used"] == 2
    assert body["allowances"]["datasets"]["used"] == 1
    assert [(n["kind"], n["state"]) for n in body["notices"]] == [
        ("exports", "near"),
        ("forecasts", "reached"),
    ]
    today = datetime.now(timezone.utc).date().isoformat()
    earlier = three_days_ago.date().isoformat()
    rows = {(row["day"], row["kind"]): row["count"] for row in body["daily"]["rows"]}
    assert rows == {
        (today, "exports"): 4,
        (today, "forecasts"): 2,
        (today, "uploads"): 1,
        (earlier, "processing"): 2,
    }
    assert body["daily"]["to"] == today
    assert body["daily"]["kinds"] == [
        "exports",
        "forecasts",
        "model_attempts",
        "processing",
        "uploads",
    ]
    with env.engine.connect() as connection:
        assert "synthetic" not in repr(list(connection.execute(select(s.plan_admissions))))


def test_usage_view_permissions_and_staff_ranking(integration):
    env = integration
    headers, actor, wid, _, _, _ = prepare(env)
    staff_headers, staff = operator(env)
    assign(env, staff, wid, exports=2)
    consume(env, actor, wid, "exports", 2)
    admin, _ = add_member(env, headers, wid, "admin")
    member, _ = add_member(env, headers, wid)
    assert env.client.get(f"/workspaces/{wid}/usage", headers=admin).status_code == 200
    assert env.client.get(f"/workspaces/{wid}/usage", headers=member).status_code == 403
    outsider, _ = identity(env, f"usage-outsider-{uuid4().hex}@example.test")
    assert env.client.get(f"/workspaces/{wid}/usage", headers=outsider).status_code == 404
    assert env.client.get("/admin/usage/workspaces", headers=headers).status_code == 403

    quiet = workspace(env, headers, "Quiet usage workspace")
    assign(env, staff, quiet, exports=100)
    consume(env, actor, quiet, "exports", 1)
    viewed = env.client.get(f"/workspaces/{wid}/usage", headers=staff_headers)
    assert viewed.status_code == 200, viewed.text
    assert viewed.json()["allowances"]["exports"]["used"] == 2
    listed = env.client.get("/admin/usage/workspaces?limit=200", headers=staff_headers)
    assert listed.status_code == 200, listed.text
    ranked = [row for row in listed.json()["workspaces"] if row["workspace_id"] in {wid, quiet}]
    assert [row["workspace_id"] for row in ranked] == [wid, quiet]
    assert ranked[0]["highest"] == "exports" and ranked[0]["highest_percent"] == 100
    assert ranked[0]["operations"]["exports"] == {"used": 2, "limit": 2, "state": "reached"}
    assert ranked[1]["highest_percent"] == 1
    with env.engine.connect() as connection:
        actions = set(
            connection.execute(
                select(s.staff_audit.c.action).where(s.staff_audit.c.actor_id == staff.id)
            ).scalars()
        )
    assert {"plan.usage_viewed", "plan.usage_listed"} <= actions
