"""Use case: Verifies native identity and private onboarding against migrated PostgreSQL.

What it does: Covers registration, credential revocation, identity approval and cross-user denial.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from execplus.domain.accounts import GUIDE_STEPS
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_workspace_integration import accept, identity, invite, workspace

PASSWORD = "fictional initial password 27"
NEXT_PASSWORD = "fictional replacement password 49"


def register(env, email="native@example.test"):
    response = env.client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Synthetic Person",
            "workspace_name": "Synthetic Workspace",
        },
    )
    assert response.status_code == 202, response.text
    return response


def login(env, email="native@example.test", password=PASSWORD):
    response = env.client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": "Bearer " + body["token"]}, body


def native(env, email="native@example.test"):
    register(env, email)
    headers, body = login(env, email)
    actor = env.runtime.identity.authenticate(body["token"])
    wid = env.client.get("/workspaces", headers=headers).json()[0]["id"]
    return headers, actor, wid, body["token"]


def test_signup_is_atomic_private_and_does_not_claim_mailbox_verification(integration):
    env = integration
    headers, actor, wid, token = native(env)
    profile = env.client.get("/auth/account", headers=headers).json()
    assert profile["kind"] == "local_password" and profile["email_verified"] is False
    assert profile["user_id"] == str(actor.id)
    assert len(token) >= 32
    with env.engine.connect() as connection:
        row = connection.execute(select(s.local_accounts)).mappings().one()
        assert PASSWORD not in row["password_hash"]
        assert (
            connection.execute(
                select(s.memberships.c.role).where(s.memberships.c.user_id == actor.id)
            ).scalar_one()
            == "owner"
        )
        assert connection.execute(select(func.count()).select_from(s.workspaces)).scalar_one() == 1
        assert token not in repr(connection.execute(select(s.sessions)).all())
    assert "password_hash" not in env.client.get("/auth/account/events", headers=headers).text
    assert env.client.get(f"/workspaces/{wid}/members", headers=headers).status_code == 200


def test_duplicate_signup_never_overwrites_native_or_operator_identity(integration):
    env = integration
    first = register(env)
    second = register(env)
    operator, actor = identity(env, "operator@example.test")
    other = register(env, actor.email)
    assert first.json() == second.json() == other.json()
    assert "token" not in first.json()
    assert env.client.get("/auth/me", headers=operator).status_code == 200
    assert (
        env.client.post(
            "/auth/login", json={"email": actor.email, "password": PASSWORD}
        ).status_code
        == 401
    )
    headers, _ = login(env)
    assert env.client.get("/workspaces", headers=headers).status_code == 200
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.local_accounts)).scalar_one() == 1
        )
        assert connection.execute(select(func.count()).select_from(s.workspaces)).scalar_one() == 1


def test_operator_provisioning_cannot_bypass_native_credentials(integration):
    env = integration
    _, actor, _, _ = native(env)
    with pytest.raises(IngestionError) as caught:
        env.runtime.identity.provision(actor.email)
    assert caught.value.code == "native_account_requires_password"


def test_unknown_bad_and_disabled_logins_have_the_same_safe_error(integration):
    env = integration
    headers, _, _, _ = native(env)
    wrong = env.client.post(
        "/auth/login", json={"email": "native@example.test", "password": NEXT_PASSWORD}
    )
    absent = env.client.post(
        "/auth/login", json={"email": "missing@example.test", "password": PASSWORD}
    )
    assert (
        env.client.post(
            "/auth/disable", headers=headers, json={"password": PASSWORD, "confirmed": True}
        ).status_code
        == 204
    )
    disabled = env.client.post(
        "/auth/login", json={"email": "native@example.test", "password": PASSWORD}
    )
    assert wrong.status_code == absent.status_code == disabled.status_code == 401
    assert wrong.json() == absent.json() == disabled.json()
    assert PASSWORD not in disabled.text and NEXT_PASSWORD not in wrong.text


def test_password_change_revokes_only_own_sessions_and_requires_current_proof(integration):
    env = integration
    headers, actor, _, old_token = native(env)
    second, _ = login(env)
    operator, _ = identity(env, "other@example.test")
    denied = env.client.post(
        "/auth/password",
        headers=headers,
        json={"current_password": NEXT_PASSWORD, "new_password": NEXT_PASSWORD},
    )
    assert denied.status_code == 401
    changed = env.client.post(
        "/auth/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": NEXT_PASSWORD},
    )
    assert changed.status_code == 200, changed.text
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    assert env.client.get("/auth/me", headers=second).status_code == 401
    assert env.client.get("/auth/me", headers=operator).status_code == 200
    replacement = {"Authorization": "Bearer " + changed.json()["token"]}
    assert env.client.get("/auth/me", headers=replacement).json()["id"] == str(actor.id)
    assert changed.json()["token"] != old_token
    assert (
        env.client.post(
            "/auth/login", json={"email": actor.email, "password": PASSWORD}
        ).status_code
        == 401
    )
    assert login(env, actor.email, NEXT_PASSWORD)[1]["user"]["id"] == str(actor.id)


def test_expiry_logout_and_bounded_sessions(integration):
    env = integration
    headers, actor, _, _ = native(env)
    with env.engine.begin() as connection:
        connection.execute(
            update(s.sessions)
            .where(s.sessions.c.user_id == actor.id)
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    for _ in range(8):
        headers, _ = login(env)
    with env.engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count()).select_from(s.sessions).where(s.sessions.c.user_id == actor.id)
            ).scalar_one()
            == 8
        )
    assert env.client.post("/auth/logout", headers=headers).status_code == 204
    assert env.client.get("/auth/me", headers=headers).status_code == 401


def test_self_asserted_email_never_claims_an_existing_invitation(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    invitation = invite(env, owner, wid, "native@example.test").json()
    headers, actor, _, _ = native(env)
    assert accept(env, headers, wid, invitation["id"]).status_code == 403
    path = f"/workspaces/{wid}/invitations/{invitation['id']}/identity-approval"
    assert (
        env.client.post(
            path, headers=headers, json={"account_id": str(actor.id), "identity_checked": True}
        ).status_code
        == 404
    )
    assert (
        env.client.post(
            path, headers=owner, json={"account_id": str(actor.id), "identity_checked": False}
        ).status_code
        == 422
    )
    assert (
        env.client.post(
            path, headers=owner, json={"account_id": str(uuid4()), "identity_checked": True}
        ).status_code
        == 404
    )
    assert (
        env.client.post(
            path, headers=owner, json={"account_id": str(actor.id), "identity_checked": True}
        ).status_code
        == 204
    )
    assert accept(env, headers, wid, invitation["id"]).status_code == 200


def test_email_only_native_staff_grants_are_forbidden(integration):
    env = integration
    _, actor, _, _ = native(env)
    with pytest.raises(IngestionError) as caught:
        env.runtime.operations.change_staff(actor.email, "admin")
    assert caught.value.code == "native_identity_check_required"
    with pytest.raises(IngestionError):
        env.runtime.operations.change_staff(
            actor.email, "admin", confirmed_user_id=uuid4(), identity_checked=True
        )
    grant = env.runtime.operations.change_staff(
        actor.email, "admin", confirmed_user_id=actor.id, identity_checked=True
    )
    assert grant["role"] == "admin"
    assert env.runtime.operations.change_staff(actor.email, None)["revoked"]


def test_disabled_actor_cannot_use_retained_service_object_to_create_or_read(integration):
    env = integration
    headers, actor, wid, _ = native(env)
    env.runtime.accounts.disable(actor, PASSWORD, True, "testclient")
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    for call in (
        lambda: env.runtime.service.list_workspaces(actor),
        lambda: env.runtime.service.list_members(actor, UUID(wid)),
        lambda: env.runtime.service.create_workspace(actor, "Bypass", 3),
        lambda: env.runtime.organizations.create(actor, "Bypass"),
        lambda: env.runtime.organizations.list(actor),
        lambda: env.runtime.accounts.guide(actor, UUID(wid)),
        lambda: env.runtime.operations.access(actor),
    ):
        with pytest.raises(IngestionError):
            call()


def test_operator_recovery_requires_explicit_checked_identity_and_retains_disable(integration):
    env = integration
    headers, actor, _, _ = native(env)
    with pytest.raises(IngestionError):
        env.runtime.accounts.recover(actor.id, NEXT_PASSWORD, identity_checked=False)
    env.runtime.accounts.disable(actor, PASSWORD, True, "testclient")
    env.runtime.accounts.recover(actor.id, NEXT_PASSWORD, identity_checked=True)
    assert (
        env.client.post(
            "/auth/login", json={"email": actor.email, "password": NEXT_PASSWORD}
        ).status_code
        == 401
    )
    env.runtime.accounts.recover(actor.id, NEXT_PASSWORD, identity_checked=True, reenable=True)
    restored, _ = login(env, actor.email, NEXT_PASSWORD)
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    events = env.client.get("/auth/account/events", headers=restored).json()["events"]
    assert {event["action"] for event in events} >= {
        "account.disabled",
        "account.recovered",
        "account.enabled",
    }


def test_rate_admission_is_atomic_under_concurrency(integration):
    now = datetime.now(timezone.utc)
    store = integration.runtime.accounts.store
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(
            pool.map(
                lambda _: store.consume_auth_attempt(
                    "login", "same-synthetic@example.test", "synthetic-peer", now
                ),
                range(20),
            )
        )
    assert sum(results) == 10
    assert store.consume_auth_attempt(
        "login", "same-synthetic@example.test", "synthetic-peer", now + timedelta(minutes=16)
    )
    with integration.engine.connect() as connection:
        assert "same-synthetic" not in repr(
            connection.execute(select(s.account_rate_windows)).all()
        )


def test_guide_is_private_versioned_resumable_and_does_not_invent_completed_steps(integration):
    env = integration
    headers, _actor, wid, _ = native(env)
    path = f"/workspaces/{wid}/onboarding-progress"
    initial = env.client.get(path, headers=headers).json()
    assert initial["version"] == 0
    assert sum(step["observed"] for step in initial["steps"]) == 1
    body = {
        "expected_version": 0,
        "active_step": "meaning",
        "skipped_steps": ["data"],
        "paused": True,
        "finished": False,
    }
    saved = env.client.put(path, headers=headers, json=body)
    assert saved.status_code == 200 and saved.json()["version"] == 1
    assert env.client.put(path, headers=headers, json=body).status_code == 409
    assert env.client.get(path, headers=headers).json()["paused"] is True
    body.update(expected_version=1, paused=False, finished=True)
    assert env.client.put(path, headers=headers, json=body).status_code == 422
    body["skipped_steps"] = list(GUIDE_STEPS[1:])
    finished = env.client.put(path, headers=headers, json=body)
    assert finished.status_code == 200 and finished.json()["finished"] is True
    assert sum(step["observed"] for step in finished.json()["steps"]) == 1
    stranger, _ = identity(env, "stranger@example.test")
    assert env.client.get(path, headers=stranger).status_code == 404
    assert (
        env.client.put(path, headers=stranger, json={**body, "expected_version": 2}).status_code
        == 404
    )
    assert env.client.get("/auth/account/events", headers=stranger).json()["events"] == []
    with env.engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(s.uploads)).scalar_one() == 0
        assert (
            connection.execute(select(func.count()).select_from(s.analysis_runs)).scalar_one() == 0
        )


def test_teammate_guide_does_not_reveal_owner_progress(integration):
    env = integration
    owner, _owner_actor = identity(env, "owner@example.test")
    teammate, teammate_actor = identity(env, "member@example.test")
    wid = workspace(env, owner)
    invitation = invite(env, owner, wid, teammate_actor.email).json()
    assert accept(env, teammate, wid, invitation["id"]).status_code == 200
    path = f"/workspaces/{wid}/onboarding-progress"
    body = {
        "expected_version": 0,
        "active_step": "meaning",
        "skipped_steps": ["quality"],
        "paused": True,
        "finished": False,
    }
    assert env.client.put(path, headers=teammate, json=body).status_code == 200
    assert env.client.get(path, headers=owner).json()["version"] == 0
    assert (
        env.client.delete(
            f"/workspaces/{wid}/members/{teammate_actor.id}", headers=owner
        ).status_code
        == 204
    )
    assert env.client.get(path, headers=teammate).status_code == 404
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.onboarding_progress)).scalar_one()
            == 0
        )


def test_signup_failure_rolls_back_identity_and_workspace_together(integration, monkeypatch):
    from execplus.infrastructure.persistence.accounts import SQLAccountRepository

    env = integration

    def fail(*args, **kwargs):
        raise IngestionError("synthetic_failure", "Synthetic plan failure", 503)

    monkeypatch.setattr(SQLAccountRepository, "initialize_native_workspace_plan", fail)
    with pytest.raises(IngestionError):
        env.runtime.accounts.register(
            "rollback@example.test", PASSWORD, "Person", "Workspace", "testclient"
        )
    with env.engine.connect() as connection:
        for table in (s.users, s.workspaces, s.memberships, s.local_accounts, s.account_events):
            assert connection.execute(select(func.count()).select_from(table)).scalar_one() == 0


def test_same_email_concurrent_signup_creates_only_one_owned_workspace(integration):
    env = integration
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                env.runtime.accounts.register,
                "concurrent@example.test",
                PASSWORD,
                "Person",
                "Workspace",
                "testclient",
            )
            for _ in range(2)
        ]
        for future in futures:
            assert future.result() is None
    with env.engine.connect() as connection:
        for table in (s.users, s.workspaces, s.memberships, s.local_accounts):
            assert connection.execute(select(func.count()).select_from(table)).scalar_one() == 1


def test_registration_switch_origin_guard_and_safe_errors(integration):
    env = integration
    options = env.client.get("/auth/options").json()
    assert options["local_registration_enabled"] is True
    raw = {
        "email": "guard@example.test",
        "password": PASSWORD,
        "display_name": "Person",
        "workspace_name": "Workspace",
    }
    assert (
        env.client.post(
            "/auth/register", headers={"Origin": "https://other.test"}, json=raw
        ).status_code
        == 403
    )
    malformed = env.client.post("/auth/register", json={**raw, "secret_field": PASSWORD})
    assert malformed.status_code == 422 and PASSWORD not in malformed.text
    wrong_unicode = env.client.post(
        "/auth/register",
        content=json_bytes({**raw, "display_name": "\ud800"}),
        headers={"Content-Type": "application/json"},
    )
    assert wrong_unicode.status_code == 422
    env.runtime.accounts.registration_enabled = False
    assert env.client.get("/auth/options").json()["local_registration_enabled"] is False
    assert env.client.post("/auth/register", json=raw).status_code == 403
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.local_accounts)).scalar_one() == 0
        )


def json_bytes(value):
    import json

    return json.dumps(value, ensure_ascii=True).encode()


def native_analysis(env):
    from test_studies import run
    from test_understanding import confirm, context
    from test_workspace_integration import dataset, upload

    headers, actor, wid, _ = native(env)
    did = dataset(env, headers, wid)
    uploaded = upload(
        env, headers, wid, did, b"city,amount,cost\nNorth,0.10,0.05\nSouth,0.20,0.15\n"
    )
    assert uploaded.status_code == 201
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uploaded.json()['id']}"
    meaning = context(env, headers, root)
    for column in meaning["definition"]["columns"]:
        if column["role"] == "metric":
            column["unit"] = "USD"
    assert confirm(env, headers, root, meaning).status_code == 201
    study = run(env, headers, root)
    assert study.status_code == 201, study.text
    value = study.json()
    assert (
        env.client.patch(
            f"/workspaces/{wid}/studies/{value['study']['id']}",
            headers=headers,
            json={"shared": True},
        ).status_code
        == 204
    )
    board = env.client.post(
        f"/workspaces/{wid}/study-boards",
        headers=headers,
        json={"name": "Native verified board", "shared": True, "pins": [value["version"]["id"]]},
    )
    assert board.status_code == 201, board.text
    return headers, actor, wid, did, root, board.json()


@pytest.mark.parametrize("action", ["password", "disable"])
def test_credential_change_revokes_scoped_keys_embeds_and_only_own_access(integration, action):
    from test_integration_access_integration import exchange, grant, issue, path, read_embed

    env = integration
    headers, actor, wid, did, root, board = native_analysis(env)
    key_headers, issued = issue(env, headers, wid, did)
    embed = grant(env, headers, wid, board["id"])
    opened = exchange(env, embed)
    assert opened.status_code == 200, opened.text
    embed_session = opened.json()["session_secret"]
    assert read_embed(env, embed_session).status_code == 200
    assert env.client.post(path(root) + "/rows", headers=key_headers, json={}).status_code == 200
    other_headers, _ = identity(env, "preserved-other@example.test")
    if action == "password":
        env.runtime.accounts.change_password(actor, PASSWORD, NEXT_PASSWORD, "testclient")
    else:
        env.runtime.accounts.disable(actor, PASSWORD, True, "testclient")
    assert env.client.post(path(root) + "/rows", headers=key_headers, json={}).status_code in {
        403,
        404,
    }
    assert read_embed(env, embed_session).status_code in {403, 404}
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    assert env.client.get("/auth/me", headers=other_headers).status_code == 200
    with env.engine.connect() as connection:
        assert (
            connection.execute(
                select(s.integration_keys.c.revoked_at).where(
                    s.integration_keys.c.id == UUID(issued["key"]["id"])
                )
            ).scalar_one()
            is not None
        )
        assert (
            connection.execute(
                select(s.embed_grants.c.revoked_at).where(
                    s.embed_grants.c.id == UUID(embed["grant"]["id"])
                )
            ).scalar_one()
            is not None
        )


def test_disable_during_customer_query_prevents_answer_publication(integration, monkeypatch):
    from test_integration_access_integration import issue, path

    env = integration
    headers, actor, wid, did, root, _ = native_analysis(env)
    key, _ = issue(env, headers, wid, did)
    original = env.runtime.analytics.run_query

    async def disable_after_calculation(*args, **kwargs):
        value = await original(*args, **kwargs)
        env.runtime.accounts.disable(actor, PASSWORD, True, "testclient")
        return value

    monkeypatch.setattr(env.runtime.analytics, "run_query", disable_after_calculation)
    response = env.client.post(
        path(root) + "/query", headers=key, json={"metric": "amount", "aggregation": "sum"}
    )
    assert response.status_code in {403, 404}, response.text
    assert "0.30" not in response.text and "North" not in response.text


def test_disabled_owner_cannot_execute_a_previously_queued_job(integration):
    import asyncio

    env = integration
    headers, actor, wid, _, root, _ = native_analysis(env)
    thread = env.client.post(root + "/threads", headers=headers).json()
    job = env.client.post(
        f"/workspaces/{wid}/threads/{thread['id']}/jobs",
        headers=headers,
        json={"question": "Show the first 10 records", "request_id": str(uuid4())},
    )
    assert job.status_code == 202, job.text
    env.runtime.accounts.disable(actor, PASSWORD, True, "testclient")
    asyncio.run(env.runtime.jobs.process())
    with env.engine.connect() as connection:
        stored = (
            connection.execute(select(s.jobs).where(s.jobs.c.id == UUID(job.json()["id"])))
            .mappings()
            .one()
        )
        assert stored["status"] == "failed"
        assert stored["failure_code"] == "unauthorized"
        failed_turn = (
            connection.execute(
                select(s.thread_turns).where(s.thread_turns.c.job_id == stored["id"])
            )
            .mappings()
            .one()
        )
        assert failed_turn["status"] == "failed" and failed_turn["query_id"] is None
        assert set(failed_turn["evidence"]) <= {"access_reference"}


def test_staff_scope_rechecks_revocation_before_releasing_results_and_rolls_back(integration):
    from execplus.domain.ingestion import AuditEvent

    env = integration
    _, actor, wid, _ = native(env)
    env.runtime.operations.change_staff(
        actor.email, "admin", confirmed_user_id=actor.id, identity_checked=True
    )
    with (
        pytest.raises(IngestionError) as caught,
        env.runtime.operations.staff_scope(
            actor, "synthetic.staff_read", workspace_id=UUID(wid), admin=True
        ) as repo,
    ):
        repo.workspace(UUID(wid), lock=True)
        repo.require_active_actor(actor.id)
        repo.add(
            AuditEvent(
                uuid4(),
                UUID(wid),
                actor.id,
                "synthetic.unpublished",
                "workspace",
                UUID(wid),
                datetime.now(timezone.utc),
            )
        )
        env.runtime.operations.change_staff(actor.email, None)
    assert caught.value.code == "staff_required"
    with env.engine.connect() as connection:
        assert (
            connection.execute(
                select(s.audit_events.c.id).where(
                    s.audit_events.c.action == "synthetic.unpublished"
                )
            ).first()
            is None
        )
        assert (
            connection.execute(
                select(s.staff_audit.c.id).where(
                    s.staff_audit.c.action == "synthetic.staff_read",
                    s.staff_audit.c.outcome == "success",
                )
            ).first()
            is None
        )


def test_native_staff_role_change_and_disable_do_not_invert_workspace_account_locks(
    integration, monkeypatch
):
    from threading import Event

    from execplus.infrastructure.persistence.accounts import SQLAccountRepository

    env = integration
    _, actor, wid, _ = native(env)
    env.runtime.operations.change_staff(
        actor.email, "admin", confirmed_user_id=actor.id, identity_checked=True
    )
    started, release, disabling = Event(), Event(), Event()
    original_lock = SQLAccountRepository.lock_account_workspaces

    def begin_disable(self, user_id):
        disabling.set()
        return original_lock(self, user_id)

    monkeypatch.setattr(SQLAccountRepository, "lock_account_workspaces", begin_disable)

    def staff_read():
        with env.runtime.operations.staff_scope(
            actor, "synthetic.staff_read", workspace_id=UUID(wid)
        ) as repo:
            repo.workspace(UUID(wid), lock=True)
            started.set()
            if not release.wait(15):
                raise AssertionError("Synthetic release timed out")
        return True

    with ThreadPoolExecutor(max_workers=3) as pool:
        active = pool.submit(staff_read)
        assert started.wait(5)
        try:
            changed = pool.submit(
                env.runtime.operations.change_staff,
                actor.email,
                "support",
                confirmed_user_id=actor.id,
                identity_checked=True,
            )
            assert changed.result(timeout=5)["role"] == "support"
            disabled = pool.submit(
                env.runtime.accounts.disable, actor, PASSWORD, True, "testclient"
            )
            assert disabling.wait(5)
            assert not disabled.done()
        finally:
            release.set()
        assert active.result(timeout=10)
        assert disabled.result(timeout=10) is None
    with pytest.raises(IngestionError):
        env.runtime.operations.access(actor)


@pytest.mark.parametrize("operation", ["create", "revoke"])
def test_disable_serializes_with_credential_creation_and_revocation(
    integration, monkeypatch, operation
):
    from threading import Event

    from execplus.infrastructure.persistence.accounts import SQLAccountRepository
    from execplus.infrastructure.persistence.integrations import SQLIntegrationRepository

    env = integration
    _, actor, wid, _ = native(env)
    did = env.runtime.service.create_dataset(actor, UUID(wid), "Synthetic source").id
    service = env.runtime.integration_access
    existing = (
        service.create_key(actor, UUID(wid), "Synthetic key", (did,), ("rows:read",), 3600)
        if operation == "revoke"
        else None
    )
    started, release, disabling = Event(), Event(), Event()
    original_lock = SQLAccountRepository.lock_account_workspaces

    def begin_disable(self, user_id):
        disabling.set()
        return original_lock(self, user_id)

    monkeypatch.setattr(SQLAccountRepository, "lock_account_workspaces", begin_disable)
    method = "add_integration_key" if operation == "create" else "update_integration_key"
    original = getattr(SQLIntegrationRepository, method)

    def blocked(self, value):
        started.set()
        if not release.wait(15):
            raise AssertionError("Synthetic credential release timed out")
        return original(self, value)

    monkeypatch.setattr(SQLIntegrationRepository, method, blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        if operation == "create":
            credential = pool.submit(
                service.create_key, actor, UUID(wid), "Synthetic key", (did,), ("rows:read",), 3600
            )
        else:
            credential = pool.submit(service.revoke_key, actor, UUID(wid), existing["key"]["id"])
        assert started.wait(5)
        try:
            disable = pool.submit(env.runtime.accounts.disable, actor, PASSWORD, True, "testclient")
            assert disabling.wait(5)
            assert not disable.done()
        finally:
            release.set()
        credential.result(timeout=10)
        disable.result(timeout=10)
    with env.engine.connect() as connection:
        assert (
            connection.execute(
                select(s.integration_keys.c.revoked_at).where(
                    s.integration_keys.c.user_id == actor.id
                )
            ).scalar_one()
            is not None
        )


@pytest.mark.parametrize("operation", ["create", "list"])
def test_disable_and_join_path_operations_do_not_invert_account_workspace_locks(
    integration, monkeypatch, operation
):
    import asyncio
    from threading import Event, local

    from execplus.infrastructure.persistence.accounts import SQLAccountRepository
    from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository

    env = integration
    _, actor, wid, _ = native(env)
    left = env.runtime.service.create_dataset(actor, UUID(wid), "Synthetic left").id
    right = env.runtime.service.create_dataset(actor, UUID(wid), "Synthetic right").id
    locked, join_started = Event(), Event()
    thread = local()
    original_locks = SQLAccountRepository.lock_account_workspaces
    original_workspace = SQLWorkspaceRepository.workspace

    def hold_workspaces(self, user_id):
        original_locks(self, user_id)
        locked.set()
        if not join_started.wait(10):
            raise AssertionError("Synthetic join did not request its workspace")

    def workspace_lock(self, workspace_id, *, lock=False):
        if lock and getattr(thread, "joining", False):
            join_started.set()
        return original_workspace(self, workspace_id, lock=lock)

    monkeypatch.setattr(SQLAccountRepository, "lock_account_workspaces", hold_workspaces)
    monkeypatch.setattr(SQLWorkspaceRepository, "workspace", workspace_lock)

    def join_operation():
        thread.joining = True
        action = (
            env.runtime.joins.create_join_path(actor, UUID(wid), left, "key", right, "key")
            if operation == "create"
            else env.runtime.joins.list_join_paths(actor, UUID(wid))
        )
        return asyncio.run(action)

    with ThreadPoolExecutor(max_workers=2) as pool:
        disabled = pool.submit(env.runtime.accounts.disable, actor, PASSWORD, True, "testclient")
        assert locked.wait(5)
        joined = pool.submit(join_operation)
        disabled.result(timeout=15)
        with pytest.raises(IngestionError) as caught:
            joined.result(timeout=15)
    assert caught.value.status == 403
