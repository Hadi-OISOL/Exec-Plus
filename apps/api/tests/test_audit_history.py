"""Use case: Makes workspace activity searchable without disclosing private work.

What it does: Verifies SQL-filtered visibility, bounded stable pages and current sharing checks.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, update

from execplus.domain.ingestion import AuditEvent
from execplus.infrastructure.persistence import schema as s
from test_studies import add_member, prepare, run
from test_workspace_integration import identity, workspace


def write_event(env, wid, actor_id, action, resource_type, resource_id=None, created_at=None):
    record = AuditEvent(
        uuid4(),
        UUID(str(wid)),
        actor_id,
        action,
        resource_type,
        resource_id or uuid4(),
        created_at or datetime.now(timezone.utc),
    )
    with env.runtime.service.uow() as repo:
        repo.add(record)
    return record


@pytest.mark.parametrize("role", ["member", "admin"])
def test_audit_history_hides_others_private_ids_including_generic_resource_types(integration, role):
    env = integration
    owner, owner_actor, wid, _, _, _ = prepare(env)
    member, member_actor = add_member(env, owner, wid, role)
    path = f"/workspaces/{wid}/audit-history"
    private = [
        write_event(env, wid, owner_actor.id, action, kind)
        for action, kind in (
            ("job.created", "job"),
            ("conversation.complete", "thread_turn"),
            ("preference.updated", "dataset"),
            ("view.dismissed", "view"),
            ("alert.delivered", "refresh"),
            ("report.sent", "report_delivery"),
            ("forecast.created", "forecast"),
            ("forecast.compared", "forecast_comparison"),
            ("query.executed", "query"),
            ("knowledge.searched", "dataset"),
            ("future.private_action", "future_resource"),
        )
    ]
    own = write_event(env, wid, member_actor.id, "forecast.created", "forecast")
    shared = write_event(env, wid, owner_actor.id, "refresh.activated", "refresh")
    result = env.client.get(path, headers=member)
    assert result.status_code == 200, result.text
    ids = {item["id"] for item in result.json()["events"]}
    assert str(own.id) in ids and str(shared.id) in ids
    assert not ids.intersection(str(item.id) for item in private)
    assert all(str(item.resource_id) not in result.text for item in private)
    assert all(
        set(item)
        == {
            "id",
            "workspace_id",
            "actor_id",
            "action",
            "resource_type",
            "resource_id",
            "created_at",
        }
        for item in result.json()["events"]
    )
    owner_result = env.client.get(path, headers=owner).json()["events"]
    assert {str(item.id) for item in private} <= {item["id"] for item in owner_result}
    legacy = env.client.get(f"/workspaces/{wid}/audit-events", headers=member)
    assert legacy.status_code == (200 if role == "admin" else 403)
    if role == "admin":
        assert all(str(item.resource_id) not in legacy.text for item in private)
    outsider, _ = identity(env, "audit-outsider@example.test")
    assert env.client.get(path, headers=outsider).status_code == 404
    assert env.client.get(path).status_code == 401
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{member_actor.id}", headers=owner).status_code
        == 204
    )
    assert env.client.get(path, headers=member).status_code == 404


def test_audit_history_shared_study_versions_do_not_leak_unrelated_private_studies(integration):
    env = integration
    owner, _, wid, _, _, path = prepare(env)
    member, _ = add_member(env, owner, wid)
    private = run(env, owner, path).json()
    shared = run(env, owner, path).json()
    share_path = f"/workspaces/{wid}/studies/{shared['study']['id']}"
    assert env.client.patch(share_path, headers=owner, json={"shared": True}).status_code == 204
    history = f"/workspaces/{wid}/audit-history"
    visible = env.client.get(history, headers=member, params={"resource_type": "study"})
    assert visible.status_code == 200, visible.text
    resources = {item["resource_id"] for item in visible.json()["events"]}
    assert shared["version"]["id"] in resources
    assert shared["study"]["id"] in resources
    assert private["version"]["id"] not in resources
    assert private["study"]["id"] not in resources
    assert env.client.patch(share_path, headers=owner, json={"shared": False}).status_code == 204
    assert (
        env.client.get(history, headers=member, params={"resource_type": "study"}).json()["events"]
        == []
    )


@pytest.mark.parametrize("kind", ["document", "saved_item", "dashboard"])
def test_audit_history_rechecks_current_shared_resource_visibility(integration, kind):
    env = integration
    owner, _, wid, did, _, source = prepare(env)
    member, _ = add_member(env, owner, wid)
    records = []
    for shared in (False, True):
        if kind == "document":
            response = env.client.post(
                f"/workspaces/{wid}/datasets/{did}/documents",
                headers=owner,
                params={"name": "sensitive-title.txt", "shared": shared},
                content=b"Private source passage that never belongs in the audit history.",
            )
        elif kind == "saved_item":
            response = env.client.post(
                source + "/saved-items",
                headers=owner,
                json={
                    "kind": "question",
                    "name": "sensitive-title",
                    "shared": shared,
                    "payload": {"question": "Sensitive question text must never appear in audit."},
                },
            )
        else:
            response = env.client.post(
                f"/workspaces/{wid}/study-boards",
                headers=owner,
                json={
                    "name": "sensitive-title",
                    "shared": shared,
                    "pins": [],
                },
            )
        assert response.status_code == 201, response.text
        records.append(response.json()["id"])
    path = f"/workspaces/{wid}/audit-history"
    result = env.client.get(path, headers=member, params={"resource_type": kind})
    assert {item["resource_id"] for item in result.json()["events"]} == {records[1]}
    assert "sensitive-title" not in result.text
    assert "Private source passage" not in result.text
    assert "Sensitive question text" not in result.text
    table = {"document": s.documents, "saved_item": s.saved_items, "dashboard": s.study_boards}[
        kind
    ]
    with env.engine.begin() as connection:
        connection.execute(update(table).where(table.c.id == UUID(records[1])).values(shared=False))
    assert (
        env.client.get(path, headers=member, params={"resource_type": kind}).json()["events"] == []
    )


def test_audit_history_stable_sql_pagination_filters_private_before_limit(integration):
    env = integration
    owner, owner_actor, wid, _, _, _ = prepare(env)
    member, actor = add_member(env, owner, wid)
    now = datetime.now(timezone.utc)
    expected = [
        write_event(env, wid, actor.id, "forecast.created", "forecast", created_at=now)
        for _ in range(5)
    ]
    for _ in range(110):
        write_event(
            env,
            wid,
            owner_actor.id,
            "forecast.created",
            "forecast",
            created_at=now + timedelta(seconds=1),
        )
    foreign = workspace(env, member, "Foreign")
    write_event(env, foreign, actor.id, "forecast.created", "forecast", created_at=now)
    captured = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if "FROM audit_events" in statement:
            captured.append(statement)

    event.listen(env.engine, "before_cursor_execute", capture)
    try:
        ids, cursor = [], None
        while True:
            params = {"action": "forecast.created", "limit": 2}
            if cursor:
                params["cursor"] = cursor
            response = env.client.get(
                f"/workspaces/{wid}/audit-history", headers=member, params=params
            )
            assert response.status_code == 200, response.text
            page = response.json()
            assert 1 <= len(page["events"]) <= 2
            ids.extend(item["id"] for item in page["events"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
            assert len(ids) <= 5
    finally:
        event.remove(env.engine, "before_cursor_execute", capture)
    assert ids == [
        str(item.id) for item in sorted(expected, key=lambda value: value.id, reverse=True)
    ]
    assert len(ids) == len(set(ids)) == 5
    assert len(captured) == 3 and all("LIMIT" in statement for statement in captured)


def test_audit_history_metadata_search_date_filters_and_team_visibility(integration):
    env = integration
    owner, actor, wid, _, _, _ = prepare(env)
    member, _ = add_member(env, owner, wid)
    stamp = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    target = write_event(env, wid, actor.id, "forecast.created", "forecast", created_at=stamp)
    other = write_event(
        env, wid, actor.id, "forecast.created", "forecast", created_at=stamp - timedelta(days=1)
    )
    path = f"/workspaces/{wid}/audit-history"
    response = env.client.get(
        path,
        headers=owner,
        params={
            "since": stamp.isoformat(),
            "until": stamp.isoformat(),
            "resource_type": "forecast",
            "q": str(target.resource_id),
        },
    )
    assert [item["id"] for item in response.json()["events"]] == [str(target.id)]
    for query in ("%", "_", "' OR 1=1 --", str(other.id)):
        found = env.client.get(
            path,
            headers=owner,
            params={"q": query, "since": stamp.isoformat(), "until": stamp.isoformat()},
        )
        assert found.status_code == 200 and found.json()["events"] == []
    own_team = env.client.get(path, headers=owner, params={"resource_type": "invitation"})
    assert own_team.json()["events"]
    visible_team = env.client.get(path, headers=member, params={"action": "invitation.created"})
    assert visible_team.json()["events"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"q": "x" * 81},
        {"q": "unsafe\nfilter"},
        {"cursor": "!invalid"},
        {"cursor": "bnVsbA"},
        {"since": "2026-01-01T00:00:00"},
        {"since": "2026-02-01T00:00:00Z", "until": "2026-01-01T00:00:00Z"},
    ],
)
def test_audit_history_rejects_malformed_or_unbounded_filters(integration, params):
    env = integration
    owner, _ = identity(env, "audit-validation@example.test")
    wid = workspace(env, owner)
    result = env.client.get(f"/workspaces/{wid}/audit-history", headers=owner, params=params)
    assert result.status_code == 422, result.text
