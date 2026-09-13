"""Use case: Verifies a model's proposed classification and plan are safely interpreted.

What it does: Proves malformed, ambiguous, and hallucinated model responses never
produce an executable request, while well-formed numerical proposals do.
"""

import json

from execplus.domain.intent import route_response
from execplus.domain.models import QuestionKind
from execplus.domain.semantics import AggregationKind, FilterOperator, dataset_view


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


def test_routes_valid_numerical_plan():
    raw = json.dumps(
        {
            "kind": "numerical",
            "plan": {
                "metric": "revenue",
                "aggregation": "sum",
                "group_by": ["region"],
                "filters": [{"column": "region", "operator": "eq", "value": "North"}],
            },
        }
    )
    routed = route_response(raw, view())
    assert routed.kind == QuestionKind.NUMERICAL
    assert routed.request is not None
    assert routed.request.metric == "revenue"
    assert routed.request.aggregation == AggregationKind.SUM
    assert routed.request.group_by == ("region",)
    assert routed.request.filters[0].column == "region"
    assert routed.request.filters[0].operator == FilterOperator.EQ


def test_routes_ambiguous_with_options():
    raw = json.dumps(
        {"kind": "ambiguous", "message": "Which amount?", "options": ["revenue", "cost"]}
    )
    routed = route_response(raw, view())
    assert routed.kind == QuestionKind.AMBIGUOUS
    assert routed.options == ("revenue", "cost")
    assert routed.message == "Which amount?"


def test_routes_textual():
    raw = json.dumps({"kind": "textual", "message": "That needs a written explanation."})
    routed = route_response(raw, view())
    assert routed.kind == QuestionKind.TEXTUAL


def test_routes_unsupported():
    raw = json.dumps({"kind": "unsupported", "message": "Out of scope."})
    routed = route_response(raw, view())
    assert routed.kind == QuestionKind.UNSUPPORTED
    assert routed.message == "Out of scope."


def test_rejects_hallucinated_metric_column():
    raw = json.dumps({"kind": "numerical", "plan": {"metric": "profit", "aggregation": "sum"}})
    routed = route_response(raw, view())
    assert routed.kind == QuestionKind.UNSUPPORTED


def test_rejects_hallucinated_group_by_dimension():
    raw = json.dumps(
        {
            "kind": "numerical",
            "plan": {"metric": "revenue", "aggregation": "sum", "group_by": ["made_up_column"]},
        }
    )
    routed = route_response(raw, view())
    assert routed.kind == QuestionKind.UNSUPPORTED


def test_rejects_invalid_aggregation():
    raw = json.dumps({"kind": "numerical", "plan": {"metric": "revenue", "aggregation": "median"}})
    routed = route_response(raw, view())
    assert routed.kind == QuestionKind.UNSUPPORTED


def test_rejects_invalid_filter_column():
    raw = json.dumps(
        {
            "kind": "numerical",
            "plan": {
                "metric": "revenue",
                "aggregation": "sum",
                "filters": [{"column": "made_up", "operator": "eq", "value": 1}],
            },
        }
    )
    routed = route_response(raw, view())
    assert routed.kind == QuestionKind.UNSUPPORTED


def test_rejects_malformed_json():
    routed = route_response("not json at all", view())
    assert routed.kind == QuestionKind.UNSUPPORTED


def test_rejects_non_object_json():
    routed = route_response("[1, 2, 3]", view())
    assert routed.kind == QuestionKind.UNSUPPORTED


def test_rejects_unknown_kind():
    routed = route_response(json.dumps({"kind": "opinion"}), view())
    assert routed.kind == QuestionKind.UNSUPPORTED


def test_rejects_missing_plan_for_numerical():
    routed = route_response(json.dumps({"kind": "numerical"}), view())
    assert routed.kind == QuestionKind.UNSUPPORTED
