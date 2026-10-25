"""Use case: Reads tables or a user's own SELECT from customer databases with read-only sessions.

What it does: Connects PostgreSQL, MySQL/MariaDB and SQL Server with the user's credentials,
lists schemas and tables with approximate row counts, previews rows and streams bounded
copies to a file in batches.
"""

import socket
import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, BinaryIO, Literal
from urllib.parse import quote, unquote

from pymysql import _auth as mysql_auth  # type: ignore[import-untyped]
from sqlalchemy import (
    MetaData,
    Table,
    Text,
    case,
    cast,
    create_engine,
    event,
    func,
    inspect,
    literal,
    literal_column,
    select,
    text,
)
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import Select

from execplus.application.connector_ports import (
    ConnectorApiError,
    ConnectorField,
    ConnectorSession,
)
from execplus.domain.connectors import (
    MAX_IMPORT_BYTES,
    RecordBuffer,
    Source,
    scalar,
    source_too_large,
    write_rows_csv,
)
from execplus.domain.google_oauth import MAX_COLUMNS
from execplus.infrastructure.connectors.base import HostPolicy
from execplus.infrastructure.connectors.sql_guard import checked_select

SESSION_OPTIONS = (
    "-c default_transaction_read_only=on -c statement_timeout=30000 "
    "-c idle_in_transaction_session_timeout=30000"
)
MAX_LISTED = 500
PREVIEW_ROWS = 20
BATCH_ROWS = 2000
STATEMENT_SECONDS = 120
TLS_MODES = ("require", "verify", "off")
QUERY_PREFIX = "query/"
SSL_CONNECTION_ERROR = 2026


def _is_binary(column: Any) -> bool:
    try:
        return column.type.python_type in {bytes, bytearray, memoryview}
    except NotImplementedError:
        return False


