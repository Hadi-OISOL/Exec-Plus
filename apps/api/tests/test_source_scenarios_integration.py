"""Use case: Verifies source-derived scenarios against retained files and private receipts.

What it does: Exercises real replay, successors, governance, exports and concurrent
policy revocation without model arithmetic or source mutation.
"""

from copy import deepcopy
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select, update

from execplus.application.services import decision_analysis as service_module
from execplus.domain.source_scenarios import METHOD
from execplus.infrastructure.persistence import schema as s
from test_analysis_access_policies import grant, revise
from test_result_exports import download_text
from test_source_scenarios import request
from test_studies import add_member, prepare
from test_understanding import confirm, context

CONTENT = b"region,quantity,sales,cost,fixed,secret\nNorth,2,10,6,3,500\nSouth,3,20,8,4,900\n"


def fixture(env, content=CONTENT):
    headers, actor, wid, did, uid, root = prepare(env, content)
    current = context(env, headers, root)
    current["definition"]["grain"] = "record"
    for column in current["definition"]["columns"]:
        if column["name"] == "quantity":
            column.update(unit="items", currency="")
        elif column["name"] in {"sales", "cost", "fixed"}:
            column.update(unit="", currency="USD")
    response = confirm(env, headers, root, current)
    assert response.status_code == 201, response.text
    return headers, actor, wid, did, uid, root


def create(env, headers, root, **changes):
    options = env.client.get(root + "/decision-analysis/options", headers=headers)
    assert options.status_code == 200, options.text
    current = options.json()
    return env.client.post(
        root + "/decision-analysis/source-scenarios",
        headers=headers,
        json={
            **request(),
            "name": "Declared sales and costs",
            "revision_id": current["revision_id"],
            "understanding_id": current["understanding_id"],
            **changes,
        },
    )


def endpoint(root, body):
    return root.split("/uploads/")[0] + "/decision-analysis/" + body["run"]["id"]


@pytest.mark.parametrize("basis", ["per_unit", "row_totals"])
def test_source_model_replays_exact_projection_and_immutable_results(integration, basis):
    env = integration
    content = (
        CONTENT
        if basis == "per_unit"
        else CONTENT.replace(b",2,10,6,3,", b",2,20,12,3,").replace(b",3,20,8,4,", b",3,60,24,4,")
    )
    headers, _, wid, _, _, root = fixture(env, content)
    response = create(env, headers, root, basis=basis)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run"]["method_version"] == METHOD
    assert Decimal(body["run"]["result"]["baseline"]["revenue"]) == 80
    assert Decimal(body["run"]["result"]["alternatives"][0]["result"]["remaining"]) == Decimal(
        "37.6"
    )
    assert "coverage_query_ids" not in body["run"]["evidence"]
    assert env.client.get(endpoint(root, body), headers=headers).json()["run"] == body["run"]
    query = f"/workspaces/{wid}/queries/{body['run']['evidence']['query_id']}"
    receipt = env.client.get(query, headers=headers)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["model_route"] == "deterministic:" + METHOD
    replay = env.client.post(query + "/replay", headers=headers)
    assert replay.status_code == 200, replay.text
    assert len(replay.json()["rows"]) == 2
    summary = env.client.get(
        root.split("/uploads/")[0] + "/decision-analysis", headers=headers
    ).json()
    assert summary[0]["method_version"] == METHOD


def test_source_scenario_receipts_runs_successors_and_reviews_are_private(integration):
    env = integration
    headers, _, wid, _, _, root = fixture(env)
    response = create(env, headers, root)
    assert response.status_code == 201, response.text
    body = response.json()
    member, _ = add_member(env, headers, wid, "admin")
    assert env.client.get(endpoint(root, body), headers=member).status_code == 404
    assert create(env, member, root, parent_run_id=body["run"]["id"]).status_code == 404
    query = f"/workspaces/{wid}/queries/{body['run']['evidence']['query_id']}"
    assert env.client.get(query, headers=member).status_code == 404
    assert env.client.post(query + "/replay", headers=member).status_code == 404
    review = env.client.post(
        endpoint(root, body) + "/reviews",
        headers=headers,
        json=dict(
            target="decision", status="approved", note="This is only a what-if", expected_version=0
        ),
    )
    assert review.status_code == 422 and review.json()["error"]["code"] == "scenario_not_decision"


