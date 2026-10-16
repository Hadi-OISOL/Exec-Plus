"""Use case: Delivers explicitly configured private metadata notifications.

What it does: Manages owner subscriptions, rechecks current access before each
signed attempt and drains bounded transport work without retaining raw errors.
"""

import asyncio
import logging
from contextlib import suppress
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from execplus.application.integration_ports import IntegrationStore, WebhookTransport
from execplus.application.services.dataset_access import authorize_sources, dataset_access
from execplus.application.services.integration_access import audit
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.integration_access import unavailable, validate_scope
from execplus.domain.webhooks import (
    EVENTS,
    WebhookDelivery,
    WebhookSubscription,
    destination,
    outcome,
    signature,
    signing_key,
)

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(
        self,
        store: IntegrationStore,
        transport: WebhookTransport,
        master: bytes,
        allowed_origins: tuple[str, ...],
        *,
        allow_local: bool = False,
        interval: float = 10,
    ) -> None:
        self.store, self.transport, self.master = store, transport, master
        self.allowed_origins, self.allow_local, self.interval = (
            allowed_origins,
            allow_local,
            interval,
        )
        self.stop = asyncio.Event()
        self.lock = asyncio.Lock()
        self.last_success: datetime | None = None
        self.last_failure: datetime | None = None
        self.capacity_limited = False

    @property
    def enabled(self) -> bool:
        return len(self.master) >= 32 and bool(self.allowed_origins)

    def create(
        self,
        actor: User,
        wid: UUID,
        datasets: tuple[UUID, ...],
        events: tuple[str, ...],
        target: str,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise IngestionError(
                "webhook_disabled", "An operator must configure an approved receiver first.", 422
            )
        validate_scope(datasets, ("profile:read",))
        if not events or len(set(events)) != len(events) or not set(events) <= EVENTS:
            raise IngestionError("webhook_events", "Choose supported notification events.", 422)
        target = destination(target, self.allowed_origins, allow_local=self.allow_local)
        now = datetime.now(timezone.utc)
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            membership = repo.membership(wid, actor.id)
            if membership.role != "owner":
                raise IngestionError(
                    "integration_owner", "Only the owner can manage webhooks.", 403
                )
            for did in datasets:
                dataset_access(repo, actor, wid, did)
            if (
                sum(value.revoked_at is None for value in repo.webhook_subscriptions(wid, None))
                >= 20
            ):
                raise IngestionError("webhook_limit", "Revoke an unused webhook first.", 422)
            value = WebhookSubscription(
                uuid4(), wid, actor.id, membership.created_at, datasets, events, target, 1, now
            )
            repo.add_webhook_subscription(value)
            audit(repo, actor, wid, "integration.webhook_created", value.id)
        return {
            "subscription": asdict(value),
            "signing_secret": signing_key(self.master, value.id, 1).hex(),
        }

    def list_subscriptions(self, actor: User, wid: UUID) -> dict[str, Any]:
        with self.store.transaction() as repo:
            if repo.membership(wid, actor.id).role != "owner":
                raise IngestionError(
                    "integration_owner", "Only the owner can manage webhooks.", 403
                )
            values = repo.webhook_subscriptions(wid, None)
        return {
            "subscriptions": [asdict(item) for item in values],
            "enabled": self.enabled,
            "allowed_origins": self.allowed_origins,
            "poll_seconds": self.interval,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "capacity_limited": self.capacity_limited,
        }

    def change(self, actor: User, wid: UUID, sid: UUID, *, rotate: bool) -> dict[str, Any]:
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            if repo.membership(wid, actor.id).role != "owner":
                raise unavailable()
            value = repo.webhook_subscription(wid, sid)
            if value.revoked_at is not None:
                raise unavailable()
            if rotate and not self.enabled:
                raise IngestionError("webhook_disabled", "Webhook delivery is disabled.", 422)
            value = replace(
                value,
                signing_version=value.signing_version + int(rotate),
                revoked_at=None if rotate else datetime.now(timezone.utc),
            )
            repo.update_webhook_subscription(value)
            audit(
                repo,
                actor,
                wid,
                "integration.webhook_rotated" if rotate else "integration.webhook_revoked",
                sid,
            )
        return {
            "subscription": asdict(value),
            **(
                {"signing_secret": signing_key(self.master, sid, value.signing_version).hex()}
                if rotate
                else {}
            ),
        }

    def deliveries(self, actor: User, wid: UUID, sid: UUID) -> list[dict[str, Any]]:
        with self.store.transaction() as repo:
            if repo.membership(wid, actor.id).role != "owner":
                raise unavailable()
            repo.webhook_subscription(wid, sid)
            return [asdict(item) for item in repo.webhook_deliveries(sid, 100)]

    def _authorize(
        self, subscription: WebhookSubscription, delivery: WebhookDelivery
    ) -> WebhookSubscription:
        with self.store.transaction() as repo:
            repo.workspace(subscription.workspace_id, lock=True)
            value = repo.webhook_subscription(subscription.workspace_id, subscription.id)
            actor = repo.user(value.user_id)
            membership = repo.membership(value.workspace_id, actor.id)
            if (
                value.revoked_at is not None
                or membership.created_at != value.membership_created_at
                or delivery.event.dataset_id not in value.dataset_ids
                or delivery.event.kind not in value.event_types
            ):
                raise unavailable()
            dataset_access(repo, actor, value.workspace_id, delivery.event.dataset_id)
            if delivery.event.kind.startswith("job."):
                job = repo.job(value.workspace_id, delivery.event.resource_id)
                if job.owner_id != actor.id or "job." + job.status != delivery.event.kind:
                    raise unavailable()
                authorize_sources(repo, actor, value.workspace_id, job.sources)
            else:
                candidate = repo.refresh_candidate(value.workspace_id, delivery.event.resource_id)
                if candidate.created_by != actor.id or candidate.status != "activated":
                    raise unavailable()
            destination(value.destination, self.allowed_origins, allow_local=self.allow_local)
            return value

    def _attempt(self, subscription: WebhookSubscription, delivery: WebhookDelivery) -> None:
        now = datetime.now(timezone.utc)
        try:
            value = self._authorize(subscription, delivery)
        except IngestionError:
            self.store.complete_webhook(delivery, "cancelled", now, None)
            return
        body = delivery.event.body()
        headers = {
            "X-ExecPlus-Event-ID": str(delivery.event.id),
            "X-ExecPlus-Signature": signature(
                signing_key(self.master, value.id, value.signing_version),
                int(now.timestamp()),
                body,
            ),
        }
        result = self.transport.send(value.destination, body, headers)
        status, due = outcome(datetime.now(timezone.utc), delivery.attempts, result)
        self.store.complete_webhook(delivery, status, due, result)

    async def poll_once(self) -> bool:
        if not self.enabled:
            return True
        async with self.lock:

            def work() -> None:
                result = self.store.collect_webhooks(datetime.now(timezone.utc))
                self.capacity_limited = bool(result["capacity_limited"])
                for _ in range(10):
                    if self.stop.is_set():
                        break
                    claimed = self.store.claim_webhook(datetime.now(timezone.utc))
                    if claimed is None:
                        break
                    self._attempt(*claimed)

            pending = asyncio.create_task(asyncio.to_thread(work))
            try:
                try:
                    await asyncio.shield(pending)
                except asyncio.CancelledError:
                    with suppress(Exception, asyncio.CancelledError):
                        await pending
                    raise
            except Exception:
                self.last_failure = datetime.now(timezone.utc)
                logger.warning("webhook_delivery_unavailable")
                return False
            self.last_success = datetime.now(timezone.utc)
            return True

    async def run(self) -> None:
        while not self.stop.is_set():
            await self.poll_once()
            with suppress(TimeoutError):
                await asyncio.wait_for(self.stop.wait(), self.interval)
