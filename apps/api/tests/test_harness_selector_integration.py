"""Verify the staged harness skips the optional planning selector only."""

import json
from uuid import UUID

import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.services.intent_router import IntentRouterService
from test_analytics_integration import uploaded_dataset
from test_harness_context import query
from test_harness_context_integration import Planner
from test_workspace_integration import identity, workspace


class CountingSelector:
    def __init__(self):
        self.calls = 0

    async def complete(self, request):
        self.calls += 1
        return ModelResponse(
            json.dumps({"route": "numerical", "columns": ["revenue"]}), "local", "selector"
        )


@pytest.mark.asyncio
async def test_staged_harness_skips_selector_while_legacy_keeps_it_and_exact_result(integration):
    headers, actor = identity(integration, "selector-comparison@example.test")
    wid = workspace(integration, headers)
    did, uid = uploaded_dataset(integration, headers, wid)
    answers = []
    for context_enabled, expected_calls in ((True, 0), (False, 1)):
        planner = Planner(query())
        selector = CountingSelector()
        router = IntentRouterService(
            planner,
            integration.runtime.analytics,
            selector=selector,
            context_enabled=context_enabled,
        )
        answer = await router.ask(actor, UUID(wid), UUID(did), UUID(uid), "total revenue")
        assert selector.calls == expected_calls
        assert len(planner.requests) == 1
        assert str(answer.value) == "350.000000000000"
        assert answer.lineage.aggregation == "sum" and answer.lineage.metric == "revenue"
        assert answer.lineage.filters == () and answer.lineage.grouping == ()
        has_hint = "Selection hint:" in planner.requests[0].messages[-1].content
        assert has_hint is not context_enabled
        answers.append(answer)
    assert answers[0].value == answers[1].value
    assert answers[0].lineage.receipt["sources"] == answers[1].lineage.receipt["sources"]
    assert answers[0].lineage.query_id != answers[1].lineage.query_id
