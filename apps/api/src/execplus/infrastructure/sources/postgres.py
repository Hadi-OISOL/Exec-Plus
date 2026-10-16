"""Use case: Reads complete approved PostgreSQL tables into immutable CSV snapshots.

What it does: Pins endpoints, loads operator-only secret references, checks a read-only
role, streams bounded scalar rows in one snapshot, and emits content-free failures.
"""

import csv
import hashlib
import ipaddress
import json
import os
import stat
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql

from execplus.domain.source_imports import (
    MAX_CELL_BYTES,
    PostgresSource,
    SourceSnapshot,
    SourceTable,
    invalid,
)

SCALAR_TYPES = frozenset(
    {
        "int2",
        "int4",
        "int8",
        "numeric",
        "text",
        "varchar",
        "bpchar",
        "bool",
        "date",
        "timestamp",
        "timestamptz",
        "uuid",
    }
)


@dataclass(frozen=True)
class Credentials:
    username: str = field(repr=False)
    password: str = field(repr=False)
    root_cert: str | None = field(default=None, repr=False)


class PostgresSecrets:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()

    def load(self, reference: str) -> Credentials:
        if not reference or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for char in reference
        ):
            raise invalid("source_secret", "The operator source secret is unavailable.", 503)
        try:
            fd = os.open(
                self.directory / (reference + ".json"),
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            )
            with os.fdopen(fd, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
                    raise ValueError
                if metadata.st_size > 16384:
                    raise ValueError
                body = json.loads(stream.read(16385))
            if not isinstance(body, dict) or set(body) - {"username", "password", "root_cert"}:
                raise ValueError
            username, password = body["username"], body["password"]
            if (
                not isinstance(username, str)
                or not 1 <= len(username.encode()) <= 63
                or not isinstance(password, str)
                or not 1 <= len(password) <= 4096
                or any(ord(char) < 32 or ord(char) == 127 for char in username)
                or "\x00" in password
            ):
                raise ValueError
            cert = body.get("root_cert")
            if cert is not None:
                if (
                    not isinstance(cert, str)
                    or not cert.endswith(".crt")
                    or Path(cert).name != cert
                ):
                    raise ValueError
                target = self.directory / cert
                if target.is_symlink() or not target.is_file():
                    raise ValueError
                cert = str(target)
            return Credentials(username, password, cert)
        except (OSError, ValueError, KeyError, TypeError):
            raise invalid(
                "source_secret", "The operator source secret is unavailable.", 503
            ) from None


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise invalid("source_value", "The source contains an unsupported non-finite number.")
        return str(value)
    if isinstance(value, str) and not value.strip():
        raise invalid(
            "source_value", "Empty source text cannot be distinguished from a missing CSV cell."
        )
    if isinstance(value, str | int | UUID):
        return str(value)
    raise invalid("source_value", "The source contains an unsupported value type.")


class PostgresSnapshotExtractor:
    def __init__(
        self,
        secrets: PostgresSecrets,
        forbidden_endpoints: frozenset[tuple[str, int, str]],
        *,
        local_test: bool = False,
    ) -> None:
        self.secrets = secrets
        self.forbidden_endpoints = forbidden_endpoints
        self.local_test = local_test

    @staticmethod
    def _remaining(started: float, timeout: int) -> int:
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise invalid("source_timeout", "The source read reached its time limit.", 504)
        return max(1, int(remaining * 1000))

    @classmethod
    def _budget(cls, connection: psycopg.Connection[Any], started: float, timeout: int) -> None:
        connection.execute(
            sql.SQL("SET LOCAL statement_timeout = {}").format(
                sql.Literal(cls._remaining(started, timeout))
            )
        )

    def read(self, source: PostgresSource, selection: SourceTable) -> SourceSnapshot:
        source.select(selection.schema, selection.table, selection.columns)
        address = ipaddress.ip_address(source.address)
        if (address.is_loopback and not self.local_test) or (
            source.address,
            source.port,
            source.database,
        ) in self.forbidden_endpoints:
            raise invalid("source_endpoint", "This source endpoint is not eligible for import.")
        credentials = self.secrets.load(source.secret_ref)
        started = time.monotonic()
        local = self.local_test and address.is_loopback
        try:
            with psycopg.connect(
                host=source.host,
                hostaddr=source.address,
                port=source.port,
                dbname=source.database,
                user=credentials.username,
                password=credentials.password,
                sslmode="disable" if local else "verify-full",
                sslrootcert=credentials.root_cert,
                connect_timeout=min(source.timeout_seconds, 5),
                application_name="execplus-readonly-source",
                options=(
                    f"-c statement_timeout={source.timeout_seconds * 1000} -c lock_timeout=2000"
                ),
            ) as connection:
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                connection.execute("SET LOCAL search_path = pg_catalog")
                connection.execute("SET LOCAL timezone = 'UTC'")
                connection.execute("SET LOCAL datestyle = 'ISO, YMD'")
                connection.execute("SET LOCAL lock_timeout = '2000ms'")
                self._budget(connection, started, source.timeout_seconds)
                role = connection.execute(
                    "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls "
                    "FROM pg_catalog.pg_roles WHERE rolname = current_user"
                ).fetchone()
                if role is None or any(role):
                    raise invalid("source_role", "Use a dedicated read-only source account.")
                self._budget(connection, started, source.timeout_seconds)
                metadata = connection.execute(
                    "SELECT c.oid, c.relkind, c.relispartition, "
                    "EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhparent=c.oid), "
                    "pg_catalog.has_table_privilege(c.oid, 'SELECT'), "
                    "pg_catalog.has_table_privilege(c.oid, "
                    "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') "
                    "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
                    "ON n.oid=c.relnamespace "
                    "WHERE n.nspname=%s AND c.relname=%s",
                    (selection.schema, selection.table),
                ).fetchone()
                if metadata is None or metadata[1] != "r" or metadata[2] or metadata[3]:
                    raise invalid("source_table", "Use an approved ordinary source table.")
                if not metadata[4] or metadata[5]:
                    raise invalid("source_role", "Grant SELECT only on the approved source table.")
                self._budget(connection, started, source.timeout_seconds)
                found = connection.execute(
                    "SELECT a.attname, t.typname, n.nspname "
                    "FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_type t ON t.oid=a.atttypid "
                    "JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace "
                    "WHERE a.attrelid=%s AND a.attname=ANY(%s) "
                    "AND a.attnum>0 AND NOT a.attisdropped",
                    (metadata[0], list(selection.columns)),
                ).fetchall()
                types = {
                    name: kind
                    for name, kind, namespace in found
                    if namespace == "pg_catalog" and kind in SCALAR_TYPES
                }
                if set(types) != set(selection.columns):
                    raise invalid(
                        "source_schema", "The approved fields changed or use unsupported types."
                    )
                table = sql.Identifier(selection.schema, selection.table)
                self._budget(connection, started, source.timeout_seconds)
                count = connection.execute(
                    sql.SQL("SELECT COUNT(*) FROM (SELECT 1 FROM ONLY {} LIMIT {}) limited").format(
                        table, sql.Literal(source.max_rows + 1)
                    )
                ).fetchone()
                if count is None or not 1 <= count[0] <= source.max_rows:
                    raise invalid(
                        "source_rows", "The complete source must fit the approved row limit."
                    )
                columns = [sql.Identifier(name) for name in selection.columns]
                oversize = [
                    sql.SQL("pg_catalog.octet_length({}::text) > {}").format(
                        column, sql.Literal(MAX_CELL_BYTES)
                    )
                    for column in columns
                ]
                fields = [
                    sql.SQL("CASE WHEN {} THEN NULL ELSE {} END").format(test, column)
                    for test, column in zip(oversize, columns, strict=True)
                ]
                query = sql.SQL("SELECT {}, ({}) FROM ONLY {} ORDER BY {} LIMIT {}").format(
                    sql.SQL(", ").join(fields),
                    sql.SQL(" OR ").join(oversize),
                    table,
                    sql.SQL(", ").join(columns),
                    sql.Literal(source.max_rows + 1),
                )
                output = StringIO(newline="")
                writer = csv.writer(output, lineterminator="\n")
                writer.writerow(selection.columns)
                content = bytearray(output.getvalue().encode())
                rows = 0
                self._budget(connection, started, source.timeout_seconds)
                with connection.cursor(name="execplus_snapshot") as cursor:
                    cursor.itersize = 8
                    cursor.execute(query)
                    for record in cursor:
                        self._remaining(started, source.timeout_seconds)
                        if record[-1]:
                            raise invalid(
                                "source_value", "A source cell exceeds the supported size."
                            )
                        values = [cell(value) for value in record[:-1]]
                        if not any(value.strip() for value in values):
                            raise invalid(
                                "source_value", "Completely empty source records are not supported."
                            )
                        output.seek(0)
                        output.truncate(0)
                        writer.writerow(values)
                        content.extend(output.getvalue().encode())
                        rows += 1
                        if len(content) > source.max_bytes or rows > source.max_rows:
                            raise invalid(
                                "source_size", "The complete source exceeds its import limit.", 413
                            )
                if rows != count[0]:
                    raise invalid(
                        "source_snapshot",
                        "The source did not return a complete consistent snapshot.",
                        409,
                    )
                self._remaining(started, source.timeout_seconds)
                payload = bytes(content)
                return SourceSnapshot(
                    payload,
                    tuple((name, types[name]) for name in selection.columns),
                    rows,
                    datetime.now(timezone.utc),
                    source.version,
                    hashlib.sha256(payload).hexdigest(),
                )
        except (psycopg.errors.QueryCanceled, psycopg.errors.LockNotAvailable):
            raise invalid(
                "source_timeout", "The source read reached its time limit.", 504
            ) from None
        except psycopg.Error:
            raise invalid(
                "source_unavailable", "The approved source could not be read.", 503
            ) from None
        except (ValueError, OverflowError, UnicodeError):
            raise invalid("source_value", "The source contains an unsupported value.") from None


def controlled_extractor(
    directory: Path, host: str, port: int, database: str, *, local_test: bool = False
) -> PostgresSnapshotExtractor:
    import socket

    try:
        addresses = {
            str(item[4][0]) for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
    except OSError:
        raise invalid(
            "source_unavailable", "Source import configuration is unavailable.", 503
        ) from None
    return PostgresSnapshotExtractor(
        PostgresSecrets(directory),
        frozenset((address, port, database) for address in addresses),
        local_test=local_test,
    )
