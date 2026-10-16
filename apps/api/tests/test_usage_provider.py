"""Use case: Verifies durable accounting around actual mocked HTTP model attempts.

What it does: Exercises retries, malformed usage, cancellation, attribution and
storage outages without a hosted provider or disclosure of request content.
"""

import asyncio
import json
from dataclasses import replace
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from execplus.application.contracts import ModelMessage, ModelRequest
from execplus.application.usage_context import usage_scope
from execplus.domain.errors import IncompleteModelResponseError, ProviderUnavailableError
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import ModelTier
from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel
from execplus.infrastructure.persistence import schema as s
from test_usage_metering_integration import configured

SECRET = "Private request and model content never belongs in the ledger"
REQUEST = ModelRequest((ModelMessage("user", SECRET),), ModelTier.SMALL)


def model(service, monkeypatch, handler, attempts=1):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler))
    )
    return OpenAICompatibleLanguageModel(
        "https://model.test/v1",
        "private-provider-key",
        "fictional-model",
        "fictional-model",
        "test-provider",
        max_attempts=attempts,
        retry_backoff_seconds=0,
        metering=service,
    )


def response(usage=None, **changes):
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": SECRET}}],
            "model": "fictional-model",
            "usage": usage,
            **changes,
        },
    )


def rows(env):
    with env.engine.connect() as connection:
        return [dict(row) for row in connection.execute(select(s.usage_attempts)).mappings()]


@pytest.mark.asyncio
async def test_each_retry_is_recorded_and_only_reported_cost_is_settled(integration, monkeypatch):
    service, _, _, _, _, _, _, scope, _ = configured(integration, monkeypatch)
    calls = []

    def handle(request):
        calls.append(request)
        return (
            httpx.Response(503, json={"error": SECRET})
            if len(calls) == 1
            else response(
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "prompt_tokens_details": {"cached_tokens": 20},
                }
            )
        )

    adapter = model(service, monkeypatch, handle, attempts=2)
    with usage_scope(scope):
        result = await adapter.complete(REQUEST)
    assert result.input_tokens == 100 and result.output_tokens == 50
    records = rows(integration)
    assert len(calls) == len(records) == 2
    failed, succeeded = sorted(records, key=lambda item: item["cost"] is not None)
    assert failed["outcome"] == "http_error" and failed["cost"] is None
    assert failed["held_exposure"] == Decimal("0.1")
    assert succeeded["cost"] == Decimal("0.00062875")
    assert all(item["operation_id"] == scope.operation_id for item in records)
    with integration.engine.connect() as connection:
        evidence = list(connection.execute(select(s.model_usage_events.c.snapshot)).scalars())
    assert SECRET not in json.dumps(evidence, default=str)
    assert "private-provider-key" not in json.dumps(evidence, default=str)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["truncated", "invalid_response", "timeout", "cancelled"])
async def test_failed_or_cancelled_attempts_retain_known_usage_or_unknown_exposure(
    integration, monkeypatch, outcome
):
    service, _, _, _, _, _, _, scope, _ = configured(integration, monkeypatch)

    async def handle(request):
        if outcome == "timeout":
            raise httpx.ReadTimeout(SECRET)
        if outcome == "cancelled":
            raise asyncio.CancelledError
        usage = {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 0},
        }
        changes = (
            {"choices": []}
            if outcome == "invalid_response"
            else {"choices": [{"finish_reason": "length", "message": {"content": SECRET}}]}
        )
        return response(usage, **changes)

    adapter = model(service, monkeypatch, handle)
    expected = {"truncated": IncompleteModelResponseError, "cancelled": asyncio.CancelledError}.get(
        outcome, ProviderUnavailableError
    )
    with usage_scope(scope), pytest.raises(expected):
        await adapter.complete(REQUEST)
    (record,) = rows(integration)
    assert record["outcome"] == outcome
    assert record["cost"] is None if outcome in {"cancelled", "timeout"} else record["cost"] > 0
    assert record["held_exposure"] == (Decimal("0.1") if record["cost"] is None else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "usage,changed_model",
    [
        (None, False),
        ({"prompt_tokens": True, "completion_tokens": 1}, False),
        ({"prompt_tokens": 10**30, "completion_tokens": 1}, False),
        ({"prompt_tokens": -1, "completion_tokens": 1}, False),
        ({"prompt_tokens": 10, "completion_tokens": 1}, False),
        (
            {
                "prompt_tokens": 10,
                "completion_tokens": 1,
                "prompt_tokens_details": {"cached_tokens": 0},
            },
            True,
        ),
    ],
)
async def test_untrusted_or_incomplete_usage_never_becomes_a_zero_bill(
    integration, monkeypatch, usage, changed_model
):
    service, _, _, _, _, _, _, scope, _ = configured(integration, monkeypatch)
    adapter = model(
        service,
        monkeypatch,
        lambda request: response(usage, **({"model": "different-model"} if changed_model else {})),
    )
    with usage_scope(scope):
        await adapter.complete(REQUEST)
    (record,) = rows(integration)
    assert record["state"] == "unknown" and record["cost"] is None
    assert record["held_exposure"] == Decimal("0.1")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unattributed", "admission_outage", "allowance", "revoked"])
