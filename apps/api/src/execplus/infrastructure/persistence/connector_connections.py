"""Use case: Persists each user's sealed connection to an external data platform.

What it does: Reads, upserts and deletes one row per user and provider, never plaintext secrets.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Engine, and_, delete, select, update

from execplus.application.connector_ports import ConnectorConnection
from execplus.infrastructure.persistence.schema import connector_connections


class SqlConnectorConnections:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _record(row: dict) -> ConnectorConnection:  # type: ignore[type-arg]
        return ConnectorConnection(
            row["user_id"], row["provider"], row["display_name"], row["sealed_credentials"]
        )

    def get(self, user_id: UUID, provider: str) -> ConnectorConnection | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(connector_connections).where(
                        and_(
                            connector_connections.c.user_id == user_id,
                            connector_connections.c.provider == provider,
                        )
                    )
                )
                .mappings()
                .first()
            )
        return self._record(dict(row)) if row else None

    def list(self, user_id: UUID) -> list[ConnectorConnection]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(connector_connections).where(connector_connections.c.user_id == user_id)
                )
                .mappings()
                .all()
            )
        return [self._record(dict(row)) for row in rows]

    def save(self, record: ConnectorConnection) -> None:
        now = datetime.now(timezone.utc)
        values = dict(
            display_name=record.display_name,
            sealed_credentials=record.sealed_credentials,
            updated_at=now,
        )
        match = and_(
            connector_connections.c.user_id == record.user_id,
            connector_connections.c.provider == record.provider,
        )
        with self.engine.begin() as connection:
            changed = connection.execute(
                update(connector_connections).where(match).values(**values)
            ).rowcount
            if not changed:
                connection.execute(
                    connector_connections.insert().values(
                        user_id=record.user_id,
                        provider=record.provider,
                        created_at=now,
                        **values,
                    )
                )

    def delete(self, user_id: UUID, provider: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                delete(connector_connections).where(
                    and_(
                        connector_connections.c.user_id == user_id,
                        connector_connections.c.provider == provider,
                    )
                )
            )
