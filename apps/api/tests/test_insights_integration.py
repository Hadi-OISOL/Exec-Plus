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
    response = integration.client.get(root + "/analyst-overview?analyst=segment", headers=outsider)
    assert response.status_code in {403, 404}


def receipts(integration) -> list[str]:
    with integration.engine.connect() as connection:
        return [row.metric for row in connection.execute(select(s.query_executions))]


def test_overview_dashboard_and_per_analyst_requests_share_one_analyst_run(integration):
    owner, _, root, _ = setup(integration, CONTENT)
    combined = integration.client.get(root + "/analyst-overview", headers=owner).json()
    assert receipts(integration).count("Analyst team projection") == 1
    assert integration.client.get(root + "/auto-dashboard", headers=owner).status_code == 200
    after_dashboard = receipts(integration)
    assert after_dashboard.count("Analyst team projection") == 1
    for name in ("quality", "composition", "distribution", "segment", "relationship", "outlier"):
        response = integration.client.get(f"{root}/analyst-overview?analyst={name}", headers=owner)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["version"] == "insights-analyst-v1" and body["analyst"] == name
        expected = [card["id"] for card in combined["insights"] if card["analyst"] == name]
        assert sorted(card["id"] for card in body["insights"]) == sorted(expected)
    assert len(receipts(integration)) == len(after_dashboard)
    again = integration.client.get(root + "/analyst-overview", headers=owner).json()
    assert again["insights"] == combined["insights"]
    bad = integration.client.get(root + "/analyst-overview?analyst=astrology", headers=owner)
    assert bad.status_code == 422


DATED = (
    "day,amount,region\n"
    + "".join(
        f"2024-{month:02d}-{day:02d},{month * 10 + day},{'North' if day % 2 else 'South'}\n"
        for month in range(1, 8)
        for day in (1, 9, 17, 28)
    )
    + "2024-07-31,1,North\n"
).encode()


def test_trend_analyst_returns_cross_checked_growth_with_replayable_receipts(integration):
    owner, wid, root, _ = setup(integration, DATED)
    response = integration.client.get(root + "/analyst-overview?analyst=trend", headers=owner)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cross_check"]["dropped"] == [], body
    (card,) = body["insights"]
    evidence = {item["label"]: item["value"] for item in card["evidence"]}
    assert evidence["First month (2024-01)"] == "95"
    assert evidence["Last month (2024-07)"] == "336"
    assert evidence["Growth"] == "253.68"
    for check in card["cross_check"]["checks"]:
        assert check["agrees"]
        replay = integration.client.post(
            f"/workspaces/{wid}/queries/{check['query_id']}/replay", headers=owner
        )
        assert replay.status_code == 200, replay.text
    combined = integration.client.get(root + "/analyst-overview", headers=owner).json()
    assert all(item["analyst"] != "trend" for item in combined["insights"])
