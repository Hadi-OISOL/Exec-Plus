"""Use case: Supplies an explicit no-model runtime.

What it does: Allows deterministic development paths to run without an LLM dependency.
"""

from execplus.application.contracts import ModelRequest, ModelResponse
from execplus.domain.errors import ModelDisabledError


class DisabledLanguageModel:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        raise ModelDisabledError("Language-model features are disabled")