def test_source_successor_preserves_original_and_refuses_changed_basis_or_meaning(integration):
    env = integration
    headers, _, _, _, _, root = fixture(env)
    body = create(env, headers, root).json()
    successor = create(env, headers, root, parent_run_id=body["run"]["id"], sensitivity=None)
    assert successor.status_code == 201, successor.text
    assert successor.json()["run"]["result"]["parent_run_id"] == body["run"]["id"]
    assert env.client.get(endpoint(root, body), headers=headers).json()["run"] == body["run"]
    invalid = create(env, headers, root, parent_run_id=body["run"]["id"], basis="row_totals")
    assert invalid.status_code == 422, invalid.text
    current = context(env, headers, root)
    next(item for item in current["definition"]["columns"] if item["name"] == "quantity")[
        "meaning"
    ] = "A different declared quantity"
    assert confirm(env, headers, root, current).status_code == 201
    reopened = env.client.get(endpoint(root, body), headers=headers)
    assert reopened.status_code == 200 and reopened.json()["current"] is False
    assert reopened.json()["run"] == body["run"]
    assert create(env, headers, root, parent_run_id=body["run"]["id"]).status_code == 422


@pytest.mark.parametrize("field", ["request", "result", "evidence", "method_version"])
def test_source_scenario_saved_contract_tampering_is_refused(integration, field):
    env = integration
    headers, _, _, _, _, root = fixture(env)
    body = create(env, headers, root).json()
    value = deepcopy(body["run"][field])
    if field == "method_version":
        value = "aggregate-scenarios-v1"
    elif field == "evidence":
        value["units"]["sales"] = "EUR"
    else:
        value["tampered"] = True
    with env.engine.begin() as connection:
        connection.execute(
            update(s.analysis_runs)
            .where(s.analysis_runs.c.id == UUID(body["run"]["id"]))
            .values(**{field: value})
        )
    assert env.client.get(endpoint(root, body), headers=headers).status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        dict(row_basis_confirmed=False),
        dict(assumptions_confirmed=1),
        dict(model="python"),
        dict(price="10"),
        dict(sensitivity=dict(driver="price", percent_changes=[0, 10])),
        dict(
            alternatives=[
                dict(
                    name="Auto demand",
                    price="10",
                    quantity="learn",
                    variable_cost="0",
                    fixed_cost="0",
                )
            ]
        ),
    ],
)
def test_source_http_contract_has_no_inferred_driver_or_extra_expression(integration, changes):
    env = integration
    headers, _, _, _, _, root = fixture(env)
    response = create(env, headers, root, **changes)
    assert response.status_code == 422, response.text
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=headers).json()
        == []
    )


def test_source_model_requires_one_shared_governed_population(integration):
    env = integration
    headers, _, _, _, _, root = fixture(env)
    current = context(env, headers, root)
    current["definition"]["metrics"] = [
        dict(
            name="North sales",
            column="sales",
            aggregation="sum",
            filters=[dict(column="region", operator="eq", value="North")],
        )
    ]
    assert confirm(env, headers, root, current).status_code == 201
    response = create(env, headers, root)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "scenario_population_mismatch"
    good = create(env, headers, root, filters=[dict(column="region", operator="eq", value="North")])
    assert good.status_code == 201, good.text
    assert good.json()["run"]["result"]["sample_count"] == 1
    assert Decimal(good.json()["run"]["result"]["baseline"]["revenue"]) == 20


@pytest.mark.parametrize(
    "content",
    [
        CONTENT.replace(b",3,20,8,4,", b",3,,8,4,"),
        CONTENT.replace(b",3,20,8,4,", b",3,20,,4,"),
        b"region,quantity,sales,cost,fixed,secret\n" + b"North,1,1,1,1,1\n" * 10001,
    ],
)
def test_source_complete_population_is_never_silently_sampled_or_imputed(integration, content):
    env = integration
    headers, _, _, _, _, root = fixture(env, content)
    response = create(env, headers, root)
    assert response.status_code == 422, response.text
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=headers).json()
        == []
    )


def restricted_fixture(env):
    owner, owner_actor, wid, did, _, root = fixture(env)
    member, actor = add_member(env, owner, wid)
    path, body = grant(
        env,
        owner,
        owner_actor,
        wid,
        did,
        actor,
        ["quantity", "sales", "cost", "fixed"],
        dict(column="region", operator="eq", value="North"),
    )
    return owner, member, actor, root, path, body


