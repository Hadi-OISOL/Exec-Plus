"""Use case: Verifies scoped API reads reuse private saved results and job status.

What it does: Checks exact agreement, explicit operation/dataset limits, ownership,
revocation during replay and truthful OpenAPI without calling a model or provider.
"""

import asyncio
from uuid import UUID, uuid4

import pytest

from execplus.infrastructure.persistence import schema as s
from test_decision_analysis_integration import create as create_analysis
from test_forecast_integration import create as create_forecast
from test_forecast_integration import daily
from test_integration_access_integration import exchange, grant, issue, read_embed, shared
from test_studies import add_member, prepare, run
from test_workspace_integration import dataset


def saved_result(env, kind):
    content = (
        daily() if kind == "forecasts" else b"city,amount,cost\n" + b"A,10,1\n" * 8 + b"B,100,2\n"
    )
    owner, actor, wid, did, _, root = prepare(env, content)
    if kind == "studies":
        value = run(env, owner, root).json()
        identifier = value["version"]["id"]
        ordinary = f"/workspaces/{wid}/study-versions/{identifier}"
        scoped = f"/integration/v1/workspaces/{wid}/studies/{identifier}"
    elif kind == "forecasts":
        response = create_forecast(env, owner, root)
        assert response.status_code == 201, response.text
        identifier = response.json()["id"]
        ordinary = f"/workspaces/{wid}/datasets/{did}/forecasts/{identifier}"
        scoped = "/integration/v1" + ordinary
    elif kind == "analyses":
        response = create_analysis(env, owner, root)
        assert response.status_code == 201, response.text
        identifier = response.json()["run"]["id"]
        ordinary = f"/workspaces/{wid}/datasets/{did}/decision-analysis/{identifier}"
        scoped = f"/integration/v1/workspaces/{wid}/datasets/{did}/analyses/{identifier}"
    else:
        tid = env.client.post(root + "/threads", headers=owner).json()["id"]
        response = env.client.post(
            f"/workspaces/{wid}/threads/{tid}/jobs",
            headers=owner,
            json={"question": "What is the total of amount?", "request_id": str(uuid4())},
        )
        assert response.status_code == 202, response.text
        identifier = response.json()["id"]
        ordinary = f"/workspaces/{wid}/jobs/{identifier}"
        scoped = "/integration/v1" + ordinary
    return owner, actor, wid, did, ordinary, scoped


@pytest.mark.parametrize("kind", ["studies", "forecasts", "analyses", "jobs"])
def test_scoped_result_matches_original_and_requires_explicit_operation_and_dataset(
    integration, kind
):
    env = integration
    owner, _, wid, did, ordinary, scoped = saved_result(env, kind)
    key, issued = issue(env, owner, wid, did, operations=[kind + ":read"])
    expected = env.client.get(ordinary, headers=owner)
    actual = env.client.get(scoped, headers=key)
    assert expected.status_code == actual.status_code == 200, actual.text
    assert actual.json() == expected.json()
    assert issued["secret"] not in actual.text
    wrong_operation, _ = issue(env, owner, wid, did, operations=["rows:read"])
    assert env.client.get(scoped, headers=wrong_operation).status_code == 404
    other_did = dataset(env, owner, wid)
    wrong_dataset, _ = issue(env, owner, wid, other_did, operations=[kind + ":read"])
    assert env.client.get(scoped, headers=wrong_dataset).status_code == 404
    assert env.client.get(scoped.replace(wid, str(uuid4())), headers=key).status_code == 404
    if kind in {"forecasts", "analyses"}:
        assert env.client.get(scoped.replace(did, other_did), headers=key).status_code == 404
    assert env.client.get(ordinary, headers=key).status_code == 401
    assert env.client.get(scoped, headers=owner).status_code == 404
    assert env.client.get(scoped).status_code == 401
    assert env.client.get(ordinary + "/export.pdf", headers=key).status_code in {401, 404}
    if kind == "jobs":
        assert set(actual.json()) == {
            "id",
            "workspace_id",
            "thread_id",
            "turn_id",
            "status",
            "created_at",
            "updated_at",
            "attempts",
            "current_stage",
            "cancel_requested",
            "failure_code",
        }
    response = env.client.delete(
        f"/workspaces/{wid}/integrations/keys/{issued['key']['id']}", headers=owner
    )
    assert response.status_code == 204
    assert env.client.get(scoped, headers=key).status_code == 404


