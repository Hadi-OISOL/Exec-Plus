"""Use case: Enforces actual serialized byte bounds before and after model dispatch.

What it does: Uses only mocked HTTP, preserves unknown exposure on oversized
responses, and never equates characters or byte counts with billable tokens.
"""

import json

import httpx
import pytest

from execplus.application.contracts import ModelMessage, ModelRequest
from execplus.application.usage_context import usage_scope
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.models import ModelTier
from execplus.infrastructure.models import openai_compatible as provider
from test_usage_metering_integration import configured
from test_usage_provider import REQUEST, model, response, rows


@pytest.mark.asyncio
async def test_request_bound_counts_serialized_utf8_and_never_reserves_or_dispatches(
    integration, monkeypatch
):
    service, _, _, _, _, _, _, scope, _ = configured(integration, monkeypatch)
    calls = []
    adapter = model(service, monkeypatch, lambda request: calls.append(request) or response())
    monkeypatch.setattr(provider, "MAX_REQUEST_BYTES", 180)
    request = ModelRequest((ModelMessage("user", "界" * 60),), ModelTier.SMALL)
    with usage_scope(scope), pytest.raises(ProviderUnavailableError, match="request exceeds"):
        await adapter.complete(request)
    assert calls == [] and rows(integration) == []


class Chunks(httpx.AsyncByteStream):
    def __init__(self):
        self.closed = False
        self.sent = 0

    async def __aiter__(self):
        for _ in range(30):
            self.sent += 1
            yield b"x" * 65536

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["declared", "streamed", "compressed"])
async def test_oversized_or_compressed_response_is_closed_without_retry_and_exposure_is_unknown(
    integration, monkeypatch, kind
):
    service, _, _, _, _, _, _, scope, _ = configured(integration, monkeypatch)
    stream = Chunks()
    calls = []

    def handle(request):
        calls.append(request)
        headers = (
            {"content-length": "9999999"}
            if kind == "declared"
            else {"content-encoding": "gzip"}
            if kind == "compressed"
            else {}
        )
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, headers=headers, stream=stream)

    adapter = model(service, monkeypatch, handle, attempts=3)
    monkeypatch.setattr(provider, "MAX_RESPONSE_BYTES", 100000)
    with usage_scope(scope), pytest.raises(ProviderUnavailableError, match="transport limits"):
        await adapter.complete(REQUEST)
    assert len(calls) == 1 and stream.closed
    assert stream.sent <= 2
    (record,) = rows(integration)
    assert record["outcome"] == "invalid_response" and record["cost"] is None
    assert record["held_exposure"] > 0


@pytest.mark.asyncio
async def test_bounded_request_keeps_payload_options_and_reported_tokens(monkeypatch):
    calls = []
    adapter = model(
        None,
        monkeypatch,
        lambda request: (
            calls.append(request) or response({"prompt_tokens": 10, "completion_tokens": 2})
        ),
    )
    result = await adapter.complete(REQUEST)
    sent = json.loads(calls[0].content)
    assert sent["messages"][0]["content"] == REQUEST.messages[0].content
    assert result.input_tokens == 10 and result.output_tokens == 2
