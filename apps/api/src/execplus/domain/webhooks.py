"""Use case: Defines signed, bounded metadata-only integration events.

What it does: Builds stable event bodies, derives isolated signing keys and selects
finite retry states without putting customer result values or raw errors in events.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from execplus.domain.ingestion import IngestionError
from execplus.domain.integration_access import origin, require_time

EVENTS = frozenset({"job.succeeded", "job.failed", "refresh.accepted"})
RETRY_SECONDS = (10, 30, 120, 600, 3600)
MAX_ATTEMPTS = len(RETRY_SECONDS) + 1


def destination(value: str, allowed_origins: tuple[str, ...], *, allow_local: bool = False) -> str:
    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(value)
        base = origin(parsed.scheme + "://" + parsed.netloc, allow_local=allow_local)
    except (ValueError, IngestionError):
        raise IngestionError(
            "webhook_destination", "Choose an operator-approved destination.", 422
        ) from None
    if (
        len(value) > 2000
        or base not in allowed_origins
        or parsed.query
        or parsed.fragment
        or any(ord(char) < 33 or ord(char) > 126 for char in value)
        or "\\" in value
    ):
        raise IngestionError("webhook_destination", "Choose an operator-approved destination.", 422)
    return base + (parsed.path or "/")


def signing_key(master: bytes, subscription_id: UUID, version: int) -> bytes:
    if len(master) < 32 or isinstance(version, bool) or version < 1:
        raise ValueError("A protected master secret and positive signing version are required")
    message = f"execplus-webhook-v1:{subscription_id}:{version}".encode("ascii")
    return hmac.digest(master, message, "sha256")


def signature(secret: bytes, timestamp: int, body: bytes) -> str:
    if len(secret) < 32 or timestamp < 0 or len(body) > 4096:
        raise ValueError("Webhook signature input exceeds its fixed bounds")
    signed = str(timestamp).encode("ascii") + b"." + body
    return f"t={timestamp},v1=" + hmac.new(secret, signed, hashlib.sha256).hexdigest()


def verify_signature(
    secret: bytes, header: str, body: bytes, now: int, tolerance: int = 300
) -> bool:
    try:
        timestamp_text, supplied = header.split(",v1=")
        if not timestamp_text.startswith("t=") or len(supplied) != 64:
            return False
        timestamp = int(timestamp_text[2:])
        if abs(now - timestamp) > tolerance:
            return False
        return hmac.compare_digest(signature(secret, timestamp, body), header)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class WebhookEvent:
    id: UUID
    subscription_id: UUID
    kind: str
    resource_id: UUID
    dataset_id: UUID
    occurred_at: datetime

    def body(self) -> bytes:
        require_time(self.occurred_at)
        if self.kind not in EVENTS:
            raise ValueError("Only fixed webhook event categories are allowed")
        return json.dumps(
            {
                "version": "execplus-event-v1",
                "id": str(self.id),
                "type": self.kind,
                "resource_id": str(self.resource_id),
                "dataset_id": str(self.dataset_id),
                "occurred_at": self.occurred_at.isoformat(),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")


@dataclass(frozen=True)
class WebhookSubscription:
    id: UUID
    workspace_id: UUID
    user_id: UUID
    membership_created_at: datetime
    dataset_ids: tuple[UUID, ...]
    event_types: tuple[str, ...]
    destination: str
    signing_version: int
    created_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class WebhookDelivery:
    event: WebhookEvent
    status: str
    attempts: int
    next_attempt_at: datetime
    last_status: int | None = None
    last_attempt_at: datetime | None = None
    lease_until: datetime | None = None
    lease_id: UUID | None = None


def outcome(now: datetime, attempts: int, response_status: int | None) -> tuple[str, datetime]:
    require_time(now)
    if not 1 <= attempts <= MAX_ATTEMPTS:
        raise ValueError("Delivery attempts must be within the bounded retry policy")
    if response_status is not None and not 100 <= response_status <= 599:
        raise ValueError("Invalid HTTP delivery status")
    if response_status is not None and 200 <= response_status < 300:
        return "delivered", now
    if attempts == MAX_ATTEMPTS or (
        response_status is not None and response_status < 500 and response_status not in {408, 429}
    ):
        return "failed", now
    return "pending", now + timedelta(seconds=RETRY_SECONDS[attempts - 1])
