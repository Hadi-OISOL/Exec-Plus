"""Use case: Verifies product-report privacy and historical semantics on real PostgreSQL.

What it does: Checks scoped aggregates, human cohorts, revocation and compatible optimized paths.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import event, insert, select, update

from execplus.application.services import product_usage
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.reporting import SQLReportingRepository
from test_workspace_integration import accept, identity, invite, workspace

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz else NOW.replace(tzinfo=None)


def activity(env, wid, actor, action, when, count=1):
    with env.engine.begin() as connection:
        connection.execute(
            insert(s.audit_events),
            [
                dict(
                    id=uuid4(),
                    workspace_id=UUID(wid),
                    actor_id=actor.id,
                    action=action,
                    resource_type="fixture",
                    resource_id=uuid4(),
                    created_at=when,
                )
                for _ in range(count)
            ],
        )


def member(env, owner, wid, email):
    headers, actor = identity(env, email)
    invitation = invite(env, owner, wid, email).json()
    assert accept(env, headers, wid, invitation["id"]).status_code == 200
    return headers, actor


def report(env, owner, wid, monkeypatch, weeks=5):
    monkeypatch.setattr(product_usage, "datetime", FixedClock)
    response = env.client.get(f"/workspaces/{wid}/product-usage?weeks={weeks}", headers=owner)
    assert response.status_code == 200, response.text
    return response.json()


def test_usage_retention_has_true_first_cohorts_maturity_and_no_private_identities(
    integration, monkeypatch
):
    env = integration
    owner, owner_actor = identity(env, "usage-owner@example.test")
    wid = workspace(env, owner, seats=5)
    _, alice = member(env, owner, wid, "usage-alice@example.test")
    _, bob = member(env, owner, wid, "usage-bob@example.test")
    _, removed = member(env, owner, wid, "usage-removed@example.test")
    _, never = member(env, owner, wid, "usage-never@example.test")
    activity(env, wid, owner_actor, "upload.stored", datetime(2026, 8, 10, tzinfo=timezone.utc))
    activity(env, wid, alice, "job.submitted", datetime(2026, 9, 7, tzinfo=timezone.utc), 3)
    activity(env, wid, alice, "study.created", datetime(2026, 9, 14, tzinfo=timezone.utc))
    activity(env, wid, alice, "job.submitted", datetime(2026, 10, 5, tzinfo=timezone.utc))
    activity(env, wid, bob, "study.created", datetime(2026, 9, 14, tzinfo=timezone.utc))
    activity(env, wid, bob, "forecast.created", datetime(2026, 9, 28, tzinfo=timezone.utc))
    activity(env, wid, removed, "dashboard.opened", datetime(2026, 9, 21, tzinfo=timezone.utc))
    for action in [
        "query.executed",
        "refresh.activated",
        "job.completed",
        "staff.workspace_viewed",
    ]:
        activity(env, wid, never, action, NOW - timedelta(days=1))
    activity(env, wid, never, "job.submitted", NOW + timedelta(days=1))
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{removed.id}", headers=owner).status_code
        == 204
    )
    value = report(env, owner, wid, monkeypatch)
    assert value["summary"] == dict(
        active_users=3,
        active_members=2,
        current_members=4,
        activated_members=2,
        never_active_members=1,
        inactive_14d_members=1,
    )
    assert [item["cohort_week"] for item in value["cohorts"]] == [
        "2026-09-07",
        "2026-09-14",
        "2026-09-21",
    ]
    assert value["cohorts"][0]["cells"][1]["retained"] == 1
    assert value["cohorts"][0]["cells"][2]["retained"] == 0
    assert value["cohorts"][0]["cells"][4]["retained"] is None
    assert value["weekly"][0]["active_users"] == 1
    assert value["weekly"][0]["actions"] == 3
    assert value["usage"]["queries_completed"] == 1
    assert value["usage"]["forecasts_created"] == 1
    rendered = str(value)
    for actor in [owner_actor, alice, bob, removed, never]:
        assert str(actor.id) not in rendered and actor.email not in rendered
    assert "staff.workspace_viewed" not in rendered


def test_product_usage_scopes_managers_and_rechecks_revocation(integration, monkeypatch):
    env = integration
    owner, _ = identity(env, "usage-roles-owner@example.test")
    wid = workspace(env, owner)
    headers, actor = member(env, owner, wid, "usage-roles-member@example.test")
    outsider, other = identity(env, "usage-other@example.test")
    other_wid = workspace(env, outsider)
    activity(env, other_wid, other, "job.submitted", NOW - timedelta(days=1), 5)
    value = report(env, owner, wid, monkeypatch)
    assert value["summary"]["active_users"] == 0
    path = f"/workspaces/{wid}/product-usage"
    assert env.client.get(path, headers=headers).status_code == 403
    assert env.client.get(path, headers=outsider).status_code == 404
    assert env.client.get(path).status_code == 401
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{actor.id}", headers=owner).status_code == 204
    )
    assert env.client.get(path, headers=headers).status_code == 404
    for invalid in ["0", "13", "abc", "1.5"]:
        assert env.client.get(path + "?weeks=" + invalid, headers=owner).status_code == 422


def test_support_and_background_activity_do_not_create_product_retention(integration, monkeypatch):
    env = integration
    owner, actor = identity(env, "usage-background@example.test")
    wid = workspace(env, owner)
    for weeks in [1, 2, 3]:
        for action in [
            "support.created",
            "support.replied",
            "query.executed",
            "observation.complete",
            "report.delivered",
            "job.claimed",
            "job.complete",
        ]:
            activity(env, wid, actor, action, NOW - timedelta(weeks=weeks))
    value = report(env, owner, wid, monkeypatch)
    assert value["summary"]["active_users"] == 0
    assert value["cohorts"] == []
    assert value["usage"]["queries_completed"] == 3
    assert value["summary"]["never_active_members"] == 1


def test_product_reports_and_onboarding_do_not_load_raw_history_or_source_values(
    integration, monkeypatch
):
    env = integration
    owner, actor = identity(env, "usage-aggregate@example.test")
    wid = workspace(env, owner)
    activity(env, wid, actor, "job.submitted", NOW - timedelta(days=1), 250)
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(env.engine, "before_cursor_execute", capture)
    try:
        value = report(env, owner, wid, monkeypatch)
        onboarding = env.client.get(f"/workspaces/{wid}/onboarding", headers=owner)
        assert onboarding.status_code == 200
    finally:
        event.remove(env.engine, "before_cursor_execute", capture)
    assert value["features"][0]["actions"] == 250
    assert len(statements) < 25
    assert not any("audit_events.id," in statement for statement in statements)
    assert not any("usage_events.id," in statement for statement in statements)
    assert not any("uploads.storage_key" in statement for statement in statements)


def test_legacy_onboarding_retains_historical_upload_and_returning_user_semantics(integration):
    env = integration
    owner, actor = identity(env, "usage-legacy@example.test")
    wid = workspace(env, owner)
    headers, _ = member(env, owner, wid, "usage-legacy-member@example.test")
    with env.engine.begin() as connection:
        connection.execute(
            insert(s.usage_events).values(
                id=uuid4(),
                workspace_id=UUID(wid),
                actor_id=actor.id,
                kind="upload",
                quantity=1,
                resource_id=uuid4(),
                created_at=NOW,
            )
        )
    activity(env, wid, actor, "query.executed", NOW - timedelta(weeks=2))
    activity(env, wid, actor, "query.executed", NOW - timedelta(weeks=1))
    for access in [owner, headers]:
        value = env.client.get(f"/workspaces/{wid}/onboarding", headers=access).json()
        assert {row["id"]: row["complete"] for row in value["checklist"]}["upload"]
        assert value["usage"] == {} and value["returning_users"] is None
    legacy = env.client.get(f"/workspaces/{wid}/usage-analytics", headers=owner).json()
    assert legacy["usage"]["upload"] == 1
    assert legacy["returning_users"] == 1
    assert (
        legacy["retention_definition"]
        == "An actor with activity in at least two ISO calendar weeks."
    )
    assert env.client.get(f"/workspaces/{wid}/usage", headers=owner).json()["events"]


def test_upload_storage_quantities_are_windowed_and_do_not_sum_seat_limit_snapshots(
    integration, monkeypatch
):
    env = integration
    owner, actor = identity(env, "usage-meter@example.test")
    wid = workspace(env, owner)
    with env.engine.begin() as connection:
        for kind, quantity, when in [
            ("storage_bytes", 100, NOW - timedelta(days=1)),
            ("upload", 1, NOW - timedelta(days=1)),
            ("storage_bytes", 500, NOW - timedelta(weeks=20)),
            ("storage_bytes", 200, NOW + timedelta(days=1)),
            ("seat_limit", 50, NOW - timedelta(days=1)),
        ]:
            connection.execute(
                insert(s.usage_events).values(
                    id=uuid4(),
                    workspace_id=UUID(wid),
                    actor_id=actor.id,
                    kind=kind,
                    quantity=quantity,
                    resource_id=uuid4(),
                    created_at=when,
                )
            )
    value = report(env, owner, wid, monkeypatch)
    assert value["usage"]["storage_bytes"] == 100
    assert value["usage"]["uploads"] == 1
    assert "seat_limit" not in value["usage"]
    with env.engine.connect() as connection:
        assert connection.execute(select(s.usage_events.c.id)).first()


def test_staff_aggregate_access_is_audited_revocable_and_does_not_grant_data_access(
    integration, monkeypatch
):
    env = integration
    owner, _ = identity(env, "usage-staff-owner@example.test")
    wid = workspace(env, owner)
    staff_headers, staff_actor = identity(env, "usage-staff@example.test")
    path = f"/admin/workspaces/{wid}/product-usage"
    assert env.client.get(path, headers=owner).status_code == 403
    env.runtime.operations.change_staff(staff_actor.email, "support")
    assert env.client.get(path, headers=staff_headers).status_code == 403
    env.runtime.operations.change_staff(staff_actor.email, "admin")
    monkeypatch.setattr(product_usage, "datetime", FixedClock)
    response = env.client.get(path, headers=staff_headers)
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["current_members"] == 1
    assert env.client.get(f"/workspaces/{wid}/datasets", headers=staff_headers).status_code == 404
    with env.engine.connect() as connection:
        actions = (
            connection.execute(
                select(s.staff_audit.c.outcome).where(
                    s.staff_audit.c.actor_id == staff_actor.id,
                    s.staff_audit.c.action == "admin.product_usage",
                )
            )
            .scalars()
            .all()
        )
    assert sorted(actions) == ["denied", "success"]
    env.runtime.operations.change_staff(staff_actor.email, None)
    assert env.client.get(path, headers=staff_headers).status_code == 403


def test_reporting_rechecks_manager_role_after_computation(integration, monkeypatch):
    env = integration
    owner, _ = identity(env, "usage-recheck-owner@example.test")
    wid = workspace(env, owner)
    admin, actor = identity(env, "usage-recheck-admin@example.test")
    invitation = invite(env, owner, wid, actor.email, "admin").json()
    assert accept(env, admin, wid, invitation["id"]).status_code == 200
    original = SQLReportingRepository.product_usage_facts

    def revoke(repo, *args):
        value = original(repo, *args)
        with env.engine.begin() as connection:
            connection.execute(
                update(s.memberships)
                .where(
                    s.memberships.c.workspace_id == UUID(wid),
                    s.memberships.c.user_id == actor.id,
                )
                .values(role="member")
            )
        return value

    monkeypatch.setattr(SQLReportingRepository, "product_usage_facts", revoke)
    assert env.client.get(f"/workspaces/{wid}/product-usage", headers=admin).status_code == 403
