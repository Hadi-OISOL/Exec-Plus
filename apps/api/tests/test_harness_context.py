"""Use case: Checks bounded planning and verified context without a provider.

What it does: Rejects hidden execution/dependencies and stale or overbroad context.
"""

import json
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from execplus.application.conversation_context import ResultContext
from execplus.domain.agent_capabilities import CAPABILITY_POLICIES, capability_catalog
from execplus.domain.analysis_plan import conversation_plan
from execplus.domain.conversation_requirements import is_contextual_reply, requires_compound_data
from execplus.domain.intent import route_response
from execplus.domain.models import CalculationLineage, QuestionKind, VerifiedMetricAnswer
from test_intent import view


def query(aggregation="sum", **changes):
    return {
        "kind": "numerical",
        "plan": {
            "metric": "revenue",
            "aggregation": aggregation,
            "group_by": [],
            "filters": [],
            **changes,
        },
    }


def test_compound_plan_keeps_every_typed_scope_and_receipt_dependency():
    first = query(filters=[{"column": "region", "operator": "ieq", "value": "West"}])
    second = query("avg", filters=[{"column": "region", "operator": "ne", "value": "West"}])
    routed = route_response(json.dumps({"kind": "compound", "steps": [first, second]}), view())
    assert routed.kind == QuestionKind.MIXED
    assert len(routed.data_steps) == 2
    plan = conversation_plan(routed, ())
    assert plan.budget.max_queries == 2
    assert [step.operation for step in plan.steps] == ["query", "query", "assemble_evidence"]
    assert plan.steps[-1].dependencies == ("data_1", "data_2")
    assert plan.steps[0].parameters["plan"]["filters"][0]["value"] == "West"
    assert plan.steps[1].parameters["plan"]["filters"][0]["operator"] == "ne"


@pytest.mark.parametrize(
    "steps",
    [
        [],
        [query()],
        [query(), query(), query()],
        [query(), {"kind": "textual", "query": "policy"}],
        [query(), {"kind": "compound", "steps": [query(), query()]}],
        [query(), query(metric="hidden")],
        [query(), {**query(), "depends_on": "data_1"}],
        [query(), query(sql="SELECT *")],
        [query(), query(filters=[{"column": "region", "operator": "sql", "value": "x"}])],
        [
            query(),
            query(filters=[{"column": "region", "operator": "eq", "value": "x", "code": "x"}]),
        ],
        [query(), query(filters=[{"column": "revenue", "operator": "gt", "value": float("inf")}])],
    ],
)
def test_compound_rejects_excess_steps_hidden_tools_fields_and_parameters(steps):
    routed = route_response(json.dumps({"kind": "compound", "steps": steps}), view())
    assert routed.kind == QuestionKind.UNSUPPORTED
    assert not routed.data_steps


def test_registry_is_immutable_and_catalog_carries_authorization_and_evidence_contract():
    with pytest.raises(TypeError):
        CAPABILITY_POLICIES["shell"] = CAPABILITY_POLICIES["query"]
    catalog = capability_catalog(patterns=False, documents=False)
    assert "retrieve_documents" not in {item["operation"] for item in catalog}
    contract = next(item["contract"] for item in catalog if item["operation"] == "query")
    assert contract["verification"] == "execution_receipt"
    assert "source_access" in contract["authorization"]
    assert contract["timeout_seconds"] == 100


@pytest.mark.parametrize(
    "question",
    [
        "What about last year?",
        "Show me only the West region",
        "Compare those two",
        "Why might that be?",
        "Explain that simply",
        "and by region?",
    ],
)
def test_ordinary_english_ellipses_are_contextual(question):
    assert is_contextual_reply(question, view())


def test_compound_requirement_does_not_mistake_date_range_for_two_calculations():
    assert requires_compound_data("total revenue and average revenue", view())
    assert not requires_compound_data("total revenue between January and March", view())


def test_result_context_is_actor_workspace_and_source_bound_and_has_verified_value():
    actor, wid, turn = uuid4(), uuid4(), uuid4()
    lineage = CalculationLineage(
        uuid4(),
        wid,
        uuid4(),
        "Sales",
        3,
        "revenue",
        "sum",
        (),
        ("region = West",),
        "",
        receipt={"sources": []},
    )
    answer = VerifiedMetricAnswer("Revenue (USD)", Decimal("350.00"), lineage)
    context = ResultContext(actor, wid, turn, (answer,))
    assert context.current_for(actor, wid, ())
    assert not context.current_for(uuid4(), wid, ())
    assert not context.current_for(actor, uuid4(), ())
    assert not context.current_for(actor, wid, ({"revision_id": "new"},))
    assert not replace(context, answers=(answer, answer, answer)).current_for(actor, wid, ())
    assert str(lineage.query_id) in context.describe()
    assert "350.00" in context.describe()
    assert "region = West" in context.describe()


@pytest.mark.parametrize(
    "question,allowed",
    [
        ("total revenue and average revenue", True),
        ("total revenue and average revenue then divide the results", False),
        ("total revenue and average revenue and their difference", False),
        ("total revenue and count records", False),
    ],
)
def test_compound_keeps_requested_operations_and_refuses_unexecuted_dependencies(question, allowed):
    from execplus.domain.conversation_requirements import compound_covers_request

    routed = route_response(
        json.dumps({"kind": "compound", "steps": [query(), query("avg")]}), view()
    )
    assert compound_covers_request(question, routed, view()) is allowed
