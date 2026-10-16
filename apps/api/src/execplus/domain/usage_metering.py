"""Use case: Defines explicit model-usage reservations and evidence-based settlement.

What it does: Validates bounded provider counts, computes declared prices exactly,
and retains unknown exposure without inventing a zero bill or provider guarantee.
"""

import re
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID

from execplus.domain.ingestion import IngestionError

MAX_REPORTED_TOKENS = 1_000_000_000
MAX_MONEY = Decimal("1000000000000")
OPERATIONS = frozenset({"conversation", "data_reading", "document_answer", "summary"})
OUTCOMES = frozenset(
    {
        "succeeded",
        "truncated",
        "invalid_response",
        "http_error",
        "timeout",
        "cancelled",
        "interrupted",
    }
)


def _time(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Use an explicit timezone for usage records")


def _money(value: Decimal, *, positive: bool = False) -> None:
    with localcontext() as context:
        context.prec = 80
        exponent = (
            value.normalize().as_tuple().exponent
            if isinstance(value, Decimal) and value.is_finite()
            else None
        )
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value < 0
        or value > MAX_MONEY
        or (positive and value == 0)
        or not isinstance(exponent, int)
        or exponent < -12
    ):
        raise ValueError("Use a finite nonnegative declared amount with at most twelve decimals")


def _label(value: str, maximum: int = 160) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or not value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("Use bounded nonempty configuration metadata")


@dataclass(frozen=True)
class UsageAttribution:
    workspace_id: UUID
    actor_id: UUID
    operation_id: UUID
    operation: str

    def __post_init__(self) -> None:
        if (
            any(
                not isinstance(value, UUID)
                for value in (self.workspace_id, self.actor_id, self.operation_id)
            )
            or self.operation not in OPERATIONS
        ):
            raise ValueError("Usage requires a workspace, actor and supported operation")


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    invalid_report: bool = False

    def __post_init__(self) -> None:
        for value in (self.input_tokens, self.output_tokens, self.cached_input_tokens):
            if value is not None and (
                type(value) is not int or not 0 <= value <= MAX_REPORTED_TOKENS
            ):
                raise ValueError("Use bounded integer token counts or explicit unknown values")
        if (
            self.cached_input_tokens is not None
            and self.input_tokens is not None
            and self.cached_input_tokens > self.input_tokens
        ):
            raise ValueError("Cached input cannot exceed total input")
        if type(self.invalid_report) is not bool:
            raise ValueError("Use an explicit report validation flag")


def reported_usage(value: Any) -> TokenUsage:
    if value is None:
        return TokenUsage()
    if not isinstance(value, dict):
        return TokenUsage(invalid_report=True)
    invalid = False

    def count(raw: Any) -> int | None:
        nonlocal invalid
        if raw is None:
            return None
        if type(raw) is int and 0 <= raw <= MAX_REPORTED_TOKENS:
            return raw
        invalid = True
        return None

    incoming = count(value.get("prompt_tokens"))
    outgoing = count(value.get("completion_tokens"))
    details = value.get("prompt_tokens_details")
    cached = None
    if details is not None:
        if isinstance(details, dict):
            cached = count(details.get("cached_tokens"))
        else:
            invalid = True
    if "prompt_cache_hit_tokens" in value:
        provider_cached = count(value["prompt_cache_hit_tokens"])
        if cached is not None and provider_cached != cached:
            invalid, cached = True, None
        elif cached is None:
            cached = provider_cached
    if cached is not None and incoming is not None and cached > incoming:
        invalid, cached = True, None
    return TokenUsage(incoming, outgoing, cached, invalid)


@dataclass(frozen=True)
class UsagePrice:
    id: UUID
    provider: str
    model: str
    currency: str
    input_per_million: Decimal
    output_per_million: Decimal
    cached_input_per_million: Decimal | None
    evidence_ref: str
    created_by: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        for value in (self.id, self.created_by):
            if not isinstance(value, UUID):
                raise ValueError("Price records require explicit identifiers")
        for label in (self.provider, self.model, self.evidence_ref):
            _label(label)
        if not isinstance(self.currency, str) or not re.fullmatch("[A-Z]{3}", self.currency):
            raise ValueError("Declare a three-letter currency code")
        for amount in (self.input_per_million, self.output_per_million):
            _money(amount)
        if self.cached_input_per_million is not None:
            _money(self.cached_input_per_million)
        _time(self.created_at)


def priced_usage(usage: TokenUsage, price: UsagePrice | None) -> Decimal | None:
    if (
        price is None
        or usage.invalid_report
        or usage.input_tokens is None
        or usage.output_tokens is None
    ):
        return None
    cached_rate = price.cached_input_per_million
    if (
        cached_rate is not None
        and cached_rate != price.input_per_million
        and usage.cached_input_tokens is None
    ):
        return None
    cached = usage.cached_input_tokens or 0
    with localcontext() as context:
        context.prec = 80
        return (
            Decimal(usage.input_tokens - cached) * price.input_per_million
            + Decimal(cached)
            * (cached_rate if cached_rate is not None else price.input_per_million)
            + Decimal(usage.output_tokens) * price.output_per_million
        ) / Decimal(1_000_000)


