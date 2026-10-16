"""Use case: Verifies scoped keys and embed sessions against real saved work.

What it does: Exercises policy projection, owner management, revocation races,
current source sharing, exact results, rate limits and single-use grants.
"""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from execplus.infrastructure.persistence import schema as s
from test_dataset_access import fixture
from test_studies import add_member, prepare, run


def issue(env, owner, wid, did, user_id=None, operations=None):
    response = env.client.post(
        f"/workspaces/{wid}/integrations/keys",
        headers=owner,
        json={
            "name": "Read-only fixture",
            "user_id": str(user_id) if user_id else None,
            "dataset_ids": [did],
            "operations": operations or ["profile:read", "rows:read", "query:read"],
            "expires_seconds": 3600,
        },
    )
    assert response.status_code == 201, response.text
    value = response.json()
    return {"Authorization": "Bearer " + value["secret"]}, value


def scoped_issuer(env):
    values = fixture(env)
    owner, actor, _, _, _, _, _, _, policy_path, raw = values
    limited = {**raw["grants"][1], "user_id": str(actor.id)}
    updated = {**raw, "expected_version": 1, "grants": [limited, raw["grants"][1]]}
    response = env.client.put(policy_path, headers=owner, json=updated)
    assert response.status_code == 200, response.text
    return (*values[:-1], {**updated, "expected_version": 2})


def path(root):
    return "/integration/v1" + root


def shared(env):
    owner, actor, wid, did, _, root = prepare(env)
    result = run(env, owner, root).json()
    sid, vid = result["study"]["id"], result["version"]["id"]
    assert (
        env.client.patch(
            f"/workspaces/{wid}/studies/{sid}", headers=owner, json={"shared": True}
        ).status_code
        == 204
    )
    board = env.client.post(
        f"/workspaces/{wid}/study-boards",
        headers=owner,
        json={"name": "Shared exact board", "shared": True, "pins": [vid]},
    )
    assert board.status_code == 201, board.text
    return owner, actor, wid, did, root, sid, board.json()


