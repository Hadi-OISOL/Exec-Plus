"""Use case: Verifies local product allowances without billing or external calls.

What it does: Exercises real stock and operation concurrency, native defaults,
private summaries, exact receipt replay and immutable administrator history.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from execplus.application.services.plans import admit
from execplus.domain.ingestion import IngestionError
from execplus.domain.plans import DEMO, checked_limits, checked_period
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.accounts import SQLAccountRepository
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from test_local_accounts_integration import PASSWORD, native
from test_studies import add_member, prepare, run
from test_workspace_integration import identity, invite, upload, workspace


def assign(env, actor, wid, **limits):
    env.runtime.operations.change_staff(
        actor.email, "admin", confirmed_user_id=actor.id, identity_checked=True
    )
    service = env.runtime.plans
    key = "fixture-" + uuid4().hex[:12]
    service.configure(actor, key, "Synthetic local allowance", {**DEMO, **limits}, 0)
    before = service.assigned(actor, UUID(wid))
    start = datetime.now(timezone.utc) - timedelta(seconds=1)
    return service.assign(
        actor, UUID(wid), key, before["version"] if before else 0, start, start + timedelta(days=30)
    )


@pytest.mark.parametrize(
    "bad", [{}, {**DEMO, "seats": True}, {**DEMO, "exports": -1}, {**DEMO, "datasets": 1.5}]
)
def test_catalog_rejects_unsafe_or_incomplete_limits(bad):
    with pytest.raises(IngestionError):
        checked_limits(bad)


def test_period_requires_aware_bounded_nonempty_interval():
    now = datetime.now(timezone.utc)
    for start, end in (
        (now, now),
        (now, now + timedelta(days=367)),
        (now.replace(tzinfo=None), now),
    ):
        with pytest.raises(IngestionError):
            checked_period(start, end)


def test_native_workspaces_receive_explicit_demo_and_legacy_keeps_prior_behavior(integration):
    env = integration
    headers, _actor, wid, _ = native(env)
    summary = env.client.get(f"/workspaces/{wid}/plan", headers=headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["assignment"]["basis"] == "native_default"
    assert summary.json()["allowances"]["seats"]["remaining"] == 4
    another = workspace(env, headers)
    assert (
        env.client.get(f"/workspaces/{another}/plan", headers=headers).json()["assignment"][
            "plan_key"
        ]
        == "demo"
    )
    old_headers, _ = identity(env, "legacy-plan@example.test")
    old = workspace(env, old_headers)
    assert (
        env.client.get(f"/workspaces/{old}/plan", headers=old_headers).json()["assignment"] is None
    )
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.workspace_plans)).scalar_one()
            == 2
        )
        assert (
            connection.execute(
                select(func.count())
                .select_from(s.audit_events)
                .where(s.audit_events.c.action == "plan.default_assigned")
            ).scalar_one()
            == 2
        )


def test_resource_limits_are_atomic_under_concurrency_and_lowering_retains_data(integration):
    env = integration
    headers, actor, wid, _, _, _ = prepare(env)
    assign(env, actor, wid, datasets=2)

    def create(index):
        try:
            return env.runtime.service.create_dataset(actor, UUID(wid), f"Synthetic {index}").id
        except IngestionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(create, range(6)))
    assert results.count("plan_limit") == 5
    assign(env, actor, wid, datasets=0)
    assert len(env.client.get(f"/workspaces/{wid}/datasets", headers=headers).json()) == 2
    summary = env.client.get(f"/workspaces/{wid}/plan", headers=headers).json()
    assert summary["allowances"]["datasets"] == {
        "limit": 0,
        "used": 2,
        "remaining": 0,
        "basis": "current_resources",
    }


def test_seat_file_storage_and_study_allowances_are_backend_enforced(integration):
    env = integration
    headers, actor, wid, did, _, root = prepare(env)
    assign(env, actor, wid, seats=1, file_bytes=5, saved_studies=0)
    assert invite(env, headers, wid, "invited-plan@example.test").status_code == 429
    assert upload(env, headers, wid, did).status_code == 429
    assert run(env, headers, root).status_code == 429
    with env.engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(s.uploads)).scalar_one() == 1
        assert connection.execute(select(func.count()).select_from(s.studies)).scalar_one() == 0
    assign(env, actor, wid, storage_bytes=0)
    assert upload(env, headers, wid, did).status_code == 429


def test_operation_admission_is_atomic_idempotent_private_and_period_bound(integration):
    env = integration
    headers, actor, wid, _, _, _ = prepare(env)
    assignment = assign(env, actor, wid, exports=2)
    uow = SQLUnitOfWork(env.engine)

    def attempt(identifier, body="synthetic"):
        try:
            with uow() as repo:
                return admit(repo, actor, UUID(wid), "exports", identifier, body)
        except IngestionError as error:
            return error.code

    identifier = uuid4()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: attempt(identifier), range(4)))
    assert results.count(True) == 1 and results.count(False) == 3
    assert attempt(identifier, "different") == "plan_request_conflict"
    assert attempt(uuid4()) is True and attempt(uuid4()) == "plan_limit"
    key = assignment["plan_key"]
    # Same-period assignment does not reset already admitted operations.
    env.runtime.plans.assign(
        actor, UUID(wid), key, 1, assignment["starts_at"], assignment["ends_at"]
    )
    assert attempt(uuid4()) == "plan_limit"
    end = datetime.now(timezone.utc) - timedelta(seconds=1)
    env.runtime.plans.assign(actor, UUID(wid), key, 2, end - timedelta(days=1), end)
    assert attempt(uuid4()) == "plan_expired"
    assert attempt(identifier) is False
    with env.engine.connect() as connection:
        rows = list(connection.execute(select(s.plan_admissions)).mappings())
    assert len(rows) == 2 and all("synthetic" not in repr(row) for row in rows)
    member, _ = add_member_after_allowance(env, headers, wid)
    assert env.client.get(f"/workspaces/{wid}/plan", headers=member).status_code == 403


def add_member_after_allowance(env, headers, wid):
    # Expired plans deliberately block new invitations; use a separate legacy owner setup instead.
    with SQLUnitOfWork(env.engine)() as repo:
        owner = repo.user(repo.members(UUID(wid))[0].user_id)
    assign(env, owner, wid)
    return add_member(env, headers, wid)


def test_query_caps_keep_exact_saved_receipts_readable_and_do_not_charge_replay(integration):
    env = integration
    headers, actor, wid, _, _, root = prepare(env)
    result = run(env, headers, root)
    assert result.status_code == 201, result.text
    query = result.json()["version"]["evidence"]["query_ids"][0]
    assign(env, actor, wid, processing=0)
    assert run(env, headers, root).status_code == 429
    replay = env.client.post(f"/workspaces/{wid}/queries/{query}/replay", headers=headers)
    assert replay.status_code == 200, replay.text
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.plan_admissions)).scalar_one()
            == 0
        )


def test_customer_cannot_configure_assign_or_read_another_workspace_plan(integration):
    env = integration
    headers, actor, wid, _, _, _ = prepare(env)
    other_headers, _ = identity(env, "unrelated-plan@example.test")
    other_wid = workspace(env, other_headers)
    assert env.client.get(f"/workspaces/{other_wid}/plan", headers=headers).status_code == 404
    assert env.client.get(f"/admin/workspaces/{wid}/plan", headers=headers).status_code == 403
    body = {"expected_version": 0, "name": "Not authorized", "limits": DEMO}
    assert env.client.put("/admin/plans/owner-plan", headers=headers, json=body).status_code == 403
    assign(env, actor, wid)
    bad = {**body, "limits": {**DEMO, "seats": True}}
    assert env.client.put("/admin/plans/bad-plan", headers=headers, json=bad).status_code == 422
    assert (
        env.client.get("/plans", headers={**headers, "Idempotency-Key": "private text"}).status_code
        == 422
    )


def test_native_disable_and_usage_operator_controls_keep_workspace_first_lock_order(
    integration, monkeypatch
):
    from execplus.infrastructure.persistence.usage_metering import SQLUsageRepository

    env = integration
    _, actor, wid, _ = native(env)
    env.runtime.operations.change_staff(
        actor.email, "admin", confirmed_user_id=actor.id, identity_checked=True
    )
    locked, proceed, attempted, guarded = Event(), Event(), Event(), Event()
    original_accounts = SQLAccountRepository.lock_account_workspaces
    original_workspace = SQLUsageRepository.lock_workspace
    original_guard = SQLUsageRepository.require_operator

    def account_locks(repo, user_id):
        original_accounts(repo, user_id)
        locked.set()
        assert proceed.wait(5)

    def usage_workspace(repo, workspace_id):
        attempted.set()
        original_workspace(repo, workspace_id)

    def usage_guard(repo, user_id):
        guarded.set()
        original_guard(repo, user_id)

    monkeypatch.setattr(SQLAccountRepository, "lock_account_workspaces", account_locks)
    monkeypatch.setattr(SQLUsageRepository, "lock_workspace", usage_workspace)
    monkeypatch.setattr(SQLUsageRepository, "require_operator", usage_guard)
    with ThreadPoolExecutor(max_workers=2) as pool:
        disabled = pool.submit(
            env.runtime.accounts.disable, actor, PASSWORD, True, "synthetic-test"
        )
        assert locked.wait(5)
        pending = pool.submit(env.runtime.usage_metering.pending, actor.id, UUID(wid))
        assert attempted.wait(5)
        try:
            assert not guarded.is_set()
        finally:
            proceed.set()
        disabled.result(timeout=5)
        with pytest.raises(IngestionError):
            pending.result(timeout=5)


def test_upload_processing_admission_precedes_parser_and_rejected_stock_is_uncharged(
    integration, monkeypatch
):
    env = integration
    headers, actor, wid, did, _, _ = prepare(env)
    assign(env, actor, wid, processing=0)
    calls = []
    monkeypatch.setattr(
        env.runtime.service.parser, "parse", lambda *args, **kwargs: calls.append(True)
    )
    response = upload(env, headers, wid, did)
    assert response.status_code == 429, response.text
    assert calls == []
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.plan_admissions)).scalar_one()
            == 0
        )


def test_forecast_retry_reuses_one_vintage_and_rejects_changed_inputs(integration):
    from test_forecast_integration import daily, request

    env = integration
    headers, actor, wid, _, _, root = prepare(env, daily())
    assign(env, actor, wid, forecasts=1)
    key = {**headers, "Idempotency-Key": str(uuid4())}
    body = request(env, headers, root)
    first = env.client.post(root + "/forecasts", headers=key, json=body)
    assert first.status_code == 201, first.text
    second = env.client.post(root + "/forecasts", headers=key, json=body)
    assert second.status_code == 201, second.text
    assert first.json() == second.json()
    changed = env.client.post(
        root + "/forecasts", headers=key, json={**body, "name": "Changed retry"}
    )
    assert changed.status_code == 409, changed.text
    assert env.client.post(root + "/forecasts", headers=headers, json=body).status_code == 429
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.forecast_runs)).scalar_one() == 1
        )
        assert (
            connection.execute(
                select(func.count())
                .select_from(s.plan_admissions)
                .where(s.plan_admissions.c.kind == "forecasts")
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("format", ["pdf", "xlsx", "csv", "png"])
def test_export_admission_preserves_authorization_and_retry_counting(integration, format):
    from test_pdf_exports import setup

    env = integration
    owner, actor, wid, _, _, _, url, _ = setup(env, grouped=True)
    assign(env, actor, wid, exports=1)
    key = {**owner, "Idempotency-Key": str(uuid4())}
    path = url.replace(".pdf", "." + format)
    first = env.client.get(path, headers=key)
    assert first.status_code == 200, first.text
    assert env.client.get(path, headers=key).status_code == 200
    assert env.client.get(path, headers=owner).status_code == 429
    member, _ = add_member(env, owner, wid)
    assert env.client.get(path, headers=member).status_code in {403, 404}
    with env.engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(s.plan_admissions)
                .where(s.plan_admissions.c.kind == "exports")
            ).scalar_one()
            == 1
        )


def test_plan_model_allowance_is_in_same_transaction_as_existing_financial_ledger(
    integration, monkeypatch
):
    from execplus.domain.usage_metering import UsageAttribution

    env = integration
    _, actor, wid, _, _, _ = prepare(env)
    assign(env, actor, wid, model_attempts=1)
    scope = UsageAttribution(UUID(wid), actor.id, uuid4(), "conversation")
    service = env.runtime.usage_metering
    identifier = uuid4()

    def reserve():
        return service.reserve(scope, identifier, "fixture-only", "no-provider-call")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: reserve(), range(4)))
    assert all(value.id == identifier for value in results)
    with pytest.raises(IngestionError) as caught:
        service.reserve(scope, uuid4(), "fixture-only", "no-provider-call")
    assert caught.value.code == "plan_limit"
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.usage_attempts)).scalar_one() == 1
        )
        assert (
            connection.execute(
                select(func.count())
                .select_from(s.plan_admissions)
                .where(s.plan_admissions.c.kind == "model_attempts")
            ).scalar_one()
            == 1
        )


def test_api_keys_cannot_bypass_compute_caps_but_authorized_embed_receipts_remain_readable(
    integration,
):
    from test_integration_access_integration import exchange, grant, issue, path, read_embed, shared

    env = integration
    owner, actor, wid, did, root, _, board = shared(env)
    key, _ = issue(env, owner, wid, did)
    token = grant(env, owner, wid, board["id"])
    session = exchange(env, token).json()["session_secret"]
    assign(env, actor, wid, processing=0)
    denied = env.client.post(
        path(root) + "/query", headers=key, json={"metric": "amount", "aggregation": "sum"}
    )
    assert denied.status_code == 429, denied.text
    assert read_embed(env, session).status_code == 200
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.plan_admissions)).scalar_one()
            == 0
        )


def test_consolidation_export_admissions_rollback_when_one_company_is_at_cap(integration):
    from test_company_consolidation_integration import create, fixture

    env = integration
    owner, actor, _, path, body, _, _ = fixture(env)
    value = create(env, owner, path, body)
    companies = sorted(body["companies"], key=lambda item: item["workspace_id"])
    assign(env, actor, companies[0]["workspace_id"], exports=1)
    assign(env, actor, companies[1]["workspace_id"], exports=0)
    denied = env.client.get(path + "/" + value["run"]["id"] + "/export.pdf", headers=owner)
    assert denied.status_code == 429, denied.text
    with env.engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(s.plan_admissions)
                .where(s.plan_admissions.c.kind == "exports")
            ).scalar_one()
            == 0
        )


def test_malformed_idempotency_key_keeps_exact_origin_and_safe_error(integration):
    env = integration
    headers, _ = identity(env, "header-plan@example.test")
    for origin, expected in (
        ("http://localhost:3000", "http://localhost:3000"),
        ("https://untrusted.example.test", None),
    ):
        result = env.client.get(
            "/plans", headers={**headers, "Origin": origin, "Idempotency-Key": "not an opaque UUID"}
        )
        assert result.status_code == 422 and result.json()["error"]["code"] == "idempotency_key"
        assert result.headers.get("access-control-allow-origin") == expected
        assert "not an opaque UUID" not in result.text
        assert "x-request-id" in result.headers
