"""Use case: Proves the starter-kit walkthrough through existing ExecPlus services.

What it does: Imports fictional files, confirms explicit meanings, and verifies saved real analyses.
"""

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

from execplus.domain.samples import sample_csv
from test_decision_analysis_integration import create as create_decision
from test_decision_analysis_integration import endpoint
from test_forecast_integration import create as create_forecast
from test_patterns_integration import discover, reopen, service
from test_scenarios_integration import create as create_scenario
from test_understanding import confirm, context
from test_workspace_integration import identity, workspace


def prepare_demo(env, sample_id):
    owner, actor = identity(env, f"starter-{uuid4().hex}@example.test")
    wid = workspace(env, owner)
    response = env.client.post(f"/workspaces/{wid}/samples/{sample_id}", headers=owner)
    assert response.status_code == 201, response.text
    value = response.json()
    did, uid = value["dataset_id"], value["id"]
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    assert env.client.get(root + "/content", headers=owner).content == sample_csv(sample_id)
    current = context(env, owner, root)
    assert current["state"] != "confirmed"
    definition = current["definition"]
    definition.update(
        domain="sales" if sample_id == "retail-v1" else "operations",
        grain="record",
        description=(
            "Entirely fictional: one complete day of operations in one region. "
            "Sales after the stated discount, before returns, tax and shipping."
            if sample_id == "retail-v1"
            else "Entirely fictional optional one-time actions with assumed additive benefits."
        ),
    )
    units = {
        "Orders": "orders",
        "Revenue_USD": "USD",
        "Ad_Spend_USD": "USD",
        "Visits": "visits",
        "Returns": "returns",
        "Delivery_Hours": "hours",
        "Discount_pct": "percent",
        "Support_Tickets": "tickets",
        "Cost_USD": "USD",
        "Benefit_USD": "USD",
        "Staff_Hours": "hours",
    }
    for column in definition["columns"]:
        name = column["name"]
        if name in units:
            column.update(
                role="metric",
                unit=units[name],
                currency="USD" if units[name] == "USD" else "",
                meaning=f"Fictional {name}, as declared in the starter guide.",
            )
            definition["metrics"].append(
                dict(
                    name=name,
                    column=name,
                    aggregation="avg" if name in {"Delivery_Hours", "Discount_pct"} else "sum",
                    filters=[],
                )
            )
        elif name in {"Record_ID", "Action"}:
            column.update(role="identifier")
        else:
            column.update(role="dimension")
        if name == "Date":
            column.update(date_meaning="Completed day of retail operations")
    response = confirm(env, owner, root, current)
    assert response.status_code == 201, response.text
    return owner, actor, wid, did, uid, root


def test_retail_sample_exact_queries_patterns_and_grouped_replay(integration):
    env = integration
    owner, actor, wid, did, uid, root = prepare_demo(env, "retail-v1")
    for metric, value in (("Revenue_USD", "8235156.60"), ("Orders", "141464")):
        response = env.client.post(
            root + "/query", headers=owner, json={"metric": metric, "aggregation": "sum"}
        )
        assert response.status_code == 200, response.text
        assert Decimal(response.json()["rows"][0][0]) == Decimal(value)
    ordinary = discover(env, actor, wid, did, uid)
    assert ordinary["result"]["coverage"]["filtered_rows"] == 1095
    assert ordinary["result"]["findings"]
    assert len(ordinary["request"]["metrics"]) == 8
    assert set(ordinary["request"]["categories"]) == {"Region", "Campaign", "Week_Part"}
    grouped = asyncio.run(
        service(env).discover(
            actor,
            UUID(wid),
            UUID(did),
            UUID(uid),
            ("Ad_Spend_USD", "Revenue_USD"),
            group_by="Region",
        )
    )
    result = grouped["result"]
    assert result["pooled"]["support"] == 1095
    assert result["pooled"]["statistics"]["pearson"] == "-0.923299"
    assert set(result["comparisons"]["pearson"]["reversal_groups"]) == {"North", "Central", "South"}
    expected = {"North": "0.779377", "Central": "0.840858", "South": "0.859925"}
    assert {g["label"]: g["statistics"]["pearson"] for g in result["groups"]} == expected
    assert all(group["complete_pairs"] == 365 for group in result["groups"])
    assert reopen(env, actor, wid, ordinary) == ordinary
    assert reopen(env, actor, wid, grouped) == grouped


