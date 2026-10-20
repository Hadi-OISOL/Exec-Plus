"""Use case: Verifies ranked plans and answer presentation without external services.

What it does: Checks plan grammar, deterministic ranked SQL accepted by the executor
validator, chart recommendations, exact shares and grounded follow-up questions.
"""

import json
from decimal import Decimal
from uuid import uuid4

import pytest

from execplus.domain.analysis_plan import conversation_plan
from execplus.domain.answer_presentation import (
    follow_up_questions,
    recommended_chart,
    share_of_total,
)
from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.intent import canonical_question, route_response
from execplus.domain.models import CalculationLineage, QuestionKind
from execplus.domain.semantics import (
    AggregationKind,
    MetricRequest,
    RowOrder,
    RowRequest,
    plan_query,
    plan_rows,
)
from execplus.infrastructure.query.validation import validated_query
from test_intent import view
from test_semantics import scope

SOURCE = (
    {
        "dataset_id": str(uuid4()),
        "upload_id": str(uuid4()),
        "revision_id": str(uuid4()),
        "source_checksum": "a" * 64,
        "output_checksum": "b" * 64,
    },
)


def lineage(aggregation="count", grouping=("region",), metric="*", sql="SELECT 1"):
    return CalculationLineage(
        uuid4(), uuid4(), uuid4(), "farm", 4, metric, aggregation, grouping, (), sql
    )


def test_ranked_groups_and_ordered_records_pass_the_execution_grammar():
    dataset_id = uuid4()
    ranked = plan_query(
        scope(dataset_id),
        dataset_id,
        view(),
        MetricRequest("revenue", AggregationKind.AVG, ("region",), order="desc", limit=3),
        row_limit=1000,
    )
    assert ranked.sql.endswith('ORDER BY "__value" DESC NULLS LAST, "region" LIMIT 3')
    validated_query(ranked.sql, {"dataset"}, 0)
    ordered = plan_rows(
        scope(dataset_id),
        dataset_id,
        view(),
        RowRequest(columns=("region", "revenue"), order_by=RowOrder("revenue", "desc")),
        row_limit=5,
    )
    assert ordered.sql.endswith('ORDER BY "revenue" DESC NULLS LAST, "region", "revenue" LIMIT 5')
    validated_query(ordered.sql, {"dataset"}, 0)
    with pytest.raises(UnsupportedQuestionError):
        plan_query(
            scope(dataset_id),
            dataset_id,
            view(),
            MetricRequest("revenue", AggregationKind.SUM, order="desc"),
            row_limit=1000,
        )


@pytest.mark.parametrize(
    "plan",
    [
        {"metric": "revenue", "aggregation": "sum", "order": "desc"},
        {"metric": "revenue", "aggregation": "sum", "group_by": ["region"], "limit": 3},
        {"metric": "revenue", "aggregation": "sum", "group_by": ["region"], "order": "up"},
        {
            "metric": "revenue",
            "aggregation": "sum",
            "group_by": ["region"],
            "order": "desc",
            "limit": 0,
        },
    ],
)
def test_invalid_ranking_proposals_are_refused(plan):
    routed = route_response(json.dumps({"kind": "numerical", "plan": plan}), view())
    assert routed.kind == QuestionKind.UNSUPPORTED


def test_valid_proposals_keep_new_fields_and_legacy_plan_bodies_stay_unchanged():
    ranked = route_response(
        json.dumps(
            {
                "kind": "numerical",
                "plan": {
                    "metric": "revenue",
                    "aggregation": "sum",
                    "group_by": ["region"],
                    "order": "desc",
                    "limit": 2,
                },
            }
        ),
        view(),
    )
    assert ranked.request.order == "desc" and ranked.request.limit == 2
    assert conversation_plan(ranked, SOURCE).steps[0].parameters["plan"]["limit"] == 2
    legacy = route_response(
        json.dumps({"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "sum"}}),
        view(),
    )
    assert set(conversation_plan(legacy, SOURCE).steps[0].parameters["plan"]) == {
        "metric",
        "aggregation",
        "group_by",
        "filters",
    }
    rows = route_response(
        json.dumps(
            {
                "kind": "rows",
                "plan": {
                    "columns": [],
                    "filters": [],
                    "limit": 5,
                    "order_by": {"column": "region", "direction": "desc"},
                },
            }
        ),
        view(),
    )
    assert rows.kind == QuestionKind.UNSUPPORTED
    patterns = route_response(json.dumps({"kind": "patterns", "columns": ["revenue"]}), view())
    assert patterns.kind == QuestionKind.PATTERNS and patterns.guide_columns == ("revenue",)
    assert route_response(json.dumps({"kind": "patterns", "columns": ["x"]}), view()).kind == (
        QuestionKind.UNSUPPORTED
    )


def test_charts_follow_operation_value_types_and_requested_presentation():
    rows = (("North", 3), ("South", 1))
    assert (
        recommended_chart("share of records", lineage(), ("region", "__value"), rows)["type"]
        == "pie"
    )
    assert (
        recommended_chart("records by region", lineage(), ("region", "__value"), rows)["type"]
        == "bar"
    )
    assert (
        recommended_chart(
            "show it as a pie", lineage("avg", metric="revenue"), ("region", "__value"), rows
        )["type"]
        == "bar"
    )
    assert (
        recommended_chart(
            "x", lineage("rows", ()), ("a", "b"), ((Decimal("1"), 2), (Decimal("3"), 4))
        )["type"]
        == "scatter"
    )
    assert (
        recommended_chart("x", lineage("rows", ()), ("a",), ((Decimal("1"),),))["type"]
        == "histogram"
    )
    assert (
        recommended_chart("x", lineage("sum", (), "revenue"), ("__value",), ((1,),))["type"]
        == "kpi"
    )
    ranked = lineage(sql='SELECT 1 ORDER BY "__value" DESC NULLS LAST LIMIT 1')
    assert recommended_chart("share", ranked, ("region", "__value"), rows)["type"] == "bar"
    assert share_of_total(ranked, rows) == []


def test_shares_are_exact_rounded_parts_of_the_returned_total():
    shares = share_of_total(lineage(), (("Yes", 49), ("No", 51), (None, 0)))
    assert shares == [
        {"label": "Yes", "percent": "49.0"},
        {"label": "No", "percent": "51.0"},
        {"label": "", "percent": "0.0"},
    ]
    assert share_of_total(lineage("avg", metric="revenue"), (("a", 1),)) == []
    assert share_of_total(lineage(), (("a", -1), ("b", 2))) == []


def test_follow_ups_use_only_real_unused_fields():
    asked = follow_up_questions(
        "average revenue by region",
        lineage("avg", metric="revenue"),
        (("North", 1), ("South", 2)),
        view(),
    )
    assert asked == ("Which region has the highest average revenue?",)
    counted = follow_up_questions("how many records", lineage(grouping=()), ((4,),), view())
    assert counted == (
        "How many records are there by region?",
        "What is the average revenue by region?",
    )


@pytest.mark.parametrize(
    "answer",
    [
        lineage("avg", metric="revenue"),
        lineage(grouping=()),
        lineage(),
        lineage("rows", ()),
    ],
)
def test_every_follow_up_is_an_offered_question_planned_without_a_model(answer):
    rows = (("North", 1), ("South", 2))
    for question in follow_up_questions("x", answer, rows, view()):
        planned = canonical_question(question, view())
        assert planned is not None and planned.kind != QuestionKind.UNSUPPORTED, question
