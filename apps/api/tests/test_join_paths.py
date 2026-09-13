"""Use case: Verifies cross-dataset join combination and query planning.

What it does: Proves ambiguous column overlaps are refused, generated SQL always
qualifies columns by table, and unauthorized datasets are rejected before planning.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from execplus.domain.errors import AuthorizationError, UnsupportedQuestionError
from execplus.domain.join_paths import JoinPath, combine, plan_join_query
from execplus.domain.models import WorkspaceScope
from execplus.domain.semantics import (
    AggregationKind,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    dataset_view,
)


def sales_view():
    return dataset_view(
        {
            "columns": [
                {
                    "name": "sku",
                    "type": "text",
                    "role": "dimension",
                    "semantic_tags": ["identifier"],
                },
                {"name": "date", "type": "date", "role": "dimension", "semantic_tags": ["date"]},
                {
                    "name": "revenue",
                    "type": "decimal",
                    "role": "metric",
                    "semantic_tags": ["revenue"],
                },
            ]
        }
    )


def products_view():
    return dataset_view(
        {
            "columns": [
                {
                    "name": "sku",
                    "type": "text",
                    "role": "dimension",
                    "semantic_tags": ["identifier"],
                },
                {"name": "category", "type": "text", "role": "dimension", "semantic_tags": []},
            ]
        }
    )


def make_join_path(left_id, right_id):
    return JoinPath(
        id=uuid4(),
        workspace_id=uuid4(),
        left_dataset_id=left_id,
        left_column="sku",
        right_dataset_id=right_id,
        right_column="sku",
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
    )


def test_combine_merges_metrics_and_dimensions_from_both_sides():
    path = make_join_path(uuid4(), uuid4())
    combined = combine(sales_view(), products_view(), path)
    assert combined.view.metrics == {"revenue"}
    assert combined.view.dimensions == {"sku", "date", "category"}


def test_combine_rejects_ambiguous_overlapping_column_names():
    path = make_join_path(uuid4(), uuid4())
    left = sales_view()
    right = dataset_view(
        {
            "columns": [
                {"name": "sku", "type": "text", "role": "dimension"},
                {"name": "date", "type": "date", "role": "dimension"},
            ]
        }
    )
    with pytest.raises(UnsupportedQuestionError):
        combine(left, right, path)


def test_combine_rejects_join_column_missing_from_either_side():
    path = JoinPath(
        uuid4(),
        uuid4(),
        uuid4(),
        "missing_column",
        uuid4(),
        "sku",
        uuid4(),
        datetime.now(timezone.utc),
    )
    with pytest.raises(UnsupportedQuestionError):
        combine(sales_view(), products_view(), path)


def test_plan_join_query_qualifies_every_column_by_table():
    left_id, right_id = uuid4(), uuid4()
    path = JoinPath(
        uuid4(), uuid4(), left_id, "sku", right_id, "sku", uuid4(), datetime.now(timezone.utc)
    )
    combined = combine(sales_view(), products_view(), path)
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({left_id, right_id}))
    request = MetricRequest(
        metric="revenue",
        aggregation=AggregationKind.SUM,
        group_by=("category",),
        filters=(MetricFilter("date", FilterOperator.GTE, "2026-01-01"),),
    )
    plan = plan_join_query(scope, path, combined, request, row_limit=100)
    assert plan.sql == (
        'SELECT "dataset_right"."category", SUM("dataset_left"."revenue") AS "__value" '
        'FROM "dataset_left" JOIN "dataset_right" '
        'ON "dataset_left"."sku" = "dataset_right"."sku" '
        'WHERE "dataset_left"."date" >= ? '
        'GROUP BY "dataset_right"."category" LIMIT 100'
    )


def test_plan_join_query_rejects_dataset_outside_scope():
    left_id, right_id = uuid4(), uuid4()
    path = JoinPath(
        uuid4(), uuid4(), left_id, "sku", right_id, "sku", uuid4(), datetime.now(timezone.utc)
    )
    combined = combine(sales_view(), products_view(), path)
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({left_id}))
    request = MetricRequest(metric="revenue", aggregation=AggregationKind.SUM)
    with pytest.raises(AuthorizationError):
        plan_join_query(scope, path, combined, request, row_limit=100)


def test_plan_join_query_rejects_unsupported_metric():
    left_id, right_id = uuid4(), uuid4()
    path = JoinPath(
        uuid4(), uuid4(), left_id, "sku", right_id, "sku", uuid4(), datetime.now(timezone.utc)
    )
    combined = combine(sales_view(), products_view(), path)
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"member"}), frozenset({left_id, right_id}))
    request = MetricRequest(metric="made_up", aggregation=AggregationKind.SUM)
    with pytest.raises(UnsupportedQuestionError):
        plan_join_query(scope, path, combined, request, row_limit=100)
