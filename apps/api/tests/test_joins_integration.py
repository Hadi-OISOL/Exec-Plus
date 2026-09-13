"""Use case: Proves cross-dataset join paths and joined queries against real infrastructure.

What it does: Exercises golden aggregate values across two real datasets and tenant
isolation for join paths, through the HTTP API.
"""

from test_workspace_integration import dataset, identity, upload, workspace

SALES_CSV = b"sku,revenue\nA1,100\nA1,50\nB2,200\n"
PRODUCTS_CSV = b"sku,category\nA1,Widgets\nB2,Gadgets\n"


def two_datasets(env, headers, wid):
    sales_did = dataset(env, headers, wid)
    sales_response = upload(env, headers, wid, sales_did, SALES_CSV, "sales.csv", "text/csv")
    assert sales_response.status_code == 201, sales_response.text
    products_did = dataset(env, headers, wid)
    products_response = upload(
        env, headers, wid, products_did, PRODUCTS_CSV, "products.csv", "text/csv"
    )
    assert products_response.status_code == 201, products_response.text
    return (
        sales_did,
        sales_response.json()["id"],
        products_did,
        products_response.json()["id"],
    )


def create_join_path(env, headers, wid, left_did, right_did):
    return env.client.post(
        f"/workspaces/{wid}/join-paths",
        headers=headers,
        json={
            "left_dataset_id": left_did,
            "left_column": "sku",
            "right_dataset_id": right_did,
            "right_column": "sku",
        },
    )


def test_join_path_query_returns_golden_aggregate_across_two_datasets(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    sales_did, sales_uid, products_did, products_uid = two_datasets(env, owner, wid)

    created = create_join_path(env, owner, wid, sales_did, products_did)
    assert created.status_code == 201, created.text
    join_path_id = created.json()["id"]

    response = env.client.post(
        f"/workspaces/{wid}/join-paths/{join_path_id}/query",
        headers=owner,
        json={
            "left_upload_id": sales_uid,
            "right_upload_id": products_uid,
            "metric": "revenue",
            "aggregation": "sum",
            "group_by": ["category"],
            "filters": [],
        },
    )

    assert response.status_code == 200, response.text
    rows = {(row[0], row[1]) for row in response.json()["rows"]}
    assert rows == {("Widgets", 150.0), ("Gadgets", 200.0)}
    assert response.json()["lineage"]["sql"].count("JOIN") == 1


def test_list_join_paths_returns_created_path(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    sales_did, _, products_did, _ = two_datasets(env, owner, wid)
    create_join_path(env, owner, wid, sales_did, products_did)

    response = env.client.get(f"/workspaces/{wid}/join-paths", headers=owner)

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1


def test_join_path_query_across_workspaces_is_not_found(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    outsider, _ = identity(env, "outsider@example.test")
    wid = workspace(env, owner)
    sales_did, sales_uid, products_did, products_uid = two_datasets(env, owner, wid)
    created = create_join_path(env, owner, wid, sales_did, products_did)
    join_path_id = created.json()["id"]
    other_wid = workspace(env, outsider)

    response = env.client.post(
        f"/workspaces/{other_wid}/join-paths/{join_path_id}/query",
        headers=outsider,
        json={
            "left_upload_id": sales_uid,
            "right_upload_id": products_uid,
            "metric": "revenue",
            "aggregation": "sum",
            "group_by": [],
            "filters": [],
        },
    )

    assert response.status_code == 404
