"""Use case: Collects durable customer events and leases bounded outbound attempts.

What it does: Uses metadata-only SQL joins, stable deduplication, bounded retention,
lease identities and database deadlines before network work begins.
"""

from datetime import datetime, timedelta
from time import monotonic
from uuid import uuid4

from sqlalchemy import (
    Connection,
    Engine,
    String,
    and_,
    cast,
    delete,
    exists,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, insert

from execplus.domain.webhooks import MAX_ATTEMPTS, WebhookDelivery, WebhookSubscription
from execplus.infrastructure.persistence import schema as s


def budget(connection: Connection, deadline: float) -> None:
    remaining = int((deadline - monotonic()) * 1000)
    if remaining <= 0:
        raise TimeoutError("Webhook persistence deadline exhausted")
    connection.execute(
        select(
            func.set_config("statement_timeout", str(remaining), True),
            func.set_config("lock_timeout", str(min(1000, remaining)), True),
        )
    )


class SQLWebhookOutbox:
    engine: Engine

    def collect_webhooks(self, now: datetime) -> dict[str, int]:
        cutoff = now - timedelta(days=30)
        sub, deliveries = s.webhook_subscriptions, s.webhook_deliveries
        jobs, threads = s.jobs, s.threads
        candidates, feeds, audit = s.refresh_candidates, s.refresh_feeds, s.audit_events
        with self.engine.begin() as connection:
            deadline = monotonic() + 5
            budget(connection, deadline)
            connection.execute(select(func.pg_advisory_xact_lock(619_832_062)))
            budget(connection, deadline)
            connection.execute(delete(deliveries).where(deliveries.c.occurred_at < cutoff))
            budget(connection, deadline)
            count = connection.execute(select(func.count()).select_from(deliveries)).scalar_one()
            room = min(200, max(0, 5000 - count))
            if not room:
                return {"collected": 0, "capacity_limited": 1}
            job_kind = literal("job.") + jobs.c.status
            job_query = (
                select(
                    sub.c.id.label("subscription_id"),
                    job_kind.label("kind"),
                    jobs.c.id.label("resource_id"),
                    threads.c.dataset_id,
                    jobs.c.updated_at.label("occurred_at"),
                )
                .select_from(
                    jobs.join(threads, jobs.c.thread_id == threads.c.id).join(
                        sub,
                        and_(
                            sub.c.workspace_id == jobs.c.workspace_id,
                            sub.c.user_id == jobs.c.owner_id,
                        ),
                    )
                )
                .where(
                    sub.c.revoked_at.is_(None),
                    jobs.c.status.in_(("succeeded", "failed")),
                    jobs.c.updated_at >= sub.c.created_at,
                    jobs.c.updated_at >= cutoff,
                    cast(sub.c.dataset_ids, JSONB).contains(
                        func.jsonb_build_array(cast(threads.c.dataset_id, String))
                    ),
                    cast(sub.c.event_types, JSONB).contains(func.jsonb_build_array(job_kind)),
                    ~exists(
                        select(deliveries.c.id).where(
                            deliveries.c.subscription_id == sub.c.id,
                            deliveries.c.kind == job_kind,
                            deliveries.c.resource_id == jobs.c.id,
                        )
                    ),
                )
            )
            refresh_query = (
                select(
                    sub.c.id.label("subscription_id"),
                    literal("refresh.accepted").label("kind"),
                    candidates.c.id.label("resource_id"),
                    feeds.c.dataset_id,
                    audit.c.created_at.label("occurred_at"),
                )
                .select_from(
                    candidates.join(feeds, candidates.c.feed_id == feeds.c.id)
                    .join(
                        audit,
                        and_(
                            audit.c.resource_id == candidates.c.id,
                            audit.c.action == "refresh.activated",
                        ),
                    )
                    .join(
                        sub,
                        and_(
                            sub.c.workspace_id == candidates.c.workspace_id,
                            sub.c.user_id == candidates.c.created_by,
                        ),
                    )
                )
                .where(
                    sub.c.revoked_at.is_(None),
                    candidates.c.status == "activated",
                    audit.c.created_at >= sub.c.created_at,
                    audit.c.created_at >= cutoff,
                    cast(sub.c.dataset_ids, JSONB).contains(
                        func.jsonb_build_array(cast(feeds.c.dataset_id, String))
                    ),
                    cast(sub.c.event_types, JSONB).contains(["refresh.accepted"]),
                    ~exists(
                        select(deliveries.c.id).where(
                            deliveries.c.subscription_id == sub.c.id,
                            deliveries.c.kind == "refresh.accepted",
                            deliveries.c.resource_id == candidates.c.id,
                        )
                    ),
                )
            )
            budget(connection, deadline)
            rows = (
                connection.execute(
                    job_query.union_all(refresh_query).order_by("occurred_at").limit(room)
                )
                .mappings()
                .all()
            )
            values = [
                dict(id=uuid4(), **dict(row), status="pending", attempts=0, next_attempt_at=now)
                for row in rows
            ]
            if values:
                budget(connection, deadline)
                connection.execute(
                    insert(deliveries).on_conflict_do_nothing(
                        index_elements=["subscription_id", "kind", "resource_id"]
                    ),
                    values,
                )
            return {"collected": len(values), "capacity_limited": int(count + len(values) >= 5000)}

    def claim_webhook(self, now: datetime) -> tuple[WebhookSubscription, WebhookDelivery] | None:
        from execplus.infrastructure.persistence.integrations import (
            delivery_record,
            subscription_record,
        )

        table = s.webhook_deliveries
        with self.engine.begin() as connection:
            deadline = monotonic() + 5
            budget(connection, deadline)
            connection.execute(
                update(table)
                .where(
                    table.c.status == "sending",
                    table.c.lease_until <= now,
                    table.c.attempts >= MAX_ATTEMPTS,
                )
                .values(status="failed", lease_until=None, lease_id=None)
            )
            budget(connection, deadline)
            row = (
                connection.execute(
                    select(table)
                    .where(
                        table.c.attempts < MAX_ATTEMPTS,
                        or_(
                            and_(table.c.status == "pending", table.c.next_attempt_at <= now),
                            and_(table.c.status == "sending", table.c.lease_until <= now),
                        ),
                    )
                    .order_by(table.c.next_attempt_at, table.c.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            value = dict(row)
            value.update(
                status="sending",
                attempts=row["attempts"] + 1,
                last_attempt_at=now,
                lease_until=now + timedelta(seconds=30),
                lease_id=uuid4(),
            )
            budget(connection, deadline)
            connection.execute(update(table).where(table.c.id == row["id"]).values(**value))
            budget(connection, deadline)
            subscription = (
                connection.execute(
                    select(s.webhook_subscriptions).where(
                        s.webhook_subscriptions.c.id == row["subscription_id"]
                    )
                )
                .mappings()
                .one()
            )
            return subscription_record(subscription), delivery_record(value)

    def complete_webhook(
        self,
        delivery: WebhookDelivery,
        status: str,
        next_attempt: datetime,
        response_status: int | None,
    ) -> bool:
        with self.engine.begin() as connection:
            budget(connection, monotonic() + 5)
            row = connection.execute(
                update(s.webhook_deliveries)
                .where(
                    s.webhook_deliveries.c.id == delivery.event.id,
                    s.webhook_deliveries.c.status == "sending",
                    s.webhook_deliveries.c.lease_id == delivery.lease_id,
                )
                .values(
                    status=status,
                    next_attempt_at=next_attempt,
                    last_status=response_status,
                    lease_id=None,
                    lease_until=None,
                )
                .returning(s.webhook_deliveries.c.id)
            ).scalar_one_or_none()
            return row is not None
