"""Use case: Derives a queryable semantic view and validated read-only query plans.

What it does: Turns a dataset profile into an allowlisted view and a structured
metric request into planner-generated, parameter-bound, read-only SQL.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from execplus.domain.errors import AuthorizationError, UnsafeQueryError, UnsupportedQuestionError
from execplus.domain.models import QueryPlan, Scalar, WorkspaceScope

VIEW_NAME = "dataset"
VALUE_ALIAS = "__value"
RECORD_COUNT = "*"

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
    IEQ = "ieq"
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


TIME_PERIODS = ("day", "week", "month", "quarter", "year", "weekday", "weekend")
DAY_OF_WEEK_LABEL = "%u %A"
WEEKEND_FROM_ISO_DAY = 6
PRODUCT_SIGN = " * "


@dataclass(frozen=True, slots=True)
class MetricRequest:
    metric: str
    aggregation: AggregationKind
    group_by: tuple[str, ...] = ()
    filters: tuple[MetricFilter, ...] = ()
    order: Literal["asc", "desc"] | None = None
    limit: int | None = None
    period: Literal["day", "week", "month", "quarter", "year", "weekday", "weekend"] | None = None
    times: str | None = None

    @property
    def label(self) -> str:
        return f"{self.metric}{PRODUCT_SIGN}{self.times}" if self.times else self.metric


@dataclass(frozen=True, slots=True)
class RowOrder:
    column: str
    direction: Literal["asc", "desc"]


@dataclass(frozen=True, slots=True)
class RowExtremum:
    column: str
    direction: Literal["min", "max"]


@dataclass(frozen=True, slots=True)
class RowRequest:
    filters: tuple[MetricFilter, ...] = ()
    columns: tuple[str, ...] = ()
    extremum: RowExtremum | None = None
    order_by: RowOrder | None = None


@dataclass(frozen=True, slots=True)
class SemanticColumn:
    name: str
    type: str
    role: str
    tags: frozenset[str] = frozenset()
    has_time: bool = False


@dataclass(frozen=True, slots=True)
class DatasetView:
    columns: tuple[SemanticColumn, ...]
    metrics: frozenset[str]
    dimensions: frozenset[str]
    sources: tuple[dict[str, str], ...] = ()
    definition: dict[str, Any] | None = None

    def column(self, name: str) -> SemanticColumn | None:
        return next((entry for entry in self.columns if entry.name == name), None)


def dataset_view(profile: dict[str, Any]) -> DatasetView:
    columns = tuple(
        SemanticColumn(
            str(entry["name"]),
            str(entry["type"]),
            str(entry["role"]),
            frozenset(str(tag) for tag in entry.get("semantic_tags", ()))
            | frozenset(re.findall(r"[a-z]+", str(entry["name"]).lower()))
            & {"headcount", "salary", "tenure", "turnover", "hires"},
            entry.get("datetime") is True,
        )
        for entry in profile["columns"]
    )
    metrics = frozenset(column.name for column in columns if column.role == "metric")
    dimensions = frozenset(column.name for column in columns if column.role == "dimension")
    return DatasetView(columns, metrics, dimensions)


def recommend_metrics(view: DatasetView, limit: int = 6) -> tuple[str, ...]:
    return tuple(sorted(view.metrics))[:limit]


def supports_metric(view: DatasetView, metric: str, aggregation: AggregationKind) -> bool:
    if metric == RECORD_COUNT:
        return aggregation == AggregationKind.COUNT
    if aggregation == AggregationKind.COUNT:
        column = view.column(metric)
        return (
            column is not None
            and column.role != "ignored"
            and (column.role != "metric" or metric in view.metrics)
        )
    return metric in view.metrics


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
        if isinstance(value, bool) or not isinstance(value, int | float | Decimal | str):
            raise UnsupportedQuestionError(f"{column.name!r} requires a numeric filter value")
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise UnsupportedQuestionError("Use a valid numeric filter value") from None
        if not number.is_finite():
            raise UnsupportedQuestionError("Numeric filters must be finite")
        return number
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
        if (
            isinstance(clause.value, str)
            and clause.value != clause.column
            and view.column(clause.value)
        ):
            raise UnsupportedQuestionError(
                f"Comparing {clause.column} with another field ({clause.value}) in the same "
                "row is not supported yet. Filter by a fixed value, or ask for each field."
            )
        normalized = normalize_filter_value(column, clause.value)
        if clause.operator == FilterOperator.IEQ:
            if column.type != "text" or not isinstance(normalized, str):
                raise UnsupportedQuestionError("Case-insensitive equality requires a text column")
            where_clauses.append(f"LOWER({qualify(clause.column)}) = LOWER(?)")
            params.append(normalized)
            continue
        operator_sql = _OPERATOR_SQL[clause.operator]
        target = qualify(clause.column)
        if column.has_time and not isinstance(normalized, datetime):
            target = f"CAST({target} AS DATE)"
        where_clauses.append(f"{target} {operator_sql} ?")
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
    # Record counts do not depend on nullable measures. Field counts retain SQL's
    # non-null semantics, including visible categories and identifiers.
    if not supports_metric(view, request.metric, request.aggregation):
        raise UnsupportedQuestionError(f"{request.metric!r} is not a supported metric")
    if request.times is not None and (
        request.aggregation not in (AggregationKind.SUM, AggregationKind.AVG)
        or request.times not in view.metrics
        or request.times == request.metric
    ):
        raise UnsupportedQuestionError(
            "A row-level product needs two different measures inside a sum or average"
        )
    for name in request.group_by:
        if name not in view.dimensions:
            raise UnsupportedQuestionError(f"{name!r} is not a supported dimension")
    if VALUE_ALIAS in {column.name for column in view.columns}:
        raise UnsafeQueryError("The dataset defines a column that collides with a reserved alias")

    where_clauses, params = build_where(view, request.filters)

    select = [quote_identifier(name) for name in request.group_by]
    if request.period is not None:
        dated = [
            index
            for index, name in enumerate(request.group_by)
            if (column := view.column(name)) is not None and column.type == "date"
        ]
        if request.period not in TIME_PERIODS or len(dated) != 1:
            raise UnsupportedQuestionError("A calendar period needs exactly one grouped date field")
        name = quote_identifier(request.group_by[dated[0]])
        if request.period == "weekday":
            select[dated[0]] = f"STRFTIME({name}, ?) AS {name}"
            params.insert(0, DAY_OF_WEEK_LABEL)
        elif request.period == "weekend":
            select[dated[0]] = f"CASE WHEN ISODOW({name}) >= ? THEN ? ELSE ? END AS {name}"
            params[:0] = [WEEKEND_FROM_ISO_DAY, "weekend", "weekday"]
        else:
            select[dated[0]] = f"CAST(DATE_TRUNC(?, {name}) AS DATE) AS {name}"
            params.insert(0, request.period)
    argument = RECORD_COUNT if request.metric == RECORD_COUNT else quote_identifier(request.metric)
    if request.times is not None:
        argument += f" * {quote_identifier(request.times)}"
    select.append(
        f"{request.aggregation.value.upper()}({argument}) AS {quote_identifier(VALUE_ALIAS)}"
    )
    sql = f"SELECT {', '.join(select)} FROM {quote_identifier(VIEW_NAME)}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    if request.period is not None:
        sql += " GROUP BY ALL"
    elif request.group_by:
        sql += " GROUP BY " + ", ".join(quote_identifier(name) for name in request.group_by)
    if not 1 <= row_limit <= 100_000:
        raise UnsafeQueryError("The query row limit is outside supported bounds")
    if request.order is not None and not request.group_by:
        raise UnsupportedQuestionError("Ranking requires at least one group")
    if request.limit is not None and (request.order is None or not 1 <= request.limit <= 1000):
        raise UnsupportedQuestionError("A ranked result needs an order and 1 to 1000 groups")
    if request.group_by:
        ordering = [quote_identifier(name) for name in request.group_by]
        if request.order is not None:
            ordering.insert(
                0, f"{quote_identifier(VALUE_ALIAS)} {request.order.upper()} NULLS LAST"
            )
        sql += " ORDER BY " + ", ".join(ordering)
    sql += f" LIMIT {min(request.limit or row_limit, row_limit)}"

    validate_read_only(sql)
    question = (
        "count of records"
        if request.metric == RECORD_COUNT
        else f"{request.aggregation.value} of {request.label}"
    )
    if request.group_by:
        question += f" grouped by {', '.join(request.group_by)}"
    if request.period is not None:
        question += f" per {request.period}"
    if request.order is not None:
        question += f" ranked {request.order}"
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
    if request.extremum is not None:
        extreme = request.extremum
        if extreme.column not in view.metrics or extreme.direction not in {"min", "max"}:
            raise UnsupportedQuestionError(
                "Choose a visible numeric measure and minimum or maximum"
            )
        name = quote_identifier(extreme.column)
        inner = f"SELECT {extreme.direction.upper()}({name}) FROM {quote_identifier(VIEW_NAME)}"
        if where_clauses:
            inner += " WHERE " + " AND ".join(where_clauses)
        where_clauses.append(f"{name} = ({inner})")
        params = [*params, *params]
    select_sql = ", ".join(quote_identifier(name) for name in selected)
    sql = f"SELECT {select_sql} FROM {quote_identifier(VIEW_NAME)}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    if not 1 <= row_limit <= 100_000:
        raise UnsafeQueryError("The query row limit is outside supported bounds")
    if request.order_by is not None:
        order = request.order_by
        if request.extremum is not None or order.column not in view.metrics:
            raise UnsupportedQuestionError("Order records by one visible numeric measure")
        sql += f" ORDER BY {quote_identifier(order.column)} {order.direction.upper()} NULLS LAST"
        sql += "".join(f", {quote_identifier(name)}" for name in selected)
    sql += f" LIMIT {row_limit}"

    validate_read_only(sql)
    return QueryPlan(
        query_id=uuid4(),
        workspace_id=scope.workspace_id,
        dataset_id=dataset_id,
        question=(
            f"records with {request.extremum.direction} of {request.extremum.column} "
            "(including ties)"
            if request.extremum
            else f"records ordered by {request.order_by.column} {request.order_by.direction}"
            if request.order_by
            else "row-level drill-down"
        ),
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