@pytest.mark.parametrize("kind", ["studies", "forecasts", "analyses", "jobs"])
def test_another_workspace_owner_key_cannot_read_private_saved_result(integration, kind):
    env = integration
    owner, _, wid, did, _, scoped = saved_result(env, kind)
    member, user = add_member(env, owner, wid, "admin")
    with env.engine.begin() as connection:
        connection.execute(
            s.memberships.update()
            .where(s.memberships.c.workspace_id == UUID(wid), s.memberships.c.user_id == user.id)
            .values(role="owner")
        )
    key, _ = issue(env, member, wid, did, operations=[kind + ":read"])
    assert env.client.get(scoped, headers=key).status_code == 404


@pytest.mark.parametrize("kind", ["studies", "forecasts", "analyses", "jobs"])
def test_revoked_key_during_saved_result_read_discards_delivery(integration, monkeypatch, kind):
    env = integration
    owner, actor, wid, did, _, scoped = saved_result(env, kind)
    key, issued = issue(env, owner, wid, did, operations=[kind + ":read"])
    service = {
        "studies": env.runtime.studies,
        "forecasts": env.runtime.forecasts,
        "analyses": env.runtime.decision_analysis,
        "jobs": env.runtime.jobs,
    }[kind]
    method = "get" if kind == "jobs" else "open"
    original = getattr(service, method)

    def revoke():
        env.runtime.integration_access.revoke_key(actor, UUID(wid), UUID(issued["key"]["id"]))

    if kind == "jobs":

        def read(*args, **kwargs):
            value = original(*args, **kwargs)
            revoke()
            return value
    else:

        async def read(*args, **kwargs):
            value = await original(*args, **kwargs)
            await asyncio.to_thread(revoke)
            return value

    monkeypatch.setattr(service, method, read)
    response = env.client.get(scoped, headers=key)
    assert response.status_code == 404 and "results" not in response.json()


def test_openapi_documents_scoped_bearer_for_every_customer_endpoint(integration):
    document = integration.client.get("/openapi.json").json()
    scheme = document["components"]["securitySchemes"]["ScopedIntegrationKey"]
    assert scheme["type"] == "http" and scheme["scheme"] == "bearer"
    routes = {
        path: operations
        for path, operations in document["paths"].items()
        if path.startswith("/integration/v1/")
    }
    assert len(routes) == 8
    for operations in routes.values():
        for operation in operations.values():
            assert operation["security"] == [{"ScopedIntegrationKey": []}]


@pytest.mark.parametrize("change", ["study_unshared", "board_unshared", "board_version"])
def test_sharing_change_before_final_key_transaction_discards_result(
    integration, monkeypatch, change
):
    env = integration
    owner, _, wid, did, _, sid, board = shared(env)
    member, user = add_member(env, owner, wid, "admin")
    with env.engine.begin() as connection:
        connection.execute(
            s.memberships.update()
            .where(s.memberships.c.workspace_id == UUID(wid), s.memberships.c.user_id == user.id)
            .values(role="owner")
        )
    operation = "studies:read" if change == "study_unshared" else "boards:read"
    key, _ = issue(env, member, wid, did, operations=[operation])
    identifier = board["pins"][0] if change == "study_unshared" else board["id"]
    path = f"/integration/v1/workspaces/{wid}/{operation.split(':')[0]}/{identifier}"
    assert env.client.get(path, headers=key).status_code == 200
    service = env.runtime.integration_access
    original = service.perform

    async def perform(token, workspace, dataset_id, scope, action, **kwargs):
        async def changed(actor, credential):
            value = await action(actor, credential)
            with env.engine.begin() as connection:
                if change == "study_unshared":
                    connection.execute(
                        s.studies.update().where(s.studies.c.id == UUID(sid)).values(shared=False)
                    )
                else:
                    values = (
                        {"shared": False}
                        if change == "board_unshared"
                        else {"version": board["version"] + 1}
                    )
                    connection.execute(
                        s.study_boards.update()
                        .where(s.study_boards.c.id == UUID(board["id"]))
                        .values(**values)
                    )
            return value

        return await original(token, workspace, dataset_id, scope, changed, **kwargs)

    monkeypatch.setattr(service, "perform", perform)
    denied = env.client.get(path, headers=key)
    assert denied.status_code in {404, 422}, denied.text
    assert "display" not in denied.json()


