"""Use case: Regression tests for D6, a category-value follow-up that kept failing live.

What it does: Replays both plausible model plans for "and which region sells the most
laptops?" through a scripted planner and the real thread, router and query services,
checks the answer against pandas, and checks that a refused follow-up offers clickable
complete questions that run without a model.
"""

import io
from uuid import UUID

import pandas as pd
import pytest

from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from test_harness_context_integration import Planner
from test_workspace_integration import dataset, identity, upload, workspace

SALES_CSV = (
    b"region,product,quantity,revenue\n"
    b"West,Laptop,3,3000.00\n"
    b"West,Phone,10,2000.00\n"
    b"East,Laptop,5,2500.00\n"
    b"East,Phone,1,9000.00\n"
)
LAPTOP = [{"column": "product", "operator": "ieq", "value": "Laptop"}]


def plan(metric, group_by=("region",), filters=(), order="desc"):
    return {
        "kind": "numerical",
        "plan": {
            "metric": metric,
            "aggregation": "sum",
            "group_by": list(group_by),
            "filters": list(filters),
            **({"order": order} if order else {}),
        },
    }


def setup(env, *plans):
    headers, actor = identity(env, "followups@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    response = upload(env, headers, wid, did, SALES_CSV, "sales.csv", "text/csv")
    assert response.status_code == 201, response.text
    model = Planner(*plans)
    router = IntentRouterService(
        model, env.runtime.analytics, context_enabled=True, orchestration_enabled=True
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    return actor, UUID(wid), UUID(did), UUID(response.json()["id"]), model, threads


def pandas_leader():
    frame = pd.read_csv(io.BytesIO(SALES_CSV))
    totals = frame[frame["product"] == "Laptop"].groupby("region")["revenue"].sum()
    return totals.idxmax(), totals.max()


@pytest.mark.asyncio
@pytest.mark.parametrize("measure", ["quantity", "revenue"])
async def test_laptop_followup_keeps_the_previous_measure_for_both_model_plans(
    integration, measure
):
    actor, wid, did, uid, _, threads = setup(
        integration, plan("revenue"), plan(measure, filters=LAPTOP)
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    first, _ = await threads.ask(actor, wid, thread.id, "Which region has the highest revenue?")
    assert first[0].rows[0][0] == "East"
    answer, turn = await threads.ask(
        actor, wid, thread.id, "and which region sells the most laptops?"
    )
    assert turn.status == "complete", turn.message
    region, total = pandas_leader()
    assert answer[1].metric == "revenue"
    assert answer[0].rows[0][0] == region == "West"
    assert float(answer[0].rows[0][1]) == total


@pytest.mark.asyncio
async def test_named_measure_change_is_still_honoured(integration):
    actor, wid, did, uid, _, threads = setup(
        integration, plan("revenue"), plan("quantity", filters=LAPTOP)
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    await threads.ask(actor, wid, thread.id, "Which region has the highest revenue?")
    answer, turn = await threads.ask(
        actor, wid, thread.id, "and which region has the most laptop quantity?"
    )
    assert turn.status == "complete"
    assert answer[1].metric == "quantity"
    assert answer[0].rows[0][0] == "East"


@pytest.mark.asyncio
async def test_refused_followup_offers_clickable_complete_questions(integration):
    west = [{"column": "region", "operator": "eq", "value": "West"}]
    actor, wid, did, uid, model, threads = setup(
        integration,
        plan("revenue", group_by=(), filters=west, order=None),
        plan("revenue", group_by=("product",)),
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    await threads.ask(actor, wid, thread.id, "total revenue for West")
    answer, turn = await threads.ask(actor, wid, thread.id, "and by product?")
    assert answer is None and turn.kind == "ambiguous"
    choices = turn.evidence["clarification"]["choices"]
    assert choices[0] == "Which product has the highest total revenue?"
    answer, turn = await threads.ask(actor, wid, thread.id, choices[0])
    assert turn.model_route == "deterministic:offered-question-v1"
    assert answer[0].rows[0][0] == "Phone"
    assert len(model.requests) == 2


def test_offered_question_with_a_category_value_plans_an_exact_filter():
    from execplus.domain.intent import canonical_question
    from test_live_dataset_defects import sales_view

    question = "Which region has the highest total revenue_usd where product equals Laptop?"
    routed = canonical_question(question, sales_view())
    assert routed is not None and routed.request is not None
    assert routed.request.group_by == ("region",)
    assert [(f.column, f.operator.value, f.value) for f in routed.request.filters] == [
        ("product", "ieq", "Laptop")
    ]
