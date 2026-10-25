"""Use case: Defines secure workspace and ingestion records.

What it does: Holds provider-neutral records, role policy, and stable failure codes.
"""

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

MULTI_TABLE_FORMATS = frozenset({"xlsx", "xlsm", "xls", "xlsb", "ods", "sqlite"})


def stored_table(format: str) -> tuple[str, int]:
    """Split a stored upload format such as "r:xlsx#2" into its file suffix and table index."""
    base, _, index = format.removeprefix("r:").partition("#")
    return base, int(index) if index.isdecimal() else 0


class IngestionError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 400,
        *,
        details: dict[str, int] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details or {}


def validate_filename(filename: str) -> str:
    name = unicodedata.normalize("NFKC", filename).strip()
    if (
        not name
        or len(name) > 200
        or name.startswith(".")
        or any(char in name for char in "/\\:%")
        or any(unicodedata.category(char).startswith("C") for char in name)
    ):
        raise IngestionError(
            "unsafe_filename", "Use a plain filename without paths or control characters.", 422
        )
    return name


def file_too_large(limit: int) -> IngestionError:
    return IngestionError(
        "file_too_large", f"Files must be at most {limit // (1024 * 1024)} MiB.", 413
    )


def require_seat_limit(limit: int) -> None:
    if not 3 <= limit <= 50:
        raise IngestionError("invalid_seat_limit", "Choose a seat limit from 3 to 50.", 422)


def require_manager(role: str) -> None:
    if role not in {"owner", "admin"}:
        raise IngestionError("forbidden", "An owner or admin role is required.", 403)


@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    display_name: str
    created_at: datetime


@dataclass(frozen=True)
class Workspace:
    id: UUID
    name: str
    seat_limit: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Membership:
    workspace_id: UUID
    user_id: UUID
    role: str
    created_at: datetime


@dataclass(frozen=True)
class Invitation:
    id: UUID
    workspace_id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    invited_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class Dataset:
    id: UUID
    workspace_id: UUID
    name: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Upload:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    filename: str
    content_type: str
    size: int
    storage_key: str
    checksum: str
    status: str
    format: str
    row_count: int
    column_count: int
    created_by: UUID
    created_at: datetime

    sample_id: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    id: UUID
    workspace_id: UUID
    actor_id: UUID
    action: str
    resource_type: str
    resource_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class FileStructure:
    format: str
    row_count: int
    column_count: int
    sheet_count: int


@dataclass(frozen=True)
class ObjectMetadata:
    size: int


@dataclass(frozen=True)
class MemberView:
    workspace_id: UUID
    user_id: UUID
    role: str
    email: str