async def test_no_http_request_without_attribution_membership_and_durable_admission(
    integration, monkeypatch, failure, caplog
):
    service, owner, _, wid, _, _, _, scope, _ = configured(integration, monkeypatch)
    calls = []
    adapter = model(service, monkeypatch, lambda request: calls.append(request))
    if failure == "admission_outage":

        def fail(*args):
            raise RuntimeError(SECRET)

        monkeypatch.setattr(service, "reserve", fail)
    elif failure == "allowance":
        for _ in range(2):
            service.reserve(scope, uuid4(), "test-provider", "fictional-model")
    elif failure == "revoked":
        from test_studies import add_member

        _, actor = add_member(integration, owner, wid)
        scope = replace(scope, actor_id=actor.id)
        integration.runtime.service.remove_member(
            integration.runtime.identity.authenticate(owner["Authorization"].split()[1]),
            UUID(wid),
            actor.id,
        )
    expected = ProviderUnavailableError if failure == "admission_outage" else IngestionError
    with pytest.raises(expected):
        if failure == "unattributed":
            await adapter.complete(REQUEST)
        else:
            with usage_scope(scope):
                await adapter.complete(REQUEST)
    assert calls == [] and SECRET not in caplog.text


@pytest.mark.asyncio
async def test_settlement_outage_does_not_publish_answer_or_resend_and_remains_recoverable(
    integration, monkeypatch, caplog
):
    service, _, _, _, _, _, _, scope, _ = configured(integration, monkeypatch)
    calls = []

    def handle(request):
        calls.append(request)
        return response(
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "prompt_tokens_details": {"cached_tokens": 0},
            }
        )

    def fail(*args):
        raise RuntimeError(SECRET)

    adapter = model(service, monkeypatch, handle, attempts=3)
    monkeypatch.setattr(service, "finish", fail)
    with usage_scope(scope), pytest.raises(ProviderUnavailableError):
        await adapter.complete(REQUEST)
    (record,) = rows(integration)
    assert len(calls) == 1 and record["state"] == "started" and record["cost"] is None
    assert record["held_exposure"] == Decimal("0.1")
    assert SECRET not in caplog.text


@pytest.mark.asyncio
async def test_durable_job_reports_allowance_exhaustion_before_any_model_dispatch(
    integration, monkeypatch
):
    from execplus.application.services import usage_metering as usage_service
    from test_conversation_jobs import job_path, prepared, submit
    from test_usage_metering import NOW, attribution, policy

    env = integration
    owner, wid, _, path, _ = prepared(env)
    actor = env.runtime.identity.authenticate(owner["Authorization"].split()[1])
    env.runtime.operations.change_staff(actor.email, "admin")
    metering = env.runtime.usage_metering
    monkeypatch.setattr(usage_service, "now", lambda: NOW)
    allowance = policy(workspace_id=UUID(wid), created_by=actor.id, max_attempts=1)
    metering.set_policy(actor.id, allowance, 0)
    scope = attribution(workspace_id=UUID(wid), actor_id=actor.id)
    metering.reserve(scope, uuid4(), "test-provider", "fictional-model")
    calls = []
    env.runtime.jobs.threads.intent_router.model = model(
        metering, monkeypatch, lambda request: calls.append(request)
    )
    job = submit(env, owner, path)
    assert await env.runtime.jobs.process() == {"processed": 1}
    current = env.client.get(job_path(job), headers=owner).json()
    assert current["status"] == "failed" and current["failure_code"] == "usage_attempt_limit"
    assert calls == [] and len(rows(env)) == 1
    assert "allowance" in env.client.get(path, headers=owner).json()["turns"][-1]["message"]


@pytest.mark.asyncio
async def test_successful_durable_job_binds_all_provider_evidence_to_its_private_turn(
    integration, monkeypatch
):
    from test_conversation_jobs import job_path, prepared, submit
    from test_unified_conversation import NUMERICAL

    env = integration
    owner, wid, _, path, _ = prepared(env)
    env.runtime.jobs.threads.intent_router.model = model(
        env.runtime.usage_metering,
        monkeypatch,
        lambda request: response(
            {"prompt_tokens": 10, "completion_tokens": 5},
            choices=[{"message": {"content": json.dumps(NUMERICAL)}}],
        ),
    )
    job = submit(env, owner, path)
    await env.runtime.jobs.process()
    state = env.client.get(job_path(job), headers=owner).json()
    assert state["status"] == "succeeded", state
    (record,) = rows(env)
    assert str(record["operation_id"]) == job["turn_id"]
    assert str(record["workspace_id"]) == wid and record["operation"] == "conversation"
    assert record["cost"] is None and record["state"] == "unknown"
