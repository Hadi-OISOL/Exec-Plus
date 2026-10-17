"""Use case: Connects ExecPlus to OpenAI-compatible language-model endpoints.

What it does: Translates provider-neutral requests without exposing infrastructure
details, retrying only the transient failures the provider itself calls temporary.
"""

import asyncio
import json
from dataclasses import replace

import httpx

from execplus.application.contracts import ModelRequest, ModelResponse
from execplus.application.progress import provider_attempt
from execplus.application.services.usage_metering import UsageMeteringService
from execplus.domain.errors import IncompleteModelResponseError, ProviderUnavailableError
from execplus.domain.models import ModelTier
from execplus.domain.usage_metering import TokenUsage, reported_usage
from execplus.infrastructure.models.accounting import AttemptAccounting

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class _PayloadLimit(ValueError):
    pass


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
        metering: UsageMeteringService | None = None,
    ) -> None:
        self._metering = metering
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
        serialized = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        if len(serialized) > MAX_REQUEST_BYTES:
            raise ProviderUnavailableError("The model request exceeds the local transport limit.")
        headers["Content-Type"] = "application/json"
        headers["Accept-Encoding"] = "identity"
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            if attempt > 0:
                await asyncio.sleep(self._retry_backoff_seconds * attempt)
            await provider_attempt()
            accounting = AttemptAccounting(self._metering, self._provider_name, model)
            usage = TokenUsage()
            try:
                async with (
                    httpx.AsyncClient(timeout=self._timeout_seconds) as client,
                    client.stream(
                        "POST",
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        content=serialized,
                    ) as response,
                ):
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise _PayloadLimit
                    declared = response.headers.get("content-length", "")
                    if declared.isdigit() and int(declared) > MAX_RESPONSE_BYTES:
                        raise _PayloadLimit
                    received = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        if len(received) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise _PayloadLimit
                        received.extend(chunk)
                try:
                    body = json.loads(received)
                except ValueError:
                    body = None
                if isinstance(body, dict):
                    usage = reported_usage(body.get("usage"))
                    if body.get("model", model) != model:
                        usage = replace(usage, invalid_report=True)
                response.raise_for_status()
                if not isinstance(body, dict):
                    raise ValueError("Incomplete model response")
                choice = body["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise IncompleteModelResponseError(
                        "The language-model reply ended before it was complete."
                    )
                content = choice["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Incomplete model response")
                accounting.finish("succeeded", usage)
                return ModelResponse(
                    content=content,
                    model=str(body.get("model", model)),
                    provider=self._provider_name,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                )
            except _PayloadLimit:
                accounting.finish("invalid_response", usage, preserve_failure=True)
                raise ProviderUnavailableError(
                    "The model response is outside the local transport limits."
                ) from None
            except asyncio.CancelledError:
                accounting.finish("cancelled", usage, preserve_failure=True)
                raise
            except IncompleteModelResponseError:
                accounting.finish("truncated", usage, preserve_failure=True)
                raise
            except httpx.HTTPStatusError as error:
                accounting.finish("http_error", usage)
                last_error = error
                if error.response.status_code not in _RETRYABLE_STATUS_CODES:
                    break
            except httpx.TimeoutException as error:
                accounting.finish("timeout", usage)
                last_error = error
            except httpx.HTTPError as error:
                accounting.finish("http_error", usage)
                last_error = error
            except (
                KeyError,
                IndexError,
                ValueError,
                TypeError,
                AttributeError,
            ) as error:
                accounting.finish("invalid_response", usage)
                last_error = error
        raise ProviderUnavailableError(
            "The language-model provider is unavailable. Try again later."
        ) from last_error
