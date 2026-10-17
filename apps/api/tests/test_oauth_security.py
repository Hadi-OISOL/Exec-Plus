"""Use case: Proves provider consent cannot cross browser/account or revocation boundaries.

What it does: Uses fake providers and real isolated SQL transactions for replay, session exchange,
connection races, native isolation and self-service plan enforcement. No provider network calls.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from execplus.application.connector_ports import ConnectorConnection, ProviderTokens
from execplus.application.google_ports import GoogleApiError, GoogleConnection, TokenSet
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from execplus.presentation.routes.oauth import BROWSER_COOKIE, EXCHANGE_COOKIE
from test_connectors_service import connect_oauth
from test_connectors_service import enable as enable_connectors
from test_google_access import DRIVE, SHEET, connect, enable, exchange, sign_in
from test_local_accounts_integration import native
from test_workspace_integration import dataset, identity, workspace


def begin_google(env, headers):
    started = env.client.post("/integrations/google/connect", headers=headers)
    assert started.status_code == 200, started.text
    return parse_qs(urlparse(started.json()["url"]).query)["state"][0]


def finish_google(env, state, code="good"):
    return env.client.get(
        "/integrations/google/callback",
        params={"state": state, "code": code},
        follow_redirects=False,
    )


def session_count(env):
    with env.engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(s.sessions)).scalar_one()


def test_google_connect_cannot_be_completed_in_another_browser_even_with_matching_email(
    integration,
):
    env = integration
    headers, actor, _, _ = native(env, "claimed-owner@example.test")
    google, _ = enable(env)
    state = begin_google(env, headers)
    google.grant("good", actor.email, DRIVE)
    browser = env.client.cookies.get(BROWSER_COOKIE)
    env.client.cookies.clear()
    denied = finish_google(env, state)
    assert denied.headers["location"].endswith("oauth_error=oauth_state_invalid")
    assert google.used == set()
    assert env.runtime.google_access.connections.get(actor.id) is None
    env.client.cookies.set(BROWSER_COOKIE, browser)
    accepted = finish_google(env, state)
    assert accepted.headers["location"].endswith("oauth=complete")
    assert env.runtime.google_access.connections.get(actor.id) is not None
    assert (
        "good" not in accepted.headers["location"] and "token" not in accepted.headers["location"]
    )


def test_google_callback_and_session_exchange_are_both_single_use(integration):
    env = integration
    headers, actor = identity(env, "single-use@example.test")
    google, _ = enable(env)
    state = begin_google(env, headers)
    google.grant("good", actor.email, DRIVE)
    finish_google(env, state)
    handoff = env.client.cookies.get(EXCHANGE_COOKIE)
    result = exchange(env)
    assert result["provider"] == "google" and set(result) == {"provider", "token"}
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    assert env.client.get(
        "/auth/me", headers={"Authorization": "Bearer " + result["token"]}
    ).json()["id"] == str(actor.id)
    env.client.cookies.set(EXCHANGE_COOKIE, handoff)
    assert env.client.post("/auth/oauth/exchange", json={}).status_code == 400
    replay = finish_google(env, state)
    assert replay.headers["location"].endswith("oauth_error=oauth_state_invalid")
    assert len(google.used) == 1 and session_count(env) == 1


@pytest.mark.parametrize("mutation", ["logout", "disable", "disconnect", "new_attempt"])
def test_callback_rechecks_initiating_account_and_operation_after_provider_io(
    integration, mutation
):
    env = integration
    headers, actor, _, token = native(env, f"callback-{mutation}@example.test")
    google, _ = enable(env)
    state = begin_google(env, headers)
    google.grant("good", actor.email, DRIVE)
    original = google.exchange_code

    def during_io(*args):
        if mutation == "logout":
            env.runtime.identity.revoke(token)
        elif mutation == "disable":
            with env.engine.begin() as db:
                db.execute(
                    update(s.local_accounts)
                    .where(s.local_accounts.c.user_id == actor.id)
                    .values(disabled_at=datetime.now(timezone.utc))
                )
        elif mutation == "disconnect":
            env.runtime.google_access.disconnect(actor)
        else:
            begin_google(env, headers)
        return original(*args)

    google.exchange_code = during_io
    callback = finish_google(env, state)
    assert callback.headers["location"].endswith("oauth_error=oauth_state_invalid")
    with env.engine.connect() as db:
        assert db.execute(select(func.count()).select_from(s.google_connections)).scalar_one() == 0
    assert EXCHANGE_COOKIE not in env.client.cookies


@pytest.mark.parametrize("mutation", ["logout", "disable", "disconnect"])
def test_picker_refuses_tokens_when_session_or_connection_changes_during_refresh(
    integration, mutation
):
    env = integration
    headers, actor, _, token = native(env, f"picker-{mutation}@example.test")
    google, _ = enable(env)
    connect(env, google, headers, email=actor.email)

    def refresh(_):
        if mutation == "logout":
            env.runtime.identity.revoke(token)
        elif mutation == "disable":
            with env.engine.begin() as db:
                db.execute(
                    update(s.local_accounts)
                    .where(s.local_accounts.c.user_id == actor.id)
                    .values(disabled_at=datetime.now(timezone.utc))
                )
        else:
            env.runtime.google_access.disconnect(actor)
        return TokenSet("must-not-be-returned", 3600)

    google.refresh = refresh
    response = env.client.get("/integrations/google/picker-token", headers=headers)
    assert response.status_code in {401, 409}
    assert "must-not-be-returned" not in response.text


@pytest.mark.parametrize("stage", ["refresh", "spreadsheet"])
def test_google_stale_provider_errors_do_not_delete_a_new_connection(integration, stage):
    env = integration
    headers, actor = identity(env, f"stale-{stage}@example.test")
    google, vault = enable(env)
    connect(env, google, headers, email=actor.email)
    replacement = GoogleConnection(actor.id, actor.email, DRIVE, vault.seal("new-refresh"))

    def fail(*_):
        env.runtime.google_access.connections.save(replacement)
        raise GoogleApiError(401, "invalid_grant")

    if stage == "refresh":
        google.refresh = fail
    else:
        google.spreadsheet = fail
    response = env.client.get(f"/integrations/google/spreadsheets/{SHEET}", headers=headers)
    assert response.status_code == 409
    assert env.runtime.google_access.connections.get(actor.id).version == replacement.version


@pytest.mark.parametrize("operation", ["sources", "import"])
def test_connector_rechecks_connection_after_read_and_before_output(integration, operation):
    env = integration
    oauth, _, _ = enable_connectors(env)
    headers, actor = identity(env, f"read-{operation}@example.test")
    connect_oauth(env, headers)
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    original = oauth.sources if operation == "sources" else oauth.fetch

    def interrupted(*args):
        env.runtime.connectors.disconnect(actor, "quickbooks")
        return original(*args)

    if operation == "sources":
        oauth.sources = interrupted
        response = env.client.get("/connectors/quickbooks/sources", headers=headers)
    else:
        oauth.fetch = interrupted
        response = env.client.post(
            f"/workspaces/{wid}/datasets/{did}/connectors/quickbooks/import",
            headers=headers,
            json={"source_id": "Invoice"},
        )
    assert response.status_code == 409
    assert env.client.get(f"/workspaces/{wid}/datasets/{did}/uploads", headers=headers).json() == []


@pytest.mark.parametrize("mutation", ["disconnect", "logout", "disable"])
def test_credential_validation_cannot_restore_a_revoked_or_disabled_connection(
    integration, mutation
):
    env = integration
    headers, actor, _, token = native(env, f"credential-{mutation}@example.test")
    _, credentials, _ = enable_connectors(env)

    def validate(values):
        assert values["api_key"] == "  exact secret  "
        if mutation == "disconnect":
            env.runtime.connectors.disconnect(actor, "odoo")
        elif mutation == "logout":
            env.runtime.identity.revoke(token)
        else:
            with env.engine.begin() as db:
                db.execute(
                    update(s.local_accounts)
                    .where(s.local_accounts.c.user_id == actor.id)
                    .values(disabled_at=datetime.now(timezone.utc))
                )
        return "Account"

    credentials.validate = validate
    response = env.client.post(
        "/connectors/odoo/credentials",
        headers=headers,
        json={"values": {"url": " https://local.test ", "api_key": "  exact secret  "}},
    )
    assert response.status_code in {400, 401}
    with env.engine.connect() as db:
        assert (
            db.execute(select(func.count()).select_from(s.connector_connections)).scalar_one() == 0
        )


def test_stale_connector_rotation_cannot_overwrite_a_reconnect(integration):
    env = integration
    oauth, _, vault = enable_connectors(env)
    headers, actor = identity(env, "connector-race@example.test")
    connect_oauth(env, headers)
    replacement = ConnectorConnection(
        actor.id, "quickbooks", "New company", vault.seal('{"refresh_token":"new","context":{}}')
    )

    def refresh(*_):
        env.runtime.connectors.connections.save(replacement)
        return ProviderTokens("stale", "stale-rotated", 3600)

    oauth.refresh = refresh
    response = env.client.get("/connectors/quickbooks/sources", headers=headers)
    assert response.status_code == 409
    assert (
        env.runtime.connectors.connections.get(actor.id, "quickbooks").version
        == replacement.version
    )


def test_signin_principal_uses_subject_and_receives_demo_plan(integration):
    env = integration
    google, _ = enable(env)
    sign_in(env, google, "new-selfservice@example.test", sub="stable-subject")
    result = exchange(env)
    assert set(result) == {"token"}
    headers = {"Authorization": "Bearer " + result["token"]}
    me = env.client.get("/auth/me", headers=headers).json()
    profile = env.client.get("/auth/account", headers=headers).json()
    assert profile["kind"] == "external_google" and profile["password_changed_at"] is None
    wid = workspace(env, headers)
    with env.engine.connect() as db:
        plan = (
            db.execute(select(s.workspace_plans).where(s.workspace_plans.c.workspace_id == wid))
            .mappings()
            .one()
        )
        assert plan["plan_key"] == "demo" and plan["basis"] == "native_default"
        assert db.execute(select(s.external_identities.c.subject)).scalar_one() == "stable-subject"
    # Provider email changes must not move the existing principal to another user.
    google.used.clear()
    sign_in(env, google, "changed-email@example.test", sub="stable-subject")
    again = exchange(env)
    assert (
        env.client.get("/auth/me", headers={"Authorization": "Bearer " + again["token"]}).json()[
            "id"
        ]
        == me["id"]
    )
    with pytest.raises(IngestionError):
        env.runtime.identity.provision("new-selfservice@example.test")


@pytest.mark.parametrize("origin", [None, "https://attacker.test", "null"])
def test_session_exchange_requires_exact_origin_and_does_not_consume_on_rejection(
    integration, origin
):
    env = integration
    google, _ = enable(env)
    sign_in(env, google)
    correct = env.client.headers.pop("Origin")
    response = env.client.post(
        "/auth/oauth/exchange", json={}, headers={} if origin is None else {"Origin": origin}
    )
    assert response.status_code == 403 and "token" not in response.text
    env.client.headers["Origin"] = correct
    assert set(exchange(env)) == {"token"}


def test_handoff_is_browser_bound_expires_and_cannot_resurrect_logout(integration):
    env = integration
    headers, actor = identity(env, "handoff@example.test")
    google, _ = enable(env)
    connect(env, google, headers, email=actor.email)
    browser = env.client.cookies.get(BROWSER_COOKIE)
    handoff = env.client.cookies.get(EXCHANGE_COOKIE)
    env.client.cookies.clear()
    env.client.cookies.set(EXCHANGE_COOKIE, handoff)
    env.client.cookies.set(BROWSER_COOKIE, "another-browser-" + "x" * 32)
    assert env.client.post("/auth/oauth/exchange", json={}).status_code == 400
    env.client.cookies.clear()
    # A fresh callback is necessary after losing the binding cookie.
    google.used.clear()
    connect(env, google, headers, email=actor.email)
    env.runtime.identity.revoke(headers["Authorization"].split()[1])
    assert env.client.post("/auth/oauth/exchange", json={}).status_code == 401
    assert session_count(env) == 0 and browser


def test_expired_attempts_and_handoffs_are_refused_and_old_state_is_cleaned(integration):
    env = integration
    google, _ = enable(env)
    started = env.client.get("/auth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    with env.engine.begin() as db:
        db.execute(
            update(s.oauth_attempts).values(
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=30)
            )
        )
    google.grant("old", "expired@example.test", "openid email profile")
    response = env.client.get(
        "/auth/google/callback", params={"state": state, "code": "old"}, follow_redirects=False
    )
    assert (
        response.headers["location"].endswith("oauth_error=oauth_state_invalid")
        and google.used == set()
    )
    sign_in(env, google)
    with env.engine.begin() as db:
        assert db.execute(select(func.count()).select_from(s.oauth_attempts)).scalar_one() == 1
        db.execute(
            update(s.oauth_attempts).values(
                handoff_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
            )
        )
    assert env.client.post("/auth/oauth/exchange", json={}).status_code == 400


def test_attempt_start_is_throttled_without_trusting_forwarded_addresses(integration):
    env = integration
    enable(env)
    for _ in range(5):
        assert env.client.get("/auth/google/start", follow_redirects=False).status_code == 302
    blocked = env.client.get(
        "/auth/google/start", headers={"X-Forwarded-For": "203.0.113.8"}, follow_redirects=False
    )
    assert (
        blocked.status_code == 429
        and blocked.json()["error"]["code"] == "authentication_rate_limit"
    )


def test_two_concurrent_callbacks_can_claim_one_attempt_only(integration):
    env = integration
    headers, _ = identity(env, "claim-race@example.test")
    enable(env)
    state = begin_google(env, headers)
    browser = env.client.cookies.get(BROWSER_COOKIE)

    def claim(_):
        try:
            env.runtime.oauth_state.claim(state, browser, "google", "connect")
            return "accepted"
        except IngestionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    assert sorted(results) == ["accepted", "oauth_state_invalid"]


def test_external_accounts_require_exact_invitation_and_staff_approval(integration):
    from test_workspace_integration import accept, invite

    env = integration
    google, _ = enable(env)
    sign_in(env, google, "external-teammate@example.test")
    token = exchange(env)["token"]
    actor = env.runtime.identity.authenticate(token)
    headers = {"Authorization": "Bearer " + token}
    owner, _ = identity(env, "external-owner@example.test")
    wid = workspace(env, owner)
    invitation = invite(env, owner, wid, actor.email).json()
    assert accept(env, headers, wid, invitation["id"]).status_code == 403
    approval = f"/workspaces/{wid}/invitations/{invitation['id']}/identity-approval"
    assert (
        env.client.post(
            approval, headers=owner, json={"account_id": str(actor.id), "identity_checked": True}
        ).status_code
        == 204
    )
    assert accept(env, headers, wid, invitation["id"]).status_code == 200
    with pytest.raises(IngestionError) as denied:
        env.runtime.operations.change_staff(actor.email, "admin")
    assert denied.value.code == "native_identity_check_required"
    assert (
        env.runtime.operations.change_staff(
            actor.email, "admin", confirmed_user_id=actor.id, identity_checked=True
        )["role"]
        == "admin"
    )
    with env.engine.begin() as db:
        db.execute(
            update(s.external_identities)
            .where(s.external_identities.c.user_id == actor.id)
            .values(disabled_at=datetime.now(timezone.utc))
        )
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    for call in (
        lambda: env.runtime.service.list_workspaces(actor),
        lambda: env.runtime.operations.access(actor),
    ):
        with pytest.raises(IngestionError):
            call()


def test_disabled_external_actor_cannot_use_keys_embeds_or_queued_jobs(integration):
    import asyncio
    from uuid import UUID

    from sqlalchemy import delete

    from test_integration_access_integration import exchange as open_embed
    from test_integration_access_integration import grant, issue, path, read_embed
    from test_local_accounts_integration import native_analysis

    env = integration
    headers, actor, wid, did, root, board = native_analysis(env)
    # This shared authorization fixture explicitly replaces its fictional password principal
    # with a provider subject. Actual provider registration is covered independently above.
    with env.engine.begin() as db:
        db.execute(delete(s.local_accounts).where(s.local_accounts.c.user_id == actor.id))
        db.execute(
            s.external_identities.insert().values(
                provider="google",
                subject=str(actor.id),
                user_id=actor.id,
                created_at=datetime.now(timezone.utc),
            )
        )
    key, _ = issue(env, headers, wid, did)
    embed = open_embed(env, grant(env, headers, wid, board["id"])).json()["session_secret"]
    assert read_embed(env, embed).status_code == 200
    assert env.client.post(path(root) + "/rows", headers=key, json={}).status_code == 200
    thread = env.client.post(root + "/threads", headers=headers).json()
    job = env.client.post(
        f"/workspaces/{wid}/threads/{thread['id']}/jobs",
        headers=headers,
        json={"question": "Show the first 10 records", "request_id": str(uuid4())},
    )
    assert job.status_code == 202, job.text
    with env.engine.begin() as db:
        db.execute(
            update(s.external_identities)
            .where(s.external_identities.c.user_id == actor.id)
            .values(disabled_at=datetime.now(timezone.utc))
        )
    assert env.client.post(path(root) + "/rows", headers=key, json={}).status_code in {403, 404}
    assert read_embed(env, embed).status_code in {403, 404}
    asyncio.run(env.runtime.jobs.process())
    with env.engine.connect() as db:
        stored = (
            db.execute(select(s.jobs).where(s.jobs.c.id == UUID(job.json()["id"]))).mappings().one()
        )
        assert stored["status"] == "failed" and stored["failure_code"] == "unauthorized"


@pytest.mark.parametrize("provider", ["google", "quickbooks"])
@pytest.mark.parametrize("mutation", ["disconnect", "logout", "replace"])
def test_provider_upload_commit_rechecks_after_storage_write(
    integration, monkeypatch, provider, mutation
):
    env = integration
    headers, actor = identity(env, f"commit-{provider}-{mutation}@example.test")
    if provider == "google":
        gateway, vault = enable(env)
        connect(env, gateway, headers, email=actor.email)
        service = env.runtime.google_access
    else:
        _, _, vault = enable_connectors(env)
        connect_oauth(env, headers)
        service = env.runtime.connectors
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    original = env.runtime.service.storage.put

    def replace_connection():
        if provider == "google":
            service.connections.save(
                GoogleConnection(actor.id, actor.email, DRIVE, vault.seal("new"))
            )
        else:
            service.connections.save(
                ConnectorConnection(actor.id, provider, "new", vault.seal("{}"))
            )

    def during_storage(*args, **kwargs):
        result = original(*args, **kwargs)
        if mutation == "logout":
            env.runtime.identity.revoke(headers["Authorization"].split()[1])
        elif mutation == "replace":
            replace_connection()
        elif provider == "google":
            service.disconnect(actor)
        else:
            service.disconnect(actor, provider)
        return result

    monkeypatch.setattr(env.runtime.service.storage, "put", during_storage)
    base = f"/workspaces/{wid}/datasets/{did}"
    url = base + (
        "/google-sheets/import" if provider == "google" else "/connectors/quickbooks/import"
    )
    body = {"spreadsheet_id": SHEET} if provider == "google" else {"source_id": "Invoice"}
    response = env.client.post(url, headers=headers, json=body)
    assert response.status_code in {401, 409}, response.text
    with env.engine.connect() as db:
        assert db.execute(select(func.count()).select_from(s.uploads)).scalar_one() == 0
    assert (
        env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket).get("KeyCount", 0)
        == 0
    )


def test_credential_json_is_bounded_before_authentication_or_parsing(integration):
    env = integration
    enable_connectors(env)
    for headers in (
        {"Content-Type": "application/json"},
        {"Content-Type": "application/json", "Content-Length": "1"},
    ):
        response = env.client.post(
            "/connectors/odoo/credentials",
            headers=headers,
            content=b'{"values":{"api_key":"' + b"s" * 10000 + b'"}}',
        )
        assert response.status_code == 413
        assert "ssss" not in response.text


@pytest.mark.parametrize("provider", ["google", "quickbooks"])
def test_provider_import_audit_failure_rolls_back_publication_and_retry_is_clean(
    integration, monkeypatch, provider
):
    from execplus.domain.ingestion import AuditEvent
    from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository

    env = integration
    headers, actor = identity(env, f"audit-{provider}@example.test")
    if provider == "google":
        gateway, _ = enable(env)
        connect(env, gateway, headers, email=actor.email)
    else:
        enable_connectors(env)
        connect_oauth(env, headers)
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    action = "google_sheets.imported" if provider == "google" else "connector.imported"
    original = SQLWorkspaceRepository.add

    def reject_import_audit(repo, value):
        if isinstance(value, AuditEvent) and value.action == action:
            raise IngestionError("synthetic_audit_failure", "Audit unavailable.", 503)
        return original(repo, value)

    monkeypatch.setattr(SQLWorkspaceRepository, "add", reject_import_audit)
    base = f"/workspaces/{wid}/datasets/{did}"
    url = base + (
        "/google-sheets/import" if provider == "google" else "/connectors/quickbooks/import"
    )
    body = {"spreadsheet_id": SHEET} if provider == "google" else {"source_id": "Invoice"}
    failed = env.client.post(url, headers=headers, json=body)
    assert failed.status_code == 503, failed.text
    with env.engine.connect() as db:
        assert db.execute(select(func.count()).select_from(s.uploads)).scalar_one() == 0
        assert db.execute(select(func.count()).select_from(s.revisions)).scalar_one() == 0
        assert (
            db.execute(
                select(func.count())
                .select_from(s.audit_events)
                .where(s.audit_events.c.action == action)
            ).scalar_one()
            == 0
        )
    assert (
        env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket).get("KeyCount", 0)
        == 0
    )

    monkeypatch.setattr(SQLWorkspaceRepository, "add", original)
    retried = env.client.post(url, headers=headers, json=body)
    assert retried.status_code == 201, retried.text
    with env.engine.connect() as db:
        assert db.execute(select(func.count()).select_from(s.uploads)).scalar_one() == 1
        assert db.execute(select(func.count()).select_from(s.revisions)).scalar_one() == 1
        assert (
            db.execute(
                select(func.count())
                .select_from(s.audit_events)
                .where(s.audit_events.c.action == action)
            ).scalar_one()
            == 1
        )
    assert (
        env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket).get("KeyCount", 0)
        == 1
    )
