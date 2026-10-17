"""Use case: Reads tables from a customer's PostgreSQL database with a read-only session.

What it does: Connects with the user's credentials, lists tables and copies a bounded table.
"""

from typing import Any, Literal
from urllib.parse import quote, unquote

from sqlalchemy import (
    LargeBinary,
    MetaData,
    Table,
    Text,
    case,
    cast,
    create_engine,
    func,
    inspect,
    literal,
    select,
    text,
)
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from execplus.application.connector_ports import (
    ConnectorApiError,
    ConnectorField,
    ConnectorSession,
)
from execplus.domain.connectors import MAX_IMPORT_BYTES, RecordBuffer, Source, source_too_large
from execplus.domain.google_oauth import MAX_COLUMNS
from execplus.infrastructure.connectors.base import HostPolicy

SESSION_OPTIONS = (
    "-c default_transaction_read_only=on -c statement_timeout=30000 "
    "-c idle_in_transaction_session_timeout=30000"
)
MAX_LISTED = 500


class PostgresConnector:
    id = "postgresql"
    label = "PostgreSQL database"
    kind: Literal["oauth", "credentials"] = "credentials"
    description = "Any table or view in a PostgreSQL database, read through a read-only session."
    fields: tuple[ConnectorField, ...] = (
        ConnectorField("host", "Host", placeholder="db.example.com"),
        ConnectorField("port", "Port", placeholder="5432"),
        ConnectorField("database", "Database name"),
        ConnectorField("user", "User"),
        ConnectorField("password", "Password", secret=True),
    )

    def __init__(self, policy: HostPolicy) -> None:
        self.policy = policy

    def _engine(self, credentials: dict[str, str]) -> Engine:
        host = credentials.get("host", "").strip()
        if not host or any(char in host for char in "/@ "):
            raise ConnectorApiError(422, "invalid_host")
        self.policy.check_host(host)
        port = credentials.get("port", "").strip() or "5432"
        if not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ConnectorApiError(422, "invalid_port")
        for name in ("database", "user"):
            if not credentials.get(name, "").strip():
                raise ConnectorApiError(422, "missing_field")
        url = URL.create(
            "postgresql+psycopg",
            username=credentials["user"],
            password=credentials.get("password", ""),
            host=host,
            port=int(port),
            database=credentials["database"],
        )
        return create_engine(
            url,
            poolclass=NullPool,
            connect_args={
                "connect_timeout": 10,
                "sslmode": "prefer" if self.policy.allow_private else "require",
                "options": SESSION_OPTIONS,
            },
        )

    def validate(self, credentials: dict[str, str]) -> str:
        engine = self._engine(credentials)
        try:
            with engine.connect() as connection:
                name = connection.execute(text("SELECT current_database()")).scalar_one()
                read_only = connection.execute(text("SHOW transaction_read_only")).scalar_one()
        except SQLAlchemyError:
            raise ConnectorApiError(401, "connection_failed") from None
        finally:
            engine.dispose()
        if read_only != "on":
            raise ConnectorApiError(403, "not_read_only")
        return f"{name}@{credentials['host'].strip()}"

    def sources(self, session: ConnectorSession, parent: str | None) -> list[Source]:
        engine = self._engine(session.context)
        try:
            inspector = inspect(engine)
            if parent is None:
                schemas = [
                    name
                    for name in inspector.get_schema_names()
                    if not name.startswith("pg_") and name != "information_schema"
                ]
                return [
                    Source(f"schema/{quote(name, safe='')}", name, container=True)
                    for name in sorted(schemas)[:MAX_LISTED]
                ]
            schema = unquote(parent.removeprefix("schema/"))
            names = sorted(
                set(inspector.get_table_names(schema)) | set(inspector.get_view_names(schema))
            )[:MAX_LISTED]
            return [
                Source(f"table/{quote(schema, safe='')}/{quote(name, safe='')}", name)
                for name in names
            ]
        except SQLAlchemyError:
            raise ConnectorApiError(502, "database_error") from None
        finally:
            engine.dispose()

    def fetch(
        self, session: ConnectorSession, source_id: str, max_rows: int
    ) -> list[dict[str, Any]]:
        parts = source_id.split("/")
        if len(parts) != 3 or parts[0] != "table":
            raise ConnectorApiError(404, "unknown_source")
        schema, name = unquote(parts[1]), unquote(parts[2])
        engine = self._engine(session.context)
        try:
            inspector = inspect(engine)
            known = set(inspector.get_table_names(schema)) | set(inspector.get_view_names(schema))
            if name not in known:
                raise ConnectorApiError(404, "unknown_source")
            table = Table(name, MetaData(), schema=schema, autoload_with=engine)
            columns = [
                column for column in table.columns if not isinstance(column.type, LargeBinary)
            ]
            if not columns:
                raise ConnectorApiError(422, "no_readable_columns")
            if len(columns) > MAX_COLUMNS:
                raise source_too_large()
            row_bytes = sum(
                (func.coalesce(func.octet_length(cast(column, Text)), 0) for column in columns),
                start=literal(0),
            )
            fits = row_bytes <= MAX_IMPORT_BYTES
            projection = [case((fits, column), else_=None).label(column.name) for column in columns]
            records = RecordBuffer()
            with engine.connect().execution_options(
                stream_results=True, max_row_buffer=1
            ) as connection:
                rows = connection.execute(select(fits, *projection).limit(max_rows))
                for row in rows:
                    if not row[0]:
                        raise source_too_large()
                    records.append(
                        dict(zip((column.name for column in columns), row[1:], strict=True))
                    )
        except SQLAlchemyError:
            raise ConnectorApiError(502, "database_error") from None
        finally:
            engine.dispose()
        return records
