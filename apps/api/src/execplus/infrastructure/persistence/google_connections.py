"""Use case: Persists and revokes versioned encrypted Google connections.

What it does: Uses actor locks and conditional mutation to protect a newer connection.
"""

from uuid import UUID

from sqlalchemy import Engine, delete, select

from execplus.application.google_ports import GoogleConnection
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.oauth_state import (
    active_user,
    revoke_attempts,
    save_connection,
)


class SqlGoogleConnections:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get(self, user_id: UUID) -> GoogleConnection | None:
        with self.engine.begin() as connection:
            active_user(connection, user_id)
            row = (
                connection.execute(
                    select(s.google_connections).where(s.google_connections.c.user_id == user_id)
                )
                .mappings()
                .first()
            )
        return (
            GoogleConnection(
                row["user_id"],
                row["google_email"],
                row["scope"],
                row["refresh_token_encrypted"],
                row["version"],
            )
            if row
            else None
        )

    def save(self, record: GoogleConnection, *, expected_version: UUID | None = None) -> None:
        with self.engine.begin() as connection:
            active_user(connection, record.user_id)
            if expected_version is not None:
                actual = connection.execute(
                    select(s.google_connections.c.version).where(
                        s.google_connections.c.user_id == record.user_id
                    )
                ).scalar_one_or_none()
                if actual != expected_version:
                    raise IngestionError(
                        "google_reconnect", "Your Google connection changed. Try again.", 409
                    )
            save_connection(connection, record)

    def current(self, record: GoogleConnection) -> bool:
        current = self.get(record.user_id)
        return current is not None and current.version == record.version

    def delete(self, user_id: UUID, *, expected_version: UUID | None = None) -> None:
        with self.engine.begin() as connection:
            active_user(connection, user_id)
            match = s.google_connections.c.user_id == user_id
            if expected_version is not None:
                match &= s.google_connections.c.version == expected_version
            else:
                revoke_attempts(connection, user_id, "google")
            connection.execute(delete(s.google_connections).where(match))
