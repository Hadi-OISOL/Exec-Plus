"""Use case: Executes validated read-only query plans against an in-memory snapshot.

What it does: Loads an authorized dataset snapshot into DuckDB and runs one
bounded, parameterized SELECT under a row, memory, and time limit.
"""

import asyncio
from datetime import date
from decimal import Decimal, InvalidOperation

import duckdb

from execplus.domain.errors import AuthorizationError, UnsafeQueryError
from execplus.domain.join_paths import LEFT_VIEW_NAME, RIGHT_VIEW_NAME, JoinPath
from execplus.domain.models import QueryPlan, QueryResult, Scalar, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import VIEW_NAME, DatasetView, quote_identifier

_DUCKDB_TYPES = {
    "integer": "BIGINT",
    "decimal": "DOUBLE",
    "date": "DATE",
    "boolean": "BOOLEAN",
    "text": "VARCHAR",
    "empty": "VARCHAR",
}


def _coerce(value: str, kind: str) -> Scalar:
    value = value.strip()
    if not value:
        return None
    try:
        if kind == "integer":
            return int(Decimal(value))
        if kind == "decimal":
            return float(Decimal(value))
        if kind == "boolean":
            return value.lower() == "true"
        if kind == "date":
            return date.fromisoformat(value)
    except (InvalidOperation, ValueError):
        return None
    return value


class DuckDBQueryExecutor:
    def __init__(
        self, timeout_seconds: float, memory_limit_mb: int, insert_batch_size: int = 500
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._memory_limit_mb = memory_limit_mb
        self._insert_batch_size = insert_batch_size

    async def execute(
        self, plan: QueryPlan, scope: WorkspaceScope, table: TableData, view: DatasetView
    ) -> QueryResult:
        if not scope.permits_dataset(plan.dataset_id):
            raise AuthorizationError("The dataset is not authorized for this workspace scope")

        connection = duckdb.connect(":memory:")

        def run() -> tuple[tuple[str, ...], list[tuple[Scalar, ...]]]:
            connection.execute(f"SET memory_limit = '{self._memory_limit_mb}MB'")
            self._load(connection, table, view)
            cursor = connection.execute(plan.sql, list(plan.params))
            description = cursor.description or []
            columns = tuple(str(column[0]) for column in description)
            return columns, cursor.fetchall()

        try:
            columns, rows = await asyncio.wait_for(
                asyncio.to_thread(run), timeout=self._timeout_seconds
            )
        except TimeoutError:
            # Interruption is best-effort and not always immediate (DuckDB docs);
            # the connection is intentionally left rather than closed concurrently
            # with the still-running worker thread.
            connection.interrupt()
            raise UnsafeQueryError("Query exceeded the time limit") from None
        connection.close()
        return QueryResult(
            query_id=plan.query_id,
            columns=columns,
            rows=tuple(tuple(row) for row in rows),
            records_analyzed=len(table.rows),
        )

    async def execute_join(
        self,
        plan: QueryPlan,
        scope: WorkspaceScope,
        join_path: JoinPath,
        left_table: TableData,
        left_view: DatasetView,
        right_table: TableData,
        right_view: DatasetView,
    ) -> QueryResult:
        if not (
            scope.permits_dataset(join_path.left_dataset_id)
            and scope.permits_dataset(join_path.right_dataset_id)
        ):
            raise AuthorizationError("Both joined datasets must be authorized for this scope")

        connection = duckdb.connect(":memory:")

        def run() -> tuple[tuple[str, ...], list[tuple[Scalar, ...]]]:
            connection.execute(f"SET memory_limit = '{self._memory_limit_mb}MB'")
            self._load(connection, left_table, left_view, LEFT_VIEW_NAME)
            self._load(connection, right_table, right_view, RIGHT_VIEW_NAME)
            cursor = connection.execute(plan.sql, list(plan.params))
            description = cursor.description or []
            columns = tuple(str(column[0]) for column in description)
            return columns, cursor.fetchall()

        try:
            columns, rows = await asyncio.wait_for(
                asyncio.to_thread(run), timeout=self._timeout_seconds
            )
        except TimeoutError:
            connection.interrupt()
            raise UnsafeQueryError("Query exceeded the time limit") from None
        connection.close()
        return QueryResult(
            query_id=plan.query_id,
            columns=columns,
            rows=tuple(tuple(row) for row in rows),
            records_analyzed=len(left_table.rows) + len(right_table.rows),
        )

    def _load(
        self,
        connection: duckdb.DuckDBPyConnection,
        table: TableData,
        view: DatasetView,
        table_name: str = VIEW_NAME,
    ) -> None:
        by_name = {column.name: column for column in view.columns}
        kinds = [by_name[name].type for name in table.headers]
        types = [_DUCKDB_TYPES[kind] for kind in kinds]
        columns_sql = ", ".join(
            f"{quote_identifier(name)} {kind}"
            for name, kind in zip(table.headers, types, strict=True)
        )
        connection.execute(f"CREATE TABLE {quote_identifier(table_name)} ({columns_sql})")

        column_count = max(1, len(table.headers))
        batch_size = max(1, min(self._insert_batch_size, 20_000 // column_count))
        placeholders = "(" + ", ".join(["?"] * len(table.headers)) + ")"
        insert_prefix = f"INSERT INTO {quote_identifier(table_name)} VALUES "
        rows = table.rows
        for start in range(0, len(rows), batch_size):
            chunk = rows[start : start + batch_size]
            values_sql = ", ".join([placeholders] * len(chunk))
            flat_params = [
                _coerce(cell, kind) for row in chunk for cell, kind in zip(row, kinds, strict=True)
            ]
            connection.execute(insert_prefix + values_sql, flat_params)
