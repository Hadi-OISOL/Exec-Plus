"""Use case: Protects exact arithmetic, isolated execution, replay and summary evidence.

What it does: Reproduces audit findings through real query execution and HTTP boundaries.
"""

import asyncio
from dataclasses import replace
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from execplus.domain.errors import AuthorizationError, UnsafeQueryError
from execplus.domain.kpi_library import compatible_kpis
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import AggregationKind, MetricRequest, dataset_view, plan_query
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from test_duckdb_executor import scope
from test_workspace_integration import accept, dataset, identity, invite, upload, workspace


@pytest.mark.asyncio
async def test_decimal_sum_and_average_never_pass_through_binary_floats():
    data = TableData(("amount",), (("0.1",), ("0.2",)))
    view = dataset_view(profile(data))
    did = uuid4()
    authorized = scope(did)
    executor = DuckDBQueryExecutor(5, 64)
    for kind, expected in [
        (AggregationKind.SUM, Decimal("0.3")),
        (AggregationKind.AVG, Decimal("0.15")),
    ]:
        plan = plan_query(authorized, did, view, MetricRequest("amount", kind), row_limit=10)
        result = await executor.execute(plan, authorized, data, view)
        assert isinstance(result.rows[0][0], Decimal)
        assert result.rows == ((expected,),)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_csv('/etc/passwd') LIMIT 1",
        "SELECT current_setting('home_directory') FROM dataset LIMIT 1",
        "SELECT amount FROM dataset; DROP TABLE dataset",
        "SELECT amount FROM dataset",
        "SELECT amount FROM dataset LIMIT 100001",
        "SELECT amount FROM dataset UNION SELECT amount FROM dataset LIMIT 1",
        "SELECT amount FROM other_workspace LIMIT 1",
    ],
)
async def test_executor_rejects_forged_sql_independently_of_planner(sql):
    data = TableData(("amount",), (("0.1",),))
    view = dataset_view(profile(data))
    did = uuid4()
    authorized = scope(did)
    plan = plan_query(
        authorized, did, view, MetricRequest("amount", AggregationKind.SUM), row_limit=10
    )
    with pytest.raises(UnsafeQueryError):
        await DuckDBQueryExecutor(5, 64).execute(replace(plan, sql=sql), authorized, data, view)
    with pytest.raises(AuthorizationError):
        await DuckDBQueryExecutor(5, 64).execute(
            replace(plan, workspace_id=uuid4()), authorized, data, view
        )


def test_competing_kpi_tags_are_not_silently_chosen_and_profile_v1_is_frozen():
    data = TableData(("net_revenue", "gross_revenue", "salary"), (("1", "2", "3"),))
    original = profile(data)
    assert original["columns"][2]["semantic_tags"] == []
    view = dataset_view(original)
    assert "finance.total_revenue" not in {match.definition.id for match in compatible_kpis(view)}
    assert "hr.average_salary" in {match.definition.id for match in compatible_kpis(view)}


