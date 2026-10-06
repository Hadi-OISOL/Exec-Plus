"""Use case: Verifies staff access and private support workflows against real persistence.

What it does: Covers tenant boundaries, safe metadata, revocation, transitions and races.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from execplus.infrastructure.persistence import schema as s
from test_studies import add_member
from test_workspace_integration import dataset, identity, upload, workspace


def setup(env):
    owner, actor = identity(env, f"support-owner-{uuid4().hex}@example.test")
    wid = workspace(env, owner)
    staff, support = identity(env, f"support-agent-{uuid4().hex}@example.test")
    env.runtime.operations.change_staff(support.email, "support")
    admin, administrator = identity(env, f"platform-admin-{uuid4().hex}@example.test")
    env.runtime.operations.change_staff(administrator.email, "admin")
    return owner, actor, wid, staff, support, admin, administrator


def create(env, headers, wid, **changes):
    return env.client.post(
        f"/workspaces/{wid}/support-tickets",
        headers=headers,
        json={
            "subject": "Need help with a forecast",
            "description": "Intentionally shared support description, no source attachment.",
            "feature": "forecast",
            "category": "question",
            **changes,
        },
    )


def test_staff_grants_are_separate_revocable_and_do_not_grant_customer_data(integration):
    env = integration
    owner, _actor, wid, staff, _support, admin, administrator = setup(env)
    assert env.client.get("/admin/access", headers=owner).json() == {"role": None}
    assert env.client.get("/admin/workspaces", headers=owner).status_code == 403
    assert env.client.get("/admin/workspaces", headers=staff).status_code == 403
    did = dataset(env, owner, wid)
    assert upload(env, owner, wid, did, b"city,amount\nROW_SENTINEL,1\n").status_code == 201
    response = env.client.get(f"/admin/workspaces/{wid}", headers=admin)
    assert response.status_code == 200
    value = response.json()
    assert value["active_seats"] == 1 and value["uploads"] == 1 and value["datasets"] == 1
    assert value["plan"] == {"id": "private_demo", "billing": "unconfigured"}
    assert "ROW_SENTINEL" not in response.text
    assert set(value) == {
        "id",
        "name",
        "created_at",
        "seat_limit",
        "active_seats",
        "uploads",
        "storage_bytes",
        "owners",
        "datasets",
        "documents",
        "forecasts",
        "jobs",
        "support",
        "plan",
    }
    for headers in (staff, admin):
        assert env.client.get(f"/workspaces/{wid}/datasets", headers=headers).status_code == 404
    env.runtime.operations.change_staff(administrator.email, None)
    assert env.client.get("/admin/access", headers=admin).json() == {"role": None}
    assert env.client.get(f"/admin/workspaces/{wid}", headers=admin).status_code == 403
    env.runtime.operations.change_staff(administrator.email, "admin")
    assert env.client.get("/admin/access", headers=admin).json() == {"role": "admin"}
    with env.engine.connect() as connection:
        events = connection.execute(select(s.staff_audit)).mappings().all()
    assert any(
        event["origin"] == "operator_cli" and event["action"] == "staff.revoked" for event in events
    )
    assert any(
        event["action"] == "admin.workspace_opened"
        and event["outcome"] == "success"
        and event["workspace_id"] == UUID(wid)
        for event in events
    )
    assert any(
        event["outcome"] == "denied" and event["actor_id"] == administrator.id for event in events
    )
    assert "ROW_SENTINEL" not in json.dumps([dict(row) for row in events], default=str)


def test_support_complete_lifecycle_retains_versions_replies_and_resolution(integration):
    env = integration
    owner, _, wid, staff, support, _, _ = setup(env)
    response = create(env, owner, wid)
    assert response.status_code == 201, response.text
    value = response.json()
    tid = value["ticket"]["id"]
    user_path = f"/workspaces/{wid}/support-tickets/{tid}"
    path = "/admin" + user_path
    assert value["ticket"]["version"] == 1 and value["events"][0]["kind"] == "created"
    first_event = value["events"][0]
    assert env.client.get(path, headers=staff).status_code == 200
    version = 1
    for status in ("triaged", "in_progress", "waiting_on_customer", "escalated"):
        response = env.client.patch(
            path,
            headers=staff,
            json={
                "expected_version": version,
                "status": status,
                "priority": "high",
                "assignee_id": str(support.id),
            },
        )
        assert response.status_code == 200, response.text
        version = response.json()["ticket"]["version"]
        assert response.json()["ticket"]["status"] == status
    response = env.client.post(
        user_path + "/messages",
        headers=owner,
        json={"expected_version": version, "body": "Here is the requested clarification."},
    )
    assert response.status_code == 201
    version += 1
    response = env.client.post(
        path + "/messages",
        headers=staff,
        json={"expected_version": version, "body": "Please review the coverage dates."},
    )
    assert response.status_code == 201 and response.json()["events"][-1]["actor_role"] == "staff"
    version += 1
    response = env.client.patch(
        path,
        headers=staff,
        json={
            "expected_version": version,
            "status": "resolved",
            "body": "The declared coverage resolves the question.",
        },
    )
    assert response.status_code == 200 and response.json()["ticket"]["resolved_at"]
    version += 1
    assert (
        env.client.post(
            path + "/messages",
            headers=staff,
            json={"expected_version": version, "body": "Not without reopening"},
        ).status_code
        == 409
    )
    assert (
        env.client.patch(
            path, headers=staff, json={"expected_version": version, "status": "open"}
        ).status_code
        == 409
    )
    response = env.client.post(
        user_path + "/reopen",
        headers=owner,
        json={"expected_version": version, "body": "A follow-up remains."},
    )
    assert response.status_code == 200
    value = response.json()
    assert value["ticket"]["status"] == "open" and value["ticket"]["resolved_at"] is None
    assert value["events"][0] == first_event
    assert [event["sequence"] for event in value["events"]] == list(range(1, version + 2))
    assert (
        env.client.post(
            user_path + "/reopen", headers=owner, json={"expected_version": version + 1}
        ).status_code
        == 409
    )
    assert env.client.get(user_path, headers=owner).json() == value


def test_other_members_including_owner_cannot_read_or_mutate_private_tickets(integration):
    env = integration
    owner, _, wid, staff, support, admin, _ = setup(env)
    member, actor = add_member(env, owner, wid)
    value = create(env, member, wid, description="PRIVATE_REQUEST_SENTINEL").json()
    tid = value["ticket"]["id"]
    path = f"/workspaces/{wid}/support-tickets/{tid}"
    assert (
        env.client.get(f"/workspaces/{wid}/support-tickets", headers=owner).json()["tickets"] == []
    )
    for method, suffix, body in (
        ("GET", "", None),
        ("POST", "/messages", {"expected_version": 1, "body": "no"}),
        ("POST", "/reopen", {"expected_version": 1}),
    ):
        assert (
            env.client.request(method, path + suffix, headers=owner, json=body).status_code == 404
        )
    assert (
        env.client.patch(
            path, headers=member, json={"expected_version": 1, "status": "resolved"}
        ).status_code
        == 405
    )
    other_wid = workspace(env, owner, name="Other workspace")
    assert env.client.get("/admin" + path.replace(wid, other_wid), headers=staff).status_code == 404
    for headers in (staff, admin):
        assert env.client.get("/admin" + path, headers=headers).status_code == 200
    assert (
        "PRIVATE_REQUEST_SENTINEL"
        not in env.client.get(f"/workspaces/{wid}/audit-history", headers=owner).text
    )
    env.runtime.operations.change_staff(support.email, None)
    assert env.client.get("/admin" + path, headers=staff).status_code == 403
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{actor.id}", headers=owner).status_code == 204
    )
    assert env.client.get(path, headers=member).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"subject": ""},
        {"subject": "x" * 121},
        {"description": "x" * 4001},
        {"feature": "arbitrary"},
        {"category": "arbitrary"},
        {"description": "\x00"},
        {"status": "resolved"},
        {"requester_id": str(uuid4())},
    ],
)
def test_support_creation_rejects_unbounded_or_privileged_fields(integration, changes):
    env = integration
    owner, _, wid, *_ = setup(env)
    assert create(env, owner, wid, **changes).status_code == 422
    assert (
        env.client.get(f"/workspaces/{wid}/support-tickets", headers=owner).json()["tickets"] == []
    )


def test_support_concurrent_updates_have_one_winner_and_no_lost_reply(integration):
    env = integration
    owner, _, wid, staff, *_ = setup(env)
    value = create(env, owner, wid).json()
    path = f"/admin/workspaces/{wid}/support-tickets/{value['ticket']['id']}/messages"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda body: env.client.post(
                    path, headers=staff, json={"expected_version": 1, "body": body}
                ),
                ["First response", "Second response"],
            )
        )
    assert sorted(response.status_code for response in responses) == [201, 409]
    current = env.client.get(path.removesuffix("/messages"), headers=staff).json()
    assert current["ticket"]["version"] == 2 and len(current["events"]) == 2
    assert current["events"][-1]["body"] in {"First response", "Second response"}


def test_support_assignment_requires_current_grant_and_can_be_cleared(integration):
    env = integration
    owner, actor, wid, staff, support, _admin, administrator = setup(env)
    value = create(env, owner, wid).json()
    path = f"/admin/workspaces/{wid}/support-tickets/{value['ticket']['id']}"
    assert (
        env.client.patch(
            path, headers=staff, json={"expected_version": 1, "assignee_id": str(actor.id)}
        ).status_code
        == 422
    )
    env.runtime.operations.change_staff(administrator.email, None)
    assert (
        env.client.patch(
            path, headers=staff, json={"expected_version": 1, "assignee_id": str(administrator.id)}
        ).status_code
        == 422
    )
    assigned = env.client.patch(
        path, headers=staff, json={"expected_version": 1, "assignee_id": str(support.id)}
    )
    assert assigned.status_code == 200
    assert (
        env.client.patch(
            path, headers=staff, json={"expected_version": 2, "assignee_id": None}
        ).json()["ticket"]["assignee_id"]
        is None
    )
    assert env.client.get("/admin/staff", headers=staff).json()["staff"] == [
        {"id": str(support.id), "email": support.email, "role": "support"}
    ]


def test_support_and_admin_lists_are_bounded_stable_and_literal(integration):
    env = integration
    owner, _, wid, staff, _, admin, _ = setup(env)
    keys = []
    for index in range(5):
        keys.append(create(env, owner, wid, subject=f"Case {index}").json()["ticket"]["id"])
    path = f"/workspaces/{wid}/support-tickets"
    first = env.client.get(path + "?limit=2", headers=owner).json()
    second = env.client.get(
        path, headers=owner, params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()
    third = env.client.get(
        path, headers=owner, params={"limit": 2, "cursor": second["next_cursor"]}
    ).json()
    assert [item["id"] for page in (first, second, third) for item in page["tickets"]] == list(
        reversed(keys)
    )
    assert third["next_cursor"] is None
    assert (
        env.client.get("/admin/support-tickets", headers=staff, params={"q": "%"}).json()["tickets"]
        == []
    )
    assert (
        len(
            env.client.get(
                "/admin/support-tickets", headers=staff, params={"workspace_id": wid, "q": "Case 1"}
            ).json()["tickets"]
        )
        == 1
    )
    for query in ("limit=0", "limit=101", "cursor=invalid", "status=arbitrary", "priority=urgent"):
        assert env.client.get(path + "?" + query, headers=owner).status_code == 422
    for _ in range(2):
        workspace(env, owner)
    first = env.client.get("/admin/workspaces?limit=1", headers=admin).json()
    second = env.client.get(
        "/admin/workspaces", headers=admin, params={"limit": 1, "cursor": first["next_cursor"]}
    ).json()
    assert first["workspaces"][0]["id"] != second["workspaces"][0]["id"]


def test_support_id_search_preserves_requester_workspace_and_status_filters(integration):
    env = integration
    owner, _, wid, staff, _, _, _ = setup(env)
    member, _ = add_member(env, owner, wid)
    ticket = create(env, member, wid).json()["ticket"]
    tid = ticket["id"]
    path = f"/workspaces/{wid}/support-tickets"
    for headers, expected in ((member, [tid]), (owner, [])):
        response = env.client.get(path, headers=headers, params={"q": tid})
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["tickets"]] == expected
    assert env.client.get(path + f"/{tid}", headers=owner).status_code == 404
    other_workspace = workspace(env, owner)
    response = env.client.get(
        f"/workspaces/{other_workspace}/support-tickets", headers=owner, params={"q": tid}
    )
    assert response.status_code == 200 and response.json()["tickets"] == []
    for filters, expected in (
        ({"q": tid}, [tid]),
        ({"q": tid, "workspace_id": wid}, [tid]),
        ({"q": tid, "workspace_id": other_workspace}, []),
        ({"q": tid, "status": "resolved"}, []),
        ({"q": tid, "priority": "high"}, []),
        ({"q": tid[:-1]}, []),
        ({"q": tid + "g"}, []),
    ):
        response = env.client.get("/admin/support-tickets", headers=staff, params=filters)
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["tickets"]] == expected
    literal = "not-a-uuid%'_"
    created = create(env, member, wid, subject=f"Literal {literal}").json()["ticket"]
    response = env.client.get(path, headers=member, params={"q": literal})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["tickets"]] == [created["id"]]


def test_admin_workspace_id_search_is_exact_and_keeps_name_search(integration):
    env = integration
    owner, _, wid, staff, _, admin, _ = setup(env)
    other_workspace = workspace(env, owner)
    for query, expected in ((wid, [wid]), (wid[:-1], []), (wid + "g", []), ("%'_", [])):
        response = env.client.get("/admin/workspaces", headers=admin, params={"q": query})
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["workspaces"]] == expected
    assert other_workspace != wid
    name = env.client.get(f"/admin/workspaces/{wid}", headers=admin).json()["name"]
    response = env.client.get("/admin/workspaces", headers=admin, params={"q": name})
    assert {item["id"] for item in response.json()["workspaces"]} == {wid, other_workspace}
    for headers in (owner, staff):
        assert (
            env.client.get("/admin/workspaces", headers=headers, params={"q": wid}).status_code
            == 403
        )


def test_support_feedback_reference_requires_requester_and_workspace(integration):
    env = integration
    owner, _, wid, *_ = setup(env)
    member, _ = add_member(env, owner, wid)
    feedback = env.client.post(
        f"/workspaces/{wid}/feedback",
        headers=member,
        json={"feature": "dashboard", "rating": 2, "category": "confusing"},
    ).json()
    assert create(env, owner, wid, feedback_id=feedback["id"]).status_code == 404
    response = create(env, member, wid, feedback_id=feedback["id"])
    assert (
        response.status_code == 201 and response.json()["ticket"]["feedback_id"] == feedback["id"]
    )
    other = workspace(env, member)
    assert create(env, member, other, feedback_id=feedback["id"]).status_code == 404


def test_support_text_is_not_copied_into_audit_records(integration, caplog):
    env = integration
    owner, _, wid, staff, *_ = setup(env)
    value = create(
        env, owner, wid, subject="SUPPORT_SUBJECT_PRIVATE", description="SUPPORT_BODY_PRIVATE"
    ).json()
    path = f"/admin/workspaces/{wid}/support-tickets/{value['ticket']['id']}"
    assert (
        env.client.post(
            path + "/messages",
            headers=staff,
            json={"expected_version": 1, "body": "SUPPORT_REPLY_PRIVATE"},
        ).status_code
        == 201
    )
    with env.engine.connect() as connection:
        data = [
            dict(row)
            for table in (s.audit_events, s.staff_audit)
            for row in connection.execute(select(table)).mappings()
        ]
    output = json.dumps(data, default=str) + caplog.text
    for value in ("SUPPORT_SUBJECT_PRIVATE", "SUPPORT_BODY_PRIVATE", "SUPPORT_REPLY_PRIVATE"):
        assert value not in output


def test_support_diagnostics_require_own_job_and_return_only_safe_fixed_metadata(integration):
    from test_conversation_jobs import prepared, submit

    env = integration
    owner, wid, _, path, _ = prepared(env)
    member, _ = add_member(env, owner, wid)
    staff, operator = identity(env, "diagnostic-support@example.test")
    env.runtime.operations.change_staff(operator.email, "support")
    job = submit(env, owner, path, question="PRIVATE_QUESTION_SENTINEL")
    assert create(env, member, wid, job_id=job["id"]).status_code == 404
    response = create(env, owner, wid, job_id=job["id"])
    assert response.status_code == 201
    value = response.json()
    assert set(value["diagnostics"]) == {
        "id",
        "status",
        "current_stage",
        "failure_code",
        "created_at",
        "updated_at",
    }
    assert value["diagnostics"]["status"] == "queued"
    assert "PRIVATE_QUESTION_SENTINEL" not in response.text
    other = workspace(env, owner)
    assert create(env, owner, other, job_id=job["id"]).status_code == 404
    with env.engine.begin() as connection:
        connection.execute(
            update(s.jobs)
            .where(s.jobs.c.id == UUID(job["id"]))
            .values(current_stage="PRIVATE_STAGE_SENTINEL", failure_code="PRIVATE_FAILURE_SENTINEL")
        )
    detail = env.client.get(
        f"/admin/workspaces/{wid}/support-tickets/{value['ticket']['id']}", headers=staff
    )
    assert detail.status_code == 200
    assert detail.json()["diagnostics"]["current_stage"] is None
    assert detail.json()["diagnostics"]["failure_code"] is None
    assert "PRIVATE_" not in detail.text
    assert env.client.get(f"/workspaces/{wid}/jobs/{job['id']}", headers=staff).status_code == 404


def test_staff_role_changes_and_revocation_have_reconstructible_cli_audit(integration):
    env = integration
    headers, actor = identity(env, "role-history@example.test")
    for role in ("support", "admin", None):
        env.runtime.operations.change_staff(actor.email, role)
        assert env.client.get("/admin/access", headers=headers).json()["role"] == role
    with env.engine.connect() as connection:
        events = (
            connection.execute(select(s.staff_audit).order_by(s.staff_audit.c.created_at))
            .mappings()
            .all()
        )
    assert [event["action"] for event in events] == [
        "staff.granted_support",
        "staff.granted_admin",
        "staff.revoked",
    ]
    assert all(
        event["origin"] == "operator_cli"
        and event["actor_id"] is None
        and event["resource_id"] == actor.id
        for event in events
    )


def test_failed_staff_audit_rolls_back_grant_and_ticket_change(integration, monkeypatch):
    from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository

    env = integration
    owner, actor, wid, staff, *_ = setup(env)
    value = create(env, owner, wid).json()
    original = SQLWorkspaceRepository.add_staff_audit

    def fail(self, event):
        raise RuntimeError("synthetic audit outage")

    monkeypatch.setattr(SQLWorkspaceRepository, "add_staff_audit", fail)
    with pytest.raises(RuntimeError):
        env.runtime.operations.change_staff(actor.email, "admin")
    with env.runtime.service.uow() as repo:
        assert repo.staff_grant(actor.id) is None
    with pytest.raises(RuntimeError):
        env.client.patch(
            f"/admin/workspaces/{wid}/support-tickets/{value['ticket']['id']}",
            headers=staff,
            json={"expected_version": 1, "status": "triaged"},
        )
    monkeypatch.setattr(SQLWorkspaceRepository, "add_staff_audit", original)
    assert (
        env.client.get(
            f"/workspaces/{wid}/support-tickets/{value['ticket']['id']}", headers=owner
        ).json()
        == value
    )


def test_support_event_limit_and_open_ticket_limit_are_enforced(integration):
    from dataclasses import replace
    from datetime import datetime, timezone

    from execplus.domain.operations import SupportTicket

    env = integration
    owner, actor, wid, _staff, *_ = setup(env)
    value = create(env, owner, wid).json()
    tid = UUID(value["ticket"]["id"])
    with env.engine.begin() as connection:
        connection.execute(
            update(s.support_tickets).where(s.support_tickets.c.id == tid).values(version=200)
        )
    response = env.client.post(
        f"/workspaces/{wid}/support-tickets/{tid}/messages",
        headers=owner,
        json={"expected_version": 200, "body": "More"},
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "support_limit"
    moment = datetime.now(timezone.utc)
    template = SupportTicket(
        uuid4(),
        UUID(wid),
        actor.id,
        "Bounded request",
        "Shared text",
        "other",
        "other",
        "open",
        "normal",
        1,
        moment,
        moment,
    )
    with env.runtime.service.uow() as repo:
        for _ in range(49):
            repo.add_support_ticket(replace(template, id=uuid4()))
    assert create(env, owner, wid).status_code == 409


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "cursor=bad", "q=" + "x" * 81])
def test_admin_list_rejects_unbounded_requests(integration, query):
    env = integration
    _, _, _, _, _, admin, _ = setup(env)
    assert env.client.get("/admin/workspaces?" + query, headers=admin).status_code == 422
