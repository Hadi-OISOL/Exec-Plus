"""Use case: Checks exact declared pricing and conservative unknown-usage handling.

What it does: Exercises malformed provider counters, reservation limits, idempotent
settlement and asynchronous ownership context without contacting a provider.
"""

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from uuid import uuid4

import pytest

from execplus.application.usage_context import current_usage, usage_scope
from execplus.domain.ingestion import IngestionError
from execplus.domain.usage_metering import (
    TokenUsage,
    UsageAttempt,
    UsageAttribution,
    UsagePolicy,
    UsagePrice,
    UsageTotals,
    check_allowance,
    finish_attempt,
    priced_usage,
    reconcile_unknown,
    release_attempt,
    reported_usage,
    start_attempt,
)

NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)


def price(**changes):
    return UsagePrice(
        **dict(
            id=uuid4(),
            provider="test-provider",
            model="fictional-model",
            currency="USD",
            input_per_million=Decimal("2.75"),
            output_per_million=Decimal("8.125"),
            cached_input_per_million=Decimal("0.125"),
            evidence_ref="test-fixture-only",
            created_by=uuid4(),
            created_at=NOW,
        )
        | changes
    )


def attribution(**changes):
    return UsageAttribution(
        **dict(
            workspace_id=uuid4(), actor_id=uuid4(), operation_id=uuid4(), operation="conversation"
        )
        | changes
    )


def policy(**changes):
    return UsagePolicy(
        **dict(
            id=uuid4(),
            workspace_id=uuid4(),
            version=1,
            plan_key="fictional-test-plan",
            starts_at=NOW,
            ends_at=NOW + timedelta(days=1),
            max_attempts=10,
            max_in_flight=2,
            currency="USD",
            spend_limit=Decimal("1"),
            reservation_per_attempt=Decimal("0.1"),
            created_by=uuid4(),
        )
        | changes
    )


def attempt(**changes):
    return UsageAttempt(
        **dict(
            id=uuid4(),
            attribution=attribution(),
            provider="test-provider",
            model="fictional-model",
            created_at=NOW,
            policy_id=uuid4(),
            price=price(),
            currency="USD",
            held_exposure=Decimal("0.1"),
        )
        | changes
    )


@pytest.mark.parametrize("bad", [True, -1, 1.1, "100", 1_000_000_001, float("inf"), {}, []])
def test_untrusted_token_counts_remain_unknown_and_never_become_zero(bad):
    usage = reported_usage({"prompt_tokens": bad, "completion_tokens": 2})
    assert usage.input_tokens is None and usage.output_tokens == 2 and usage.invalid_report
    assert priced_usage(usage, price()) is None


@pytest.mark.parametrize("raw", [None, {}, {"prompt_tokens": 0}])
def test_absent_provider_usage_is_not_a_zero_cost(raw):
    usage = reported_usage(raw)
    assert usage.output_tokens is None and priced_usage(usage, price()) is None


def test_declared_token_rates_match_an_independent_exact_fraction_calculation():
    usage = reported_usage(
        {
            "prompt_tokens": 12345,
            "completion_tokens": 6789,
            "prompt_tokens_details": {"cached_tokens": 345},
        }
    )
    value = priced_usage(usage, price())
    expected = (
        Fraction(12000) * Fraction(11, 4) + Fraction(345) / 8 + Fraction(6789) * Fraction(65, 8)
    ) / 1_000_000
    assert Fraction(value) == expected
    assert priced_usage(TokenUsage(0, 0, 0), price()) == 0
    assert priced_usage(usage, None) is None


def test_missing_or_invalid_cache_breakdown_cannot_invent_a_discount():
    assert priced_usage(TokenUsage(10, 5), price()) is None
    uniform = price(cached_input_per_million=Decimal("2.75"))
    assert priced_usage(TokenUsage(10, 5), uniform) == Decimal("0.000068125")
    invalid = reported_usage(
        {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 11},
        }
    )
    assert invalid.cached_input_tokens is None and invalid.invalid_report
    assert priced_usage(invalid, uniform) is None


@pytest.mark.parametrize(
    "bad", [Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("0.0000000000001")]
)
def test_operator_prices_are_explicit_finite_exact_amounts(bad):
    with pytest.raises(ValueError):
        price(input_per_million=bad)


@pytest.mark.parametrize(
    "totals,code",
    [
        (UsageTotals(attempts=10), "usage_attempt_limit"),
        (UsageTotals(in_flight=2), "usage_concurrency"),
        (
            UsageTotals(known_cost=Decimal("0.8"), held_exposure=Decimal("0.100000000001")),
            "usage_spend_limit",
        ),
        (UsageTotals(held_exposure=Decimal("1"), unknown_attempts=10), "usage_spend_limit"),
    ],
)
def test_allowance_reserves_known_cost_plus_uncertain_exposure(totals, code):
    with pytest.raises(IngestionError) as caught:
        check_allowance(policy(), totals, NOW)
    assert caught.value.code == code


