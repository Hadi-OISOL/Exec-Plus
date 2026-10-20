"""Use case: Declares what the application needs from each external data platform.

What it does: Keeps platform APIs, drivers and credentials behind protocols the services depend on.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from execplus.domain.connectors import Source


@dataclass(frozen=True)
class ConnectorField:
    name: str
    label: str
    secret: bool = False
    placeholder: str = ""


@dataclass(frozen=True)
class ConnectorSession:
    access_token: str = ""
    context: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderTokens:
    access_token: str
    refresh_token: str | None = None
    expires_in: int = 0
    context: dict[str, str] = field(default_factory=dict)


class ConnectorApiError(Exception):
    def __init__(self, status: int, code: str = "") -> None:
        super().__init__(f"The platform request failed with status {status}")
        self.status = status
        self.code = code


class Connector(Protocol):
    id: str
    label: str
    kind: Literal["oauth", "credentials"]
    description: str
    fields: tuple[ConnectorField, ...]

    def sources(self, session: ConnectorSession, parent: str | None) -> list[Source]: ...

    def fetch(
        self, session: ConnectorSession, source_id: str, max_rows: int
    ) -> list[dict[str, Any]]: ...


class OAuthConnector(Connector, Protocol):
    uses_pkce: bool

    def authorization_url(self, *, redirect_uri: str, state: str, challenge: str) -> str: ...

    def exchange_code(
        self, code: str, redirect_uri: str, verifier: str, callback: dict[str, str]
    ) -> ProviderTokens: ...

    def refresh(self, refresh_token: str, context: dict[str, str]) -> ProviderTokens: ...

    def revoke(self, refresh_token: str) -> None: ...

    def account_name(self, context: dict[str, str]) -> str: ...


class CredentialConnector(Connector, Protocol):
    def validate(self, credentials: dict[str, str]) -> str: ...


@dataclass(frozen=True)
class ConnectorConnection:
    user_id: UUID
    provider: str
    display_name: str
    sealed_credentials: str
    version: UUID = field(default_factory=uuid4)


class ConnectorConnections(Protocol):
    def get(self, user_id: UUID, provider: str) -> ConnectorConnection | None: ...

    def list(self, user_id: UUID) -> list[ConnectorConnection]: ...

    def save(
        self, connection: ConnectorConnection, *, expected_version: UUID | None = None
    ) -> None: ...

    def current(self, connection: ConnectorConnection) -> bool: ...

    def delete(
        self, user_id: UUID, provider: str, *, expected_version: UUID | None = None
    ) -> None: ...
