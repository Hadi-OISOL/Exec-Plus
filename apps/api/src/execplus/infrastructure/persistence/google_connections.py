"""Use case: Persists each user's encrypted Google connection.

What it does: Reads, upserts and deletes one connection row per user, never plaintext tokens.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Engine, delete, select, update

from execplus.application.google_ports import GoogleConnection
from execplus.infrastructure.persistence.schema import google_connections


class SqlGoogleConnections:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get(self, user_id: UUID) -> GoogleConnection | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(google_connections).where(google_connections.c.user_id == user_id)
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return GoogleConnection(
            row["user_id"], row["google_email"], row["scope"], row["refresh_token_encrypted"]
        )

    def save(self, connection_record: GoogleConnection) -> None:
        now = datetime.now(timezone.utc)
        values = dict(
            google_email=connection_record.google_email,
            scope=connection_record.scope,
            refresh_token_encrypted=connection_record.refresh_token_sealed,
            updated_at=now,
        )
        with self.engine.begin() as connection:
            changed = connection.execute(
                update(google_connections)
                .where(google_connections.c.user_id == connection_record.user_id)
                .values(**values)
            ).rowcount
            if not changed:
                connection.execute(
                    google_connections.insert().values(
                        user_id=connection_record.user_id, created_at=now, **values
                    )
                )

    def delete(self, user_id: UUID) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                delete(google_connections).where(google_connections.c.user_id == user_id)
            )
