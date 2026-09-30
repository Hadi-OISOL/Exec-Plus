"""Use case: Defines provider-neutral application messages.

What it does: Keeps model and retrieval structures independent from vendor SDKs.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from execplus.domain.models import ModelTier


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ModelRequest:
    messages: tuple[ModelMessage, ...]
    tier: ModelTier
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class ModelResponse:
    content: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    chunk_id: UUID
    workspace_id: UUID
    dataset_id: UUID
    text: str
    metadata: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk: KnowledgeChunk
    score: float


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    name: str
    healthy: bool
    detail: str
