"""Use case: Executes validated read-only query plans against an in-memory snapshot.

What it does: Loads an authorized dataset snapshot into DuckDB and runs one
bounded, parameterized SELECT under a row, memory, and time limit.
"""

import asyncio
import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from functools import lru_cache
from threading import Event, Lock

import duckdb
from sqlglot import exp

from execplus.domain.columnar import ColumnarTable
from execplus.domain.compute import ColumnarBudget, QueryBudget
from execplus.domain.errors import AuthorizationError, QueryDataError, UnsafeQueryError
from execplus.domain.join_paths import LEFT_VIEW_NAME, RIGHT_VIEW_NAME, JoinPath
from execplus.domain.models import QueryPlan, QueryResult, Scalar, WorkspaceScope
from execplus.domain.profiling import (
    TableData,
    is_missing_placeholder,
    parse_date,
    parse_datetime,
)
from execplus.domain.semantics import VIEW_NAME, DatasetView, SemanticColumn, quote_identifier
from execplus.infrastructure.query.validation import validated_query

_DUCKDB_TYPES = {
    "integer": "BIGINT",
    "decimal": "DECIMAL(38, 12)",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "boolean": "BOOLEAN",
    "text": "VARCHAR",
    "empty": "VARCHAR",
}


@lru_cache(maxsize=39)
def _decimal_bounds(scale: int) -> tuple[Decimal, Decimal]:
    return Decimal(f"1e{38 - scale}"), Decimal((0, (1,), -scale))


def _coerce(value: str, kind: str, scale: int = 12) -> Scalar:
    value = value.strip()
    if not value:
        return None
    try:
        if kind == "integer":
            number = Decimal(value)
            if (
                not number.is_finite()
                or number != number.to_integral_value()
                or not -(2**63) <= number < 2**63
            ):
                raise ValueError("Invalid integer")
            return int(number)
        if kind == "decimal":
            number = Decimal(value)
            limit, quantum = _decimal_bounds(scale)
            if not number.is_finite() or number.copy_abs() >= limit:
                raise ValueError("Out of supported decimal range")
            with localcontext() as context:
                context.prec = 50
                exact = number.quantize(quantum)
                if number != exact:
                    raise ValueError("Out of supported decimal precision")
            return exact
        if kind == "boolean":
            if value.lower() not in {"true", "false"}:
                raise ValueError("Invalid boolean")
            return value.lower() == "true"
        if kind == "date":
            try:
                return date.fromisoformat(value)
            except ValueError:
                parsed_date = parse_date(value)
                if parsed_date is None:
                    raise
                return parsed_date
        if kind == "datetime":
            parsed = parse_datetime(value)
            if parsed is None:
                raise ValueError("Invalid date-time")
            return parsed[0]
    except (InvalidOperation, ValueError):
        raise UnsafeQueryError(
            "Correct conflicting or out-of-range values before querying"
        ) from None
    return value


def conversion_message(name: str, row_number: int, kind: str, scale: int) -> str:
    requirement = {
        "integer": "a whole number in the signed 64-bit range",
        "decimal": f"a decimal fitting 38 digits with {scale} decimal places",
        "date": "an unambiguous date such as 2026-04-02 or 2 Apr 2026, not 02/04/2026",
        "datetime": "a valid date-time such as YYYY-MM-DD HH:MM:SS",
        "boolean": "true or false",
    }.get(kind, "the column's expected type")
    return (
        f'Column "{name}", data row {row_number}: expected {requirement}. '
        "Correct the source and upload a new version. No values were rounded or skipped."
    )


