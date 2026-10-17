"""Use case: Stores serializable model reservations and immutable usage events.

What it does: Locks workspace admission, aggregates bounded metadata in PostgreSQL,
and preserves token/cost uncertainty without retaining request or response content.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, and_, case, false, func, or_, select, true, update
from sqlalchemy.exc import IntegrityError

from execplus.application.services.dataset_access import require_workspace_access
from execplus.application.usage_ports import UsageRepository
from execplus.domain.ingestion import AuditEvent, IngestionError
from execplus.domain.operations import StaffAudit
from execplus.domain.plans import fingerprint
from execplus.domain.usage_metering import (
    TokenUsage,
    UsageAttempt,
    UsageAttribution,
    UsagePolicy,
    UsagePrice,
    UsageTotals,
)
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json(item) for item in value]
    return value


def _price(row: Any) -> UsagePrice:
    definition = row["definition"]
    return UsagePrice(
        row["id"],
        row["provider"],
        row["model"],
        row["currency"],
        Decimal(definition["input_per_million"]),
        Decimal(definition["output_per_million"]),
        Decimal(definition["cached_input_per_million"])
        if definition["cached_input_per_million"] is not None
        else None,
        definition["evidence_ref"],
        row["created_by"],
        row["created_at"],
    )


class SQLUsageRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.control = SQLWorkspaceRepository(connection)

    def admit_model_attempt(
        self,
        attribution: UsageAttribution,
        attempt_id: UUID,
        provider: str,
        model: str,
        now: datetime,
    ) -> None:
        self.control.admit_plan_operation(
            attribution.workspace_id,
            attribution.actor_id,
            "model_attempts",
            attempt_id,
            fingerprint({"attribution": asdict(attribution), "provider": provider, "model": model}),
            now,
        )

    def lock_workspace(self, workspace_id: UUID) -> None:
        self.control.workspace(workspace_id, lock=True)

    def require_member(self, workspace_id: UUID, actor_id: UUID) -> None:
        self.control.membership(workspace_id, actor_id)

    def require_owner_full(self, workspace_id: UUID, actor_id: UUID) -> None:
        if self.control.membership(workspace_id, actor_id).role != "owner":
            raise IngestionError("forbidden", "Only the workspace owner can view model usage.", 403)
        require_workspace_access(self.control, self.control.user(actor_id), workspace_id)

    def require_operator(self, actor_id: UUID) -> None:
        self.control.require_active_actor(actor_id)
        grant = self.control.staff_grant(actor_id, lock=True)
        if grant is None or grant.revoked_at is not None or grant.role != "admin":
            raise IngestionError(
                "staff_required", "An active operator must configure model allowances.", 403
            )

    def require_workspace_full(self, workspace_id: UUID, actor_id: UUID) -> None:
        self.control.membership(workspace_id, actor_id)
        require_workspace_access(self.control, self.control.user(actor_id), workspace_id)

    def pending(
        self, workspace_id: UUID, limit: int, older_than: datetime | None = None
    ) -> tuple[UsageAttempt, ...]:
        scope = [
            s.usage_attempts.c.workspace_id == workspace_id,
            s.usage_attempts.c.state.in_(("reserved", "started", "unknown")),
        ]
        if older_than is not None:
            scope.extend(
                (
                    s.usage_attempts.c.created_at <= older_than,
                    s.usage_attempts.c.state.in_(("reserved", "started")),
                )
            )
        ids = self.connection.execute(
            select(s.usage_attempts.c.id)
            .where(*scope)
            .order_by(s.usage_attempts.c.created_at, s.usage_attempts.c.id)
            .limit(limit)
        ).scalars()
        values = (self.attempt(workspace_id, identifier) for identifier in ids)
        return tuple(value for value in values if value is not None)

    def policy(self, workspace_id: UUID) -> UsagePolicy | None:
        row = (
            self.connection.execute(
                select(s.usage_policies)
                .where(s.usage_policies.c.workspace_id == workspace_id)
                .order_by(s.usage_policies.c.version.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        definition = row["definition"]
        return UsagePolicy(
            row["id"],
            workspace_id,
            row["version"],
            definition["plan_key"],
            row["starts_at"],
            row["ends_at"],
            definition["max_attempts"],
            definition["max_in_flight"],
            definition["currency"],
            Decimal(definition["spend_limit"]) if definition["spend_limit"] is not None else None,
            Decimal(definition["reservation_per_attempt"])
            if definition["reservation_per_attempt"] is not None
            else None,
            row["created_by"],
        )

    def price(self, provider: str, model: str, at: datetime) -> UsagePrice | None:
        row = (
            self.connection.execute(
                select(s.usage_prices)
                .where(
                    s.usage_prices.c.provider == provider,
                    s.usage_prices.c.model == model,
                    s.usage_prices.c.created_at <= at,
                )
                .order_by(s.usage_prices.c.created_at.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        return _price(row) if row is not None else None

    def attempt(self, workspace_id: UUID, attempt_id: UUID) -> UsageAttempt | None:
        row = (
            self.connection.execute(
                select(s.usage_attempts).where(
                    s.usage_attempts.c.workspace_id == workspace_id,
                    s.usage_attempts.c.id == attempt_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        price = None
        if row["price_id"] is not None:
            price = _price(
                self.connection.execute(
                    select(s.usage_prices).where(s.usage_prices.c.id == row["price_id"])
                )
                .mappings()
                .one()
            )
        return UsageAttempt(
            id=row["id"],
            attribution=UsageAttribution(
                workspace_id, row["actor_id"], row["operation_id"], row["operation"]
            ),
            provider=row["provider"],
            model=row["model"],
            created_at=row["created_at"],
            policy_id=row["policy_id"],
            price=price,
            currency=row["currency"],
            held_exposure=row["held_exposure"],
            state=row["state"],
            version=row["version"],
            outcome=row["outcome"],
            usage=TokenUsage(**row["usage"]),
            cost=row["cost"],
            cost_basis=row["cost_basis"],
            evidence_ref=row["evidence_ref"],
            finished_at=row["finished_at"],
        )

    def totals(self, workspace_id: UUID, policy: UsagePolicy | None) -> UsageTotals:
        table = s.usage_attempts
        scope = [table.c.workspace_id == workspace_id, table.c.state != "released"]
        if policy is not None:
            scope.extend(
                (table.c.created_at >= policy.starts_at, table.c.created_at < policy.ends_at)
            )
        money_scope = table.c.currency == policy.currency if policy and policy.currency else true()
        row = (
            self.connection.execute(
                select(
                    func.count().label("attempts"),
                    func.coalesce(func.sum(case((money_scope, table.c.cost), else_=0)), 0).label(
                        "known_cost"
                    ),
                    func.coalesce(
                        func.sum(case((money_scope, table.c.held_exposure), else_=0)), 0
                    ).label("held_exposure"),
                    func.count().filter(table.c.state == "unknown").label("unknown_attempts"),
                    func.count()
                    .filter(
                        or_(
                            and_(table.c.cost.is_(None), table.c.held_exposure == 0),
                            table.c.currency.is_distinct_from(policy.currency)
                            if policy and policy.currency
                            else false(),
                        )
                    )
                    .label("uncovered_attempts"),
                )
                .select_from(table)
                .where(*scope)
            )
            .mappings()
            .one()
        )
        active = self.connection.execute(
            select(func.count())
            .select_from(table)
            .where(
                table.c.workspace_id == workspace_id,
                table.c.state.in_(("reserved", "started")),
            )
        ).scalar_one()
        return UsageTotals(
            row["attempts"],
            active,
            Decimal(row["known_cost"]),
            Decimal(row["held_exposure"]),
            row["unknown_attempts"],
            row["uncovered_attempts"],
        )

    def write_attempt(
        self,
        previous: UsageAttempt | None,
        value: UsageAttempt,
        event: str,
        actor_id: UUID,
        at: datetime,
    ) -> None:
        if event not in {
            "reserved",
            "dispatched",
            "provider_result",
            "released_before_dispatch",
            "operator_reconciled",
            "recovered",
        }:
            raise ValueError("Use a fixed accounting event")
        fields = dict(
            workspace_id=value.attribution.workspace_id,
            id=value.id,
            actor_id=value.attribution.actor_id,
            operation_id=value.attribution.operation_id,
            operation=value.attribution.operation,
            provider=value.provider,
            model=value.model,
            created_at=value.created_at,
            policy_id=value.policy_id,
            price_id=value.price.id if value.price else None,
            currency=value.currency,
            state=value.state,
            version=value.version,
            held_exposure=value.held_exposure,
            cost=value.cost,
            outcome=value.outcome,
            usage=asdict(value.usage),
            cost_basis=value.cost_basis,
            evidence_ref=value.evidence_ref,
            finished_at=value.finished_at,
        )
        if previous is None:
            self.connection.execute(s.usage_attempts.insert().values(**fields))
        else:
            result = self.connection.execute(
                update(s.usage_attempts)
                .where(
                    s.usage_attempts.c.workspace_id == value.attribution.workspace_id,
                    s.usage_attempts.c.id == value.id,
                    s.usage_attempts.c.version == previous.version,
                )
                .values(**fields)
            )
            if result.rowcount != 1:
                raise IngestionError(
                    "usage_attempt_conflict", "Usage changed before reconciliation.", 409
                )
        self.connection.execute(
            s.model_usage_events.insert().values(
                id=uuid4(),
                workspace_id=value.attribution.workspace_id,
                attempt_id=value.id,
                sequence=value.version,
                actor_id=actor_id,
                kind=event,
                created_at=at,
                snapshot=_json(fields),
            )
        )

    def add_policy(self, policy: UsagePolicy) -> None:
        body = asdict(policy)
        fields = {
            key: body.pop(key)
            for key in ("id", "workspace_id", "version", "starts_at", "ends_at", "created_by")
        }
        self.connection.execute(s.usage_policies.insert().values(**fields, definition=_json(body)))
        self.control.add(
            AuditEvent(
                uuid4(),
                policy.workspace_id,
                policy.created_by,
                "usage_policy.changed",
                "workspace",
                policy.workspace_id,
                datetime.now(timezone.utc),
            )
        )

    def add_price(self, price: UsagePrice) -> None:
        existing = (
            self.connection.execute(select(s.usage_prices).where(s.usage_prices.c.id == price.id))
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if _price(existing) != price:
                raise IngestionError(
                    "usage_price_conflict",
                    "This price identifier already has different evidence.",
                    409,
                )
            return
        body = asdict(price)
        fields = {
            key: body.pop(key)
            for key in ("id", "provider", "model", "currency", "created_by", "created_at")
        }
        try:
            self.connection.execute(
                s.usage_prices.insert().values(**fields, definition=_json(body))
            )
        except IntegrityError:
            raise IngestionError(
                "usage_price_conflict",
                "A price already exists for this model and effective time.",
                409,
            ) from None
        self.control.add_staff_audit(
            StaffAudit(
                uuid4(),
                price.created_by,
                "usage.price_configured",
                "api",
                "success",
                datetime.now(timezone.utc),
                resource_id=price.id,
            )
        )

    def summary(self, workspace_id: UUID, starts_at: datetime, ends_at: datetime) -> dict[str, Any]:
        table = s.usage_attempts
        scope = (
            table.c.workspace_id == workspace_id,
            table.c.created_at >= starts_at,
            table.c.created_at < ends_at,
        )
        counts = dict(
            self.connection.execute(
                select(
                    func.count().filter(table.c.state != "released").label("attempts"),
                    func.count()
                    .filter(table.c.state == "released")
                    .label("released_before_dispatch"),
                    func.count()
                    .filter(table.c.state.in_(("reserved", "started")))
                    .label("in_flight"),
                    func.count().filter(table.c.state == "unknown").label("unknown_cost_attempts"),
                )
                .select_from(table)
                .where(*scope)
            )
            .mappings()
            .one()
        )
        costs = [
            dict(row)
            for row in self.connection.execute(
                select(
                    table.c.currency,
                    func.sum(table.c.cost).label("known_cost"),
                    func.sum(table.c.held_exposure).label("held_exposure"),
                    func.count().filter(table.c.cost.is_not(None)).label("priced_attempts"),
                    func.count().filter(table.c.state == "unknown").label("unknown_attempts"),
                )
                .where(*scope, table.c.state != "released")
                .group_by(table.c.currency)
                .order_by(table.c.currency)
            ).mappings()
        ]
        tokens = dict(
            self.connection.execute(
                select(
                    *[
                        expression
                        for key in ("input_tokens", "output_tokens", "cached_input_tokens")
                        for expression in (
                            func.sum(table.c.usage[key].as_integer()).label(key),
                            func.count(table.c.usage[key].as_integer()).label(
                                key + "_reported_attempts"
                            ),
                        )
                    ]
                ).where(*scope, table.c.state != "released")
            )
            .mappings()
            .one()
        )
        policy = self.policy(workspace_id)
        for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
            tokens[key] = str(tokens[key]) if tokens[key] is not None else None
        allowance = None
        if policy is not None:
            allowance = {
                key: value
                for key, value in asdict(policy).items()
                if key not in {"created_by", "workspace_id"}
            }
            allowance["current_totals"] = asdict(self.totals(workspace_id, policy))
        return cast(
            dict[str, Any],
            _json(
                dict(
                    starts_at=starts_at,
                    ends_at=ends_at,
                    counts=counts,
                    costs=costs,
                    tokens=tokens,
                    allowance=allowance,
                    limitation=(
                        "Known costs use configured prices and reported usage. "
                        "Missing usage remains unknown; "
                        "reservations are not a provider invoice guarantee."
                    ),
                )
            ),
        )


class SQLUsageUnitOfWork:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def __call__(self) -> Iterator[UsageRepository]:
        with self.engine.begin() as connection:
            connection.exec_driver_sql("SET LOCAL lock_timeout = '2000ms'")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
            yield SQLUsageRepository(connection)