class SqlDatabaseConnector:
    id = ""
    label = ""
    kind: Literal["oauth", "credentials"] = "credentials"
    description = ""
    driver = ""
    dialect = ""
    default_port = 0
    size_function = "octet_length"
    system_schemas: frozenset[str] = frozenset()
    tls_modes: tuple[str, ...] = TLS_MODES

    def __init__(self, policy: HostPolicy, forbidden: tuple[str, int, str] | None = None) -> None:
        self.policy = policy
        self.forbidden = forbidden
        self.fields: tuple[ConnectorField, ...] = (
            ConnectorField("host", "Host", placeholder="db.example.com"),
            ConnectorField("port", "Port", placeholder=str(self.default_port), required=False),
            ConnectorField("database", "Database name"),
            ConnectorField("user", "User"),
            ConnectorField("password", "Password", secret=True),
            ConnectorField(
                "tls",
                "Encryption (TLS)",
                required=False,
                options=self.tls_modes if policy.allow_private else ("require", "verify"),
            ),
        )

    @staticmethod
    def _addresses(host: str) -> set[str]:
        try:
            return {str(item[4][0]) for item in socket.getaddrinfo(host, None)}
        except OSError:
            return {host}

    def _refuse_control_plane(self, host: str, port: int, database: str) -> None:
        if self.forbidden is None:
            return
        own_host, own_port, own_database = self.forbidden
        if (
            port == own_port
            and database == own_database
            and self._addresses(host) & self._addresses(own_host)
        ):
            raise ConnectorApiError(422, "control_plane_database")

    def _tls(self, credentials: dict[str, str]) -> str:
        mode = credentials.get("tls", "").strip().lower()
        if not mode:
            return ""
        if mode not in self.tls_modes or (mode == "off" and not self.policy.allow_private):
            raise ConnectorApiError(422, "invalid_tls")
        return mode

    def _connect_args(self, tls: str) -> dict[str, Any]:
        raise NotImplementedError

    def _prepare(self, engine: Engine, tls: str) -> None:
        return None

    def _refusal(self, error: SQLAlchemyError) -> ConnectorApiError | None:
        return None

    def _engine(self, credentials: dict[str, str]) -> Engine:
        host = credentials.get("host", "").strip()
        if not host or any(char in host for char in "/@ "):
            raise ConnectorApiError(422, "invalid_host")
        self.policy.check_host(host)
        port = credentials.get("port", "").strip() or str(self.default_port)
        if not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ConnectorApiError(422, "invalid_port")
        for name in ("database", "user"):
            if not credentials.get(name, "").strip():
                raise ConnectorApiError(422, "missing_field")
        tls = self._tls(credentials)
        self._refuse_control_plane(host, int(port), credentials["database"])
        url = URL.create(
            self.driver,
            username=credentials["user"],
            password=credentials.get("password", ""),
            host=host,
            port=int(port),
            database=credentials["database"],
        )
        engine = create_engine(url, poolclass=NullPool, connect_args=self._connect_args(tls))
        self._prepare(engine, tls)
        return engine

    def _check_read_only(self, connection: Connection) -> bool:
        raise NotImplementedError

    @contextmanager
    def _connection(self, credentials: dict[str, str]) -> Iterator[Connection]:
        engine = self._engine(credentials)
        try:
            with engine.connect() as connection:
                yield connection
                connection.rollback()
        except SQLAlchemyError as error:
            raise self._refusal(error) or ConnectorApiError(502, "database_error") from None
        finally:
            engine.dispose()

    def validate(self, credentials: dict[str, str]) -> str:
        engine = self._engine(credentials)
        try:
            with engine.connect() as connection:
                read_only = self._check_read_only(connection)
                connection.rollback()
        except SQLAlchemyError as error:
            raise self._refusal(error) or ConnectorApiError(401, "connection_failed") from None
        finally:
            engine.dispose()
        if not read_only:
            raise ConnectorApiError(403, "not_read_only")
        return f"{credentials['database'].strip()}@{credentials['host'].strip()}"

    def _row_counts(self, connection: Connection, schema: str) -> dict[str, int]:
        return {}

    def sources(self, session: ConnectorSession, parent: str | None) -> list[Source]:
        with self._connection(session.context) as connection:
            inspector = inspect(connection)
            if parent is None:
                schemas = [
                    name
                    for name in inspector.get_schema_names()
                    if name.lower() not in self.system_schemas and not name.startswith("pg_")
                ]
                return [
                    Source(f"schema/{quote(name, safe='')}", name, container=True)
                    for name in sorted(schemas)[:MAX_LISTED]
                ]
            schema = unquote(parent.removeprefix("schema/"))
            names = sorted(
                set(inspector.get_table_names(schema)) | set(inspector.get_view_names(schema))
            )[:MAX_LISTED]
            counts = self._row_counts(connection, schema)
            return [
                Source(
                    f"table/{quote(schema, safe='')}/{quote(name, safe='')}",
                    name,
                    rows=counts.get(name),
                )
                for name in names
            ]

    def _table_select(self, connection: Connection, source_id: str) -> tuple[Select[Any], bool]:
        parts = source_id.split("/")
        if len(parts) != 3 or parts[0] != "table":
            raise ConnectorApiError(404, "unknown_source")
        schema, name = unquote(parts[1]), unquote(parts[2])
        inspector = inspect(connection)
        known = set(inspector.get_table_names(schema)) | set(inspector.get_view_names(schema))
        if name not in known:
            raise ConnectorApiError(404, "unknown_source")
        table = Table(name, MetaData(), schema=schema, autoload_with=connection)
        columns = [column for column in table.columns if not _is_binary(column)]
        if not columns:
            raise ConnectorApiError(422, "no_readable_columns")
        if len(columns) > MAX_COLUMNS:
            raise source_too_large()
        size = getattr(func, self.size_function)
        row_bytes = sum(
            (func.coalesce(size(cast(column, Text)), 0) for column in columns),
            start=literal(0),
        )
        projection = [
            case((row_bytes <= MAX_IMPORT_BYTES, column), else_=None).label(column.name)
            for column in columns
        ]
        return select(row_bytes.label("__row_bytes"), *projection), True

    def _query_select(self, source_id: str) -> tuple[Select[Any], bool]:
        query = checked_select(unquote(source_id.removeprefix(QUERY_PREFIX)), self.dialect)
        derived = text(query.replace(":", "\\:")).columns().subquery("syntelio_query")
        return select(literal_column("*")).select_from(derived), False

    def _select(self, connection: Connection, source_id: str) -> tuple[Select[Any], bool]:
        if source_id.startswith(QUERY_PREFIX):
            return self._query_select(source_id)
        return self._table_select(connection, source_id)

    def _rows(
        self, connection: Connection, source_id: str, limit: int
    ) -> tuple[list[str], Iterator[tuple[Any, ...]]]:
        statement, guarded = self._select(connection, source_id)
        result = connection.execution_options(
            stream_results=True, max_row_buffer=BATCH_ROWS
        ).execute(statement.limit(limit))
        keys = list(result.keys())
        names = keys[1:] if guarded else keys

        def rows() -> Iterator[tuple[Any, ...]]:
            for batch in result.partitions(BATCH_ROWS):
                for row in batch:
                    if guarded and row[0] > MAX_IMPORT_BYTES:
                        raise source_too_large()
                    yield tuple(row[1:] if guarded else row)

        return names, rows()

    def fetch(
        self, session: ConnectorSession, source_id: str, max_rows: int
    ) -> list[dict[str, Any]]:
        records = RecordBuffer()
        with self._connection(session.context) as connection:
            names, rows = self._rows(connection, source_id, max_rows)
            for row in rows:
                records.append(dict(zip(names, row, strict=True)))
        return records

    def preview(self, session: ConnectorSession, source_id: str) -> dict[str, Any]:
        with self._connection(session.context) as connection:
            names, rows = self._rows(connection, source_id, PREVIEW_ROWS)
            values = [[scalar(value) for value in row] for row in rows]
        return dict(columns=names, rows=values)

    def export(
        self,
        session: ConnectorSession,
        source_id: str,
        target: BinaryIO,
        *,
        max_rows: int,
        max_bytes: int,
    ) -> int:
        with self._connection(session.context) as connection:
            names, rows = self._rows(connection, source_id, max_rows + 1)
            return write_rows_csv(names, rows, target, max_rows=max_rows, max_bytes=max_bytes)


