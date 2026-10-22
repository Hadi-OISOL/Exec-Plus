"""Use case: Proves operator-issued one-time password reset codes.

What it does: Covers identity checks, single use, expiry, session revocation,
code invalidation on password change and safe errors against migrated PostgreSQL.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_local_accounts_integration import NEXT_PASSWORD, PASSWORD, native

EMAIL = "native@example.test"


def reset(env, code, password=NEXT_PASSWORD, email=EMAIL):
    return env.client.post(
        "/auth/reset-password", json={"email": email, "code": code, "new_password": password}
    )


def test_reset_code_requires_operator_identity_check(integration):
    env = integration
    _headers, actor, _wid, _token = native(env)
    with pytest.raises(IngestionError) as error:
        env.runtime.accounts.issue_reset_code(actor.id, identity_checked=False)
    assert error.value.code == "identity_check_required"


def test_reset_code_sets_password_once_and_revokes_sessions(integration):
    env = integration
    headers, actor, _wid, _token = native(env)
    code, _expires = env.runtime.accounts.issue_reset_code(actor.id, identity_checked=True)
    with env.engine.connect() as connection:
        stored = connection.execute(select(s.account_reset_codes)).mappings().one()
    assert code not in repr(dict(stored))
    assert reset(env, "wrong-" + code).status_code == 401
    response = reset(env, code)
    assert response.status_code == 204, response.text
    env.client.cookies.clear()
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    old = env.client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert old.status_code == 401
    assert (
        env.client.post("/auth/login", json={"email": EMAIL, "password": NEXT_PASSWORD}).status_code
        == 200
    )
    again = reset(env, code, "another fictional passphrase 81")
    assert again.status_code == 401 and again.json()["error"]["code"] == "reset_code_invalid"
    events = [item["action"] for item in env.runtime.accounts.events(actor)]
    assert "reset_code.issued" in events and "password.reset" in events


def test_expired_unknown_and_superseded_codes_fail_with_the_same_error(integration):
    env = integration
    headers, actor, _wid, _token = native(env)
    code, _ = env.runtime.accounts.issue_reset_code(actor.id, identity_checked=True)
    original = env.runtime.accounts.clock
    env.runtime.accounts.clock = lambda: original() + timedelta(minutes=31)
    try:
        assert reset(env, code).json()["error"]["code"] == "reset_code_invalid"
    finally:
        env.runtime.accounts.clock = original
    unknown = reset(env, code, email="nobody@example.test")
    assert unknown.status_code == 401 and unknown.json()["error"]["code"] == "reset_code_invalid"
    code, _ = env.runtime.accounts.issue_reset_code(actor.id, identity_checked=True)
    changed = env.client.post(
        "/auth/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": NEXT_PASSWORD},
    )
    assert changed.status_code == 200
    assert reset(env, code, "another fictional passphrase 81").status_code == 401


def test_disabled_accounts_cannot_receive_or_use_codes(integration):
    env = integration
    headers, actor, _wid, _token = native(env)
    code, _ = env.runtime.accounts.issue_reset_code(actor.id, identity_checked=True)
    assert (
        env.client.post(
            "/auth/disable", headers=headers, json={"password": PASSWORD, "confirmed": True}
        ).status_code
        == 204
    )
    assert reset(env, code).status_code == 401
    with pytest.raises(IngestionError) as error:
        env.runtime.accounts.issue_reset_code(actor.id, identity_checked=True)
    assert error.value.code == "account_unavailable"


def test_reset_endpoint_is_origin_guarded_and_advertised(integration):
    env = integration
    foreign = env.client.post(
        "/auth/reset-password",
        headers={"Origin": "https://evil.example"},
        json={"email": EMAIL, "code": "x", "new_password": NEXT_PASSWORD},
    )
    assert foreign.status_code == 403
    assert env.client.get("/auth/options").json()["password_recovery"] == "operator_reset_code"
