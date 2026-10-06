"""Use case: Bounds user-visible audit history without revealing private work.

What it does: Defines shared operational actions and stable metadata-only page cursors.
"""

import base64
import binascii
import json
from datetime import datetime, timezone
from uuid import UUID

from execplus.domain.ingestion import IngestionError

SHARED_ACTIONS = (
    "dataset.created",
    "dataset.renamed",
    "upload.stored",
    "upload.downloaded",
    "sample.imported",
    "profile.created",
    "cleaning.applied",
    "revision.restored",
    "understanding.inferred",
    "understanding.confirmed",
    "understanding.rejected",
    "understanding.needs_review",
    "department.updated",
    "refresh.configured",
    "refresh.file_retained",
    "refresh.queued",
    "refresh.needs_review",
    "refresh.failed",
    "refresh.reviewed",
    "refresh.rejected",
    "refresh.conflict",
    "refresh.activated",
    "refresh.activation_failed",
    "monitor.created",
    "monitor.disabled",
    "observation.cancelled",
    "observation.complete",
    "observation.failed",
    "observation.opened",
)
MANAGER_ACTIONS = (
    "workspace.created",
    "workspace.seats_changed",
    "membership.created",
    "membership.removed",
    "invitation.created",
    "invitation.accepted",
    "invitation.revoked",
)


def audit_cursor(created_at: datetime, record_id: UUID) -> str:
    payload = json.dumps([created_at.isoformat(), str(record_id)], separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def parse_audit_cursor(value: str | None) -> tuple[datetime, UUID] | None:
    if value is None:
        return None
    try:
        if not value or len(value) > 200:
            raise ValueError
        payload = json.loads(
            base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        )
        if not isinstance(payload, list) or len(payload) != 2:
            raise ValueError
        timestamp = datetime.fromisoformat(payload[0])
        if timestamp.tzinfo is None:
            raise ValueError
        return timestamp.astimezone(timezone.utc), UUID(payload[1])
    except (ValueError, TypeError, AttributeError, binascii.Error):
        raise IngestionError(
            "invalid_audit_filter", "Reload audit history to start a new page.", 422
        ) from None
