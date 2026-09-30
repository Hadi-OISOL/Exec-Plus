"""Use case: Declares a cross-dataset join path and plans a validated two-table query.

What it does: Merges two dataset views into one combined, ambiguity-free view and
builds parameterized SQL that joins exactly the declared columns, nothing else.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from execplus.domain.errors import AuthorizationError, UnsafeQueryError, UnsupportedQuestionError
from execplus.domain.models import QueryPlan, WorkspaceScope
from execplus.domain.semantics import (
    VALUE_ALIAS,
    DatasetView,
    MetricRequest,
    build_where,
    quote_identifier,
    validate_read_only,
)

LEFT_VIEW_NAME = "dataset_left"
RIGHT_VIEW_NAME = "dataset_right"


@dataclass(frozen=True, slots=True)
class JoinPath:
    id: UUID
    workspace_id: UUID
    left_dataset_id: UUID
    left_column: str
    right_dataset_id: UUID
    right_column: str
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CombinedView:
    view: DatasetView
    left_columns: frozenset[str]
    right_columns: frozenset[str]

    def qualify(self, name: str) -> str:
        table = LEFT_VIEW_NAME if name in self.left_columns else RIGHT_VIEW_NAME
        return f"{quote_identifier(table)}.{quote_identifier(name)}"


def combine(left: DatasetView, right: DatasetView, join_path: JoinPath) -> CombinedView:
    left_names = {column.name for column in left.columns}
    right_names = {column.name for column in right.columns}
    if join_path.left_column not in left_names:
        raise UnsupportedQuestionError(
            f"{join_path.left_column!r} is not a column in the left dataset"
        )
    if join_path.right_column not in right_names:
        raise UnsupportedQuestionError(
            f"{join_path.right_column!r} is not a column in the right dataset"
        )
    # Any other shared name is ambiguous once combined: with only bare column
    # names in a request, we cannot tell which side was meant, so a join whose
    # datasets accidentally share an unrelated column name is refused rather
    # than silently guessing one side.
    overlap = (left_names & right_names) - {join_path.left_column, join_path.right_column}
    if overlap:
        raise UnsupportedQuestionError(
            f"Columns {sorted(overlap)} exist in both datasets; this join cannot disambiguate them"
        )
    columns = left.columns + right.columns
    metrics = left.metrics | right.metrics
    dimensions = left.dimensions | right.dimensions
    return CombinedView(
        DatasetView(columns, metrics, dimensions), frozenset(left_names), frozenset(right_names)
    )


def _select_columns(view: DatasetView) -> frozenset[str]:
    return frozenset(column.name for column in view.columns)


def plan_join_query(
    scope: WorkspaceScope,
    join_path: JoinPath,
    combined: CombinedView,
    request: MetricRequest,
    *,
    row_limit: int,
) -> QueryPlan:
    if not (
        scope.permits_dataset(join_path.left_dataset_id)
        and scope.permits_dataset(join_path.right_dataset_id)
    ):
        raise AuthorizationError("Both joined datasets must be authorized for this scope")
    view = combined.view
    if request.metric not in view.metrics:
        raise UnsupportedQuestionError(f"{request.metric!r} is not a supported metric")
    for name in request.group_by:
        if name not in view.dimensions:
            raise UnsupportedQuestionError(f"{name!r} is not a supported dimension")
    if VALUE_ALIAS in _select_columns(view):
        raise UnsafeQueryError("The dataset defines a column that collides with a reserved alias")

    where_clauses, params = build_where(view, request.filters, qualify=combined.qualify)

    select = [combined.qualify(name) for name in request.group_by]
    select.append(
        f"{request.aggregation.value.upper()}({combined.qualify(request.metric)})"
        f" AS {quote_identifier(VALUE_ALIAS)}"
    )
    join_condition = (
        f"{quote_identifier(LEFT_VIEW_NAME)}.{quote_identifier(join_path.left_column)} = "
        f"{quote_identifier(RIGHT_VIEW_NAME)}.{quote_identifier(join_path.right_column)}"
    )
    sql = (
        f"SELECT {', '.join(select)} FROM {quote_identifier(LEFT_VIEW_NAME)} "
        f"JOIN {quote_identifier(RIGHT_VIEW_NAME)} ON {join_condition}"
    )
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    if request.group_by:
        sql += " GROUP BY " + ", ".join(combined.qualify(name) for name in request.group_by)
    if not 1 <= row_limit <= 100_000:
        raise UnsafeQueryError("The query row limit is outside supported bounds")
    if request.group_by:
        sql += " ORDER BY " + ", ".join(combined.qualify(name) for name in request.group_by)
    sql += f" LIMIT {row_limit}"

    validate_read_only(sql)
    question = f"{request.aggregation.value} of {request.metric} across a joined dataset pair"
    return QueryPlan(
        query_id=uuid4(),
        workspace_id=scope.workspace_id,
        dataset_id=join_path.left_dataset_id,
        question=question,
        sql=sql,
        params=tuple(params),
    )
