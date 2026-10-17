"""Use case: Defines scoped customer credentials and private embed grants.

What it does: Validates explicit read-only scopes, bounded token lifetimes and exact
host origins without letting integration credentials become ordinary user sessions.
"""

import hashlib
import re
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

from execplus.domain.ingestion import IngestionError

OPERATIONS = frozenset(
    {
        "profile:read",
        "rows:read",
        "query:read",
        "boards:read",
        "studies:read",
        "forecasts:read",
        "analyses:read",
        "jobs:read",
    }
)
TOKEN_PREFIXES = frozenset({"epk", "epb", "eps"})
KEY_MAX_SECONDS = 90 * 24 * 60 * 60
BOOTSTRAP_MAX_SECONDS = 300
EMBED_MAX_SECONDS = 900


def unavailable() -> IngestionError:
    return IngestionError("integration_access", "This integration access is unavailable.", 404)


def require_time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Integration times must have a timezone")


def issue_secret(prefix: str) -> tuple[str, str]:
    if prefix not in TOKEN_PREFIXES:
        raise ValueError("Unknown integration credential kind")
    token = prefix + "_" + secrets.token_urlsafe(32)
    return token, secret_hash(token, prefix)


def secret_hash(token: str, prefix: str) -> str:
    if prefix not in TOKEN_PREFIXES or not re.fullmatch(prefix + r"_[A-Za-z0-9_-]{43}", token):
        raise unavailable()
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def lifetime(now: datetime, seconds: int, maximum: int) -> datetime:
    require_time(now)
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= maximum:
        raise IngestionError(
            "integration_expiry", "Choose an expiry within the allowed limit.", 422
        )
    return now + timedelta(seconds=seconds)


def origin(value: str, *, allow_local: bool = False) -> str:
    if not isinstance(value, str):
        raise IngestionError("integration_origin", "Use one exact HTTPS origin.", 422)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise IngestionError("integration_origin", "Use one exact HTTPS origin.", 422) from None
    host = parsed.hostname or ""
    local = host in {"localhost", "127.0.0.1", "::1"}
    if (
        len(value) > 300
        or value != value.strip()
        or any(ord(char) < 33 or ord(char) > 126 for char in value)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or not host
        or port == 0
        or "*" in value
        or "%" in value
        or "\\" in value
        or (parsed.scheme != "https" and not (allow_local and local and parsed.scheme == "http"))
        or (local and not allow_local)
        or (not local and not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host))
    ):
        raise IngestionError("integration_origin", "Use one exact HTTPS origin.", 422)
    name = f"[{host}]" if ":" in host else host
    default = 443 if parsed.scheme == "https" else 80
    return parsed.scheme + "://" + name + (f":{port}" if port and port != default else "")


def validate_scope(dataset_ids: tuple[UUID, ...], operations: tuple[str, ...]) -> None:
    if (
        not 1 <= len(dataset_ids) <= 20
        or len(set(dataset_ids)) != len(dataset_ids)
        or any(not isinstance(value, UUID) for value in dataset_ids)
        or not operations
        or len(set(operations)) != len(operations)
        or not set(operations) <= OPERATIONS
    ):
        raise IngestionError(
            "integration_scope", "Choose explicit datasets and read-only operations.", 422
        )


@dataclass(frozen=True)
class IntegrationKey:
    id: UUID
    workspace_id: UUID
    user_id: UUID
    membership_created_at: datetime
    name: str
    token_hash: str
    dataset_ids: tuple[UUID, ...]
    operations: tuple[str, ...]
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    rate_limit: int = 60

    def authorize(self, now: datetime, wid: UUID, did: UUID | None, operation: str) -> None:
        require_time(now)
        if (
            self.revoked_at is not None
            or now >= self.expires_at
            or self.workspace_id != wid
            or operation not in self.operations
            or (did is not None and did not in self.dataset_ids)
        ):
            raise unavailable()


@dataclass(frozen=True)
class EmbedGrant:
    id: UUID
    workspace_id: UUID
    user_id: UUID
    membership_created_at: datetime
    board_id: UUID
    board_version: int
    host_origin: str
    bootstrap_hash: str
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    session_hash: str | None = None
    session_expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def exchange(self, now: datetime, host: str, session_hash: str) -> "EmbedGrant":
        require_time(now)
        if (
            self.revoked_at is not None
            or self.consumed_at is not None
            or now >= self.expires_at
            or host != self.host_origin
        ):
            raise unavailable()
        return replace(
            self,
            consumed_at=now,
            session_hash=session_hash,
            session_expires_at=now + timedelta(seconds=EMBED_MAX_SECONDS),
        )

    def authorize(self, now: datetime, host: str, board_version: int) -> None:
        require_time(now)
        if (
            self.revoked_at is not None
            or self.session_hash is None
            or self.session_expires_at is None
            or now >= self.session_expires_at
            or host != self.host_origin
            or board_version != self.board_version
        ):
            raise unavailable()
