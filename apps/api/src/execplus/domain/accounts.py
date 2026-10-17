"""Use case: Defines local account and private setup contracts.

What it does: Validates password bounds and guide choices without identity providers.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from execplus.domain.ingestion import IngestionError, User

GUIDE_STEPS = (
    "setup",
    "data",
    "quality",
    "meaning",
    "analysis",
    "dashboard",
    "recommendations",
    "team",
)
GUIDE_LABELS = {
    "setup": "Account and workspace",
    "data": "Upload a file or use a sample",
    "quality": "Check the data profile",
    "meaning": "Review meanings and safe cleaning",
    "analysis": "Build and inspect an analysis",
    "dashboard": "Save an analysis or dashboard",
    "recommendations": "Explore conditional recommendations",
    "team": "Invite a teammate",
}
GUIDE_ACTIONS = {
    "data": {"upload.stored", "sample.imported"},
    "quality": {"profile.created", "sample.imported"},
    "meaning": {"understanding.confirmed"},
    "analysis": {"query.executed", "study.created"},
    "dashboard": {"saved_item.created", "dashboard.created"},
    "recommendations": {"analysis.created", "analysis.reviewed"},
    "team": {"invitation.created", "invitation.accepted"},
}


def password_input(value: str, *, new: bool = False) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise IngestionError("invalid_password", "Use a password with 15 to 128 characters.", 422)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise IngestionError("invalid_password", "Use a valid Unicode passphrase.", 422) from None
    if len(encoded) > 512 or "\x00" in value:
        raise IngestionError("invalid_password", "Use a password with 15 to 128 characters.", 422)
    if new and len(value) < 15:
        raise IngestionError("invalid_password", "Use a password with 15 to 128 characters.", 422)
    if new and (not value.strip() or len(set(value)) == 1):
        raise IngestionError(
            "invalid_password", "Choose a longer, less predictable passphrase.", 422
        )
    return value


def authentication_failed() -> IngestionError:
    return IngestionError(
        "authentication_failed", "Sign-in details are unavailable or incorrect.", 401
    )


def account_text(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise IngestionError("invalid_account_text", "Use valid Unicode text.", 422) from None
    return value


@dataclass(frozen=True)
class LocalAccount:
    user: User
    password_hash: str = field(repr=False)
    password_changed_at: datetime
    disabled_at: datetime | None


@dataclass(frozen=True)
class AccountSession:
    token: str = field(repr=False)
    expires_at: datetime
    user: User


@dataclass(frozen=True)
class GuideProgress:
    workspace_id: UUID
    user_id: UUID
    version: int
    active_step: str
    skipped_steps: tuple[str, ...]
    paused: bool
    finished: bool
    updated_at: datetime


def guide_choices(step: str, skipped: list[str]) -> tuple[str, ...]:
    if step not in GUIDE_STEPS or len(skipped) > len(GUIDE_STEPS):
        raise IngestionError("invalid_guide", "Choose an available setup step.", 422)
    if len(set(skipped)) != len(skipped) or any(item not in GUIDE_STEPS for item in skipped):
        raise IngestionError("invalid_guide", "Choose available setup steps only once.", 422)
    return tuple(item for item in GUIDE_STEPS if item in skipped)
