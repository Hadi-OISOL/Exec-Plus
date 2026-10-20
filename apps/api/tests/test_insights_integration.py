"""Use case: Verifies the analyst-overview endpoint against real PostgreSQL and object storage.

What it does: Checks cross-checked cards, replayable receipts, permissions and isolation.
"""

from sqlalchemy import select

from execplus.infrastructure.persistence import schema as s
from test_dataset_access import fixture
from test_discovery import setup
from test_workspace_integration import identity

CONTENT = b"region,crop,yield\n" + b"".join(
    f"{'North' if i % 2 else 'South'},{'Rice' if i % 3 else 'Wheat'},{10 + i % 7}\n".encode()
    for i in range(40)
)


def test_analyst_overview_returns_verified_cards_with_replayable_checks(integration):
    owner, wid, root, _ = setup(integration, CONTENT)
    response = integration.client.get(root + "/analyst-overview", headers=owner)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == "insights-v1"
    assert body["cross_check"]["dropped"] == []
    assert {card["analyst"] for card in body["insights"]} >= {
        "quality",
        "composition",
        "distribution",
        "segment",
    }
    query_ids = [
        check["query_id"]
        for card in body["insights"]
        for check in card["cross_check"]["checks"]
        if check["query_id"]
    ]
    assert query_ids
    for query_id in query_ids[:3]:
        replay = integration.client.post(
            f"/workspaces/{wid}/queries/{query_id}/replay", headers=owner
        )
        assert replay.status_code == 200, replay.text
    with integration.engine.connect() as connection:
        routes = {row.model_route for row in connection.execute(select(s.query_executions))}
    assert routes == {"deterministic:insights-v1"}


def test_analyst_overview_respects_row_and_column_policies(integration):
    _, _, member, _, _, _, _, root, _, _ = fixture(integration)
    response = integration.client.get(root + "/analyst-overview", headers=member)
    assert response.status_code == 200, response.text
    assert '"cost"' not in response.text and "Lahore" not in response.text
    assert {item["id"]: item["value"] for item in response.json()["kpis"]}["rows"] == "2"


def test_analyst_overview_denies_other_workspaces(integration):
    _, _, root, _ = setup(integration, CONTENT)
    outsider, _ = identity(integration, "outsider@example.com")
    response = integration.client.get(root + "/analyst-overview", headers=outsider)
    assert response.status_code in {403, 404}