@dataclass(frozen=True)
class UsagePolicy:
    id: UUID
    workspace_id: UUID
    version: int
    plan_key: str
    starts_at: datetime
    ends_at: datetime
    max_attempts: int | None
    max_in_flight: int | None
    currency: str | None
    spend_limit: Decimal | None
    reservation_per_attempt: Decimal | None
    created_by: UUID

    def __post_init__(self) -> None:
        if (
            any(
                not isinstance(value, UUID)
                for value in (self.id, self.workspace_id, self.created_by)
            )
            or type(self.version) is not int
            or self.version < 1
        ):
            raise ValueError("Usage policies require explicit versioned identifiers")
        _label(self.plan_key, 80)
        _time(self.starts_at)
        _time(self.ends_at)
        if self.ends_at <= self.starts_at:
            raise ValueError("An allowance requires a nonempty explicit time window")
        for value, maximum in ((self.max_attempts, 10_000_000), (self.max_in_flight, 10_000)):
            if value is not None and (type(value) is not int or not 1 <= value <= maximum):
                raise ValueError("Use a bounded positive allowance or no limit")
        if self.spend_limit is None:
            if self.currency is not None or self.reservation_per_attempt is not None:
                raise ValueError("Currency and reservations require an explicit spending limit")
        else:
            _money(self.spend_limit)
            if self.reservation_per_attempt is None:
                raise ValueError("A spending limit requires explicit per-attempt exposure")
            _money(self.reservation_per_attempt, positive=True)
            if not isinstance(self.currency, str) or not re.fullmatch("[A-Z]{3}", self.currency):
                raise ValueError("Declare the allowance currency")


@dataclass(frozen=True)
class UsageTotals:
    attempts: int = 0
    in_flight: int = 0
    known_cost: Decimal = Decimal(0)
    held_exposure: Decimal = Decimal(0)
    unknown_attempts: int = 0
    uncovered_attempts: int = 0

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 0
            for value in (
                self.attempts,
                self.in_flight,
                self.unknown_attempts,
                self.uncovered_attempts,
            )
        ):
            raise ValueError("Usage totals require nonnegative counts")
        for amount in (self.known_cost, self.held_exposure):
            if not isinstance(amount, Decimal) or not amount.is_finite() or amount < 0:
                raise ValueError("Usage totals require exact nonnegative amounts")


def check_allowance(policy: UsagePolicy | None, totals: UsageTotals, now: datetime) -> Decimal:
    _time(now)
    if policy is None:
        return Decimal(0)
    if not policy.starts_at <= now < policy.ends_at:
        raise IngestionError("usage_window", "This workspace allowance is not active.", 429)
    if policy.max_attempts is not None and totals.attempts >= policy.max_attempts:
        raise IngestionError(
            "usage_attempt_limit", "This workspace reached its request allowance.", 429
        )
    if policy.max_in_flight is not None and totals.in_flight >= policy.max_in_flight:
        raise IngestionError(
            "usage_concurrency", "This workspace already has active model requests.", 429
        )
    if policy.spend_limit is not None and totals.uncovered_attempts:
        raise IngestionError(
            "usage_unresolved",
            "Earlier model usage needs cost evidence before this spending allowance can be used.",
            429,
        )
    reserve = policy.reservation_per_attempt or Decimal(0)
    with localcontext() as context:
        context.prec = 80
        if (
            policy.spend_limit is not None
            and totals.known_cost + totals.held_exposure + reserve > policy.spend_limit
        ):
            raise IngestionError(
                "usage_spend_limit", "This workspace reached its reserved spending limit.", 429
            )
    return reserve


