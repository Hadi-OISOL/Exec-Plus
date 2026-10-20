"""Use case: Persists versioned sealed user connections to external data platforms.

What it does: Serializes connection writes and fences revoked or superseded attempts.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import Engine, delete, select

from execplus.application.connector_ports import ConnectorConnection
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.oauth_state import (
    active_user,
    connection_match,
    revoke_attempts,
    save_connection,
)


class SqlConnectorConnections:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _record(row: Any) -> ConnectorConnection:
        return ConnectorConnection(
            row["user_id"],
            row["provider"],
            row["display_name"],
            row["sealed_credentials"],
            row["version"],
        )

    def get(self, user_id: UUID, provider: str) -> ConnectorConnection | None:
        with self.engine.begin() as connection:
            active_user(connection, user_id)
            row = (
                connection.execute(
                    select(s.connector_connections).where(
                        connection_match(s.connector_connections, user_id, provider)
                    )
                )
                .mappings()
                .first()
            )
        return self._record(row) if row else None

    def list(self, user_id: UUID) -> list[ConnectorConnection]:
        with self.engine.begin() as connection:
            active_user(connection, user_id)
            rows = (
                connection.execute(
                    select(s.connector_connections).where(
                        s.connector_connections.c.user_id == user_id
                    )
                )
                .mappings()
                .all()
            )
        return [self._record(row) for row in rows]

    def save(self, record: ConnectorConnection, *, expected_version: UUID | None = None) -> None:
        with self.engine.begin() as connection:
            active_user(connection, record.user_id)
            if expected_version is not None:
                actual = connection.execute(
                    select(s.connector_connections.c.version).where(
                        connection_match(s.connector_connections, record.user_id, record.provider)
                    )
                ).scalar_one_or_none()
                if actual != expected_version:
                    raise IngestionError(
                        "connector_reconnect", "Your connection changed. Try again.", 409
                    )
            save_connection(connection, record)

    def current(self, record: ConnectorConnection) -> bool:
        current = self.get(record.user_id, record.provider)
        return current is not None and current.version == record.version

    def delete(self, user_id: UUID, provider: str, *, expected_version: UUID | None = None) -> None:
        with self.engine.begin() as connection:
            active_user(connection, user_id)
            match = connection_match(s.connector_connections, user_id, provider)
            if expected_version is not None:
                match &= s.connector_connections.c.version == expected_version
            else:
                revoke_attempts(connection, user_id, provider)
            connection.execute(delete(s.connector_connections).where(match))
