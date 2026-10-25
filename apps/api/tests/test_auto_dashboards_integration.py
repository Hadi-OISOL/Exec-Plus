"""Use case: Verifies the dataset brief and automatic dashboards against real PostgreSQL/MinIO.

What it does: Checks different dashboards per dataset, receipt replay, versioning, editing,
sharing, row/column policies and other-workspace denial through the HTTP API.
"""

from decimal import Decimal
from uuid import uuid4

from execplus.application.services import auto_dashboards as service_module
from test_auto_dashboards import sales_csv, survey_csv
from test_dataset_access import fixture
from test_studies import add_member, prepare
from test_workspace_integration import dataset, identity, upload, workspace


def own_root(env, headers, wid, content, name):
    did = dataset(env, headers, wid)
    result = upload(env, headers, wid, did, content, name, "text/csv")
    assert result.status_code == 201, result.text
    return f"/workspaces/{wid}/datasets/{did}/uploads/{result.json()['id']}"


def test_two_datasets_get_two_different_dashboards_with_replayable_receipts(integration):
    env = integration
    service_module._CACHE.clear()
    owner, _ = identity(env, f"auto-{uuid4().hex}@example.test")
    wid = workspace(env, owner)
    sales = own_root(env, owner, wid, sales_csv().encode(), "sales.csv")
    survey = own_root(env, owner, wid, survey_csv().encode(), "survey.csv")
    first = env.client.get(sales + "/auto-dashboard", headers=owner)
    second = env.client.get(survey + "/auto-dashboard", headers=owner)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    left, right = first.json()["dashboard"], second.json()["dashboard"]
    assert left["version"] == "auto-dashboard-v1" and left["number"] == 1
    assert left["needs_confirmation"] is True
    assert {tile["id"] for tile in left["tiles"]} != {tile["id"] for tile in right["tiles"]}
    assert any(tile["id"].startswith("volume:order_date") for tile in left["tiles"])
    query_ids = [key for tile in left["tiles"] for key in tile["query_ids"]]
    assert query_ids
    for query_id in query_ids[:4]:
        replay = env.client.post(f"/workspaces/{wid}/queries/{query_id}/replay", headers=owner)
        assert replay.status_code == 200, replay.text
    again = env.client.get(sales + "/auto-dashboard", headers=owner).json()["dashboard"]
    assert again["id"] == left["id"]
    brief = env.client.get(sales + "/dataset-brief", headers=owner)
    assert brief.status_code == 200 and brief.json()["dataset"]["rows"] == "240"


def test_confirmed_meanings_unlock_measure_tiles_and_edit_share_rebuild(integration):
    env = integration
    service_module._CACHE.clear()
    content = b"city,amount,cost\n" + b"".join(
        f"{city},{index}.10,{index % 7}.5\n".encode()
        for index, city in enumerate(["Karachi", "Lahore", "Quetta"] * 10)
    )
    owner, _, wid, _, _, root = prepare(env, content)
    built = env.client.get(root + "/auto-dashboard", headers=owner)
    assert built.status_code == 200, built.text
    board = built.json()["dashboard"]
    ids = [tile["id"] for tile in board["tiles"]]
    assert "kpi:sum:amount" in ids and board["needs_confirmation"] is False
    total = next(tile for tile in board["tiles"] if tile["id"] == "kpi:sum:amount")
    assert Decimal(total["kpi"]["value"]) == Decimal("438.00")
    member, _ = add_member(env, owner, wid)
    path = f"/workspaces/{wid}/auto-dashboards/{board['id']}"
    assert env.client.get(path, headers=member).status_code in {403, 404}
    edited = env.client.patch(
        path, headers=owner, json=dict(expected_number=1, tiles=ids[:2], shared=True)
    )
    assert edited.status_code == 200, edited.text
    assert [tile["id"] for tile in edited.json()["tiles"]] == ids[:2]
    assert edited.json()["number"] == 2 and edited.json()["shared"] is True
    stale = env.client.patch(path, headers=owner, json=dict(expected_number=1, shared=False))
    assert stale.status_code == 409
    opened = env.client.get(
        f"/workspaces/{wid}/auto-dashboards/{edited.json()['id']}", headers=member
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["owned"] is False
    others = env.client.get(root + "/auto-dashboard", headers=member).json()
    assert [item["id"] for item in others["shared"]] == [edited.json()["id"]]
    forbidden = env.client.patch(
        f"/workspaces/{wid}/auto-dashboards/{edited.json()['id']}",
        headers=member,
        json=dict(expected_number=2, shared=False),
    )
    assert forbidden.status_code == 403
    rebuilt = env.client.post(root + "/auto-dashboard/rebuild", headers=owner)
    assert rebuilt.status_code == 201 and rebuilt.json()["number"] == 3
    assert rebuilt.json()["shared"] is True
    invalid = env.client.patch(
        f"/workspaces/{wid}/auto-dashboards/{rebuilt.json()['id']}",
        headers=owner,
        json=dict(expected_number=3, tiles=["made:up"]),
    )
    assert invalid.status_code == 422


def test_policies_and_other_workspaces_are_enforced(integration):
    env = integration
    service_module._CACHE.clear()
    _, _, member, _, _, _, _, root, _, _ = fixture(integration)
    response = env.client.get(root + "/auto-dashboard", headers=member)
    assert response.status_code == 200, response.text
    assert '"cost"' not in response.text and "Lahore" not in response.text
    brief = env.client.get(root + "/dataset-brief", headers=member)
    assert brief.status_code == 200 and brief.json()["dataset"]["rows"] == "2"
    assert "Lahore" not in brief.text and '"cost"' not in brief.text
    outsider, _ = identity(env, f"outsider-{uuid4().hex}@example.com")
    assert env.client.get(root + "/auto-dashboard", headers=outsider).status_code in {403, 404}
    assert env.client.get(root + "/dataset-brief", headers=outsider).status_code in {403, 404}
