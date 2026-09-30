"""Use case: Verifies reproducible demo inputs, hosted model bounds and production blockers.

What it does: Prevents edited demo uploads, credential disclosure and unsupported readiness claims.
"""

import hashlib
import importlib
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from execplus.application.contracts import ModelMessage, ModelRequest
from execplus.bootstrap import build_language_model, build_runtime
from execplus.config import Settings
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.models import ModelTier
from execplus.infrastructure.release_gate import (
    REQUIRED_GATES,
    pending_gates,
    require_production_evidence,
)


@pytest.fixture
def demo_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    return importlib.import_module("create_demo_corpus"), importlib.import_module(
        "evaluate_demo_model"
    )


def test_demo_generation_is_reproducible_and_preserves_edits(tmp_path, demo_modules):
    generator, evaluator = demo_modules
    path = generator.write_demo(tmp_path)
    first = path.read_bytes()
    assert generator.write_demo(tmp_path).read_bytes() == first
    manifest = evaluator.verified_demo(tmp_path)
    assert len(manifest["documents"]) == 6 and len(manifest["questions"]) == 20
    assert manifest["synthetic"] and not manifest["production_evidence"]
    for item in manifest["documents"]:
        content = (tmp_path / item["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item["sha256"]
    for question in manifest["questions"]:
        if question["expected_kind"] == "supported":
            assert any(
                question["expected_answer"] in generator.DOCUMENTS[key][1]
                for key in question["relevant_ids"]
            )
    (tmp_path / "refunds.md").write_text("Operator edited this document")
    with pytest.raises(FileExistsError):
        generator.write_demo(tmp_path)
    with pytest.raises(ValueError, match="refuses unverified content"):
        evaluator.verified_demo(tmp_path)
    assert (tmp_path / "refunds.md").read_text() == "Operator edited this document"


@pytest.mark.asyncio
async def test_hosted_deepseek_preset_bounds_output_and_records_usage(monkeypatch):
    def handle(request):
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "deepseek-v4-pro"
        assert body["response_format"] == {"type": "json_object"}
        assert body["reasoning_effort"] == "none" and body["max_tokens"] == 1024
        assert request.headers["authorization"] == "Bearer test-only"
        return httpx.Response(
            200,
            json={
                "model": "deepseek-v4-pro",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 4},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)
    model = build_language_model(
        Settings(
            _env_file=None,
            llm_mode="hosted",
            llm_base_url="https://api.deepseek.com",
            llm_api_key="test-only",
            llm_small_model="deepseek-v4-pro",
            llm_large_model="deepseek-v4-pro",
            llm_reasoning_effort="none",
            llm_json_mode=True,
        )
    )
    response = await model.complete(
        ModelRequest((ModelMessage("user", "demo schema only"),), ModelTier.SMALL)
    )
    assert response.input_tokens == 20 and response.output_tokens == 4


@pytest.mark.asyncio
async def test_truncated_response_is_rejected_without_returning_partial_evidence(monkeypatch):
    from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": "secret incomplete JSON"},
                        }
                    ]
                },
            )
        )
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)
    model = OpenAICompatibleLanguageModel(
        "https://model.test", "key", "small", "large", "hosted", max_attempts=1
    )
    with pytest.raises(ProviderUnavailableError) as error:
        await model.complete(ModelRequest((ModelMessage("user", "demo"),), ModelTier.SMALL))
    assert "secret" not in str(error.value)


def test_production_blocks_before_initializing_external_dependencies(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Production startup must validate evidence before infrastructure")

    monkeypatch.setattr("execplus.bootstrap.create_engine", forbidden)
    with pytest.raises(ValueError, match="Production validation is incomplete"):
        build_runtime(Settings(_env_file=None, environment="production"))


def test_release_gate_requires_reviewed_intact_evidence_and_rejects_demo_scope(tmp_path):
    path = tmp_path / "release.json"
    assert set(pending_gates(str(path))) == set(REQUIRED_GATES)
    artifact = tmp_path / "review.txt"
    artifact.write_text("Test-only operator evidence artifact")
    manifest = {
        "scope": "production",
        "gates": {
            key: {
                "status": "passed",
                "reviewed_by": "test reviewer",
                "reviewed_on": date.today().isoformat(),
                "evidence_file": "review.txt",
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
            for key in REQUIRED_GATES
        },
    }
    path.write_text(json.dumps(manifest))
    require_production_evidence(str(path))
    manifest["scope"] = "demo"
    path.write_text(json.dumps(manifest))
    assert pending_gates(str(path))
    manifest["scope"] = "production"
    path.write_text(json.dumps(manifest))
    artifact.write_text("Changed after review")
    assert set(pending_gates(str(path))) == set(REQUIRED_GATES)


@pytest.mark.asyncio
async def test_demo_model_rejects_free_prose_and_invented_citations(tmp_path, demo_modules):
    from execplus.application.contracts import ModelResponse

    generator, evaluator = demo_modules
    generator.write_demo(tmp_path)
    manifest = evaluator.verified_demo(tmp_path)

    class FakeModel:
        async def complete(self, request):
            return ModelResponse('{"kind":"supported","evidence_ids":["invented"]}', "fake", "test")

    result = await evaluator.evaluate(FakeModel(), manifest, 1)
    assert result["passed"] == 0 and not result["production_evidence"]
