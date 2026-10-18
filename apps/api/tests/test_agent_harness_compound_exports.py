"""Verify compound saved answers export both governed results without re-planning."""

from uuid import UUID

from sqlalchemy import select

from execplus.infrastructure.persistence import schema as s
from test_agent_harness_runtime_evaluation import staged
from test_dataset_guidance import ask
from test_result_exports import download_text
from test_studies import add_member


def test_compound_pdf_xlsx_and_csv_replay_both_receipts_and_stay_private(integration):
    plan = {
        "kind": "compound",
        "steps": [
            {"kind": "numerical", "plan": {"metric": "sales", "aggregation": "sum"}},
            {"kind": "numerical", "plan": {"metric": "*", "aggregation": "count"}},
        ],
    }
    owner, wid, path, model = staged(integration, plan, orchestration=True)
    response = ask(integration, owner, path, "Give me sales and count the orders.")
    answer, turn_id = response["answer"], response["turn"]["id"]
    assert answer["data"]["value"] == 27
    assert answer["additional_data"][0]["value"] == 4

    query_ids = {
        answer["data"]["lineage"]["query_id"],
        answer["additional_data"][0]["lineage"]["query_id"],
    }
    with integration.engine.connect() as connection:
        receipts = connection.execute(
            select(s.query_executions.c.id, s.query_executions.c.receipt).where(
                s.query_executions.c.workspace_id == UUID(wid)
            )
        ).all()
    assert {str(row.id) for row in receipts} == query_ids
    assert all(row.receipt["outcome"] == "executed" for row in receipts)
    assert all(row.receipt["sources"] == answer["sources"] for row in receipts)

    reopened = integration.client.get(path + f"/turns/{turn_id}/answer", headers=owner)
    assert reopened.status_code == 200 and reopened.json() == answer
    for format in ("pdf", "xlsx", "csv"):
        exported = integration.client.get(
            path + f"/turns/{turn_id}/export.{format}", headers=owner
        )
        text = download_text(exported, format)
        assert "27" in text
        assert "4" in text
        if format == "pdf":
            assert "Result 1" in text and "Result 2" in text

    assert len(model.requests) == 1
    with integration.engine.connect() as connection:
        assert len(
            connection.execute(
                select(s.query_executions.c.id).where(
                    s.query_executions.c.workspace_id == UUID(wid)
                )
            ).all()
        ) == 2

    member, _ = add_member(integration, owner, wid, "admin")
    for format in ("pdf", "xlsx", "csv"):
        denied = integration.client.get(
            path + f"/turns/{turn_id}/export.{format}", headers=member
        )
        assert denied.status_code in {403, 404}
