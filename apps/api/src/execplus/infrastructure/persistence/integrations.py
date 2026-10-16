"""Use case: Stores scoped integration keys, private embed grants and webhook outbox state.

What it does: Preserves hashed credentials, applies atomic rate windows and one-use
exchanges under workspace locks, and retains bounded idempotent delivery metadata.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta
from time import monotonic
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, delete, select, update
from sqlalchemy.dialects.postgresql import insert

from execplus.application.integration_ports import IntegrationRepository
from execplus.domain.integration_access import EmbedGrant, IntegrationKey, unavailable
from execplus.domain.webhooks import WebhookDelivery, WebhookEvent, WebhookSubscription
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository
from execplus.infrastructure.persistence.webhook_outbox import SQLWebhookOutbox, budget


def key_record(row: Any) -> IntegrationKey:
    value = dict(row)
    value["dataset_ids"] = tuple(UUID(item) for item in value["dataset_ids"])
    value["operations"] = tuple(value["operations"])
    return IntegrationKey(**value)


def subscription_record(row: Any) -> WebhookSubscription:
    value = dict(row)
    value["dataset_ids"] = tuple(UUID(item) for item in value["dataset_ids"])
    value["event_types"] = tuple(value["event_types"])
    return WebhookSubscription(**value)


def delivery_record(row: Any) -> WebhookDelivery:
    value = dict(row)
    event = WebhookEvent(
        **{
            key: value.pop(key)
            for key in ("id", "subscription_id", "kind", "resource_id", "dataset_id", "occurred_at")
        }
    )
    return WebhookDelivery(event, **value)


class SQLIntegrationRepository(SQLWorkspaceRepository):
    def integration_keys(self, wid: UUID, user_id: UUID | None) -> tuple[IntegrationKey, ...]:
        query = select(s.integration_keys).where(s.integration_keys.c.workspace_id == wid)
        if user_id is not None:
            query = query.where(s.integration_keys.c.user_id == user_id)
        return tuple(
            key_record(row)
            for row in self.connection.execute(
                query.order_by(s.integration_keys.c.created_at.desc())
            ).mappings()
        )

    def integration_key(self, wid: UUID, key_id: UUID) -> IntegrationKey:
        row = (
            self.connection.execute(
                select(s.integration_keys).where(
                    s.integration_keys.c.workspace_id == wid, s.integration_keys.c.id == key_id
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise unavailable()
        return key_record(row)

    def integration_key_by_hash(self, digest: str) -> IntegrationKey | None:
        row = (
            self.connection.execute(
                select(s.integration_keys).where(s.integration_keys.c.token_hash == digest)
            )
            .mappings()
            .first()
        )
        return key_record(row) if row else None

    def add_integration_key(self, value: IntegrationKey) -> None:
        raw = asdict(value)
        raw["dataset_ids"] = [str(item) for item in value.dataset_ids]
        raw["operations"] = list(value.operations)
        self.connection.execute(insert(s.integration_keys).values(**raw))

    def update_integration_key(self, value: IntegrationKey) -> None:
        self.connection.execute(
            update(s.integration_keys)
            .where(
                s.integration_keys.c.id == value.id,
                s.integration_keys.c.workspace_id == value.workspace_id,
            )
            .values(revoked_at=value.revoked_at, last_used_at=value.last_used_at)
        )

    def consume_integration_request(self, key_id: UUID, now: datetime, limit: int) -> bool:
        window = now.replace(second=0, microsecond=0)
        self.connection.execute(
            delete(s.integration_request_windows).where(
                s.integration_request_windows.c.key_id == key_id,
                s.integration_request_windows.c.window_start < window - timedelta(minutes=2),
            )
        )
        row = self.connection.execute(
            insert(s.integration_request_windows)
            .values(key_id=key_id, window_start=window, used=1)
            .on_conflict_do_update(
                index_elements=["key_id", "window_start"],
                set_={"used": s.integration_request_windows.c.used + 1},
                where=s.integration_request_windows.c.used < limit,
            )
            .returning(s.integration_request_windows.c.used)
        ).scalar_one_or_none()
        return row is not None

    def embed_grant(self, grant_id: UUID) -> EmbedGrant:
        row = (
            self.connection.execute(select(s.embed_grants).where(s.embed_grants.c.id == grant_id))
            .mappings()
            .first()
        )
        if row is None:
            raise unavailable()
        return EmbedGrant(**row)

    def embed_grant_by_session(self, digest: str) -> EmbedGrant | None:
        row = (
            self.connection.execute(
                select(s.embed_grants).where(s.embed_grants.c.session_hash == digest)
            )
            .mappings()
            .first()
        )
        return EmbedGrant(**row) if row else None

    def embed_grants(self, wid: UUID, user_id: UUID) -> tuple[EmbedGrant, ...]:
        return tuple(
            EmbedGrant(**row)
            for row in self.connection.execute(
                select(s.embed_grants)
                .where(s.embed_grants.c.workspace_id == wid, s.embed_grants.c.user_id == user_id)
                .order_by(s.embed_grants.c.created_at.desc())
                .limit(200)
            ).mappings()
        )

    def add_embed_grant(self, value: EmbedGrant) -> None:
        self.connection.execute(insert(s.embed_grants).values(**asdict(value)))

    def update_embed_grant(self, value: EmbedGrant) -> None:
        self.connection.execute(
            update(s.embed_grants)
            .where(s.embed_grants.c.id == value.id)
            .values(
                consumed_at=value.consumed_at,
                session_hash=value.session_hash,
                session_expires_at=value.session_expires_at,
                revoked_at=value.revoked_at,
            )
        )

    def webhook_subscriptions(
        self, wid: UUID, user_id: UUID | None
    ) -> tuple[WebhookSubscription, ...]:
        query = select(s.webhook_subscriptions).where(s.webhook_subscriptions.c.workspace_id == wid)
        if user_id is not None:
            query = query.where(s.webhook_subscriptions.c.user_id == user_id)
        return tuple(
            subscription_record(row)
            for row in self.connection.execute(
                query.order_by(s.webhook_subscriptions.c.created_at.desc())
            ).mappings()
        )

    def webhook_subscription(self, wid: UUID, subscription_id: UUID) -> WebhookSubscription:
        row = (
            self.connection.execute(
                select(s.webhook_subscriptions).where(
                    s.webhook_subscriptions.c.workspace_id == wid,
                    s.webhook_subscriptions.c.id == subscription_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise unavailable()
        return subscription_record(row)

    def add_webhook_subscription(self, value: WebhookSubscription) -> None:
        raw = asdict(value)
        raw["dataset_ids"] = [str(item) for item in value.dataset_ids]
        raw["event_types"] = list(value.event_types)
        self.connection.execute(insert(s.webhook_subscriptions).values(**raw))

    def update_webhook_subscription(self, value: WebhookSubscription) -> None:
        self.connection.execute(
            update(s.webhook_subscriptions)
            .where(
                s.webhook_subscriptions.c.id == value.id,
                s.webhook_subscriptions.c.workspace_id == value.workspace_id,
            )
            .values(revoked_at=value.revoked_at, signing_version=value.signing_version)
        )

    def webhook_deliveries(self, subscription_id: UUID, limit: int) -> tuple[WebhookDelivery, ...]:
        return tuple(
            delivery_record(row)
            for row in self.connection.execute(
                select(s.webhook_deliveries)
                .where(s.webhook_deliveries.c.subscription_id == subscription_id)
                .order_by(s.webhook_deliveries.c.occurred_at.desc())
                .limit(limit)
            ).mappings()
        )

    def add_webhook_event(self, value: WebhookEvent) -> bool:
        row = self.connection.execute(
            insert(s.webhook_deliveries)
            .values(
                **asdict(value), status="pending", attempts=0, next_attempt_at=value.occurred_at
            )
            .on_conflict_do_nothing(index_elements=["subscription_id", "kind", "resource_id"])
            .returning(s.webhook_deliveries.c.id)
        ).scalar_one_or_none()
        return row is not None


class SQLIntegrationStore(SQLWebhookOutbox):
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def transaction(self) -> Iterator[IntegrationRepository]:
        with self.engine.begin() as connection:
            budget(connection, monotonic() + 5)
            yield SQLIntegrationRepository(connection)
