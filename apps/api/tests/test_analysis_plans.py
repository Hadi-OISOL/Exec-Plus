"""Use case: Proves bounded conversation plans describe registered trusted operations.

What it does: Rejects invented methods, hidden execution parameters and invalid dependency graphs.
"""

from dataclasses import replace

import pytest

from execplus.domain.analysis_plan import conversation_plan
from execplus.domain.ingestion import IngestionError
from execplus.domain.intent import RoutedIntent
from execplus.domain.jobs import ResourceBudget
from execplus.domain.models import QuestionKind
from execplus.domain.semantics import AggregationKind, MetricRequest


def plan():
    return conversation_plan(
        RoutedIntent(QuestionKind.NUMERICAL, request=MetricRequest("revenue", AggregationKind.SUM)),
        (),
    )


def test_registered_plan_preserves_exact_parameters_and_only_receipt_backed_outputs():
    value = plan()
    assert value.version == "conversation-plan-v1"
    assert value.steps[0].parameters["plan"]["metric"] == "revenue"
    assert value.steps[0].verification == "execution_receipt"
    assert value.steps[-1].dependencies == ("data",)


@pytest.mark.parametrize(
    "change",
    [
        {"operation": "python"},
        {"operation": "regression"},
        {"dependencies": ("data",)},
        {"dependencies": ("later",)},
        {"output_kind": "model_assertion"},
        {"verification": "trust_model"},
        {"parameters": {"kind": "query", "plan": {}}},
        {
            "parameters": {
                "kind": "rows",
                "plan": {"columns": [], "filters": [], "limit": 100, "code": "print(1)"},
            }
        },
        {
            "parameters": {
                "kind": "numerical",
                "plan": {
                    "metric": "revenue",
                    "aggregation": "sum",
                    "group_by": [],
                    "filters": [],
                    "endpoint": "https://untrusted.test",
                },
            }
        },
        {
            "parameters": {
                "kind": "numerical",
                "plan": {
                    "metric": "revenue",
                    "aggregation": "sum",
                    "group_by": [],
                    "filters": [{"column": "city", "operator": "sql", "value": "x"}],
                },
            }
        },
    ],
)
def test_plan_rejects_unknown_operations_nested_payloads_and_cyclic_steps(change):
    value = plan()
    with pytest.raises(IngestionError, match="outside supported bounds"):
        replace(value, steps=(replace(value.steps[0], **change), value.steps[-1]))


@pytest.mark.parametrize("changes", [{"max_queries": 0}, {"max_steps": 1}])
def test_plan_cannot_exceed_declared_budget(changes):
    value = plan()
    with pytest.raises(IngestionError):
        replace(value, budget=replace(value.budget, **changes))


@pytest.mark.parametrize(
    "budget",
    [
        {"wall_seconds": 121},
        {"max_steps": 5},
        {"max_model_calls": 4},
        {"max_provider_attempts": 8},
        {"input_bytes": True},
    ],
)
def test_resource_limits_are_bounded_server_contracts(budget):
    with pytest.raises(IngestionError):
        ResourceBudget(**budget)


def test_artifact_sources_cannot_smuggle_unrestricted_locations():
    with pytest.raises(IngestionError):
        replace(plan(), sources=({"endpoint": "file:///private"},))
