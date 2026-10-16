"""Use case: Declares bounded operator-approved source snapshot imports.

What it does: Validates exact PostgreSQL endpoints and table/field allowlists while
keeping private connection material separate from browser selections and snapshots.
"""

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from execplus.domain.ingestion import IngestionError

MAX_ROWS = 10000
MAX_COLUMNS = 50
MAX_BYTES = 20 * 1024 * 1024
MAX_CELL_BYTES = 64 * 1024


def invalid(code: str, message: str, status: int = 422) -> IngestionError:
    return IngestionError(code, message, status)


def identifier(value: str) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value.encode("utf-8")) <= 63
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise invalid("source_identifier", "Use an approved PostgreSQL table or field name.")


@dataclass(frozen=True)
class SourceTable:
    schema: str
    table: str
    columns: tuple[str, ...]

    def __post_init__(self) -> None:
        identifier(self.schema)
        identifier(self.table)
        if self.schema.startswith("pg_") or self.schema == "information_schema":
            raise invalid("source_table", "System schemas are not import sources.")
        if (
            not isinstance(self.columns, tuple)
            or not 1 <= len(self.columns) <= MAX_COLUMNS
            or any(not isinstance(column, str) for column in self.columns)
            or len(set(self.columns)) != len(self.columns)
        ):
            raise invalid("source_columns", "Choose up to fifty distinct approved fields.")
        for column in self.columns:
            identifier(column)


@dataclass(frozen=True)
class PostgresSource:
    id: UUID
    workspace_id: UUID
    version: int
    label: str
    host: str = field(repr=False)
    address: str = field(repr=False)
    port: int = field(repr=False)
    database: str = field(repr=False)
    secret_ref: str = field(repr=False)
    tables: tuple[SourceTable, ...]
    enabled: bool = True
    max_rows: int = MAX_ROWS
    max_bytes: int = MAX_BYTES
    timeout_seconds: int = 20

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.workspace_id, UUID):
            raise invalid("source_configuration", "Source ownership must be explicit.")
        if type(self.version) is not int or self.version < 1 or type(self.enabled) is not bool:
            raise invalid("source_configuration", "Use a versioned explicit source configuration.")
        if (
            not isinstance(self.label, str)
            or not self.label.strip()
            or len(self.label) > 100
            or any(ord(char) < 32 or ord(char) == 127 for char in self.label)
        ):
            raise invalid("source_configuration", "Use a short source label.")
        if not isinstance(self.host, str) or not re.fullmatch(r"[A-Za-z0-9.:-]{1,253}", self.host):
            raise invalid("source_endpoint", "The source must use one approved hostname.")
        if not isinstance(self.address, str):
            raise invalid("source_endpoint", "The source must use a pinned IP address.")
        try:
            address = ipaddress.ip_address(self.address)
        except ValueError:
            raise invalid("source_endpoint", "The source must use a pinned IP address.") from None
        if (
            address.is_unspecified
            or address.is_multicast
            or address.is_link_local
            or (isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None)
        ):
            raise invalid("source_endpoint", "This source address is not supported.")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise invalid("source_endpoint", "Use one explicit source port.")
        identifier(self.database)
        if not isinstance(self.secret_ref, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,80}", self.secret_ref
        ):
            raise invalid("source_secret", "Use an operator-managed secret reference.")
        if (
            not isinstance(self.tables, tuple)
            or not 1 <= len(self.tables) <= 20
            or any(not isinstance(item, SourceTable) for item in self.tables)
        ):
            raise invalid("source_table", "Register one to twenty approved tables.")
        if len({(item.schema, item.table) for item in self.tables}) != len(self.tables):
            raise invalid("source_table", "Register each source table once.")
        for value, upper in (
            (self.max_rows, MAX_ROWS),
            (self.max_bytes, MAX_BYTES),
            (self.timeout_seconds, 30),
        ):
            if type(value) is not int or not 1 <= value <= upper:
                raise invalid("source_limit", "Use bounded source limits.")

    def select(self, schema: str, table: str, columns: tuple[str, ...]) -> SourceTable:
        if not self.enabled:
            raise invalid("source_unavailable", "The source is unavailable.", 404)
        approved = next(
            (item for item in self.tables if (item.schema, item.table) == (schema, table)), None
        )
        selection = SourceTable(schema, table, columns)
        if approved is None or any(column not in approved.columns for column in columns):
            raise invalid(
                "source_unavailable", "The requested source selection is unavailable.", 404
            )
        return selection


@dataclass(frozen=True)
class SourceSnapshot:
    content: bytes = field(repr=False)
    columns: tuple[tuple[str, str], ...]
    row_count: int
    extracted_at: datetime
    source_version: int
    checksum: str
    method: str = "postgres-snapshot-v1"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.content, bytes)
            or not 0 < len(self.content) <= MAX_BYTES
            or type(self.row_count) is not int
            or not 1 <= self.row_count <= MAX_ROWS
            or not isinstance(self.columns, tuple)
            or not 1 <= len(self.columns) <= MAX_COLUMNS
            or any(
                not isinstance(column, tuple)
                or len(column) != 2
                or not all(isinstance(part, str) and part for part in column)
                for column in self.columns
            )
            or len({column[0] for column in self.columns}) != len(self.columns)
            or type(self.source_version) is not int
            or self.source_version < 1
            or not isinstance(self.extracted_at, datetime)
            or self.extracted_at.tzinfo is None
            or self.checksum != hashlib.sha256(self.content).hexdigest()
            or self.method != "postgres-snapshot-v1"
        ):
            raise invalid("source_snapshot", "The source snapshot is incomplete or inconsistent.")