class PostgresConnector(SqlDatabaseConnector):
    id = "postgresql"
    label = "PostgreSQL database"
    description = "Any table, view or SELECT query in a PostgreSQL database, read-only."
    driver = "postgresql+psycopg"
    dialect = "postgres"
    default_port = 5432
    system_schemas = frozenset({"information_schema"})

    def _connect_args(self, tls: str) -> dict[str, Any]:
        legacy = "prefer" if self.policy.allow_private else "require"
        modes = {"": legacy, "require": "require", "verify": "verify-full", "off": "disable"}
        args = {"connect_timeout": 10, "sslmode": modes[tls], "options": SESSION_OPTIONS}
        if tls == "verify":
            args["sslrootcert"] = "system"
        return args

    def _check_read_only(self, connection: Connection) -> bool:
        return bool(connection.execute(text("SHOW transaction_read_only")).scalar_one() == "on")

    def _row_counts(self, connection: Connection, schema: str) -> dict[str, int]:
        rows = connection.execute(
            text(
                "SELECT c.relname, c.reltuples::bigint FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = :schema AND c.relkind IN ('r', 'p', 'm')"
            ),
            dict(schema=schema),
        )
        return {str(name): int(count) for name, count in rows if count is not None and count >= 0}


class PlaintextSafeCachingSha2:
    """PyMySQL 1.2.3 drops the final OK packet of caching_sha2 RSA sign-in without TLS."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def authenticate(self, packet: Any) -> Any:
        return mysql_auth.caching_sha2_password_auth(self.connection, packet)


class MySqlConnector(SqlDatabaseConnector):
    id = "mysql"
    label = "MySQL or MariaDB database"
    description = "Any table, view or SELECT query in a MySQL or MariaDB database, read-only."
    driver = "mysql+pymysql"
    dialect = "mysql"
    default_port = 3306
    size_function = "length"
    system_schemas = frozenset({"information_schema", "mysql", "performance_schema", "sys"})

    def _connect_args(self, tls: str) -> dict[str, Any]:
        args: dict[str, Any] = dict(
            connect_timeout=10,
            read_timeout=STATEMENT_SECONDS,
            write_timeout=STATEMENT_SECONDS,
            charset="utf8mb4",
            init_command="SET SESSION TRANSACTION READ ONLY",
            auth_plugin_map={"caching_sha2_password": PlaintextSafeCachingSha2},
        )
        if tls == "off":
            args["ssl_disabled"] = True
        elif tls == "verify":
            args["ssl"] = ssl.create_default_context()
        elif tls or not self.policy.allow_private:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            args["ssl"] = context
        return args

    def _prepare(self, engine: Engine, tls: str) -> None:
        encrypted = tls != "off" and (bool(tls) or not self.policy.allow_private)

        @event.listens_for(engine, "connect")
        def session(dbapi_connection: Any, _record: Any) -> None:
            with dbapi_connection.cursor() as cursor:
                cursor.execute("SELECT VERSION()")
                version = str(cursor.fetchone()[0])
                if "mariadb" in version.lower():
                    cursor.execute(f"SET SESSION max_statement_time = {STATEMENT_SECONDS}")
                else:
                    cursor.execute(f"SET SESSION max_execution_time = {STATEMENT_SECONDS * 1000}")
                if encrypted:
                    cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
                    row = cursor.fetchone()
                    if not row or not row[1]:
                        raise ConnectorApiError(422, "tls_unavailable")

    def _refusal(self, error: SQLAlchemyError) -> ConnectorApiError | None:
        reason = getattr(error, "orig", None)
        if isinstance(reason, ConnectorApiError):
            return reason
        detail = getattr(reason, "args", ())
        if detail and detail[0] == SSL_CONNECTION_ERROR:
            return ConnectorApiError(422, "tls_unavailable")
        if "CERTIFICATE_VERIFY_FAILED" in str(reason):
            return ConnectorApiError(422, "tls_unverified")
        return None

    def _check_read_only(self, connection: Connection) -> bool:
        try:
            value = connection.execute(text("SELECT @@session.transaction_read_only")).scalar_one()
        except SQLAlchemyError:
            connection.rollback()
            value = connection.execute(text("SELECT @@session.tx_read_only")).scalar_one()
        return bool(int(value) == 1)

    def _row_counts(self, connection: Connection, schema: str) -> dict[str, int]:
        rows = connection.execute(
            text(
                "SELECT table_name, table_rows FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_type = 'BASE TABLE'"
            ),
            dict(schema=schema),
        )
        return {str(name): int(count) for name, count in rows if count is not None}


class SqlServerConnector(SqlDatabaseConnector):
    id = "sqlserver"
    label = "Microsoft SQL Server database"
    description = (
        "Any table, view or SELECT query in SQL Server or Azure SQL, read by a login "
        "without write rights."
    )
    driver = "mssql+pymssql"
    dialect = "tsql"
    default_port = 1433
    size_function = "datalength"
    tls_modes = ("require", "off")
    system_schemas = frozenset(
        {
            "sys",
            "information_schema",
            "guest",
            "db_owner",
            "db_accessadmin",
            "db_securityadmin",
            "db_ddladmin",
            "db_backupoperator",
            "db_datareader",
            "db_datawriter",
            "db_denydatareader",
            "db_denydatawriter",
        }
    )

    def _connect_args(self, tls: str) -> dict[str, Any]:
        legacy = "request" if self.policy.allow_private else "require"
        return dict(
            login_timeout=10,
            timeout=STATEMENT_SECONDS,
            encryption={"": legacy, "require": "require", "off": "off"}[tls],
            read_only=True,
            autocommit=False,
        )

    def _check_read_only(self, connection: Connection) -> bool:
        flags = connection.execute(
            text(
                "SELECT IS_SRVROLEMEMBER('sysadmin'), IS_ROLEMEMBER('db_owner'), "
                "IS_ROLEMEMBER('db_datawriter'), IS_ROLEMEMBER('db_ddladmin'), "
                "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'INSERT'), "
                "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'UPDATE'), "
                "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'DELETE'), "
                "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'ALTER'), "
                "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE TABLE')"
            )
        ).one()
        return not any(flag == 1 for flag in flags)

    def _row_counts(self, connection: Connection, schema: str) -> dict[str, int]:
        rows = connection.execute(
            text(
                "SELECT t.name, SUM(p.rows) FROM sys.tables t "
                "JOIN sys.schemas s ON s.schema_id = t.schema_id "
                "JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1) "
                "WHERE s.name = :schema GROUP BY t.name"
            ),
            dict(schema=schema),
        )
        return {str(name): int(count) for name, count in rows if count is not None}