def test_retail_sample_forecast_anomalies_and_scenario_reopen(integration):
    env = integration
    owner, _, _, _, _, root = prepare_demo(env, "retail-v1")
    response = create_forecast(
        env,
        owner,
        root,
        time_column="Date",
        metric="Orders",
        horizon=7,
        season_length=7,
        coverage_start="2025-01-01",
        coverage_end="2025-12-31",
    )
    assert response.status_code == 201, response.text
    forecast = response.json()
    result = forecast["result"]
    assert len(result["history"]) == 365
    assert sum(Decimal(item["actual"]) for item in result["history"]) == 141464
    assert len(result["predictions"]) == 7
    assert result["predictions"][0]["period"] == "2026-01-01"
    assert result["predictions"][-1]["period"] == "2026-01-07"
    path = root.split("/uploads/")[0] + "/forecasts/" + forecast["id"]
    assert env.client.get(path, headers=owner).json()["result"] == result
    response = create_decision(
        env,
        owner,
        root,
        metric="Support_Tickets",
        segment_column="Region",
        threshold="3.5",
        minimum_segment_size=8,
        materiality="0",
    )
    assert response.status_code == 201, response.text
    anomalies = response.json()
    result = anomalies["run"]["result"]
    assert result["flagged_records"] == 3
    assert result["covered_records"] == 1095
    assert {(f["segment"], f["value"]) for f in result["findings"]} == {
        ("North", "180"), ("Central", "240"), ("South", "300")
    }
    reopened = env.client.get(endpoint(root, anomalies), headers=owner)
    assert reopened.json()["run"] == anomalies["run"]
    response = create_scenario(
        env,
        owner,
        root,
        metric="Revenue_USD",
        alternatives=[
            dict(name="Assume revenue rises 10%", operation="percent_change", value="10")
        ],
    )
    assert response.status_code == 201, response.text
    scenario = response.json()
    result = scenario["run"]["result"]
    assert Decimal(result["baseline"]) == Decimal("8235156.60")
    assert Decimal(result["alternatives"][0]["result"]) == Decimal("9058672.26")
    assert Decimal(result["alternatives"][0]["difference"]) == Decimal("823515.66")
    assert env.client.get(endpoint(root, scenario), headers=owner).json()["run"] == scenario["run"]


def test_action_sample_exact_rule_selection_and_saved_replay(integration):
    env = integration
    owner, _, _, _, _, root = prepare_demo(env, "actions-v1")
    response = create_decision(
        env,
        owner,
        root,
        "allocations",
        entity_column="Action",
        cost_column="Cost_USD",
        benefit_column="Benefit_USD",
        budget="1000",
        quantum="1",
        maximum_quantity=1,
        resource_column="Staff_Hours",
        resource_capacity="10",
        prerequisites=[dict(candidate="Email campaign", requires="Tracking setup")],
        exclusions=[dict(first="Search ads", second="Social ads")],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert body["run"]["method_version"] == "selection-rules-enumeration-v1"
    assert (result["cost"], result["benefit"], result["resource_used"]) == ("1000", "160", "9")
    assert {
        row["candidate"] for row in result["allocations"] if row["quantity"] > 0
    } == {"Tracking setup", "Email campaign", "Search ads"}
    assert result["verification"]["selection_rules"] == "passed"
    assert env.client.get(endpoint(root, body), headers=owner).json()["run"] == body["run"]