def test_allowance_boundary_is_exact_and_expired_policy_does_not_become_unlimited():
    assert check_allowance(policy(), UsageTotals(known_cost=Decimal("0.9")), NOW) == Decimal("0.1")
    for instant in (NOW - timedelta(microseconds=1), NOW + timedelta(days=1)):
        with pytest.raises(IngestionError) as caught:
            check_allowance(policy(), UsageTotals(), instant)
        assert caught.value.code == "usage_window"
    assert check_allowance(None, UsageTotals(), NOW) == 0


@pytest.mark.parametrize(
    "outcome", ["timeout", "cancelled", "interrupted", "http_error", "invalid_response"]
)
def test_unknown_attempt_retains_exposure_and_requires_independent_settlement(outcome):
    reserved = attempt()
    started = start_attempt(reserved)
    value = finish_attempt(started, outcome, TokenUsage(), NOW)
    assert value.state == "unknown" and value.cost is None and value.held_exposure == Decimal("0.1")
    assert finish_attempt(value, outcome, TokenUsage(), NOW + timedelta(seconds=1)) == value
    with pytest.raises(IngestionError):
        release_attempt(value, NOW)
    with pytest.raises(ValueError):
        reconcile_unknown(value, Decimal("0"), "USD", "", NOW)
    settled = reconcile_unknown(value, Decimal("0.015"), "USD", "provider-invoice-record-abc", NOW)
    assert settled.state == "settled" and settled.cost == Decimal("0.015")
    assert settled.usage == TokenUsage() and settled.cost_basis == "operator_confirmed_charge"
    assert settled.held_exposure == 0
    assert (
        reconcile_unknown(settled, Decimal("0.015"), "USD", "provider-invoice-record-abc", NOW)
        == settled
    )
    with pytest.raises(IngestionError):
        reconcile_unknown(settled, Decimal("0"), "USD", "different-record", NOW)
    with pytest.raises(IngestionError):
        start_attempt(started)


def test_truncated_reply_keeps_reported_usage_and_real_cost_even_above_reservation():
    started = start_attempt(attempt())
    value = finish_attempt(started, "truncated", TokenUsage(1_000_000, 1_000_000, 0), NOW)
    assert value.state == "settled" and value.cost == Decimal("10.875")
    assert value.held_exposure == 0 and value.outcome == "truncated"
    with pytest.raises(IngestionError) as caught:
        check_allowance(policy(), UsageTotals(known_cost=value.cost), NOW)
    assert caught.value.code == "usage_spend_limit"
    assert started.cost is None and started.held_exposure == Decimal("0.1")


def test_only_undispatched_reservation_can_be_released_without_provider_evidence():
    reserved = attempt()
    released = release_attempt(reserved, NOW)
    assert released.state == "released" and released.held_exposure == 0 and released.cost is None
    assert release_attempt(released, NOW) == released
    with pytest.raises(IngestionError):
        finish_attempt(reserved, "succeeded", TokenUsage(1, 1, 0), NOW)
    with pytest.raises(IngestionError):
        release_attempt(start_attempt(reserved), NOW)


def test_currency_mismatch_and_inconsistent_reconciliation_fail_closed():
    value = finish_attempt(
        start_attempt(attempt(currency="EUR")), "succeeded", TokenUsage(1, 1, 0), NOW
    )
    assert value.state == "unknown" and value.held_exposure == Decimal("0.1")
    with pytest.raises(IngestionError):
        reconcile_unknown(value, Decimal("1"), "USD", "invoice-record", NOW)
    with pytest.raises(IngestionError):
        finish_attempt(value, "succeeded", TokenUsage(2, 2, 0), NOW)


def test_async_usage_context_is_private_restored_and_cannot_switch_owners():
    async def run():
        first, second = attribution(), attribution()

        async def child(value):
            with usage_scope(value):
                await asyncio.sleep(0)
                assert current_usage() == value
                with usage_scope(replace(value, operation_id=uuid4(), operation="summary")):
                    assert current_usage() == value
                with pytest.raises(IngestionError), usage_scope(attribution()):
                    pass
                return current_usage()

        assert await asyncio.gather(child(first), child(second)) == [first, second]
        assert current_usage(required=False) is None
        with pytest.raises(IngestionError):
            current_usage()
        with pytest.raises(asyncio.CancelledError), usage_scope(first):
            raise asyncio.CancelledError
        assert current_usage(required=False) is None

    asyncio.run(run())


def test_provider_cache_counts_are_used_only_when_present_consistent_and_bounded():
    value = reported_usage(
        {"prompt_tokens": 100, "completion_tokens": 10, "prompt_cache_hit_tokens": 20}
    )
    assert value == TokenUsage(100, 10, 20)
    assert reported_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "prompt_cache_hit_tokens": 20,
            "prompt_tokens_details": {"cached_tokens": 30},
        }
    ).invalid_report
