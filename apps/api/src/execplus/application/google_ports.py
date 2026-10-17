"""Use case: Declares what the application needs from Google, a token vault and connection storage.

What it does: Keeps Google, encryption and database details behind protocols the services depend on.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    expires_in: int
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str = ""


@dataclass(frozen=True)
class SheetTab:
    id: int
    title: str
    rows: int
    columns: int


@dataclass(frozen=True)
class SpreadsheetInfo:
    title: str
    tabs: tuple[SheetTab, ...]


class GoogleApiError(Exception):
    def __init__(self, status: int, code: str = "") -> None:
        super().__init__(f"Google request failed with status {status}")
        self.status = status
        self.code = code


class GoogleGateway(Protocol):
    def authorization_url(
        self,
        *,
        scopes: tuple[str, ...],
        redirect_uri: str,
        state: str,
        challenge: str,
        nonce: str,
        login_hint: str = "",
        offline: bool = False,
    ) -> str: ...

    def exchange_code(self, code: str, verifier: str, redirect_uri: str) -> TokenSet: ...

    def refresh(self, refresh_token: str) -> TokenSet: ...

    def revoke(self, token: str) -> None: ...

    def id_token_claims(self, id_token: str) -> dict[str, Any]: ...

    def spreadsheet(self, access_token: str, spreadsheet_id: str) -> SpreadsheetInfo: ...

    def sheet_values(
        self, access_token: str, spreadsheet_id: str, tab_title: str, max_bytes: int
    ) -> list[list[Any]]: ...


class TokenVault(Protocol):
    def seal(self, text: str) -> str: ...

    def unseal(self, sealed: str, max_age_seconds: int | None = None) -> str: ...


@dataclass(frozen=True)
class GoogleConnection:
    user_id: UUID
    google_email: str
    scope: str
    refresh_token_sealed: str
    version: UUID = field(default_factory=uuid4)


class GoogleConnections(Protocol):
    def get(self, user_id: UUID) -> GoogleConnection | None: ...

    def save(
        self, connection: GoogleConnection, *, expected_version: UUID | None = None
    ) -> None: ...

    def current(self, connection: GoogleConnection) -> bool: ...

    def delete(self, user_id: UUID, *, expected_version: UUID | None = None) -> None: ...


class SessionIssuer(Protocol):
    def provision(self, email: str, display_name: str = "") -> str: ...
