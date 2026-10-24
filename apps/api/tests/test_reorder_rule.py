"""Use case: Regression tests for D27, an unstable "what should I reorder first?" answer.

What it does: Scripts the two plans the model alternated between live (lowest stock and most
days since last sale) and checks neither is used: the real thread, router and query services
apply one stated reorder rule whose ranking and counts match an independent pandas check.
"""

import io
from uuid import UUID

import pandas as pd
import pytest

from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.domain.reorder import REORDER_ROUTE, asks_what_to_reorder, reorder_fields
from execplus.domain.semantics import dataset_view
from test_harness_context_integration import Planner
from test_workspace_integration import dataset, identity, upload, workspace

INVENTORY_CSV = (
    b"sku,category,warehouse,on_hand_units,reorder_point,unit_cost,days_since_last_sale\n"
    b"A1,Grocery,North,5,20,1.50,3\n"
    b"A2,Grocery,South,50,10,2.00,200\n"
    b"A3,Toys,North,0,5,4.00,30\n"
    b"A4,Toys,South,12,12,3.00,1\n"
    b"A5,Tools,North,8,30,9.00,90\n"
    b"A6,Tools,South,100,40,1.00,400\n"
)


def rows_plan(column, direction):
    return {
        "kind": "rows",
        "plan": {
            "columns": [],
            "filters": [],
            "order_by": {"column": column, "direction": direction},
        },
    }


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What should I reorder first?", True),
        ("Which items need restocking?", True),
        ("How many SKUs are below their reorder point?", True),
        ("What is running out?", True),
        ("Total reorder point by warehouse", False),
        ("What is the average unit cost?", False),
    ],
)
def test_reorder_wording(question, expected):
    assert asks_what_to_reorder(question) is expected


def test_only_inventory_like_files_get_the_rule():
    sales = dataset_view(
        {
            "columns": [
                {"name": "product", "type": "text", "role": "dimension"},
                {"name": "quantity", "type": "integer", "role": "metric"},
            ]
        }
    )
    assert reorder_fields(sales) is None


def pandas_reorder_first():
    frame = pd.read_csv(io.BytesIO(INVENTORY_CSV))
    frame["short"] = frame["reorder_point"] - frame["on_hand_units"]
    below = frame[frame["on_hand_units"] < frame["reorder_point"]]
    at = int((frame["on_hand_units"] == frame["reorder_point"]).sum())
    return list(below.sort_values("short", ascending=False)["sku"]), len(below), at


@pytest.mark.asyncio
async def test_reorder_question_uses_one_stated_rule_regardless_of_model_plan(integration):
    headers, actor = identity(integration, "inventory@example.test")
    wid = workspace(integration, headers)
    did = dataset(integration, headers, wid)
    response = upload(integration, headers, wid, did, INVENTORY_CSV, "inventory.csv", "text/csv")
    assert response.status_code == 201, response.text
    model = Planner(rows_plan("days_since_last_sale", "desc"), rows_plan("on_hand_units", "asc"))
    router = IntentRouterService(model, integration.runtime.analytics, context_enabled=True)
    threads = ThreadService(integration.runtime.threads.uow, router)
    thread = await threads.start_thread(actor, UUID(wid), UUID(did), UUID(response.json()["id"]))
    order, below, at = pandas_reorder_first()
    for _ in range(2):
        answer, turn = await threads.ask(
            actor, UUID(wid), thread.id, "What should I reorder first?"
        )
        assert turn.status == "complete"
        assert turn.model_route == REORDER_ROUTE
        message = answer.message
        assert message.startswith(
            "Rule used: items whose on_hand_units is below their reorder_point"
        )
        assert f"{below} items are below their reorder point; {at} are exactly at it." in message
        positions = [message.index(f"{sku}, ") for sku in order]
        assert positions == sorted(positions)
        assert "1. A5, Tools, North — on_hand_units 8, reorder_point 30, short by 22" in message
        assert "A2," not in message and "A6," not in message
    assert model.requests == []


def test_without_a_reorder_point_the_rule_is_lowest_stock_and_says_so():
    from decimal import Decimal

    from execplus.domain.reorder import ReorderFields, reorder_message

    fields = ReorderFields("units_in_stock", None, ("item",))
    rows = (("Pens", Decimal("2")), ("Ink", 0), ("Paper", None))
    message = reorder_message(fields, rows, 3, truncated=False)
    assert message.startswith("Rule used: lowest units_in_stock first.")
    assert "1. Ink — units_in_stock 0\n2. Pens — units_in_stock 2" in message
    assert "Paper" not in message