def test_source_model_uses_only_allowed_rows_columns_then_hides_revoked_saved_scope(integration):
    env = integration
    owner, member, _, root, policy, rules = restricted_fixture(env)
    response = create(env, member, root)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run"]["result"]["sample_count"] == 1
    assert Decimal(body["run"]["result"]["baseline"]["revenue"]) == 20
    assert {item["name"] for item in body["run"]["evidence"]["definition"]["columns"]} == {
        "quantity",
        "sales",
        "cost",
        "fixed",
    }
    assert body["run"]["evidence"]["sources"][0]["fingerprints"] == "withheld_for_restricted_access"
    assert env.client.get(endpoint(root, body), headers=member).json()["run"] == body["run"]
    assert env.client.get(endpoint(root, body), headers=owner).status_code == 404
    rules["grants"][1]["conditions"][0]["value"] = "South"
    revise(env, owner, policy, rules)
    assert env.client.get(endpoint(root, body), headers=member).status_code == 404
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=member).json()
        == []
    )


def test_source_policy_change_during_math_prevents_result_publication(integration, monkeypatch):
    env = integration
    owner, member, _, root, policy, rules = restricted_fixture(env)
    original = service_module.calculate

    def changed(raw, value):
        result = original(raw, value)
        rules["grants"][1]["conditions"][0]["value"] = "South"
        revise(env, owner, policy, rules)
        return result

    monkeypatch.setattr(service_module, "calculate", changed)
    response = create(env, member, root)
    assert response.status_code in {404, 422}, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []


@pytest.mark.parametrize("format", ["pdf", "xlsx", "csv", "png"])
def test_source_scenario_exports_exact_results_sensitivity_and_private_evidence(
    integration, format
):
    env = integration
    owner, member, _, root, policy, rules = restricted_fixture(env)
    response = create(env, member, root)
    assert response.status_code == 201, response.text
    body = response.json()
    path = (
        root.split("/uploads/")[0] + f"/analyses/{body['run']['id']}/export.{format}?kind=scenario"
    )
    downloaded = env.client.get(path, headers=member)
    exported = download_text(downloaded, format)
    assert body["run"]["result"]["alternatives"][0]["result"]["remaining"] in exported
    assert "withheld_for_restricted_access" in exported
    assert "audited net profit" in exported
    assert body["run"]["evidence"]["query_id"] in exported
    if format == "png":
        sensitivity = env.client.get(path + "&chart=1", headers=member)
        sensitivity_text = download_text(sensitivity, format)
        assert "Single-driver sensitivity" in sensitivity_text
        assert (
            body["run"]["result"]["sensitivity"]["points"][0]["result"]["remaining"]
            in sensitivity_text
        )
    assert env.client.get(path, headers=owner).status_code == 404
    assert env.client.get(endpoint(root, body), headers=member).json()["run"] == body["run"]
    rules["grants"][1]["conditions"][0]["value"] = "South"
    revise(env, owner, policy, rules)
    assert env.client.get(path, headers=member).status_code == 404


def test_source_and_legacy_methods_never_silently_change_predecessor_meaning(integration):
    env = integration
    headers, _, _, _, _, root = fixture(env)
    source = create(env, headers, root).json()
    options = env.client.get(root + "/decision-analysis/options", headers=headers).json()
    old_request = dict(
        name="Original aggregate scenario",
        revision_id=options["revision_id"],
        understanding_id=options["understanding_id"],
        metric="quantity",
        aggregation="sum",
        filters=[],
        assumptions_confirmed=True,
        alternatives=[dict(name="Ten percent", operation="percent_change", value="10")],
    )
    original = env.client.post(
        root + "/decision-analysis/scenarios", headers=headers, json=old_request
    )
    assert original.status_code == 201, original.text
    old = original.json()
    assert Decimal(old["run"]["result"]["alternatives"][0]["result"]) == Decimal("5.5")
    crossed = create(env, headers, root, parent_run_id=old["run"]["id"])
    assert crossed.status_code == 422 and "successor" in crossed.text
    crossed = env.client.post(
        root + "/decision-analysis/scenarios",
        headers=headers,
        json={**old_request, "parent_run_id": source["run"]["id"]},
    )
    assert crossed.status_code == 422 and "successor" in crossed.text
    assert env.client.get(endpoint(root, old), headers=headers).json()["run"] == old["run"]
    assert env.client.get(endpoint(root, source), headers=headers).json()["run"] == source["run"]
