"""Use case: Checks model admission and accounting with real concurrent SQL transactions.

What it does: Verifies no quota oversubscription, duplicate charges or hidden-usage
disclosure, and preserves accounting evidence through migration boundaries.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from execplus.application.services import usage_metering as service_module
from execplus.application.services.usage_metering import UsageMeteringService
from execplus.domain.ingestion import IngestionError
from execplus.domain.usage_metering import TokenUsage
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.usage_metering import SQLUsageUnitOfWork
from test_studies import add_member, prepare
from test_usage_metering import NOW, attribution, policy, price


def configured(env, monkeypatch, **limits):
    owner, actor, wid, did, uid, root = prepare(env)
    env.runtime.operations.change_staff(actor.email, "admin")
    service = UsageMeteringService(SQLUsageUnitOfWork(env.engine))
    monkeypatch.setattr(service_module, "now", lambda: NOW)
    rate = price(created_by=actor.id)
    allowance = policy(workspace_id=UUID(wid), created_by=actor.id, **limits)
    service.set_price(actor.id, rate)
    service.set_policy(actor.id, allowance, 0)
    scope = attribution(workspace_id=UUID(wid), actor_id=actor.id)
    return service, owner, actor, wid, did, uid, root, scope, allowance


def reserve(service, scope, attempt_id=None):
    return service.reserve(scope, attempt_id or uuid4(), "test-provider", "fictional-model")


def test_concurrent_provider_admission_cannot_oversubscribe_allowances(integration, monkeypatch):
    service, _, _, _, _, _, _, scope, _ = configured(integration, monkeypatch, max_attempts=3)

    def competing():
        try:
            return reserve(service, scope)
        except IngestionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda _: competing(), range(6)))
    attempts = [value for value in results if not isinstance(value, str)]
    assert len(attempts) == 2 and results.count("usage_concurrency") == 4
    for value in attempts:
        service.start(scope, value.id)
        service.finish(scope, value.id, "succeeded", TokenUsage(10, 5, 0))
    final = reserve(service, scope)
    assert final.state == "reserved"
    with pytest.raises(IngestionError) as caught:
        reserve(service, scope)
    assert caught.value.code == "usage_attempt_limit"


def test_concurrent_idempotency_and_exact_reconciliation_append_only_once(integration, monkeypatch):
    env = integration
    service, _, actor, wid, _, _, _, scope, _ = configured(env, monkeypatch)
    attempt_id = uuid4()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: reserve(service, scope, attempt_id), range(4)))
    assert all(value == results[0] for value in results)
    service.start(scope, attempt_id)
    with pytest.raises(IngestionError):
        service.start(scope, attempt_id)
    with ThreadPoolExecutor(max_workers=4) as executor:
        settled = list(
            executor.map(
                lambda _: service.finish(scope, attempt_id, "truncated", TokenUsage(100, 50, 20)),
                range(4),
            )
        )
    assert all(value == settled[0] for value in settled)
    assert settled[0].cost == Decimal("0.00062875")
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.usage_attempts)).scalar_one() == 1
        )
        assert connection.execute(
            select(s.model_usage_events.c.kind).order_by(s.model_usage_events.c.sequence)
        ).scalars().all() == ["reserved", "dispatched", "provider_result"]
    summary = service.summary(actor.id, UUID(wid), NOW, NOW + timedelta(days=1))
    assert summary["counts"]["attempts"] == 1 and summary["counts"]["unknown_cost_attempts"] == 0
    assert Decimal(summary["costs"][0]["known_cost"]) == settled[0].cost


def test_unknown_usage_holds_exposure_and_only_operator_evidence_can_settle(
    integration, monkeypatch
):
    service, owner, actor, wid, _, _, _, scope, _ = configured(
        integration, monkeypatch, spend_limit=Decimal("0.2")
    )
    values = [reserve(service, scope), reserve(service, scope)]
    for value in values:
        service.start(scope, value.id)
        service.finish(scope, value.id, "timeout", TokenUsage())
    with pytest.raises(IngestionError) as caught:
        reserve(service, scope)
    assert caught.value.code == "usage_spend_limit"
    summary = service.summary(actor.id, UUID(wid), NOW, NOW + timedelta(days=1))
    assert summary["costs"][0]["known_cost"] is None
    assert summary["tokens"]["input_tokens"] is None
    assert Decimal(summary["costs"][0]["held_exposure"]) == Decimal("0.2")
    _, user = add_member(integration, owner, wid)
    with pytest.raises(IngestionError) as denied:
        service.reconcile(
            user.id,
            UUID(wid),
            values[0].id,
            Decimal("0"),
            "USD",
            "provider_invoice_record",
            "fixture-record",
        )
    assert denied.value.code == "staff_required"
    with pytest.raises(IngestionError):
        service.reconcile(
            actor.id, UUID(wid), values[0].id, Decimal("0"), "USD", "provider_invoice_record", ""
        )
    service.reconcile(
        actor.id,
        UUID(wid),
        values[0].id,
        Decimal("0.01"),
        "USD",
        "provider_invoice_record",
        "fictional-record-1",
    )
    with pytest.raises(IngestionError):
        reserve(service, scope)
    service.reconcile(
        actor.id,
        UUID(wid),
        values[1].id,
        Decimal("0.01"),
        "USD",
        "provider_usage_record",
        "fictional-record-2",
    )
    assert reserve(service, scope).state == "reserved"


def test_summary_requires_owner_and_full_dataset_access(integration, monkeypatch):
    service, owner, actor, wid, did, _, _, scope, _ = configured(integration, monkeypatch)
    _, member = add_member(integration, owner, wid)
    reserve(service, scope)
    with pytest.raises(IngestionError):
        service.summary(member.id, UUID(wid), NOW, NOW + timedelta(days=1))
    integration.runtime.access_policies.save(
        actor,
        UUID(wid),
        UUID(did),
        0,
        True,
        [dict(user_id=str(actor.id), columns=["amount"], conditions=[])],
    )
    with pytest.raises(IngestionError) as denied:
        service.summary(actor.id, UUID(wid), NOW, NOW + timedelta(days=1))
    assert denied.value.code == "access_restricted"


def test_price_revision_does_not_reprice_an_existing_attempt(integration, monkeypatch):
    service, _, actor, _, _, _, _, scope, _ = configured(integration, monkeypatch)
    value = reserve(service, scope)
    service.set_price(
        actor.id,
        price(
            created_by=actor.id,
            created_at=NOW + timedelta(seconds=1),
            input_per_million=Decimal("999"),
        ),
    )
    monkeypatch.setattr(service_module, "now", lambda: NOW + timedelta(seconds=2))
    service.start(scope, value.id)
    settled = service.finish(scope, value.id, "succeeded", TokenUsage(100, 0, 0))
    assert settled.cost == Decimal("0.000275")
    next_attempt = reserve(service, scope)
    assert next_attempt.price.input_per_million == Decimal("999")


def test_allowance_revision_preserves_existing_window_usage(integration, monkeypatch):
    service, _, actor, _, _, _, _, scope, allowance = configured(integration, monkeypatch)
    value = reserve(service, scope)
    service.start(scope, value.id)
    service.finish(scope, value.id, "succeeded", TokenUsage(100, 0, 0))
    changed = replace(allowance, id=uuid4(), version=2, max_attempts=1)
    service.set_policy(actor.id, changed, 1)
    with pytest.raises(IngestionError) as exhausted:
        reserve(service, scope)
    assert exhausted.value.code == "usage_attempt_limit"
    with pytest.raises(IngestionError) as conflict:
        service.set_policy(actor.id, replace(changed, id=uuid4(), version=3), 1)
    assert conflict.value.code == "usage_policy_conflict"


def test_operator_recovery_preserves_uncertainty_releases_only_unsent_work(
    integration, monkeypatch
):
    service, _, actor, wid, _, _, _, scope, _ = configured(integration, monkeypatch)
    unsent = reserve(service, scope)
    sent = reserve(service, scope)
    service.start(scope, sent.id)
    with pytest.raises(IngestionError) as error:
        service.recover(actor.id, UUID(wid), NOW)
    assert error.value.code == "usage_recovery_window"
    monkeypatch.setattr(service_module, "now", lambda: NOW + timedelta(minutes=20))
    assert service.recover(actor.id, UUID(wid), NOW + timedelta(minutes=1)) == {
        "released_before_dispatch": 1,
        "unknown": 1,
    }
    assert service.recover(actor.id, UUID(wid), NOW) == {
        "released_before_dispatch": 0,
        "unknown": 0,
    }
    (pending,) = service.pending(actor.id, UUID(wid))
    assert pending.id == sent.id and pending.state == "unknown"
    assert pending.outcome == "interrupted" and pending.cost is None
    assert pending.held_exposure == Decimal("0.1")
    with pytest.raises(IngestionError):
        service.start(scope, unsent.id)
    with integration.engine.connect() as connection:
        assert connection.execute(
            select(s.model_usage_events.c.kind).where(s.model_usage_events.c.kind == "recovered")
        ).scalars().all() == ["recovered", "recovered"]


def test_provider_settlement_survives_membership_revocation_but_new_dispatch_is_denied(
    integration, monkeypatch
):
    service, owner, actor, wid, _, _, _, scope, _ = configured(integration, monkeypatch)
    _, member = add_member(integration, owner, wid)
    personal = replace(scope, actor_id=member.id)
    attempt = reserve(service, personal)
    service.start(personal, attempt.id)
    integration.runtime.service.remove_member(actor, UUID(wid), member.id)
    result = service.finish(personal, attempt.id, "cancelled", TokenUsage(10, 2, 0))
    assert result.cost is not None and result.state == "settled"
    with pytest.raises(IngestionError):
        reserve(service, personal)


def test_owner_usage_and_operator_endpoints_are_explicit_private_and_exact(
    integration, monkeypatch
):
    env = integration
    service, owner, actor, wid, did, _, _, scope, _ = configured(env, monkeypatch)
    from execplus.presentation.routes import usage_metering as routes

    env.runtime.usage_metering = service
    monkeypatch.setattr(routes, "now", lambda: NOW + timedelta(seconds=1))
    attempted = reserve(service, scope)
    service.start(scope, attempted.id)
    service.finish(scope, attempted.id, "succeeded", TokenUsage(100, 50, 20))
    path = f"/workspaces/{wid}/model-usage"
    result = env.client.get(path, headers=owner)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["tokens"]["input_tokens"] == "100"
    assert body["tokens"]["output_tokens"] == "50"
    assert Decimal(body["costs"][0]["known_cost"]) == Decimal("0.00062875")
    assert "e" not in body["costs"][0]["known_cost"].lower()
    assert body["allowance"]["availability"] == {"can_start_next": True, "code": None}
    member, _ = add_member(env, owner, wid)
    assert env.client.get(path, headers=member).status_code == 403
    admin_path = f"/admin/workspaces/{wid}/model-usage/pending"
    assert env.client.get(admin_path, headers=member).status_code == 403
    assert env.client.get(admin_path, headers=owner).status_code == 200
    assert env.client.get(path + "?days=367", headers=owner).status_code == 422
    env.runtime.access_policies.save(actor, UUID(wid), UUID(did), 0, True, [])
    assert env.client.get(path, headers=owner).status_code == 404
    assert env.client.get(admin_path, headers=owner).status_code == 404


def test_unconfigured_usage_stays_unknown_and_owner_summary_never_invents_a_bill(
    integration, monkeypatch
):
    env = integration
    _, actor, wid, _, _, _ = prepare(env)
    service = env.runtime.usage_metering
    monkeypatch.setattr(service_module, "now", lambda: NOW)
    scope = attribution(workspace_id=UUID(wid), actor_id=actor.id)
    attempted = reserve(service, scope)
    service.start(scope, attempted.id)
    service.finish(scope, attempted.id, "succeeded", TokenUsage(100, 20))
    result = service.summary(actor.id, UUID(wid), NOW, NOW + timedelta(seconds=1))
    assert result["allowance"] is None
    assert result["costs"] == [
        {
            "currency": None,
            "known_cost": None,
            "held_exposure": "0.000000000000000000",
            "priced_attempts": 0,
            "unknown_attempts": 1,
        }
    ]
    assert result["counts"]["unknown_cost_attempts"] == 1


def test_operator_configuration_requires_active_grant_and_validated_explicit_prices(
    integration, monkeypatch
):
    env = integration
    service, owner, actor, wid, _, _, _, _, allowance = configured(env, monkeypatch)
    env.runtime.usage_metering = service
    body = {
        "id": str(uuid4()),
        "provider": "test-provider",
        "model": "other-model",
        "currency": "USD",
        "input_per_million": "1.125",
        "output_per_million": "2.25",
        "cached_input_per_million": None,
        "evidence_ref": "fictional-approved-rate-v1",
        "effective_at": NOW.isoformat(),
    }
    member, _ = add_member(env, owner, wid)
    assert env.client.post("/admin/model-prices", headers=member, json=body).status_code == 403
    assert env.client.post("/admin/model-prices", headers=owner, json=body).status_code == 201
    assert env.client.post("/admin/model-prices", headers=owner, json=body).status_code == 201
    assert (
        env.client.post(
            "/admin/model-prices",
            headers=owner,
            json={
                **body,
                "id": str(uuid4()),
                "input_per_million": "3",
            },
        ).status_code
        == 409
    )
    assert (
        env.client.post(
            "/admin/model-prices",
            headers=owner,
            json={
                **body,
                "input_per_million": "NaN",
            },
        ).status_code
        == 422
    )
    plan = {
        "expected_version": 1,
        "plan_key": "explicit-fixture",
        "starts_at": NOW.isoformat(),
        "ends_at": allowance.ends_at.isoformat(),
        "max_attempts": 25,
        "max_in_flight": 1,
    }
    path = f"/admin/workspaces/{wid}/model-allowance"
    assert env.client.put(path, headers=owner, json=plan).json()["version"] == 2
    assert env.client.put(path, headers=owner, json=plan).status_code == 409
    env.runtime.operations.change_staff(actor.email, None)
    assert env.client.post("/admin/model-prices", headers=owner, json=body).status_code == 403


@pytest.mark.parametrize("settled", [False, True])
def test_new_spending_policy_never_treats_old_unpriced_or_other_currency_usage_as_zero(
    integration, monkeypatch, settled
):
    env = integration
    _, actor, wid, _, _, _ = prepare(env)
    env.runtime.operations.change_staff(actor.email, "admin")
    service = env.runtime.usage_metering
    monkeypatch.setattr(service_module, "now", lambda: NOW)
    scope = attribution(workspace_id=UUID(wid), actor_id=actor.id)
    attempted = reserve(service, scope)
    service.start(scope, attempted.id)
    service.finish(scope, attempted.id, "succeeded", TokenUsage(10, 5))
    if settled:
        service.reconcile(
            actor.id,
            UUID(wid),
            attempted.id,
            Decimal("0.01"),
            "EUR",
            "provider_invoice_record",
            "independent-fixture-eur",
        )
    service.set_policy(actor.id, policy(workspace_id=UUID(wid), created_by=actor.id), 0)
    with pytest.raises(IngestionError) as error:
        reserve(service, scope)
    assert error.value.code == "usage_unresolved"
    if not settled:
        service.reconcile(
            actor.id,
            UUID(wid),
            attempted.id,
            Decimal("0.01"),
            "USD",
            "provider_invoice_record",
            "independent-fixture-usd",
        )
        assert reserve(service, scope).held_exposure == Decimal("0.1")
