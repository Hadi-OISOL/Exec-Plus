"""Use case: Derives a queryable semantic view and validated read-only query plans.

What it does: Turns a dataset profile into an allowlisted view and a structured
metric request into planner-generated, parameter-bound, read-only SQL.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.errors import AuthorizationError, UnsafeQueryError, UnsupportedQuestionError
from execplus.domain.models import QueryPlan, Scalar, WorkspaceScope

VIEW_NAME = "dataset"
VALUE_ALIAS = "__value"

_NUMERIC_TYPES = {"integer", "decimal"}

_FORBIDDEN_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "ATTACH",
    "DETACH",
    "COPY",
    "PRAGMA",
    "CALL",
    "EXPORT",
    "IMPORT",
    "INSTALL",
    "INTO",
    "LOAD",
    "SET",
    "EXECUTE",
    "VACUUM",
    "GRANT",
    "REVOKE",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
)
_FORBIDDEN_PATTERN = re.compile(r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)


class AggregationKind(str, Enum):
    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    MIN = "min"
    MAX = "max"


class FilterOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"


_OPERATOR_SQL = {
    FilterOperator.EQ: "=",
    FilterOperator.NE: "!=",
    FilterOperator.LT: "<",
    FilterOperator.LTE: "<=",
    FilterOperator.GT: ">",
    FilterOperator.GTE: ">=",
}


@dataclass(frozen=True, slots=True)
class MetricFilter:
    column: str
    operator: FilterOperator
    value: Scalar


@dataclass(frozen=True, slots=True)
class MetricRequest:
    metric: str
    aggregation: AggregationKind
    group_by: tuple[str, ...] = ()
    filters: tuple[MetricFilter, ...] = ()


@dataclass(frozen=True, slots=True)
class RowRequest:
    filters: tuple[MetricFilter, ...] = ()
    columns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticColumn:
    name: str
    type: str
    role: str
    tags: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class DatasetView:
    columns: tuple[SemanticColumn, ...]
    metrics: frozenset[str]
    dimensions: frozenset[str]

    def column(self, name: str) -> SemanticColumn | None:
        return next((entry for entry in self.columns if entry.name == name), None)


def dataset_view(profile: dict[str, Any]) -> DatasetView:
    columns = tuple(
        SemanticColumn(
            str(entry["name"]),
            str(entry["type"]),
            str(entry["role"]),
            frozenset(str(tag) for tag in entry.get("semantic_tags", ())),
        )
        for entry in profile["columns"]
    )
    metrics = frozenset(column.name for column in columns if column.role == "metric")
    dimensions = frozenset(column.name for column in columns if column.role == "dimension")
    return DatasetView(columns, metrics, dimensions)


def recommend_metrics(view: DatasetView, limit: int = 6) -> tuple[str, ...]:
    return tuple(sorted(view.metrics))[:limit]


def recommend_trend_dimension(view: DatasetView) -> str | None:
    dates = sorted(
        name for name in view.dimensions if (column := view.column(name)) and column.type == "date"
    )
    return dates[0] if dates else None


def recommend_breakdown_dimension(view: DatasetView) -> str | None:
    candidates = sorted(
        name
        for name in view.dimensions
        if (column := view.column(name))
        and column.type != "date"
        and "identifier" not in column.tags
    )
    return candidates[0] if candidates else None


def quote_identifier(name: str) -> str:
    # Doubling an embedded quote cannot be broken out of; this is the injection
    # defense for identifiers, since bind parameters only cover values.
    return '"' + name.replace('"', '""') + '"'


def normalize_filter_value(column: SemanticColumn, value: Scalar) -> Scalar:
    if column.type in _NUMERIC_TYPES:
        if isinstance(value, bool) or not isinstance(value, int | float | Decimal):
            raise UnsupportedQuestionError(f"{column.name!r} requires a numeric filter value")
        return value
    if column.type == "date":
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                raise UnsupportedQuestionError(
                    f"{column.name!r} requires an ISO date filter value"
                ) from None
        if isinstance(value, date | datetime):
            return value
        raise UnsupportedQuestionError(f"{column.name!r} requires a date filter value")
    if column.type == "boolean":
        if not isinstance(value, bool):
            raise UnsupportedQuestionError(f"{column.name!r} requires a boolean filter value")
        return value
    return value


def build_where(
    view: DatasetView,
    filters: tuple[MetricFilter, ...],
    qualify: Callable[[str], str] = quote_identifier,
) -> tuple[list[str], list[Scalar]]:
    where_clauses: list[str] = []
    params: list[Scalar] = []
    for clause in filters:
        column = view.column(clause.column)
        if column is None:
            raise UnsupportedQuestionError(f"{clause.column!r} is not a filterable column")
        normalized = normalize_filter_value(column, clause.value)
        operator_sql = _OPERATOR_SQL[clause.operator]
        where_clauses.append(f"{qualify(clause.column)} {operator_sql} ?")
        params.append(normalized)
    return where_clauses, params


def plan_query(
    scope: WorkspaceScope,
    dataset_id: UUID,
    view: DatasetView,
    request: MetricRequest,
    *,
    row_limit: int,
) -> QueryPlan:
    if not scope.permits_dataset(dataset_id):
        raise AuthorizationError("The dataset is not authorized for this workspace scope")
    # Every "metric" role column is already numeric-typed by domain/profiling.py's
    # inference, so no separate aggregation/type compatibility check is needed here.
    if request.metric not in view.metrics:
        raise UnsupportedQuestionError(f"{request.metric!r} is not a supported metric")
    for name in request.group_by:
        if name not in view.dimensions:
            raise UnsupportedQuestionError(f"{name!r} is not a supported dimension")
    if VALUE_ALIAS in {column.name for column in view.columns}:
        raise UnsafeQueryError("The dataset defines a column that collides with a reserved alias")

    where_clauses, params = build_where(view, request.filters)

    select = [quote_identifier(name) for name in request.group_by]
    select.append(
        f"{request.aggregation.value.upper()}({quote_identifier(request.metric)})"
        f" AS {quote_identifier(VALUE_ALIAS)}"
    )
    sql = f"SELECT {', '.join(select)} FROM {quote_identifier(VIEW_NAME)}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    if request.group_by:
        sql += " GROUP BY " + ", ".join(quote_identifier(name) for name in request.group_by)
    sql += f" LIMIT {row_limit}"

    validate_read_only(sql)
    question = f"{request.aggregation.value} of {request.metric}"
    if request.group_by:
        question += f" grouped by {', '.join(request.group_by)}"
    return QueryPlan(
        query_id=uuid4(),
        workspace_id=scope.workspace_id,
        dataset_id=dataset_id,
        question=question,
        sql=sql,
        params=tuple(params),
    )


def plan_rows(
    scope: WorkspaceScope,
    dataset_id: UUID,
    view: DatasetView,
    request: RowRequest,
    *,
    row_limit: int,
) -> QueryPlan:
    if not scope.permits_dataset(dataset_id):
        raise AuthorizationError("The dataset is not authorized for this workspace scope")
    known = {column.name for column in view.columns}
    selected = request.columns or tuple(column.name for column in view.columns)
    for name in selected:
        if name not in known:
            raise UnsupportedQuestionError(f"{name!r} is not a column in this dataset")

    where_clauses, params = build_where(view, request.filters)
    select_sql = ", ".join(quote_identifier(name) for name in selected)
    sql = f"SELECT {select_sql} FROM {quote_identifier(VIEW_NAME)}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += f" LIMIT {row_limit}"

    validate_read_only(sql)
    return QueryPlan(
        query_id=uuid4(),
        workspace_id=scope.workspace_id,
        dataset_id=dataset_id,
        question="row-level drill-down",
        sql=sql,
        params=tuple(params),
    )


def validate_read_only(sql: str) -> None:
    statement = sql.strip()
    if statement.endswith(";"):
        statement = statement[:-1].strip()
    if ";" in statement:
        raise UnsafeQueryError("Only a single statement is supported")
    if statement[:6].upper() != "SELECT":
        raise UnsafeQueryError("Only SELECT statements are supported")
    if _FORBIDDEN_PATTERN.search(statement):
        raise UnsafeQueryError("The statement contains an unsupported keyword")
