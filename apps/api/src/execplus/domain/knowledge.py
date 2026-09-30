"""Use case: Models immutable source documents and reproducible citation boundaries.

What it does: Validates bounded UTF-8 documents and creates versioned passage offsets.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePath
from uuid import UUID, uuid5

from execplus.domain.ingestion import IngestionError

MAX_DOCUMENT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class Document:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    owner_id: UUID
    name: str
    checksum: str
    size: int
    shared: bool
    created_at: datetime


@dataclass(frozen=True)
class DocumentChunk:
    id: UUID
    workspace_id: UUID
    document_id: UUID
    ordinal: int
    start: int
    end: int
    checksum: str
    algorithm: str = "chunks-v1"


def document_text(name: str, content: bytes) -> str:
    if (
        PurePath(name).name != name
        or "\\" in name
        or len(name) > 100
        or PurePath(name).suffix.lower() not in {".txt", ".md"}
        or not 0 < len(content) <= MAX_DOCUMENT_BYTES
    ):
        raise IngestionError(
            "invalid_document", "Choose a UTF-8 TXT or Markdown file up to 1 MiB.", 422
        )
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise IngestionError("invalid_document", "The document must use UTF-8 text.", 422) from None
    if not text.strip() or any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        raise IngestionError("invalid_document", "The document contains unsupported content.", 422)
    return text


def chunks(document: Document, text: str) -> tuple[DocumentChunk, ...]:
    result = []
    for ordinal, start in enumerate(range(0, len(text), 900)):
        passage = text[start : start + 1000]
        result.append(
            DocumentChunk(
                uuid5(document.id, f"chunks-v1:{ordinal}"),
                document.workspace_id,
                document.id,
                ordinal,
                start,
                start + len(passage),
                hashlib.sha256(passage.encode()).hexdigest(),
            )
        )
    return tuple(result)
