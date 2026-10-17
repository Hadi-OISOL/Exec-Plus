"""Use case: Binds provider consent to a live browser and an initiating account session.

What it does: Defines one-use OAuth attempts and short-lived session handoffs without URL secrets.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from execplus.application.connector_ports import ConnectorConnection
from execplus.application.google_ports import GoogleConnection


@dataclass(frozen=True)
class OAuthAttempt:
    state_hash: str
    provider: str
    purpose: str
    user_id: UUID | None
    session_hash: str | None
    connection_version: UUID | None
    sealed_payload: str


class OAuthState(Protocol):
    def assert_connection(
        self, user_id: UUID, token: str, provider: str, version: UUID
    ) -> None: ...

    def begin(
        self,
        provider: str,
        purpose: str,
        browser: str,
        sealed_payload: str,
        *,
        user_id: UUID | None = None,
        session_token: str = "",
        peer: str = "",
    ) -> str: ...

    def claim(self, state: str, browser: str, provider: str, purpose: str) -> OAuthAttempt: ...

    def fail(self, attempt: OAuthAttempt, error_code: str) -> str: ...

    def complete_connection(
        self, attempt: OAuthAttempt, record: GoogleConnection | ConnectorConnection
    ) -> str: ...

    def complete_signin(
        self, attempt: OAuthAttempt, subject: str, email: str, display_name: str
    ) -> str: ...

    def exchange(self, handoff: str, browser: str) -> dict[str, str]: ...
