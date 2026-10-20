"""Use case: Keeps record counts distinct from nonempty-field counts.

What it does: Exercises authorized count planning, exact execution and conversational
clarification with fictional crop records, including missing values and hidden fields.
"""

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from execplus.domain.errors import UnsafeQueryError, UnsupportedQuestionError
from execplus.domain.intent import (
    canonical_cohort,
    cohort_scope_needs_clarification,
    route_response,
)
from execplus.domain.models import QuestionKind, WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import AggregationKind, MetricRequest, dataset_view, plan_query
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from execplus.infrastructure.query.validation import validated_query
from test_conversational_explorer import ScriptedModel, prepare
from test_dataset_guidance import ask


def crop_table():
    return TableData(
        ("id", "Crop_Type", "Crop_Growth_Stage", "Soil_Moisture"),
        (
            ("1", "Rice", "Harvest", "20"),
            ("2", "Wheat", "Harvest", ""),
            ("", "", "Growing", "30"),
            ("4", "Wheat", "Growing", "40"),
        ),
    )


@pytest.mark.parametrize("metric", ["*", "id", "Crop_Type", "Crop_Growth_Stage"])
def test_count_domain_accepts_records_or_visible_nonnumeric_columns(metric):
    view = dataset_view(profile(crop_table()))
    routed = route_response(
        json.dumps({"kind": "numerical", "plan": {"metric": metric, "aggregation": "count"}}),
        view,
    )
    assert routed.kind == QuestionKind.NUMERICAL
    assert routed.request == MetricRequest(metric, AggregationKind.COUNT)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metric,expected", [("*", 4), ("id", 3), ("Crop_Type", 3), ("Soil_Moisture", 3)]
)
async def test_count_domain_executes_exact_record_and_nonnull_counts(metric, expected):
    table = crop_table()
    view = dataset_view(profile(table))
    did = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({did}))
    plan = plan_query(scope, did, view, MetricRequest(metric, AggregationKind.COUNT), row_limit=100)
    result = await DuckDBQueryExecutor(5, 64).execute(plan, scope, table, view)
    assert result.rows == ((expected,),)
    assert result.records_analyzed == 4


@pytest.mark.parametrize(
    "aggregation",
    [AggregationKind.SUM, AggregationKind.AVG, AggregationKind.MIN, AggregationKind.MAX],
)
def test_count_domain_never_turns_record_marker_into_a_numeric_measure(aggregation):
    did = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({did}))
    with pytest.raises(UnsupportedQuestionError):
        plan_query(
            scope,
            did,
            dataset_view(profile(crop_table())),
            MetricRequest("*", aggregation),
            row_limit=100,
        )


@pytest.mark.parametrize(
    "sql",
    [
        'SELECT * FROM "dataset" LIMIT 10',
        'SELECT SUM(*) FROM "dataset" LIMIT 10',
        'SELECT COUNT("dataset".*) FROM "dataset" LIMIT 10',
    ],
)
def test_count_domain_does_not_allow_other_wildcard_sql(sql):
    with pytest.raises(UnsafeQueryError):
        validated_query(sql, {"dataset"}, 0)


def test_count_domain_keeps_a_policy_blocked_measure_unavailable():
    # A visible measure can still be blocked when its required filter or unit
    # column is hidden. Counting that field must not bypass that existing guard.
    view = replace(dataset_view(profile(crop_table())), metrics=frozenset())
    routed = route_response(
        json.dumps(
            {
                "kind": "numerical",
                "plan": {"metric": "Soil_Moisture", "aggregation": "count"},
            }
        ),
        view,
    )
    assert routed.kind == QuestionKind.UNSUPPORTED


def crop_content():
    table = crop_table()
    return ("\n".join(",".join(row) for row in (table.headers, *table.rows)) + "\n").encode()


def count_plan(metric="*", filters=None):
    return {
        "kind": "numerical",
        "plan": {
            "metric": metric,
            "aggregation": "count",
            "filters": filters or [],
        },
    }


def test_record_count_clarification_retains_observed_choice_and_exact_filters(integration):
    env = integration
    model = ScriptedModel(
        {
            "kind": "ambiguous",
            "message": "Which Crop_Growth_Stage?",
            "options": ["Harvest", "Growing"],
        },
        count_plan(filters=[{"column": "Crop_Growth_Stage", "operator": "eq", "value": "Harvest"}]),
    )
    owner, wid, root = prepare(env, model, content=crop_content())
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}"
    first = ask(env, owner, path, "How many crops are in that growth stage?")
    assert first["turn"]["kind"] == "ambiguous"
    assert first["turn"]["clarification"]["choices"] == ["Harvest", "Growing"]
    second = ask(env, owner, path, "Harvest")
    assert second["answer"]["value"] == 2
    assert second["answer"]["label"] == "Records"
    prompt = model.requests[-1].messages[-1].content
    assert '"latest_reply": "Harvest"' in prompt
    assert '"choices": ["Harvest", "Growing"]' in prompt
    assert '"values": ["Growing", "Harvest"]' in prompt
    assert len(model.requests) == 2
    qid = second["answer"]["lineage"]["query_id"]
    replay = env.client.post(f"/workspaces/{wid}/queries/{qid}/replay", headers=owner)
    assert replay.status_code == 200, replay.text
    assert replay.json()["rows"] == [[2]]