@dataclass(frozen=True)
class RegisteredSource:
    source: PostgresSource
    created_by: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source, PostgresSource)
            or not isinstance(self.created_by, UUID)
            or not isinstance(self.created_at, datetime)
            or self.created_at.tzinfo is None
        ):
            raise invalid("source_configuration", "Source registration needs an explicit operator.")


@dataclass(frozen=True)
class ImportSelection:
    source_id: UUID
    source_version: int
    dataset_id: UUID
    table: SourceTable
    mode: str = "upload"
    expected_feed_version: int | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_id, UUID)
            or not isinstance(self.dataset_id, UUID)
            or type(self.source_version) is not int
            or self.source_version < 1
            or not isinstance(self.table, SourceTable)
            or self.mode not in {"upload", "refresh"}
            or (self.mode == "upload" and self.expected_feed_version is not None)
            or (
                self.mode == "refresh"
                and (type(self.expected_feed_version) is not int or self.expected_feed_version < 1)
            )
        ):
            raise invalid(
                "source_selection", "Choose an approved source version and import action."
            )

    def signature(self) -> str:
        value = [
            str(self.source_id),
            self.source_version,
            str(self.dataset_id),
            self.table.schema,
            self.table.table,
            list(self.table.columns),
            self.mode,
            self.expected_feed_version,
        ]
        return hashlib.sha256(json.dumps(value, ensure_ascii=True).encode()).hexdigest()


SOURCE_FAILURES = frozenset(
    {
        "source_unavailable",
        "source_endpoint",
        "source_secret",
        "source_role",
        "source_schema",
        "source_rows",
        "source_size",
        "source_value",
        "source_timeout",
        "source_snapshot",
        "source_table",
        "source_connection",
        "source_import_failed",
        "source_authority_changed",
        "source_publication_failed",
        "source_interrupted",
    }
)


@dataclass(frozen=True)
class SourceImport:
    id: UUID
    workspace_id: UUID
    actor_id: UUID
    membership_created_at: datetime
    request_id: UUID
    selection: ImportSelection
    access_reference: dict[str, str] = field(repr=False)
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    upload_id: UUID | None = None
    candidate_id: UUID | None = None
    snapshot: dict[str, object] | None = None
    failure_code: str | None = None

    def __post_init__(self) -> None:
        if (
            any(
                not isinstance(value, UUID)
                for value in (
                    self.id,
                    self.workspace_id,
                    self.actor_id,
                    self.request_id,
                )
            )
            or not isinstance(self.selection, ImportSelection)
            or not isinstance(self.membership_created_at, datetime)
            or self.membership_created_at.tzinfo is None
            or not isinstance(self.created_at, datetime)
            or self.created_at.tzinfo is None
            or not isinstance(self.access_reference, dict)
            or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in self.access_reference.items()
            )
            or self.status not in {"extracting", "imported", "staged", "failed"}
            or (
                self.status == "extracting"
                and any(
                    value is not None
                    for value in (
                        self.completed_at,
                        self.upload_id,
                        self.candidate_id,
                        self.snapshot,
                        self.failure_code,
                    )
                )
            )
            or (
                self.status != "extracting"
                and (
                    not isinstance(self.completed_at, datetime)
                    or self.completed_at.tzinfo is None
                    or self.completed_at < self.created_at
                )
            )
        ):
            raise invalid("source_import", "The import record is inconsistent.")
        if self.status == "failed":
            if self.failure_code not in SOURCE_FAILURES or any(
                value is not None
                for value in (
                    self.upload_id,
                    self.candidate_id,
                    self.snapshot,
                )
            ):
                raise invalid("source_import", "A failed import cannot claim a saved snapshot.")
        elif self.status in {"imported", "staged"}:
            if (
                not isinstance(self.upload_id, UUID)
                or not isinstance(self.snapshot, dict)
                or self.failure_code is not None
                or (
                    self.status == "imported"
                    and (self.selection.mode != "upload" or self.candidate_id is not None)
                )
                or (
                    self.status == "staged"
                    and (
                        self.selection.mode != "refresh" or not isinstance(self.candidate_id, UUID)
                    )
                )
            ):
                raise invalid("source_import", "A completed import needs its exact saved result.")
            self._validate_snapshot()

    def _validate_snapshot(self) -> None:
        value = self.snapshot
        assert isinstance(value, dict)
        if (
            set(value) != {"checksum", "columns", "row_count", "extracted_at", "method"}
            or not isinstance(value["checksum"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", value["checksum"])
            or type(value["row_count"]) is not int
            or not 1 <= value["row_count"] <= MAX_ROWS
            or value["method"] != "postgres-snapshot-v1"
            or not isinstance(value["columns"], list)
            or len(value["columns"]) != len(self.selection.table.columns)
            or any(
                not isinstance(column, list)
                or len(column) != 2
                or not all(isinstance(part, str) and part for part in column)
                for column in value["columns"]
            )
            or [column[0] for column in value["columns"]] != list(self.selection.table.columns)
            or not isinstance(value["extracted_at"], str)
        ):
            raise invalid("source_import", "The import snapshot metadata is inconsistent.")
        try:
            extracted = datetime.fromisoformat(value["extracted_at"])
        except ValueError:
            raise invalid("source_import", "The import snapshot time is invalid.") from None
        if extracted.tzinfo is None:
            raise invalid("source_import", "The import snapshot time needs a timezone.")


def snapshot_metadata(value: SourceSnapshot) -> dict[str, object]:
    return dict(
        checksum=value.checksum,
        columns=[list(column) for column in value.columns],
        row_count=value.row_count,
        extracted_at=value.extracted_at.isoformat(),
        method=value.method,
    )
