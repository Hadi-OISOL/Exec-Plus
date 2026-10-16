"""Use case: Reserves workspace model capacity before dispatch and settles evidence.

What it does: Serializes admission and idempotent ledger writes, keeps unknown
exposure held, and separates operator configuration from private owner summaries.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from execplus.application.usage_ports import UsageRepository
from execplus.domain.ingestion import IngestionError
from execplus.domain.usage_metering import (
    TokenUsage,
    UsageAttempt,
    UsageAttribution,
    UsagePolicy,
    UsagePrice,
    check_allowance,
    finish_attempt,
    reconcile_unknown,
    release_attempt,
    start_attempt,
)

UsageUnitOfWork = Callable[[], AbstractContextManager[UsageRepository]]


def now() -> datetime:
    return datetime.now(timezone.utc)


class UsageMeteringService:
    def __init__(self, uow: UsageUnitOfWork) -> None:
        self.uow = uow

    def reserve(
        self,
        attribution: UsageAttribution,
        attempt_id: UUID,
        provider: str,
        model: str,
    ) -> UsageAttempt:
        with self.uow() as repo:
            repo.lock_workspace(attribution.workspace_id)
            repo.require_member(attribution.workspace_id, attribution.actor_id)
            previous = repo.attempt(attribution.workspace_id, attempt_id)
            if previous is not None:
                if previous.attribution.actor_id != attribution.actor_id:
                    raise IngestionError("not_found", "Usage attempt unavailable.", 404)
                if (previous.attribution, previous.provider, previous.model) != (
                    attribution,
                    provider,
                    model,
                ):
                    raise IngestionError(
                        "usage_attempt_conflict", "This attempt identifier is already in use.", 409
                    )
                return previous
            timestamp = now()
            policy = repo.policy(attribution.workspace_id)
            exposure = check_allowance(
                policy, repo.totals(attribution.workspace_id, policy), timestamp
            )
            price = repo.price(provider, model, timestamp)
            currency = (
                policy.currency if policy and policy.currency else price.currency if price else None
            )
            if policy and policy.currency and price and price.currency != policy.currency:
                raise IngestionError(
                    "usage_currency", "The configured model price uses a different currency.", 503
                )
            value = UsageAttempt(
                attempt_id,
                attribution,
                provider,
                model,
                timestamp,
                policy_id=policy.id if policy else None,
                price=price,
                currency=currency,
                held_exposure=exposure,
            )
            repo.write_attempt(None, value, "reserved", attribution.actor_id, timestamp)
            return value

    def _owned(
        self, repo: UsageRepository, attribution: UsageAttribution, attempt_id: UUID
    ) -> UsageAttempt:
        repo.lock_workspace(attribution.workspace_id)
        value = repo.attempt(attribution.workspace_id, attempt_id)
        if value is None or value.attribution != attribution:
            raise IngestionError("not_found", "Usage attempt unavailable.", 404)
        return value

    def start(self, attribution: UsageAttribution, attempt_id: UUID) -> UsageAttempt:
        with self.uow() as repo:
            previous = self._owned(repo, attribution, attempt_id)
            repo.require_member(attribution.workspace_id, attribution.actor_id)
            value = start_attempt(previous)
            repo.write_attempt(previous, value, "dispatched", attribution.actor_id, now())
            return value

    def finish(
        self,
        attribution: UsageAttribution,
        attempt_id: UUID,
        outcome: str,
        usage: TokenUsage,
    ) -> UsageAttempt:
        with self.uow() as repo:
            previous = self._owned(repo, attribution, attempt_id)
            timestamp = now()
            value = finish_attempt(previous, outcome, usage, timestamp)
            if value != previous:
                repo.write_attempt(
                    previous, value, "provider_result", attribution.actor_id, timestamp
                )
            return value

    def release(self, attribution: UsageAttribution, attempt_id: UUID) -> UsageAttempt:
        with self.uow() as repo:
            previous = self._owned(repo, attribution, attempt_id)
            timestamp = now()
            value = release_attempt(previous, timestamp)
            if value != previous:
                repo.write_attempt(
                    previous, value, "released_before_dispatch", attribution.actor_id, timestamp
                )
            return value

    def reconcile(
        self,
        operator_id: UUID,
        wid: UUID,
        attempt_id: UUID,
        cost: Decimal,
        currency: str,
        evidence_kind: str,
        evidence_ref: str,
    ) -> UsageAttempt:
        if (
            evidence_kind not in {"provider_usage_record", "provider_invoice_record"}
            or not isinstance(evidence_ref, str)
            or not evidence_ref.strip()
        ):
            raise IngestionError(
                "usage_evidence", "Use an independent provider usage or invoice record.", 422
            )
        with self.uow() as repo:
            repo.require_operator(operator_id)
            repo.lock_workspace(wid)
            repo.require_workspace_full(wid, operator_id)
            previous = repo.attempt(wid, attempt_id)
            if previous is None:
                raise IngestionError("not_found", "Usage attempt unavailable.", 404)
            timestamp = now()
            value = reconcile_unknown(
                previous, cost, currency, f"{evidence_kind}:{evidence_ref}", timestamp
            )
            if value != previous:
                repo.write_attempt(previous, value, "operator_reconciled", operator_id, timestamp)
            return value

    def set_policy(self, operator_id: UUID, policy: UsagePolicy, expected_version: int) -> None:
        with self.uow() as repo:
            repo.require_operator(operator_id)
            repo.lock_workspace(policy.workspace_id)
            previous = repo.policy(policy.workspace_id)
            version = previous.version if previous else 0
            if (
                type(expected_version) is not int
                or expected_version != version
                or policy.version != version + 1
            ):
                raise IngestionError(
                    "usage_policy_conflict",
                    "The workspace allowance changed. Reload it first.",
                    409,
                )
            if policy.created_by != operator_id:
                raise IngestionError(
                    "usage_policy_owner", "The operator must own the configuration record.", 422
                )
            repo.add_policy(policy)

    def set_price(self, operator_id: UUID, price: UsagePrice) -> None:
        with self.uow() as repo:
            repo.require_operator(operator_id)
            if price.created_by != operator_id:
                raise IngestionError(
                    "usage_price_owner", "The operator must own the price record.", 422
                )
            repo.add_price(price)

    def summary(
        self, actor_id: UUID, wid: UUID, starts_at: datetime, ends_at: datetime
    ) -> dict[str, Any]:
        if (
            starts_at.tzinfo is None
            or ends_at.tzinfo is None
            or ends_at <= starts_at
            or (ends_at - starts_at).total_seconds() > 366 * 86400
        ):
            raise IngestionError(
                "usage_period", "Choose a dated usage window of up to one year.", 422
            )
        with self.uow() as repo:
            repo.lock_workspace(wid)
            repo.require_owner_full(wid, actor_id)
            result = repo.summary(wid, starts_at, ends_at)
            if result["allowance"] is not None:
                code = None
                try:
                    policy = repo.policy(wid)
                    check_allowance(policy, repo.totals(wid, policy), now())
                except IngestionError as error:
                    code = error.code
                result["allowance"]["availability"] = {"can_start_next": code is None, "code": code}
            return result

    def pending(self, operator_id: UUID, wid: UUID, limit: int = 50) -> tuple[UsageAttempt, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise IngestionError("usage_limit", "Choose up to one hundred attempts.", 422)
        with self.uow() as repo:
            repo.require_operator(operator_id)
            repo.lock_workspace(wid)
            repo.require_workspace_full(wid, operator_id)
            return repo.pending(wid, limit)

    def recover(self, operator_id: UUID, wid: UUID, older_than: datetime) -> dict[str, int]:
        timestamp = now()
        if older_than.tzinfo is None or older_than > timestamp - timedelta(minutes=15):
            raise IngestionError(
                "usage_recovery_window",
                "Only attempts older than fifteen minutes can be recovered.",
                422,
            )
        with self.uow() as repo:
            repo.require_operator(operator_id)
            repo.lock_workspace(wid)
            repo.require_workspace_full(wid, operator_id)
            counts = {"released_before_dispatch": 0, "unknown": 0}
            for previous in repo.pending(wid, 100, older_than):
                if previous.state == "reserved":
                    value = release_attempt(previous, timestamp)
                    counts["released_before_dispatch"] += 1
                else:
                    value = finish_attempt(previous, "interrupted", TokenUsage(), timestamp)
                    counts["unknown"] += 1
                repo.write_attempt(previous, value, "recovered", operator_id, timestamp)
            return counts