def test_multisource_study_and_board_require_every_key_dataset_and_current_source_access(
    integration,
):
    from test_contribution_studies import create_contribution, prepare_contribution

    env = integration
    owner, _, wid, did, _, root, other_did, _, _, method = prepare_contribution(env)
    response = create_contribution(env, owner, root, method)
    assert response.status_code == 201, response.text
    value = response.json()
    vid, sid = value["version"]["id"], value["study"]["id"]
    assert (
        env.client.patch(
            f"/workspaces/{wid}/studies/{sid}", headers=owner, json={"shared": True}
        ).status_code
        == 204
    )
    response = env.client.post(
        f"/workspaces/{wid}/study-boards",
        headers=owner,
        json={"name": "Two source comparison", "shared": True, "pins": [vid]},
    )
    assert response.status_code == 201, response.text
    board = response.json()
    endpoints = [
        f"/integration/v1/workspaces/{wid}/studies/{vid}",
        f"/integration/v1/workspaces/{wid}/boards/{board['id']}",
    ]
    single, _ = issue(env, owner, wid, did, operations=["studies:read", "boards:read"])
    assert all(env.client.get(path, headers=single).status_code == 404 for path in endpoints)
    response = env.client.post(
        f"/workspaces/{wid}/integrations/keys",
        headers=owner,
        json={
            "name": "Both exact sources",
            "dataset_ids": [did, other_did],
            "operations": ["studies:read", "boards:read"],
        },
    )
    assert response.status_code == 201, response.text
    both = {"Authorization": "Bearer " + response.json()["secret"]}
    result = env.client.get(endpoints[0], headers=both)
    assert result.status_code == 200, result.text
    assert result.json()["display"] == value["display"]
    assert (
        env.client.get(endpoints[1], headers=both).json()["studies"][0]["display"]
        == value["display"]
    )
    view = grant(env, owner, wid, board["id"])
    session = exchange(env, view).json()["session_secret"]
    assert read_embed(env, session).status_code == 200
    revoked = env.client.put(
        f"/workspaces/{wid}/datasets/{other_did}/access-policy",
        headers=owner,
        json={"expected_version": 0, "enabled": True, "grants": []},
    )
    assert revoked.status_code == 200, revoked.text
    assert all(env.client.get(path, headers=both).status_code == 404 for path in endpoints)
    assert read_embed(env, session).status_code == 404


def test_embed_forgery_expiry_export_separation_and_redacted_read_audit(integration, monkeypatch):
    from datetime import datetime

    from sqlalchemy import select

    from execplus.application.services import integration_access

    env = integration
    owner, _, wid, _, _, _, board = shared(env)
    view = grant(env, owner, wid, board["id"])
    another = grant(env, owner, wid, board["id"])
    assert exchange(env, view, bootstrap_secret=another["bootstrap_secret"]).status_code == 404
    response = exchange(env, view)
    assert response.status_code == 200
    session = response.json()["session_secret"]
    assert read_embed(env, session).status_code == 200
    ordinary = f"/workspaces/{wid}/study-boards/{board['id']}/export.pdf"
    assert (
        env.client.get(ordinary, headers={"Authorization": "Bearer " + session}).status_code == 401
    )
    assert read_embed(env, "eps_" + "x" * 43).status_code == 404
    with env.engine.connect() as connection:
        events = (
            connection.execute(
                select(s.audit_events).where(s.audit_events.c.action == "integration.embed_read")
            )
            .mappings()
            .all()
        )
    assert len(events) == 1 and str(events[0]["resource_id"]) == view["grant"]["id"]
    assert session not in str(events) and view["bootstrap_secret"] not in str(events)
    monkeypatch.setattr(
        integration_access,
        "now_utc",
        lambda: datetime.fromisoformat(another["grant"]["expires_at"]),
    )
    assert exchange(env, another).status_code == 404
