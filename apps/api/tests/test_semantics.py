"""Use case: Verifies semantic view derivation and read-only query planning.

What it does: Proves allowlisted SQL generation, validation, and injection defenses.
"""

from datetime import date
from uuid import uuid4

import pytest

from execplus.domain.errors import AuthorizationError, UnsafeQueryError, UnsupportedQuestionError
from execplus.domain.models import WorkspaceScope
from execplus.domain.semantics import (
    AggregationKind,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    RowRequest,
    dataset_view,
    plan_query,
    plan_rows,
    quote_identifier,
    recommend_breakdown_dimension,
    recommend_metrics,
    recommend_trend_dimension,
    validate_read_only,
)


def view():
    return dataset_view(
        {
            "columns": [
                {"name": "region", "type": "text", "role": "dimension"},
                {"name": "sale_date", "type": "date", "role": "dimension"},
                {"name": "revenue", "type": "decimal", "role": "metric"},
            ]
        }
    )


def scope(dataset_id):
    return WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({dataset_id}))


def test_dataset_view_separates_metrics_and_dimensions():
    result = view()
    assert result.metrics == {"revenue"}
    assert result.dimensions == {"region", "sale_date"}
    assert result.column("revenue").type == "decimal"
    assert result.column("missing") is None


def test_plan_query_builds_parameterized_grouped_sql():
    dataset_id = uuid4()
    request = MetricRequest(
        metric="revenue",
        aggregation=AggregationKind.SUM,
        group_by=("region",),
        filters=(MetricFilter("sale_date", FilterOperator.GTE, "2026-01-01"),),
    )
    plan = plan_query(scope(dataset_id), dataset_id, view(), request, row_limit=100)
    assert plan.sql == (
        'SELECT "region", SUM("revenue") AS "__value" FROM "dataset" '
        'WHERE "sale_date" >= ? GROUP BY "region" LIMIT 100'
    )
    assert plan.params == (date(2026, 1, 1),)
    assert plan.dataset_id == dataset_id


def test_plan_query_rejects_dataset_outside_scope():
    with pytest.raises(AuthorizationError):
        plan_query(
            scope(uuid4()),
            uuid4(),
            view(),
            MetricRequest("revenue", AggregationKind.SUM),
            row_limit=10,
        )


@pytest.mark.parametrize(
    "request_",
    [
        MetricRequest("unknown", AggregationKind.SUM),
        MetricRequest("revenue", AggregationKind.SUM, group_by=("unknown",)),
        MetricRequest(
            "revenue",
            AggregationKind.SUM,
            filters=(MetricFilter("unknown", FilterOperator.EQ, 1),),
        ),
        MetricRequest(
            "revenue",
            AggregationKind.SUM,
            filters=(MetricFilter("revenue", FilterOperator.EQ, "not-a-number"),),
        ),
        MetricRequest(
            "revenue",
            AggregationKind.SUM,
            filters=(MetricFilter("sale_date", FilterOperator.EQ, "not-a-date"),),
        ),
    ],
)
def test_plan_query_rejects_unsupported_requests(request_):
    dataset_id = uuid4()
    with pytest.raises(UnsupportedQuestionError):
        plan_query(scope(dataset_id), dataset_id, view(), request_, row_limit=10)


def test_plan_query_rejects_reserved_alias_collision():
    dataset_id = uuid4()
    collided = dataset_view({"columns": [{"name": "__value", "type": "decimal", "role": "metric"}]})
    with pytest.raises(UnsafeQueryError):
        plan_query(
            scope(dataset_id),
            dataset_id,
            collided,
            MetricRequest("__value", AggregationKind.SUM),
            row_limit=10,
        )


def test_quote_identifier_escapes_embedded_quotes():
    assert quote_identifier('a"b') == '"a""b"'


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; DROP TABLE dataset",
        "DROP TABLE dataset",
        "SELECT 1 FROM dataset; SELECT 2",
        "SELECT 1 INTO other_table",
        "select * from dataset; pragma database_list",
    ],
)
def test_validate_read_only_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeQueryError):
        validate_read_only(sql)


def test_validate_read_only_accepts_plain_select():
    validate_read_only('SELECT "a" FROM "dataset" LIMIT 10')


def test_recommend_metrics_returns_sorted_metric_names():
    assert recommend_metrics(view()) == ("revenue",)


def test_recommend_trend_dimension_prefers_a_date_column():
    assert recommend_trend_dimension(view()) == "sale_date"


def test_recommend_trend_dimension_is_none_without_a_date_column():
    dateless = dataset_view(
        {
            "columns": [
                {"name": "region", "type": "text", "role": "dimension"},
                {"name": "revenue", "type": "decimal", "role": "metric"},
            ]
        }
    )
    assert recommend_trend_dimension(dateless) is None


def test_recommend_breakdown_dimension_excludes_dates_and_identifiers():
    tagged = dataset_view(
        {
            "columns": [
                {"name": "region", "type": "text", "role": "dimension", "semantic_tags": []},
                {
                    "name": "sale_date",
                    "type": "date",
                    "role": "dimension",
                    "semantic_tags": ["date"],
                },
                {
                    "name": "order_id",
                    "type": "text",
                    "role": "dimension",
                    "semantic_tags": ["identifier"],
                },
                {"name": "revenue", "type": "decimal", "role": "metric", "semantic_tags": []},
            ]
        }
    )
    assert recommend_breakdown_dimension(tagged) == "region"


def test_recommend_breakdown_dimension_is_none_without_a_candidate():
    only_dates_and_metrics = dataset_view(
        {
            "columns": [
                {"name": "sale_date", "type": "date", "role": "dimension"},
                {"name": "revenue", "type": "decimal", "role": "metric"},
            ]
        }
    )
    assert recommend_breakdown_dimension(only_dates_and_metrics) is None


def test_plan_rows_selects_all_columns_by_default():
    dataset_id = uuid4()
    plan = plan_rows(scope(dataset_id), dataset_id, view(), RowRequest(), row_limit=100)
    assert plan.sql == 'SELECT "region", "sale_date", "revenue" FROM "dataset" LIMIT 100'
    assert plan.params == ()


def test_plan_rows_applies_filters_and_bounds_rows():
    dataset_id = uuid4()
    request = RowRequest(filters=(MetricFilter("region", FilterOperator.EQ, "North"),))
    plan = plan_rows(scope(dataset_id), dataset_id, view(), request, row_limit=5)
    assert plan.sql == (
        'SELECT "region", "sale_date", "revenue" FROM "dataset" WHERE "region" = ? LIMIT 5'
    )
    assert plan.params == ("North",)


def test_plan_rows_rejects_dataset_outside_scope():
    with pytest.raises(AuthorizationError):
        plan_rows(scope(uuid4()), uuid4(), view(), RowRequest(), row_limit=10)


def test_plan_rows_rejects_unknown_column_selection():
    dataset_id = uuid4()
    with pytest.raises(UnsupportedQuestionError):
        plan_rows(
            scope(dataset_id),
            dataset_id,
            view(),
            RowRequest(columns=("not_a_column",)),
            row_limit=10,
        )