def grant(env, owner, wid, board_id):
    response = env.client.post(
        f"/workspaces/{wid}/integrations/embeds",
        headers=owner,
        json={"board_id": board_id, "host_origin": "https://host.example.test"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def exchange(env, value, **changes):
    return env.client.post(
        f"/embed/{value['grant']['id']}/exchange",
        headers={"Origin": "http://localhost:3000"},
        json={
            "bootstrap_secret": value["bootstrap_secret"],
            "host_origin": "https://host.example.test",
            **changes,
        },
    )


def read_embed(env, session, **changes):
    return env.client.post(
        "/embed/session/board",
        headers={"Origin": "http://localhost:3000"},
        json={"session_secret": session, "host_origin": "https://host.example.test", **changes},
    )


@pytest.mark.parametrize("owner_scope", ["denied", "restricted"])
def test_owner_cannot_mint_another_members_wider_authority(integration, owner_scope):
    env = integration
    owner, actor, member, user, wid, did, _, root, policy_path, raw = fixture(env)
    grants = [dict(user_id=str(user.id), columns=None, conditions=[])]
    if owner_scope == "restricted":
        grants.append(
            dict(
                user_id=str(actor.id),
                columns=["city", "amount"],
                conditions=[dict(column="city", operator="eq", value="Karachi")],
            )
        )
    saved = env.client.put(
        policy_path, headers=owner, json={**raw, "expected_version": 1, "grants": grants}
    )
    assert saved.status_code == 200
    assert env.client.post(root + "/rows", headers=member, json={}).status_code == 200
    denied = env.client.post(
        f"/workspaces/{wid}/integrations/keys",
        headers=owner,
        json={
            "name": "Forbidden delegated authority",
            "user_id": str(user.id),
            "dataset_ids": [did],
            "operations": ["rows:read"],
        },
    )
    assert denied.status_code == 403
    assert "secret" not in denied.json()
    with env.engine.connect() as connection:
        assert connection.execute(select(s.integration_keys)).first() is None
    own = env.client.post(
        f"/workspaces/{wid}/integrations/keys",
        headers=owner,
        json={"name": "Own current access", "dataset_ids": [did], "operations": ["rows:read"]},
    )
    if owner_scope == "denied":
        assert own.status_code == 404 and "secret" not in own.json()
    else:
        assert own.status_code == 201
        assert own.json()["key"]["user_id"] == str(actor.id)
        rows = env.client.post(
            path(root) + "/rows",
            headers={"Authorization": "Bearer " + own.json()["secret"]},
            json={},
        )
        assert rows.status_code == 200
        assert len(rows.json()["rows"]) == 2 and rows.json()["columns"] == ["city", "amount"]
        assert "Lahore" not in rows.text and '"cost"' not in rows.text


def test_scoped_key_preserves_exact_rows_policy_privacy_and_cannot_become_session(integration):
    env = integration
    owner, actor, member, _, wid, did, _, root, _, _ = scoped_issuer(env)
    key, issued = issue(env, owner, wid, did, actor.id)
    assert issued["key"]["user_id"] == str(actor.id)
    result = env.client.post(
        path(root) + "/query", headers=key, json={"metric": "amount", "aggregation": "sum"}
    )
    assert result.status_code == 200, result.text
    assert Decimal(result.json()["rows"][0][0]) == Decimal("0.30")
    assert result.json()["records_analyzed"] == 2
    for method, suffix, body in [("GET", "/profile", None), ("POST", "/rows", {})]:
        response = env.client.request(method, path(root) + suffix, headers=key, json=body)
        assert response.status_code == 200, response.text
        assert '"cost"' not in response.text and "Lahore" not in response.text
    assert env.client.get("/workspaces", headers=key).status_code == 401
    assert env.client.post(root + "/threads", headers=key).status_code == 401
    assert (
        env.client.post(
            path(root) + "/query", headers=owner, json={"metric": "amount", "aggregation": "sum"}
        ).status_code
        == 404
    )
    with env.engine.connect() as connection:
        row = connection.execute(select(s.integration_keys)).mappings().one()
    assert row["token_hash"] == hashlib.sha256(issued["secret"].encode()).hexdigest()
    assert issued["secret"] not in str(row)
    listed = env.client.get(f"/workspaces/{wid}/integrations/keys", headers=owner)
    assert issued["secret"] not in listed.text and row["token_hash"] not in listed.text
    assert env.client.get(f"/workspaces/{wid}/integrations/keys", headers=member).status_code == 403
    assert (
        env.client.post(
            f"/workspaces/{wid}/integrations/keys",
            headers=member,
            json={"name": "No", "dataset_ids": [did], "operations": ["query:read"]},
        ).status_code
        == 403
    )


def test_explicit_key_scope_and_atomic_rate_window(integration):
    env = integration
    owner, _, wid, did, _, root = prepare(env)
    key, issued = issue(env, owner, wid, did, operations=["rows:read"])
    assert (
        env.client.post(
            path(root) + "/query", headers=key, json={"metric": "amount", "aggregation": "sum"}
        ).status_code
        == 404
    )
    window = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    with env.engine.begin() as connection:
        connection.execute(
            s.integration_request_windows.insert().values(
                key_id=UUID(issued["key"]["id"]), window_start=window, used=59
            )
        )
    assert env.client.post(path(root) + "/rows", headers=key, json={}).status_code == 200
    limited = env.client.post(path(root) + "/rows", headers=key, json={})
    assert (
        limited.status_code == 429 and limited.json()["error"]["code"] == "integration_rate_limit"
    )
    with env.engine.connect() as connection:
        assert connection.execute(select(s.integration_request_windows.c.used)).scalar_one() == 60


def test_key_revocation_during_query_discards_result_without_holding_lock(integration, monkeypatch):
    env = integration
    owner, actor, wid, did, _, root = prepare(env)
    key, issued = issue(env, owner, wid, did)
    original = env.runtime.analytics.run_query

    async def revoke(*args, **kwargs):
        result = await original(*args, **kwargs)
        env.runtime.integration_access.revoke_key(actor, UUID(wid), UUID(issued["key"]["id"]))
        return result

    monkeypatch.setattr(env.runtime.analytics, "run_query", revoke)
    response = env.client.post(
        path(root) + "/query", headers=key, json={"metric": "amount", "aggregation": "sum"}
    )
    assert response.status_code == 404
    assert "0.30" not in response.text


def test_membership_readdition_does_not_reactivate_existing_key(integration):
    env = integration
    owner, actor, wid, did, _, root = prepare(env)
    key, _ = issue(env, owner, wid, did)
    with env.engine.begin() as connection:
        original = dict(
            connection.execute(
                select(s.memberships).where(
                    s.memberships.c.workspace_id == UUID(wid), s.memberships.c.user_id == actor.id
                )
            )
            .mappings()
            .one()
        )
        connection.execute(
            s.memberships.delete().where(
                s.memberships.c.workspace_id == UUID(wid), s.memberships.c.user_id == actor.id
            )
        )
    assert env.client.post(path(root) + "/rows", headers=key, json={}).status_code == 404
    with env.engine.begin() as connection:
        connection.execute(
            s.memberships.insert().values(
                **{**original, "created_at": original["created_at"] + timedelta(seconds=1)}
            )
        )
    assert env.client.post(path(root) + "/rows", headers=key, json={}).status_code == 404
    fresh, _ = issue(env, owner, wid, did)
    assert env.client.post(path(root) + "/rows", headers=fresh, json={}).status_code == 200


def test_policy_epoch_change_during_key_query_discards_old_scope(integration, monkeypatch):
    env = integration
    owner, _, _, _, wid, did, _, root, policy_path, raw = scoped_issuer(env)
    key, _ = issue(env, owner, wid, did)
    original = env.runtime.analytics.run_query

    async def change(*args, **kwargs):
        result = await original(*args, **kwargs)
        changed = await asyncio.to_thread(env.client.put, policy_path, headers=owner, json=raw)
        assert changed.status_code == 200
        return result

    monkeypatch.setattr(env.runtime.analytics, "run_query", change)
    assert (
        env.client.post(
            path(root) + "/query", headers=key, json={"metric": "amount", "aggregation": "sum"}
        ).status_code
        == 404
    )


def test_key_expiry_and_owner_revocation(integration, monkeypatch):
    from execplus.application.services import integration_access

    env = integration
    owner, _, wid, did, _, root = prepare(env)
    key, issued = issue(env, owner, wid, did)
    future = datetime.fromisoformat(issued["key"]["expires_at"])
    monkeypatch.setattr(integration_access, "now_utc", lambda: future)
    assert env.client.post(path(root) + "/rows", headers=key, json={}).status_code == 404
    assert (
        env.client.delete(
            f"/workspaces/{wid}/integrations/keys/{issued['key']['id']}", headers=owner
        ).status_code
        == 204
    )


def test_shared_board_api_key_remains_within_dataset_scope(integration):
    env = integration
    owner, _, wid, did, _, sid, board = shared(env)
    key, _ = issue(env, owner, wid, did, operations=["boards:read"])
    endpoint = f"/integration/v1/workspaces/{wid}/boards/{board['id']}"
    response = env.client.get(endpoint, headers=key)
    assert response.status_code == 200, response.text
    assert response.json()["studies"][0]["display"]["rows"] == [["0.300000000000"]]
    env.client.patch(f"/workspaces/{wid}/studies/{sid}", headers=owner, json={"shared": False})
    assert env.client.get(endpoint, headers=key).status_code == 404


def test_embed_exchange_exact_view_one_use_host_checks_no_secret_echo_and_revocation(integration):
    env = integration
    owner, _, wid, _, _, _, board = shared(env)
    value = grant(env, owner, wid, board["id"])
    descriptor = env.client.get(f"/embed/{value['grant']['id']}/descriptor")
    assert descriptor.json() == {"host_origin": "https://host.example.test"}
    assert value["bootstrap_secret"] not in descriptor.text
    assert exchange(env, value, host_origin="https://evil.test").status_code == 404
    denied_origin = env.client.post(
        f"/embed/{value['grant']['id']}/exchange",
        headers={"Origin": "https://evil.test"},
        json={
            "bootstrap_secret": value["bootstrap_secret"],
            "host_origin": "https://host.example.test",
        },
    )
    assert denied_origin.status_code == 403
    response = exchange(env, value)
    assert response.status_code == 200, response.text
    session = response.json()["session_secret"]
    assert exchange(env, value).status_code == 404
    result = read_embed(env, session)
    assert result.status_code == 200, result.text
    assert result.json()["studies"][0]["display"]["rows"] == [["0.300000000000"]]
    assert session not in result.text and value["bootstrap_secret"] not in result.text
    assert read_embed(env, session, host_origin="https://evil.test").status_code == 404
    assert (
        env.client.get("/workspaces", headers={"Authorization": "Bearer " + session}).status_code
        == 401
    )
    assert (
        env.client.delete(
            f"/workspaces/{wid}/integrations/embeds/{value['grant']['id']}", headers=owner
        ).status_code
        == 204
    )
    assert read_embed(env, session).status_code == 404


@pytest.mark.parametrize("change", ["board", "study", "policy"])
def test_embed_current_permissions_change_during_replay_refuses_delivery(
    integration, monkeypatch, change
):
    env = integration
    owner, _, wid, did, _, sid, board = shared(env)
    value = grant(env, owner, wid, board["id"])
    session = exchange(env, value).json()["session_secret"]
    original = env.runtime.studies.open_board

    async def changed(*args):
        result = await original(*args)
        if change == "study":
            await asyncio.to_thread(
                env.client.patch,
                f"/workspaces/{wid}/studies/{sid}",
                headers=owner,
                json={"shared": False},
            )
        elif change == "board":
            await asyncio.to_thread(
                env.client.patch,
                f"/workspaces/{wid}/study-boards/{board['id']}",
                headers=owner,
                json={
                    "name": "Changed",
                    "shared": True,
                    "pins": board["pins"],
                    "expected_version": board["version"],
                },
            )
        else:
            await asyncio.to_thread(
                env.client.put,
                f"/workspaces/{wid}/datasets/{did}/access-policy",
                headers=owner,
                json={"expected_version": 0, "enabled": True, "grants": []},
            )
        return result

    monkeypatch.setattr(env.runtime.studies, "open_board", changed)
    assert read_embed(env, session).status_code in {404, 422}


def test_embed_lifetime_cannot_extend_and_non_owner_cannot_issue(integration, monkeypatch):
    from execplus.application.services import integration_access

    env = integration
    owner, _, wid, _, _, _, board = shared(env)
    member, _ = add_member(env, owner, wid, "admin")
    assert (
        env.client.post(
            f"/workspaces/{wid}/integrations/embeds",
            headers=member,
            json={"board_id": board["id"], "host_origin": "https://host.example.test"},
        ).status_code
        == 403
    )
    value = grant(env, owner, wid, board["id"])
    session = exchange(env, value).json()
    expired = datetime.fromisoformat(session["expires_at"]) + timedelta(microseconds=1)
    monkeypatch.setattr(integration_access, "now_utc", lambda: expired)
    assert read_embed(env, session["session_secret"]).status_code == 404


def test_cancelled_profile_read_drains_source_thread_before_returning(integration, monkeypatch):
    from threading import Event

    from starlette.requests import Request

    from execplus.presentation.routes.integrations import profile

    env = integration
    owner, _, wid, did, uid, _ = prepare(env)
    _, issued = issue(env, owner, wid, did)
    entered, release, finished = Event(), Event(), Event()
    original = env.runtime.service.profile_upload

    def held(*args):
        entered.set()
        try:
            assert release.wait(5)
            return original(*args)
        finally:
            finished.set()

    monkeypatch.setattr(env.runtime.service, "profile_upload", held)

    async def cancelled():
        request = Request(
            {
                "type": "http",
                "headers": [(b"authorization", ("Bearer " + issued["secret"]).encode())],
            }
        )
        pending = asyncio.create_task(
            profile(UUID(wid), UUID(did), UUID(uid), request, env.runtime)
        )
        assert await asyncio.to_thread(entered.wait, 3)
        pending.cancel()
        await asyncio.sleep(0.05)
        assert not pending.done() and not finished.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert finished.is_set()

    asyncio.run(cancelled())