def test_invalid_count_plan_gets_one_bounded_fresh_correction(integration):
    env = integration
    model = ScriptedModel(count_plan("record_count"), count_plan())
    owner, _, root = prepare(env, model, content=crop_content())
    result = env.client.post(
        root + "/ask", headers=owner, json={"question": "Count all crop records"}
    )
    assert result.status_code == 200, result.text
    assert result.json()["value"] == 4
    assert len(model.requests) == 2
    assert "count-plan correction" in result.json()["lineage"]["model_route"]
    assert "record_count" not in model.requests[-1].messages[-1].content
    assert "same question" in model.requests[-1].messages[-1].content


def test_exact_record_handoff_runs_without_a_model_and_keeps_the_filter(integration):
    env = integration
    model = ScriptedModel()
    owner, _, root = prepare(env, model, content=crop_content())
    response = env.client.post(
        root + "/ask",
        headers=owner,
        json={
            "question": 'Show records where "Crop_Growth_Stage" equals "Harvest"',
        },
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["rows"]) == 2
    assert all(row[2] == "Harvest" for row in response.json()["rows"])
    assert not model.requests


def test_invalid_count_correction_stops_without_executing(integration):
    env = integration
    model = ScriptedModel(count_plan("record_count"), count_plan("another_invented_field"))
    owner, _, root = prepare(env, model, content=crop_content())
    result = env.client.post(root + "/ask", headers=owner, json={"question": "Count crop records"})
    assert result.status_code == 422, result.text
    assert result.json()["error"]["code"] == "clarification_required"
    assert len(model.requests) == 2


def test_record_count_respects_scoped_rows_hidden_columns_and_receipt_revocation(integration):
    from test_dataset_access import fixture

    env = integration
    owner, _, member, _, wid, _, _, root, path, policy = fixture(env)
    result = env.client.post(
        root + "/query", headers=member, json={"metric": "*", "aggregation": "count"}
    )
    assert result.status_code == 200, result.text
    assert result.json()["rows"] == [[2]]
    assert (
        env.client.post(
            root + "/query", headers=member, json={"metric": "cost", "aggregation": "count"}
        ).status_code
        == 422
    )
    query_path = f"/workspaces/{wid}/queries/{result.json()['lineage']['query_id']}"
    assert env.client.post(query_path + "/replay", headers=member).json() == result.json()
    assert env.client.post(query_path + "/replay", headers=owner).status_code == 404
    assert (
        env.client.put(path, headers=owner, json={**policy, "expected_version": 1}).status_code
        == 200
    )
    assert env.client.post(query_path + "/replay", headers=member).status_code == 404


@pytest.mark.parametrize(
    "question",
    [
        "Compare Harvest records in East",
        "Compare Harvest records from last 7 days",
        "Compare Harvest records only maize",
        "Compare Harvest records by Crop_Type",
        "Compare Harvest records where Soil_Moisture > 20",
    ],
)
def test_cohort_scope_does_not_drop_extra_conditions(question):
    view = dataset_view(profile(crop_table()))
    intent = route_response(
        json.dumps(
            {
                "kind": "cohort_comparison",
                "target_column": "Crop_Growth_Stage",
                "target_value": "Harvest",
            }
        ),
        view,
    )
    assert cohort_scope_needs_clarification(question, intent, view)


@pytest.mark.parametrize(
    "question",
    [
        "What differs for Harvest records?",
        "Compare Soil_Moisture where stage is Harvest with other records",
        'Compare records where "Crop_Growth_Stage" equals "Harvest" with other records',
    ],
)
def test_cohort_scope_accepts_only_the_target_group(question):
    view = dataset_view(profile(crop_table()))
    intent = route_response(
        json.dumps(
            {
                "kind": "cohort_comparison",
                "target_column": "Crop_Growth_Stage",
                "target_value": "Harvest",
            }
        ),
        view,
    )
    assert not cohort_scope_needs_clarification(question, intent, view)


def test_canonical_cohort_never_discards_a_suffix():
    view = dataset_view(profile(crop_table()))
    canonical = 'Compare records where "Crop_Growth_Stage" equals "Harvest" with other records'
    assert canonical_cohort(canonical, view).target_value == "Harvest"
    assert canonical_cohort(canonical + " only maize", view) is None


def test_cohort_model_payload_cannot_smuggle_extra_filters():
    view = dataset_view(profile(crop_table()))
    routed = route_response(
        json.dumps(
            {
                "kind": "cohort_comparison",
                "target_column": "Crop_Growth_Stage",
                "target_value": "Harvest",
                "filters": [{"column": "Crop_Type", "operator": "eq", "value": "Rice"}],
            }
        ),
        view,
    )
    assert routed.kind == QuestionKind.UNSUPPORTED
