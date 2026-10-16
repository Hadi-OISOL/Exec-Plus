"""Use case: Verifies the durable notification path without an external receiver.

What it does: Exercises real job completion, signed HTTP, retry fencing, rotation,
private ownership, current policy denial and database/transport boundaries.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import select, update

from execplus.application.services.webhooks import WebhookService
from execplus.domain.ingestion import IngestionError
from execplus.domain.webhooks import verify_signature
from execplus.infrastructure.integrations.webhook_http import PinnedWebhookTransport
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.integrations import SQLIntegrationStore
from test_conversation_jobs import process, submit
from test_refresh import activate, setup, stage
from test_studies import add_member, prepare
from test_webhook_transport import receiver


def service(env, base):
    return WebhookService(
        SQLIntegrationStore(env.engine),
        PinnedWebhookTransport({base: "127.0.0.1"}, allow_local=True),
        b"fictional-test-master-secret-value-0123456789",
        (base,),
        allow_local=True,
    )


def subscribe(svc, actor, wid, did, base, events=("job.succeeded", "job.failed")):
    return svc.create(actor, UUID(wid), (UUID(did),), events, base + "/events")


def diagram(env, owner, root):
    thread = env.client.post(root + "/threads", headers=owner)
    assert thread.status_code == 201, thread.text
    value = thread.json()
    path = f"/workspaces/{value['workspace_id']}/threads/{value['id']}"
    job = submit(env, owner, path, "Show a diagram of this dataset")
    assert process(env) == {"processed": 1}
    return job


def test_actual_signed_delivery_is_metadata_only_idempotent_and_after_commit(integration):
    env = integration
    owner, actor, wid, did, _, root = prepare(env)
    with receiver() as (base, requests):
        svc = service(env, base)
        issued = subscribe(svc, actor, wid, did, base)
        job = diagram(env, owner, root)
        assert asyncio.run(svc.poll_once())
        assert len(requests) == 1
        _, headers, body = requests[0]
        assert verify_signature(
            bytes.fromhex(issued["signing_secret"]),
            headers["X-ExecPlus-Signature"],
            body,
            int(datetime.now(timezone.utc).timestamp()),
        )
        payload = json.loads(body)
        assert payload["type"] == "job.succeeded" and payload["resource_id"] == job["id"]
        assert set(payload) == {"version", "id", "type", "resource_id", "dataset_id", "occurred_at"}
        assert b"amount" not in body and b"0.30" not in body
        assert asyncio.run(svc.poll_once()) and len(requests) == 1
        delivery = svc.deliveries(actor, UUID(wid), issued["subscription"]["id"])[0]
        assert delivery["status"] == "delivered" and delivery["attempts"] == 1
        assert "signing_secret" not in json.dumps(
            svc.list_subscriptions(actor, UUID(wid)), default=str
        )


def test_retry_reuses_event_identity_rotated_secret_and_stale_lease_cannot_finish(integration):
    env = integration
    owner, actor, wid, did, _, root = prepare(env)
    with receiver(status=503) as (base, requests):
        svc = service(env, base)
        issued = subscribe(svc, actor, wid, did, base)
        diagram(env, owner, root)
        now = datetime.now(timezone.utc)
        assert svc.store.collect_webhooks(now)["collected"] == 1
        first = svc.store.claim_webhook(now)
        assert first is not None
        assert svc.store.claim_webhook(now) is None
        svc._attempt(*first)
        rotated = svc.change(actor, UUID(wid), issued["subscription"]["id"], rotate=True)
        later = now + timedelta(seconds=40)
        second = svc.store.claim_webhook(later)
        assert second is not None and second[1].attempts == 2
        assert not svc.store.complete_webhook(first[1], "delivered", later, 200)
        svc._attempt(*second)
        assert requests[0][2] == requests[1][2]
        assert verify_signature(
            bytes.fromhex(rotated["signing_secret"]),
            requests[1][1]["X-ExecPlus-Signature"],
            requests[1][2],
            int(datetime.now(timezone.utc).timestamp()),
        )
        assert not verify_signature(
            bytes.fromhex(issued["signing_secret"]),
            requests[1][1]["X-ExecPlus-Signature"],
            requests[1][2],
            int(datetime.now(timezone.utc).timestamp()),
        )


@pytest.mark.parametrize("change", ["revoke", "policy", "membership"])
def test_revoked_access_cancels_before_transport(integration, change):
    env = integration
    owner, actor, wid, did, _, root = prepare(env)
    with receiver() as (base, requests):
        svc = service(env, base)
        issued = subscribe(svc, actor, wid, did, base)
        diagram(env, owner, root)
        svc.store.collect_webhooks(datetime.now(timezone.utc))
        if change == "revoke":
            svc.change(actor, UUID(wid), issued["subscription"]["id"], rotate=False)
        elif change == "policy":
            assert (
                env.client.put(
                    f"/workspaces/{wid}/datasets/{did}/access-policy",
                    headers=owner,
                    json={"expected_version": 0, "enabled": True, "grants": []},
                ).status_code
                == 200
            )
        else:
            with env.engine.begin() as connection:
                connection.execute(
                    update(s.memberships)
                    .where(s.memberships.c.user_id == actor.id)
                    .values(created_at=datetime.now(timezone.utc))
                )
        assert asyncio.run(svc.poll_once())
        assert not requests
        with env.engine.connect() as connection:
            assert (
                connection.execute(select(s.webhook_deliveries.c.status)).scalar_one()
                == "cancelled"
            )


def test_refresh_event_uses_activation_audit_time_and_disabled_delivery_needs_config(integration):
    env = integration
    owner, actor, wid, did, _, path, _ = setup(env)
    with receiver() as (base, requests):
        svc = service(env, base)
        subscribe(svc, actor, wid, did, base, ("refresh.accepted",))
        candidate = stage(env, owner, path).json()
        assert activate(env, owner, wid, candidate).status_code == 200
        assert asyncio.run(svc.poll_once())
        body = json.loads(requests[0][2])
        assert body["type"] == "refresh.accepted" and body["resource_id"] == candidate["id"]
        with env.engine.connect() as connection:
            stamp = connection.execute(
                select(s.audit_events.c.created_at).where(
                    s.audit_events.c.action == "refresh.activated"
                )
            ).scalar_one()
        assert body["occurred_at"] == stamp.isoformat()
        _, member = add_member(env, owner, wid, "admin")
        with pytest.raises(IngestionError, match="Only the owner"):
            subscribe(svc, member, wid, did, base)
        disabled = WebhookService(SQLIntegrationStore(env.engine), svc.transport, b"", ())
        with pytest.raises(IngestionError, match="operator"):
            subscribe(disabled, actor, wid, did, base)
        assert asyncio.run(disabled.poll_once())


def test_owner_endpoints_secret_once_rotation_and_nonowner_denial(integration):
    env = integration
    owner, actor, wid, did, _, _ = prepare(env)
    root = f"/workspaces/{wid}/integrations/webhooks"
    assert not env.client.get(root, headers=owner).json()["enabled"]
    with receiver() as (base, _):
        svc = service(env, base)
        env.runtime.webhooks = svc
        created = env.client.post(
            root,
            headers=owner,
            json={
                "dataset_ids": [did],
                "event_types": ["job.succeeded"],
                "destination": base + "/events",
            },
        )
        assert created.status_code == 201, created.text
        value = created.json()
        sid = value["subscription"]["id"]
        listed = env.client.get(root, headers=owner)
        assert listed.status_code == 200 and value["signing_secret"] not in listed.text
        member, _ = add_member(env, owner, wid, "admin")
        for method, suffix in [
            ("GET", ""),
            ("GET", f"/{sid}/deliveries"),
            ("POST", f"/{sid}/rotate"),
            ("DELETE", f"/{sid}"),
        ]:
            assert env.client.request(method, root + suffix, headers=member).status_code in {
                403,
                404,
            }
        rotated = env.client.post(root + f"/{sid}/rotate", headers=owner)
        assert (
            rotated.status_code == 200
            and rotated.json()["signing_secret"] != value["signing_secret"]
        )
        assert env.client.delete(root + f"/{sid}", headers=owner).status_code == 204
        assert svc.deliveries(actor, UUID(wid), UUID(sid)) == []


def test_network_work_holds_no_workspace_lock_and_cancel_drains_started_attempt(
    integration, monkeypatch
):
    import threading
    import time

    env = integration
    owner, actor, wid, did, _, root = prepare(env)
    with receiver(delay=0.2) as (base, requests):
        svc = service(env, base)
        subscribe(svc, actor, wid, did, base)
        diagram(env, owner, root)
        started = threading.Event()
        original = svc.transport.send

        def checked(*args):
            with env.engine.begin() as connection:
                connection.execute(
                    select(s.workspaces.c.id)
                    .where(s.workspaces.c.id == UUID(wid))
                    .with_for_update(nowait=True)
                ).one()
            started.set()
            return original(*args)

        monkeypatch.setattr(svc.transport, "send", checked)

        async def cancelled():
            pending = asyncio.create_task(svc.poll_once())
            assert await asyncio.to_thread(started.wait, 3)
            start = time.monotonic()
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert time.monotonic() - start >= 0.15

        asyncio.run(cancelled())
        assert len(requests) == 1
        with env.engine.connect() as connection:
            assert (
                connection.execute(select(s.webhook_deliveries.c.status)).scalar_one()
                == "delivered"
            )


def test_six_actual_failed_attempts_stop_without_recollecting_same_event(integration):
    env = integration
    owner, actor, wid, did, _, root = prepare(env)
    with receiver(status=503) as (base, requests):
        svc = service(env, base)
        subscribe(svc, actor, wid, did, base)
        diagram(env, owner, root)
        now = datetime.now(timezone.utc)
        assert svc.store.collect_webhooks(now)["collected"] == 1
        for index in range(6):
            claimed = svc.store.claim_webhook(now + timedelta(days=index))
            assert claimed is not None
            svc._attempt(*claimed)
        assert len(requests) == 6
        assert svc.store.claim_webhook(now + timedelta(days=7)) is None
        assert svc.store.collect_webhooks(now)["collected"] == 0
        with env.engine.connect() as connection:
            assert (
                connection.execute(select(s.webhook_deliveries.c.status)).scalar_one() == "failed"
            )