@dataclass(frozen=True)
class UsageAttempt:
    id: UUID
    attribution: UsageAttribution
    provider: str
    model: str
    created_at: datetime
    policy_id: UUID | None = None
    price: UsagePrice | None = None
    currency: str | None = None
    held_exposure: Decimal = Decimal(0)
    state: str = "reserved"
    version: int = 1
    outcome: str | None = None
    usage: TokenUsage = TokenUsage()
    cost: Decimal | None = None
    cost_basis: str | None = None
    evidence_ref: str | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.attribution, UsageAttribution):
            raise ValueError("An attempt requires validated attribution")
        for value in (self.provider, self.model):
            _label(value)
        _time(self.created_at)
        if self.finished_at is not None:
            _time(self.finished_at)
            if self.finished_at < self.created_at:
                raise ValueError("Settlement cannot precede reservation")
        if self.policy_id is not None and not isinstance(self.policy_id, UUID):
            raise ValueError("Use an explicit policy identifier")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("Use a positive attempt version")
        if self.state not in {"reserved", "started", "settled", "unknown", "released"}:
            raise ValueError("Use a supported attempt state")
        if self.currency is not None and not re.fullmatch("[A-Z]{3}", self.currency):
            raise ValueError("Use the declared currency")
        _money(self.held_exposure)
        if self.price is not None and (
            self.price.provider != self.provider or self.price.model != self.model
        ):
            raise ValueError("A price must match the requested provider and model exactly")
        if self.cost is not None and (
            not isinstance(self.cost, Decimal) or not self.cost.is_finite() or self.cost < 0
        ):
            raise ValueError("Use a finite nonnegative measured cost")
        if self.outcome is not None and self.outcome not in OUTCOMES:
            raise ValueError("Use a supported provider outcome")
        if self.cost_basis not in {None, "priced_reported_tokens", "operator_confirmed_charge"}:
            raise ValueError("Use a declared settlement basis")
        if not isinstance(self.usage, TokenUsage):
            raise ValueError("Use validated provider usage")
        if self.state in {"reserved", "started"} and (
            self.finished_at is not None
            or self.outcome is not None
            or self.cost is not None
            or self.cost_basis is not None
            or self.evidence_ref is not None
        ):
            raise ValueError("An unfinished request cannot contain settlement evidence")
        if self.state in {"settled", "unknown", "released"} and (
            self.finished_at is None or self.outcome is None
        ):
            raise ValueError("A finished request requires a recorded outcome and time")
        if self.state == "settled" and (
            self.cost is None
            or self.cost_basis is None
            or self.currency is None
            or self.held_exposure != 0
        ):
            raise ValueError(
                "A settled request requires cost evidence and releases its reservation"
            )
        if self.state in {"unknown", "released"} and (
            self.cost is not None or self.cost_basis is not None or self.evidence_ref is not None
        ):
            raise ValueError("Unsettled requests cannot claim a measured cost")
        if self.state == "released" and self.held_exposure != 0:
            raise ValueError("A safely undispatched request cannot retain a reservation")
        if self.cost_basis == "operator_confirmed_charge":
            if self.evidence_ref is None:
                raise ValueError("Operator settlement requires independent evidence")
            _label(self.evidence_ref)


def start_attempt(attempt: UsageAttempt) -> UsageAttempt:
    if attempt.state != "reserved":
        raise IngestionError(
            "usage_attempt_conflict", "This model attempt cannot be sent again.", 409
        )
    return replace(attempt, state="started", version=attempt.version + 1)


def release_attempt(attempt: UsageAttempt, now: datetime) -> UsageAttempt:
    _time(now)
    if attempt.state == "released":
        return attempt
    if attempt.state != "reserved":
        raise IngestionError(
            "usage_attempt_conflict",
            "An attempted request cannot be refunded without evidence.",
            409,
        )
    return replace(
        attempt,
        state="released",
        held_exposure=Decimal(0),
        version=attempt.version + 1,
        outcome="cancelled",
        finished_at=now,
    )


def finish_attempt(
    attempt: UsageAttempt, outcome: str, usage: TokenUsage, now: datetime
) -> UsageAttempt:
    _time(now)
    if outcome not in OUTCOMES:
        raise ValueError("Use a supported provider outcome")
    if attempt.state in {"settled", "unknown"}:
        if attempt.outcome == outcome and attempt.usage == usage and attempt.evidence_ref is None:
            return attempt
        raise IngestionError(
            "usage_attempt_conflict", "This attempt already has different usage evidence.", 409
        )
    if attempt.state != "started":
        raise IngestionError(
            "usage_attempt_conflict", "Only a dispatched attempt can be reconciled.", 409
        )
    cost = priced_usage(usage, attempt.price)
    if attempt.price is not None and attempt.currency not in {None, attempt.price.currency}:
        cost = None
    return replace(
        attempt,
        state="settled" if cost is not None else "unknown",
        version=attempt.version + 1,
        outcome=outcome,
        usage=usage,
        cost=cost,
        currency=attempt.currency or (attempt.price.currency if attempt.price else None),
        cost_basis="priced_reported_tokens" if cost is not None else None,
        held_exposure=Decimal(0) if cost is not None else attempt.held_exposure,
        finished_at=now,
    )


def reconcile_unknown(
    attempt: UsageAttempt, cost: Decimal, currency: str, evidence_ref: str, now: datetime
) -> UsageAttempt:
    _time(now)
    _money(cost)
    _label(evidence_ref)
    if not isinstance(currency, str) or not re.fullmatch("[A-Z]{3}", currency):
        raise ValueError("Declare the evidence currency")
    if attempt.currency is not None and currency != attempt.currency:
        raise IngestionError("usage_currency", "Evidence must use the allowance currency.", 422)
    if attempt.evidence_ref is not None:
        if (
            attempt.cost == cost
            and attempt.currency == currency
            and attempt.evidence_ref == evidence_ref
        ):
            return attempt
        raise IngestionError(
            "usage_attempt_conflict", "This attempt already has different settlement evidence.", 409
        )
    if attempt.state != "unknown":
        raise IngestionError(
            "usage_attempt_conflict",
            "Only unknown usage can be settled with independent evidence.",
            409,
        )
    return replace(
        attempt,
        state="settled",
        version=attempt.version + 1,
        currency=currency,
        cost=cost,
        cost_basis="operator_confirmed_charge",
        evidence_ref=evidence_ref,
        held_exposure=Decimal(0),
        finished_at=now,
    )
