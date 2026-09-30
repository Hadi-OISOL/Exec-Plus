"""Use case: Executes validated read-only query plans against an in-memory snapshot.

What it does: Loads an authorized dataset snapshot into DuckDB and runs one
bounded, parameterized SELECT under a row, memory, and time limit.
"""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from threading import Event, Lock

import duckdb
from sqlglot import exp

from execplus.domain.errors import AuthorizationError, UnsafeQueryError
from execplus.domain.join_paths import LEFT_VIEW_NAME, RIGHT_VIEW_NAME, JoinPath
from execplus.domain.models import QueryPlan, QueryResult, Scalar, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import VIEW_NAME, DatasetView, quote_identifier
from execplus.infrastructure.query.validation import validated_query

_DUCKDB_TYPES = {
    "integer": "BIGINT",
    "decimal": "DECIMAL(38, 12)",
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
            number = Decimal(value)
            if not number.is_finite() or number != number.to_integral_value():
                raise ValueError("Invalid integer")
            return int(number)
        if kind == "decimal":
            number = Decimal(value)
            if not number.is_finite() or abs(number) >= Decimal("1e26"):
                raise ValueError("Out of supported decimal range")
            with localcontext() as context:
                context.prec = 50
                if number != number.quantize(Decimal("1e-12")):
                    raise ValueError("Out of supported decimal precision")
            return number
        if kind == "boolean":
            if value.lower() not in {"true", "false"}:
                raise ValueError("Invalid boolean")
            return value.lower() == "true"
        if kind == "date":
            return date.fromisoformat(value)
    except (InvalidOperation, ValueError):
        raise UnsafeQueryError(
            "Correct conflicting or out-of-range values before querying"
        ) from None
    return value


class DuckDBQueryExecutor:
    def __init__(
        self, timeout_seconds: float, memory_limit_mb: int, insert_batch_size: int = 500
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._memory_limit_mb = memory_limit_mb
        self._insert_batch_size = insert_batch_size

    async def _run(
        self,
        plan: QueryPlan,
        scope: WorkspaceScope,
        tables: set[str],
        records: int,
        load: Callable[[duckdb.DuckDBPyConnection], None],
    ) -> QueryResult:
        if plan.workspace_id != scope.workspace_id or not scope.permits_dataset(plan.dataset_id):
            raise AuthorizationError("The query does not belong to the authorized workspace")
        query = validated_query(plan.sql, tables, len(plan.params))
        connection = duckdb.connect(
            ":memory:",
            config={
                "memory_limit": f"{self._memory_limit_mb}MB",
                "threads": "1",
                "enable_external_access": "false",
                "autoinstall_known_extensions": "false",
                "autoload_known_extensions": "false",
                "allow_unsigned_extensions": "false",
            },
        )
        cancelled = Event()
        closed = Event()
        guard = Lock()
        average = query.find(exp.Avg)
        if average is not None:
            alias = average.parent
            if not isinstance(alias, exp.Alias) or average is not alias.this:
                connection.close()
                raise UnsafeQueryError("Only a single direct average is supported")
            alias.set("this", exp.Sum(this=average.this.copy()))
            query.select(
                exp.alias_(exp.Count(this=average.this.copy()), "__count"), append=True, copy=False
            )

        def run() -> QueryResult:
            try:
                load(connection)
                if cancelled.is_set():
                    raise UnsafeQueryError("Query exceeded the time limit")
                matched_records = None
                if not list(query.find_all(exp.AggFunc)):
                    count_query = query.copy()
                    count_query.set("expressions", [exp.Count(this=exp.Star())])
                    count_query.set("limit", None)
                    count_query.set("order", None)
                    count_row = connection.execute(
                        count_query.sql(dialect="duckdb"), list(plan.params)
                    ).fetchone()
                    if count_row is None:
                        raise UnsafeQueryError("The matching count could not be verified")
                    matched_records = count_row[0]
                cursor = connection.execute(query.sql(dialect="duckdb"), list(plan.params))
                columns = tuple(str(column[0]) for column in cursor.description or [])
                fetched = cursor.fetchmany(100_001)
                if len(fetched) > 100_000:
                    raise UnsafeQueryError("The result exceeds the row budget")
                result_rows: list[tuple[Scalar, ...]] = []
                for row in fetched:
                    if average is not None:
                        with localcontext() as context:
                            context.prec = 50
                            value = (
                                (Decimal(row[-2]) / Decimal(row[-1])).quantize(Decimal("1e-12"))
                                if row[-1]
                                else None
                            )
                        result_rows.append((*row[:-2], value))
                    else:
                        result_rows.append(tuple(row))
                return QueryResult(
                    plan.query_id,
                    columns[:-1] if average is not None else columns,
                    tuple(result_rows),
                    records,
                    matched_records,
                )
            except duckdb.Error:
                raise UnsafeQueryError(
                    "The query failed its execution limits or data checks"
                ) from None
            finally:
                with guard:
                    connection.close()
                    closed.set()

        task = asyncio.create_task(asyncio.to_thread(run))
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=self._timeout_seconds)
        except (asyncio.TimeoutError, asyncio.CancelledError) as error:
            cancelled.set()
            with guard:
                if not closed.is_set():
                    connection.interrupt()
            with suppress(Exception, asyncio.CancelledError):
                await task
            if isinstance(error, asyncio.CancelledError):
                raise
            raise UnsafeQueryError("Query exceeded the time limit") from None

    async def execute(
        self, plan: QueryPlan, scope: WorkspaceScope, table: TableData, view: DatasetView
    ) -> QueryResult:
        return await self._run(
            plan,
            scope,
            {VIEW_NAME},
            len(table.rows),
            lambda connection: self._load(connection, table, view),
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
        if (
            join_path.workspace_id != scope.workspace_id
            or not scope.permits_dataset(join_path.left_dataset_id)
            or not scope.permits_dataset(join_path.right_dataset_id)
        ):
            raise AuthorizationError("Both joined datasets must belong to the authorized workspace")
        query = validated_query(plan.sql, {LEFT_VIEW_NAME, RIGHT_VIEW_NAME}, len(plan.params))
        joins = list(query.find_all(exp.Join))
        condition = joins[0].args.get("on") if len(joins) == 1 else None
        expected = {
            (LEFT_VIEW_NAME, join_path.left_column),
            (RIGHT_VIEW_NAME, join_path.right_column),
        }
        if (
            not isinstance(condition, exp.EQ)
            or {(node.table, node.name) for node in condition.find_all(exp.Column)} != expected
        ):
            raise UnsafeQueryError("The join must use exactly its declared keys")
        right_column = right_view.column(join_path.right_column)
        if right_column is None:
            raise UnsafeQueryError("The right join key is unavailable")
        right_index = right_table.headers.index(join_path.right_column)
        keys = [
            _coerce(row[right_index], right_column.type)
            for row in right_table.rows
            if row[right_index].strip()
        ]
        if len(keys) != len(set(keys)):
            raise UnsafeQueryError(
                "The right join key must be unique to prevent inflated aggregates"
            )
        if any(
            column.table == RIGHT_VIEW_NAME
            for aggregate in query.find_all(exp.AggFunc)
            for column in aggregate.find_all(exp.Column)
        ):
            left_column = left_view.column(join_path.left_column)
            if left_column is None:
                raise UnsafeQueryError("The left join key is unavailable")
            left_index = left_table.headers.index(join_path.left_column)
            left_keys = [
                _coerce(row[left_index], left_column.type)
                for row in left_table.rows
                if row[left_index].strip()
            ]
            if len(left_keys) != len(set(left_keys)):
                raise UnsafeQueryError(
                    "Aggregating a right-side measure requires unique left keys "
                    "to prevent duplicated or reweighted values"
                )
        if len(left_table.rows) + len(right_table.rows) > 200_000:
            raise UnsafeQueryError("The join exceeds the input row budget")

        def load(connection: duckdb.DuckDBPyConnection) -> None:
            self._load(connection, left_table, left_view, LEFT_VIEW_NAME)
            self._load(connection, right_table, right_view, RIGHT_VIEW_NAME)

        return await self._run(
            plan,
            scope,
            {LEFT_VIEW_NAME, RIGHT_VIEW_NAME},
            len(left_table.rows) + len(right_table.rows),
            load,
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