def test_receipt_replays_original_revision_after_cleaning_and_hides_it_from_other_tenants(
    integration,
):
    env = integration
    owner, _ = identity(env, "receipt@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    stored = upload(env, owner, wid, did, content=b"amount\n0.1\n0.2\n0.2\n").json()
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{stored['id']}"
    result = env.client.post(
        root + "/query", headers=owner, json={"metric": "amount", "aggregation": "sum"}
    )
    assert result.status_code == 200, result.text
    assert Decimal(result.json()["rows"][0][0]) == Decimal("0.5")
    lineage = result.json()["lineage"]
    receipt = lineage["receipt"]
    revision_id = receipt["sources"][0]["revision_id"]
    assert receipt["sources"][0]["source_checksum"] == stored["checksum"]
    assert (
        env.client.post(
            root + "/cleaning/apply",
            headers=owner,
            json={"expected_revision_id": revision_id, "drop_duplicates": True},
        ).status_code
        == 201
    )
    replay_path = f"/workspaces/{wid}/queries/{lineage['query_id']}/replay"
    replay = env.client.post(replay_path, headers=owner)
    assert replay.status_code == 200, replay.text
    assert replay.json()["rows"] == result.json()["rows"]
    outsider, _ = identity(env, "outsider@example.test")
    assert env.client.post(replay_path, headers=outsider).status_code == 404
    assert (
        env.client.post(
            root + "/query", headers=owner, json={"metric": "amount", "aggregation": "sum"}
        ).json()["rows"]
        != replay.json()["rows"]
    )


def test_failed_execution_is_audited_without_returning_a_number(integration, monkeypatch):
    env = integration
    owner, _ = identity(env, "failure@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    uid = upload(env, owner, wid, did).json()["id"]

    async def fail(*args):
        raise UnsafeQueryError("Query exceeded the time limit")

    monkeypatch.setattr(env.runtime.analytics.executor, "execute", fail)
    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/query",
        headers=owner,
        json={"metric": "amount", "aggregation": "sum"},
    )
    assert response.status_code == 422
    with env.engine.connect() as connection:
        receipt = connection.execute(select(s.query_executions.c.receipt)).scalar_one()
        assert receipt["outcome"] == "failed" and receipt["answer"] == {}
    assert any(
        item["action"] == "query.failed"
        for item in env.client.get(f"/workspaces/{wid}/audit-events", headers=owner).json()
    )


def test_threads_remain_owner_private_within_a_workspace(integration):
    env = integration
    owner, actor = identity(env, "thread-owner@example.test")
    member, _ = identity(env, "thread-member@example.test")
    wid = workspace(env, owner)
    invitation = invite(env, owner, wid, "thread-member@example.test").json()
    assert accept(env, member, wid, invitation["id"]).status_code == 200
    did = dataset(env, owner, wid)
    uid = upload(env, owner, wid, did).json()["id"]
    thread = asyncio.run(env.runtime.threads.start_thread(actor, UUID(wid), UUID(did), UUID(uid)))
    assert (
        env.client.get(f"/workspaces/{wid}/threads/{thread.id}", headers=member).status_code == 404
    )


def test_numeric_string_filters_preserve_precision_and_large_integer_json_is_exact(integration):
    env = integration
    owner, _ = identity(env, "precision@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    uid = upload(
        env, owner, wid, did, content=b"amount,category\n9007199254740993,A\n1,B\n"
    ).json()["id"]
    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/query",
        headers=owner,
        json={
            "metric": "amount",
            "aggregation": "sum",
            "filters": [{"column": "amount", "operator": "eq", "value": "9007199254740993"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["rows"] == [["9007199254740993"]]


def test_competing_semantics_clarify_before_calling_a_model(integration, monkeypatch):
    env = integration
    owner, _ = identity(env, "ambiguity@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    uid = upload(env, owner, wid, did, content=b"net_revenue,gross_revenue\n10,20\n").json()["id"]

    async def forbidden(*args):
        pytest.fail("Ambiguity must be resolved before a model can choose a metric")

    monkeypatch.setattr(env.runtime.intent_router.model, "complete", forbidden)
    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/ask",
        headers=owner,
        json={"question": "What is total revenue?"},
    )
    assert (
        response.status_code == 422 and response.json()["error"]["code"] == "clarification_required"
    )
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claim",
    [
        '{"summary":"revenue is one million"}',
        '{"summary":"revenue is 1e9 because demand increased"}',
        '{"evidence_ids":["invented"]}',
    ],
)
async def test_management_summary_rejects_unverified_words_scales_and_causes(claim):
    from execplus.application.contracts import ModelResponse
    from execplus.application.services.analytics import DashboardCard, DashboardSummary
    from execplus.application.services.summaries import SummaryService
    from execplus.domain.errors import UnverifiedAnswerError
    from execplus.domain.models import CalculationLineage, QueryResult

    class Model:
        async def complete(self, request):
            return ModelResponse(claim, "test", "test")

    query_id = uuid4()
    lineage = CalculationLineage(
        query_id, uuid4(), uuid4(), "Finance", 1, "revenue", "sum", (), (), "SELECT"
    )
    summary = DashboardSummary(
        (
            DashboardCard(
                "revenue", QueryResult(query_id, ("value",), ((Decimal("10"),),), 1), lineage
            ),
        ),
        None,
        None,
    )
    with pytest.raises(UnverifiedAnswerError):
        await SummaryService(Model()).compose(summary)
