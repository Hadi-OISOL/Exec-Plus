"""Use case: Proves the query execution core against real PostgreSQL and MinIO.

What it does: Exercises golden aggregate values, tenant isolation, and injection safety
through the HTTP API.
"""

from test_workspace_integration import dataset, identity, upload, workspace

REVENUE_CSV = (
    b"region,sale_date,revenue\n"
    b"North,2026-01-01,100.50\n"
    b"North,2026-01-02,49.50\n"
    b"South,2026-01-01,200.00\n"
)


def uploaded_dataset(env, headers, wid):
    did = dataset(env, headers, wid)
    response = upload(env, headers, wid, did, REVENUE_CSV, "revenue.csv", "text/csv")
    assert response.status_code == 201, response.text
    return did, response.json()["id"]


def query(env, headers, wid, did, uid, body):
    return env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/query", headers=headers, json=body
    )


def dashboard(env, headers, wid, did, uid, filters=None):
    return env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/dashboard",
        headers=headers,
        json={"filters": filters or []},
    )


def rows(env, headers, wid, did, uid, filters=None, limit=100):
    return env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/rows",
        headers=headers,
        json={"filters": filters or [], "limit": limit},
    )


def test_query_returns_golden_ungrouped_sum(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = query(
        env,
        owner,
        wid,
        did,
        uid,
        {"metric": "revenue", "aggregation": "sum", "group_by": [], "filters": []},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["columns"] == ["__value"]
    assert body["rows"] == [[350.0]]
    assert body["records_analyzed"] == 3
    assert body["lineage"]["metric"] == "revenue"
    assert body["lineage"]["aggregation"] == "sum"
    assert body["lineage"]["sql"].startswith("SELECT")


def test_query_group_by_returns_breakdown(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = query(
        env,
        owner,
        wid,
        did,
        uid,
        {"metric": "revenue", "aggregation": "sum", "group_by": ["region"], "filters": []},
    )

    assert response.status_code == 200, response.text
    rows = {(row[0], row[1]) for row in response.json()["rows"]}
    assert rows == {("North", 150.0), ("South", 200.0)}


def test_query_across_workspaces_is_not_found(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    outsider, _ = identity(env, "outsider@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    other_wid = workspace(env, outsider)

    response = query(
        env,
        outsider,
        other_wid,
        did,
        uid,
        {"metric": "revenue", "aggregation": "sum", "group_by": [], "filters": []},
    )

    assert response.status_code == 404


def test_query_unsupported_column_is_rejected(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = query(
        env,
        owner,
        wid,
        did,
        uid,
        {"metric": "not_a_column", "aggregation": "sum", "group_by": [], "filters": []},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_question"


def test_query_filter_value_is_treated_as_literal_data(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = query(
        env,
        owner,
        wid,
        did,
        uid,
        {
            "metric": "revenue",
            "aggregation": "sum",
            "group_by": [],
            "filters": [
                {"column": "region", "operator": "eq", "value": "'; DROP TABLE dataset; --"}
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["rows"] == [[None]]

    still_intact = query(
        env,
        owner,
        wid,
        did,
        uid,
        {"metric": "revenue", "aggregation": "sum", "group_by": [], "filters": []},
    )
    assert still_intact.json()["rows"] == [[350.0]]


def test_query_lineage_can_be_reconstructed_after_the_fact(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    executed = query(
        env,
        owner,
        wid,
        did,
        uid,
        {"metric": "revenue", "aggregation": "sum", "group_by": ["region"], "filters": []},
    )
    assert executed.status_code == 200, executed.text
    query_id = executed.json()["lineage"]["query_id"]

    reconstructed = env.client.get(f"/workspaces/{wid}/queries/{query_id}", headers=owner)

    assert reconstructed.status_code == 200, reconstructed.text
    lineage = reconstructed.json()
    assert lineage["query_id"] == query_id
    assert lineage["metric"] == "revenue"
    assert lineage["aggregation"] == "sum"
    assert lineage["grouping"] == ["region"]
    assert lineage["records_analyzed"] == 3
    assert lineage["sql"] == executed.json()["lineage"]["sql"]


def test_query_lineage_is_not_reconstructable_from_another_workspace(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    outsider, _ = identity(env, "outsider@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    other_wid = workspace(env, outsider)

    executed = query(
        env,
        owner,
        wid,
        did,
        uid,
        {"metric": "revenue", "aggregation": "sum", "group_by": [], "filters": []},
    )
    query_id = executed.json()["lineage"]["query_id"]

    response = env.client.get(f"/workspaces/{other_wid}/queries/{query_id}", headers=outsider)

    assert response.status_code == 404


def test_dashboard_returns_recommended_card_trend_and_breakdown(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = dashboard(env, owner, wid, did, uid)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["cards"]) == 1
    assert body["cards"][0]["metric"] == "revenue"
    assert body["cards"][0]["rows"] == [[350.0]]
    assert body["trend"]["dimension"] == "sale_date"
    assert body["breakdown"]["dimension"] == "region"
    breakdown_rows = {(row[0], row[1]) for row in body["breakdown"]["rows"]}
    assert breakdown_rows == {("North", 150.0), ("South", 200.0)}


def test_dashboard_card_is_kpi_labeled_when_a_kpi_matches(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = dashboard(env, owner, wid, did, uid)

    assert response.status_code == 200, response.text
    card = response.json()["cards"][0]
    assert card["kpi"]["id"] == "finance.total_revenue"
    assert card["kpi"]["explanation"]


def test_dashboard_applies_the_same_filter_to_every_card_trend_and_breakdown(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = dashboard(
        env,
        owner,
        wid,
        did,
        uid,
        filters=[{"column": "region", "operator": "eq", "value": "North"}],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cards"][0]["rows"] == [[150.0]]
    breakdown_rows = {(row[0], row[1]) for row in body["breakdown"]["rows"]}
    assert breakdown_rows == {("North", 150.0)}


def test_rows_drill_down_returns_matching_records(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = rows(
        env,
        owner,
        wid,
        did,
        uid,
        filters=[{"column": "region", "operator": "eq", "value": "North"}],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body["columns"]) == {"region", "sale_date", "revenue"}
    assert len(body["rows"]) == 2
    assert all(row[body["columns"].index("region")] == "North" for row in body["rows"])
    assert body["lineage"]["aggregation"] == "rows"


def test_rows_drill_down_respects_row_limit(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = rows(env, owner, wid, did, uid, limit=1)

    assert response.status_code == 200, response.text
    assert len(response.json()["rows"]) == 1


def test_rows_drill_down_across_workspaces_is_not_found(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    outsider, _ = identity(env, "outsider@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    other_wid = workspace(env, outsider)

    response = rows(env, outsider, other_wid, did, uid)

    assert response.status_code == 404


def test_kpis_endpoint_lists_only_compatible_definitions(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = env.client.get(f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/kpis", headers=owner)

    assert response.status_code == 200, response.text
    matched_ids = {item["id"] for item in response.json()}
    assert matched_ids == {"finance.total_revenue"}


def test_compute_kpi_returns_verified_answer_with_lineage(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/kpis/finance.total_revenue",
        headers=owner,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["label"] == "Total revenue"
    assert body["value"] == 350.0
    assert body["lineage"]["metric"] == "revenue"
    assert body["lineage"]["aggregation"] == "sum"


def test_compute_kpi_rejects_unsupported_kpi_for_dataset(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/kpis/hr.total_headcount",
        headers=owner,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_question"


FINANCE_CSV = b"category,revenue,cost\nServices,1000,400\nGoods,2000,800\n"


def finance_dataset(env, headers, wid):
    did = dataset(env, headers, wid)
    response = upload(env, headers, wid, did, FINANCE_CSV, "finance.csv", "text/csv")
    assert response.status_code == 201, response.text
    return did, response.json()["id"]


def test_dashboard_templates_lists_finance_overview_when_supported(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = finance_dataset(env, owner, wid)

    response = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/dashboard-templates", headers=owner
    )

    assert response.status_code == 200, response.text
    assert {template["id"] for template in response.json()} == {"finance.overview"}


def test_dashboard_with_template_id_builds_cards_from_the_template(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = finance_dataset(env, owner, wid)

    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/dashboard",
        headers=owner,
        json={"filters": [], "template_id": "finance.overview"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    cards_by_metric = {card["metric"]: card["rows"][0][0] for card in body["cards"]}
    assert cards_by_metric == {"revenue": 3000.0, "cost": 1200.0}
    assert body["breakdown"]["dimension"] == "category"


def test_dashboard_rejects_a_template_not_supported_by_the_dataset(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)

    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/dashboard",
        headers=owner,
        json={"filters": [], "template_id": "inventory.overview"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_question"
