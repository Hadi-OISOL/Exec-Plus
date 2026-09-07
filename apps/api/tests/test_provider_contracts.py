"""Use case: Verifies foundation provider and readiness contracts.

What it does: Checks HTTP translation, disabled providers, and safe dependency failures.
"""

import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from execplus.application.contracts import ComponentStatus, ModelMessage, ModelRequest
from execplus.application.services.health import HealthService
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.models import ModelTier, WorkspaceScope
from execplus.infrastructure.models.disabled import DisabledLanguageModel
from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel
from execplus.infrastructure.retrieval.disabled import DisabledEmbeddingStore
from execplus.main import create_app
from execplus.presentation.dependencies import get_health_service


@pytest.mark.asyncio
@pytest.mark.parametrize("tier,expected", [(ModelTier.SMALL, "small"), (ModelTier.LARGE, "large")])
async def test_http_adapter_translates_port_contract(monkeypatch, tier, expected):
    def handle(request):
        assert str(request.url) == "https://model.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "model": expected,
            "messages": [{"role": "user", "content": "schema only"}],
            "temperature": 0.0,
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)
    model = OpenAICompatibleLanguageModel(
        "https://model.test/v1/", "test-key", "small", "large", "hosted"
    )
    result = await model.complete(ModelRequest((ModelMessage("user", "schema only"),), tier))
    assert (result.content, result.model, result.provider) == ("ok", expected, "hosted")


@pytest.mark.asyncio
async def test_disabled_providers_fail_explicitly():
    with pytest.raises(ProviderUnavailableError):
        await DisabledLanguageModel().complete(ModelRequest((), ModelTier.SMALL))
    store = DisabledEmbeddingStore()
    with pytest.raises(ProviderUnavailableError):
        await store.upsert(())
    with pytest.raises(ProviderUnavailableError):
        await store.search(
            "x", WorkspaceScope(uuid4(), uuid4(), frozenset(), frozenset()), frozenset(), 1
        )
    with pytest.raises(ProviderUnavailableError):
        await store.delete_dataset(uuid4(), uuid4())


class FailingProbe:
    name = "database"

    async def check(self):
        raise RuntimeError("secret-database-password")


class HealthyProbe:
    name = "storage"

    async def check(self):
        return ComponentStatus(self.name, True, "available")


def test_readiness_failure_is_503_without_sensitive_exception():
    app = create_app()
    app.dependency_overrides[get_health_service] = lambda: HealthService(
        (FailingProbe(), HealthyProbe())
    )
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "components": [
            {"name": "database", "healthy": False, "detail": "unavailable"},
            {"name": "storage", "healthy": True, "detail": "available"},
        ],
    }
    assert "secret" not in response.text