def _column(
    table: TableData, name: str, kind: str, placeholders: bool = False
) -> tuple[str, list[Scalar]]:
    index = table.headers.index(name)
    values = [
        "" if placeholders and is_missing_placeholder(row[index]) else row[index]
        for row in table.rows
    ]
    scale = 12
    if kind == "decimal":
        for row_number, value in enumerate(values, 1):
            if not value.strip():
                continue
            try:
                number = Decimal(value.strip())
                if not number.is_finite():
                    raise InvalidOperation
                _, digits, exponent = number.as_tuple()
                if not isinstance(exponent, int):
                    raise InvalidOperation
                trailing = 0
                for digit in reversed(digits):
                    if digit:
                        break
                    trailing += 1
                required = max(0, -exponent - trailing) if number else 0
                if required > 38:
                    raise InvalidOperation
                scale = max(scale, required)
            except InvalidOperation:
                raise QueryDataError(
                    f'Column "{name}", data row {row_number}: use a finite decimal '
                    "that fits within 38 digits. No values were rounded or skipped."
                ) from None
    converted: list[Scalar] = []
    for row_number, value in enumerate(values, 1):
        try:
            converted.append(_coerce(value, kind, scale))
        except UnsafeQueryError:
            raise QueryDataError(conversion_message(name, row_number, kind, scale)) from None
    sql_type = f"DECIMAL(38, {scale})" if kind == "decimal" else _DUCKDB_TYPES[kind]
    return sql_type, converted


def _kind(column: SemanticColumn) -> str:
    return "datetime" if column.has_time and column.type == "date" else column.type


def _required(table: TableData, query: exp.Select, table_name: str) -> set[str]:
    required = {
        column.name
        for column in query.find_all(exp.Column)
        if not column.table or column.table == table_name
    }
    aliases = {selection.alias for selection in query.expressions if selection.alias}
    if required - set(table.headers) - aliases:
        raise UnsafeQueryError("The query references an unavailable source column")
    return required & set(table.headers)


def _display_only(query: exp.Select) -> set[str]:
    """Columns only shown or used as trailing tie-breakers; their bad cells may stay text."""
    if query.args.get("distinct") is not None:
        return set()
    strict = query.copy()
    order = strict.args.get("order")
    trailing = [item.this for item in order.expressions[1:]] if order is not None else []
    shown = {node.name for node in [*strict.expressions, *trailing] if isinstance(node, exp.Column)}
    strict.set("expressions", [exp.Star()])
    if order is not None:
        order.set("expressions", order.expressions[:1])
    return shown - {column.name for column in strict.find_all(exp.Column)}


def _tolerant(
    table: TableData, view: DatasetView, query: exp.Select
) -> tuple[TableData, DatasetView]:
    """Shows display-only columns with unconvertible cells as their original text."""
    shown = _display_only(query)
    columns = []
    for column in view.columns:
        if column.name in shown and column.name in table.headers and column.type != "text":
            try:
                _column(table, column.name, _kind(column), column.missing_placeholders)
            except QueryDataError:
                column = replace(column, type="text", has_time=False)
        columns.append(column)
    return table, replace(view, columns=tuple(columns))


def _load_parquet(
    connection: duckdb.DuckDBPyConnection, table: ColumnarTable, table_name: str
) -> None:
    path = table.parquet_path()
    literal = "'" + path.replace("'", "''") + "'"
    connection.execute(f"SET allowed_paths = [{literal}]")
    connection.execute("SET enable_external_access = false")
    connection.execute("SET lock_configuration = true")
    connection.execute(
        f"CREATE VIEW {quote_identifier(table_name)} AS SELECT * FROM read_parquet({literal})"
    )


def _project(table: TableData, query: exp.Select, table_name: str) -> TableData:
    required = _required(table, query, table_name)
    indices = [index for index, name in enumerate(table.headers) if name in required]
    return TableData(
        tuple(table.headers[index] for index in indices),
        tuple(tuple(row[index] for index in indices) for row in table.rows),
    )


def _json_value(value: object) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError("The prepared column contains an unsupported scalar type")


