"""Exercise the actual JSON-mode HTTP adapter against a strict synthetic provider."""

import json

import httpx
import pytest

from execplus.application.services.response_synthesis import ResponseSynthesisService
from execplus.domain.response_synthesis import FactPacket, FactStatement, validate_saved_narrative
from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel


@pytest.mark.parametrize("count,omit_last", [(2, False), (5, False), (2, True)])
@pytest.mark.asyncio
async def test_json_mode_prompt_supplies_every_required_statement(monkeypatch, count, omit_last):
    packet = FactPacket(
        tuple(
            FactStatement(f"F{i}", (f"Verified statement {i}.",), (f"receipt-{i}",), "scope")
            for i in range(1, count + 1)
        )
    )
    calls = []

    def provider(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["response_format"] == {"type": "json_object"}
        system = body["messages"][0]["content"]
        if "JSON" not in system:
            return httpx.Response(400, json={"error": "JSON mode requires a JSON instruction"})
        marker = "Complete JSON response template:\n"
        assert marker in system
        template = json.loads(system.split(marker, 1)[1])
        assert template == {
            "selections": [{"id": item.id, "variant": 0} for item in packet.statements]
        }
        facts = json.loads(body["messages"][1]["content"])["statements"]
        assert [fact["id"] for fact in facts] == [item["id"] for item in template["selections"]]
        if omit_last:
            template["selections"].pop()
        return httpx.Response(
            200,
            json={
                "model": "synthetic",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(template)}}
                ],
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(provider), **kwargs),
    )
    adapter = OpenAICompatibleLanguageModel(
        "https://provider.invalid",
        "",
        "synthetic",
        "synthetic",
        "mock",
        json_mode=True,
        max_attempts=1,
    )
    result = await ResponseSynthesisService(adapter).compose(packet, "Explain these verified facts")
    assert len(calls) == 1
    assert result.reason == ("invalid_response" if omit_last else "selected")
    assert result.body()["mode"] == ("fallback" if omit_last else "selected")
    assert validate_saved_narrative(packet, result.body())
    assert len(result.body()["segments"]) == count
