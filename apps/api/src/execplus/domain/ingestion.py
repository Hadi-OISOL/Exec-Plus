"""Use case: Defines secure workspace and ingestion records.

What it does: Holds provider-neutral records, role policy, and stable failure codes.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class IngestionError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


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