class DuckDBQueryExecutor:
    def __init__(
        self,
        timeout_seconds: float,
        memory_limit_mb: int,
        insert_batch_size: int = 5000,
        *,
        budget: QueryBudget | None = None,
        columnar: ColumnarBudget | None = None,
    ) -> None:
        self.columnar = columnar or ColumnarBudget()
        self.budget = budget or QueryBudget(
            timeout_seconds=timeout_seconds, memory_limit_mb=memory_limit_mb
        )
        self._timeout_seconds = self.budget.timeout_seconds
        self._memory_limit_mb = self.budget.memory_limit_mb
        if type(insert_batch_size) is not int or insert_batch_size < 1:
            raise ValueError("The insert batch size must be a positive integer")
        self._insert_batch_size = insert_batch_size

    def _check_inputs(self, *tables: TableData) -> None:
        if sum(len(table.rows) for table in tables) > self.budget.input_rows:
            raise UnsafeQueryError("The query exceeds the input row budget")
        if sum(len(table.headers) * len(table.rows) for table in tables) > self.budget.input_cells:
            raise UnsafeQueryError("The query exceeds the input cell budget")

    async def _run(
        self,
        plan: QueryPlan,
        scope: WorkspaceScope,
        tables: set[str],
        records: int,
        load: Callable[[duckdb.DuckDBPyConnection], None],
        *,
        columnar: bool = False,
    ) -> QueryResult:
        if plan.workspace_id != scope.workspace_id or not scope.permits_dataset(plan.dataset_id):
            raise AuthorizationError("The query does not belong to the authorized workspace")
        query = validated_query(plan.sql, tables, len(plan.params))
        limits = (
            {
                "memory_limit": f"{self.columnar.memory_limit_mb}MB",
                "threads": str(self.columnar.threads),
                "max_temp_directory_size": f"{self.columnar.spill_limit_mb}MB",
                **(
                    {"temp_directory": self.columnar.spill_directory}
                    if self.columnar.spill_directory
                    else {}
                ),
            }
            if columnar
            else {
                "memory_limit": f"{self._memory_limit_mb}MB",
                "threads": str(self.budget.threads),
                "max_temp_directory_size": "0B",
                "enable_external_access": "false",
            }
        )
        timeout = self.columnar.timeout_seconds if columnar else self._timeout_seconds
        connection = duckdb.connect(
            ":memory:",
            config={
                **limits,
                "autoinstall_known_extensions": "false",
                "autoload_known_extensions": "false",
                "allow_unsigned_extensions": "false",
            },
        )
        connection.execute("SET enable_progress_bar = false")
        cancelled = Event()
        closed = Event()
        guard = Lock()
        average = query.find(exp.Avg)
        per_day = query.find(exp.Distinct) is not None
        divided = average is not None or per_day
        ordering: list[tuple[str, bool]] = []
        limit: int | None = None
        if divided:
            numerator = average if average is not None else query.find(exp.Sum)
            alias = numerator.parent if numerator is not None else None
            if not isinstance(alias, exp.Alias) or numerator is not alias.this:
                connection.close()
                raise UnsafeQueryError("Only a single direct average is supported")
            order = query.args.get("order")
            if order is not None and any(
                item.this.output_name == alias.alias for item in order.expressions
            ):
                ordering = [
                    (item.this.output_name, bool(item.args.get("desc")))
                    for item in order.expressions
                ]
                limit_node = query.args.get("limit")
                limit = int(limit_node.expression.name) if limit_node is not None else None
                query.set("order", None)
                query.set("limit", None)
            if average is not None:
                alias.set("this", exp.Sum(this=average.this.copy()))
                query.select(
                    exp.alias_(exp.Count(this=average.this.copy()), "__count"),
                    append=True,
                    copy=False,
                )

        def run() -> QueryResult:
            try:
                load(connection)
                if cancelled.is_set():
                    raise UnsafeQueryError("Query exceeded the time limit")
                matched_records = None
                if not any(expression.find(exp.AggFunc) for expression in query.expressions):
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
                fetched = cursor.fetchmany(self.budget.result_rows + 1)
                if len(fetched) > self.budget.result_rows:
                    raise UnsafeQueryError("The result exceeds the row budget")
                result_rows: list[tuple[Scalar, ...]] = []
                for row in fetched:
                    if divided:
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
                if ordering:
                    names = columns[:-1]
                    for name, descending in reversed(ordering):
                        position = names.index(name)
                        present = [row for row in result_rows if row[position] is not None]
                        present.sort(key=lambda row: row[position], reverse=descending)  # type: ignore[arg-type, return-value]
                        result_rows = present + [
                            row for row in result_rows if row[position] is None
                        ]
                    result_rows = result_rows[:limit] if limit is not None else result_rows
                return QueryResult(
                    plan.query_id,
                    columns[:-1] if divided else columns,
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
            return await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
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
        if not isinstance(table, ColumnarTable):
            self._check_inputs(table)
        elif table.row_count > self.columnar.input_rows:
            raise UnsafeQueryError("The query exceeds the input row budget")
        query = validated_query(plan.sql, {VIEW_NAME}, len(plan.params))
        if query.find(exp.Subquery) is not None and (
            len(plan.params) % 2
            or plan.params[: len(plan.params) // 2] != plan.params[len(plan.params) // 2 :]
        ):
            raise UnsafeQueryError("The extremum must bind identical inner and outer filters")
        if isinstance(table, ColumnarTable):
            columnar = table
            required = _required(columnar, query, VIEW_NAME) - _display_only(query)
            for name in required:
                if name in columnar.manifest.errors:
                    raise QueryDataError(columnar.manifest.errors[name])
            return await self._run(
                plan,
                scope,
                {VIEW_NAME},
                columnar.row_count,
                lambda connection: _load_parquet(connection, columnar, VIEW_NAME),
                columnar=True,
            )
        return await self._run(
            plan,
            scope,
            {VIEW_NAME},
            len(table.rows),
            lambda connection: self._load(
                connection, *_tolerant(_project(table, query, VIEW_NAME), view, query)
            ),
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
        self._check_inputs(left_table, right_table)
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
        _, right_values = _column(
            right_table, right_column.name, _kind(right_column), right_column.missing_placeholders
        )
        keys = [value for value in right_values if value is not None]
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
            _, left_values = _column(
                left_table, left_column.name, _kind(left_column), left_column.missing_placeholders
            )
            left_keys = [value for value in left_values if value is not None]
            if len(left_keys) != len(set(left_keys)):
                raise UnsafeQueryError(
                    "Aggregating a right-side measure requires unique left keys "
                    "to prevent duplicated or reweighted values"
                )
        if len(left_table.rows) + len(right_table.rows) > 200_000:
            raise UnsafeQueryError("The join exceeds the input row budget")

        def load(connection: duckdb.DuckDBPyConnection) -> None:
            self._load(
                connection, _project(left_table, query, LEFT_VIEW_NAME), left_view, LEFT_VIEW_NAME
            )
            self._load(
                connection,
                _project(right_table, query, RIGHT_VIEW_NAME),
                right_view,
                RIGHT_VIEW_NAME,
            )

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
        if not table.headers:
            connection.execute(
                f"CREATE TABLE {quote_identifier(table_name)} AS "
                'SELECT true AS "__row" FROM range(?)',
                [len(table.rows)],
            )
            return
        by_name = {column.name: column for column in view.columns}
        prepared = [
            _column(table, name, _kind(by_name[name]), by_name[name].missing_placeholders)
            for name in table.headers
        ]
        types = [kind for kind, _ in prepared]
        columns_sql = ", ".join(
            f"{quote_identifier(name)} {kind}"
            for name, kind in zip(table.headers, types, strict=True)
        )
        connection.execute(f"CREATE TABLE {quote_identifier(table_name)} ({columns_sql})")

        column_count = max(1, len(table.headers))
        batch_size = max(1, min(self._insert_batch_size, 20_000 // column_count))
        columns_query = ", ".join(f"unnest(?::JSON::{kind}[])" for kind in types)
        insert = f"INSERT INTO {quote_identifier(table_name)} SELECT {columns_query}"
        for start in range(0, len(table.rows), batch_size):
            columns = [
                json.dumps(
                    values[start : start + batch_size],
                    default=_json_value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                for _, values in prepared
            ]
            connection.execute(insert, columns)
