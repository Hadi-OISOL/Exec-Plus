"""Use case: Defines resumable chunked upload sessions and per-user storage quotas.

What it does: Validates chunk order, sizes and hashes, and refuses work that exceeds a quota.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from execplus.domain.ingestion import IngestionError

OPEN = "open"
PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"
EXPIRED = "expired"
STATUSES = (OPEN, PROCESSING, COMPLETED, FAILED, CANCELLED, EXPIRED)
RESERVING = (OPEN, PROCESSING)
SUPPORTED_TYPES = {
    ".csv": {"text/csv", "application/csv", "text/plain"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}


def valid_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", lowered):
        raise IngestionError("invalid_checksum", "Send a SHA-256 checksum as 64 hex digits.", 422)
    return lowered


def require_supported(filename: str, content_type: str) -> None:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = SUPPORTED_TYPES.get(f".{suffix}")
    if allowed is None or content_type.split(";")[0].strip().lower() not in allowed:
        raise IngestionError(
            "unsupported_format", "Choose a CSV or XLSX file with its matching content type.", 415
        )


def safe_label(value: str, limit: int, fallback: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = "".join(
        " " if char in "/\\:%" or unicodedata.category(char).startswith("C") else char
        for char in text
    )
    text = " ".join(text.split()).lstrip(".").strip()
    return text[:limit].strip() or fallback


def require_quota(used: int, quota: int, requested: int) -> None:
    if used + requested > quota:
        raise IngestionError(
            "quota_exceeded",
            "This upload would exceed your storage allowance. Delete files or ask for more space.",
            409,
            details={"used_bytes": used, "quota_bytes": quota, "requested_bytes": requested},
        )


@dataclass(frozen=True)
class UploadSession:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID | None
    created_by: UUID
    filename: str
    content_type: str
    size_bytes: int
    sha256: str | None
    chunk_size: int
    chunk_hashes: list[str]
    status: str
    upload_id: UUID | None
    error_code: str | None
    error_message: str | None
    lease_until: datetime | None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    @property
    def total_chunks(self) -> int:
        return -(-self.size_bytes // self.chunk_size)

    @property
    def next_chunk(self) -> int:
        return len(self.chunk_hashes)

    @property
    def received_bytes(self) -> int:
        return min(self.next_chunk * self.chunk_size, self.size_bytes)

    def expected_length(self, index: int) -> int:
        return min(self.chunk_size, self.size_bytes - index * self.chunk_size)

    def part_key(self, index: int, digest: str) -> str:
        return f"{self.prefix}parts/{index:06d}-{digest}"

    @property
    def prefix(self) -> str:
        return f"workspaces/{self.workspace_id}/upload-sessions/{self.id}/"

    def accepts(self, index: int, length: int, digest: str, now: datetime) -> bool:
        if self.status != OPEN or self.expires_at <= now:
            raise IngestionError(
                "session_closed", "This upload session is no longer accepting chunks.", 409
            )
        if not 0 <= index < self.total_chunks:
            raise IngestionError("chunk_out_of_order", "This chunk index is out of range.", 409)
        if index < self.next_chunk:
            if self.chunk_hashes[index] != digest:
                raise IngestionError(
                    "hash_mismatch", "A different chunk was already stored at this index.", 409
                )
            return False
        if index > self.next_chunk:
            raise IngestionError("chunk_out_of_order", f"Send chunk {self.next_chunk} next.", 409)
        if length != self.expected_length(index):
            raise IngestionError(
                "invalid_chunk_size",
                f"Chunk {index} must contain exactly {self.expected_length(index)} bytes.",
                422,
            )
        return True

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "dataset_id": self.dataset_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "chunk_size": self.chunk_size,
            "received_bytes": self.received_bytes,
            "next_chunk": self.next_chunk,
            "total_chunks": self.total_chunks,
            "status": self.status,
            "upload_id": self.upload_id,
            "error": (
                {"code": self.error_code, "message": self.error_message}
                if self.error_code
                else None
            ),
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
