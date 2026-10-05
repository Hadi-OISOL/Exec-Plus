"""Use case: Connects ExecPlus to OpenAI-compatible language-model endpoints.

What it does: Translates provider-neutral requests without exposing infrastructure
details, retrying only the transient failures the provider itself calls temporary.
"""

import asyncio

import httpx

from execplus.application.contracts import ModelRequest, ModelResponse
from execplus.application.progress import provider_attempt
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
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        json_mode: bool = False,
    ) -> None:
        self._json_mode = json_mode
        self._max_output_tokens = max_output_tokens
        self._reasoning_effort = reasoning_effort
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
        if self._json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self._max_output_tokens is not None:
            payload["max_tokens"] = self._max_output_tokens
        if self._reasoning_effort is not None:
            payload["reasoning_effort"] = self._reasoning_effort
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            if attempt > 0:
                await asyncio.sleep(self._retry_backoff_seconds * attempt)
            await provider_attempt()
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                body = response.json()
                choice = body["choices"][0]
                content = choice["message"]["content"]
                if (
                    choice.get("finish_reason") == "length"
                    or not isinstance(content, str)
                    or not content.strip()
                ):
                    raise ValueError("Incomplete model response")
                usage = body.get("usage") or {}
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")
                return ModelResponse(
                    content=content,
                    model=str(body.get("model", model)),
                    provider=self._provider_name,
                    input_tokens=input_tokens
                    if type(input_tokens) is int and input_tokens >= 0
                    else None,
                    output_tokens=output_tokens
                    if type(output_tokens) is int and output_tokens >= 0
                    else None,
                )
            except httpx.HTTPStatusError as error:
                last_error = error
                if error.response.status_code not in _RETRYABLE_STATUS_CODES:
                    break
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                ValueError,
                TypeError,
                AttributeError,
            ) as error:
                last_error = error
        raise ProviderUnavailableError(
            "The language-model provider is unavailable. Try again later."
        ) from last_error
