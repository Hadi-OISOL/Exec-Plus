"""Use case: Connects ExecPlus to OpenAI-compatible language-model endpoints.

What it does: Translates provider-neutral requests without exposing infrastructure
details, retrying only the transient failures the provider itself calls temporary.
"""

import asyncio

import httpx

from execplus.application.contracts import ModelRequest, ModelResponse
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.models import ModelTier

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class OpenAICompatibleLanguageModel:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        small_model: str,
        large_model: str,
        provider_name: str,
        timeout_seconds: float = 60.0,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._models = {ModelTier.SMALL: small_model, ModelTier.LARGE: large_model}
        self._provider_name = provider_name
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    async def complete(self, request: ModelRequest) -> ModelResponse:
        model = self._models[request.tier]
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "temperature": request.temperature,
        }
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            if attempt > 0:
                await asyncio.sleep(self._retry_backoff_seconds * attempt)
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                body = response.json()
                return ModelResponse(
                    content=str(body["choices"][0]["message"]["content"]),
                    model=str(body.get("model", model)),
                    provider=self._provider_name,
                )
            except httpx.HTTPStatusError as error:
                last_error = error
                if error.response.status_code not in _RETRYABLE_STATUS_CODES:
                    break
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as error:
                last_error = error
        raise ProviderUnavailableError(
            "The language-model provider is unavailable. Try again later."
        ) from last_error
