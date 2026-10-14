"""Use case: Checks extended analysis through real private HTTP and storage boundaries.

What it does: Replays new and legacy evidence and checks privacy, freshness and refusal behavior.
"""

from copy import deepcopy
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import update

from execplus.domain.decision_analysis import checksum
from execplus.infrastructure.persistence import schema as s
from test_decision_analysis_integration import create, endpoint
from test_scenarios_integration import create as create_scenario
from test_studies import add_member, prepare
from test_understanding import confirm, context


@pytest.mark.parametrize("kind", ["anomalies", "allocations"])
def test_legacy_requests_without_extension_fields_replay(integration, kind):
    env = integration
    data = b"city,amount,cost\n" + b"Karachi,10,1\n" * 8 + b"Lahore,100,1\n"
    prepared = prepare(env, data) if kind == "anomalies" else prepare(env)
    headers, _, _, _, _, root = prepared
    response = create(env, headers, root, kind)
    assert response.status_code == 201, response.text
    body = response.json()
    raw = deepcopy(body["run"]["request"])
    for field in ("segment_column", "minimum_segment_size", "resource_column", "resource_capacity"):
        raw.pop(field, None)
    evidence = {**body["run"]["evidence"], "request_checksum": checksum(raw)}
    with env.engine.begin() as conn:
        conn.execute(
            update(s.analysis_runs)
            .where(s.analysis_runs.c.id == UUID(body["run"]["id"]))
            .values(request=raw, evidence=evidence)
        )
    reopened = env.client.get(endpoint(root, body), headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"]["result"] == body["run"]["result"]
    assert reopened.json()["run"]["method_version"] == body["run"]["method_version"]


def test_segmented_anomalies_coverage_private_feedback_and_replay(integration):
    env = integration
    data = (
        b"city,amount,cost\n"
        + b"Karachi,10,1\n" * 8
        + b"Karachi,100,1\n"
        + b"Lahore,100,1\n" * 8
        + b"Small,99,1\n"
        + b"Karachi,,1\n"
    )
    headers, _, wid, _, _, root = prepare(env, data)
    response = create(env, headers, root, segment_column="city")
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert body["run"]["method_version"] == "segmented-mad-iqr-v1"
    assert result["covered_records"] == 17 and result["excluded_records"] == 2
    assert result["findings"][0]["segment"] == "Karachi"
    url = endpoint(root, body)
    assert env.client.get(url, headers=headers).json()["run"] == body["run"]
    review = dict(
        target=result["findings"][0]["id"],
        status="investigate",
        note="Review group",
        expected_version=0,
    )
    assert env.client.post(url + "/reviews", headers=headers, json=review).status_code == 201
    member, _ = add_member(env, headers, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404
    assert env.client.post(url + "/reviews", headers=member, json=review).status_code == 404
    receipt = f"/workspaces/{wid}/queries/{body['run']['evidence']['query_id']}"
    assert env.client.post(receipt + "/replay", headers=headers).status_code == 200
    assert env.client.post(receipt + "/replay", headers=member).status_code == 404


def test_two_resource_constraints_units_replay_approval_and_staleness(integration):
    env = integration
    headers, _, wid, _, _, root = prepare(
        env, b"city,amount,cost,hours\nKarachi,10,1,4\nLahore,8,2,1\n"
    )
    meaning = context(env, headers, root)
    for column in meaning["definition"]["columns"]:
        if column["name"] == "hours":
            column.update(unit="hours", currency="")
    assert confirm(env, headers, root, meaning).status_code == 201
    legacy = create(env, headers, root, "allocations", budget="4", quantum="1")
    assert legacy.status_code == 201, legacy.text
    response = create(
        env,
        headers,
        root,
        "allocations",
        budget="4",
        quantum="1",
        resource_column="hours",
        resource_capacity="2",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run"]["evidence"]["units"]["hours"] == "hours"
    assert body["run"]["result"]["benefit"] == "16"
    assert body["run"]["result"]["resource_used"] == "2"
    assert legacy.json()["run"]["result"]["benefit"] == "28"
    url = endpoint(root, body)
    assert env.client.get(url, headers=headers).json()["run"] == body["run"]
    assert (
        env.client.get(endpoint(root, legacy.json()), headers=headers).json()["run"]
        == legacy.json()["run"]
    )
    approved = env.client.post(
        url + "/reviews",
        headers=headers,
        json=dict(
            target="decision",
            status="approved",
            note="Confirmed hours and budget",
            expected_version=0,
        ),
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["approval_effective"] is True
    member, _ = add_member(env, headers, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404
    meaning = context(env, headers, root)
    meaning["definition"]["columns"][1]["meaning"] = "Updated benefit assumption"
    assert confirm(env, headers, root, meaning).status_code == 201
    assert env.client.get(url, headers=headers).json()["approval_effective"] is False


def test_compound_scenario_mixed_alternatives_successor_and_private_replay(integration):
    env = integration
    headers, _, wid, _, _, root = prepare(env)
    alternatives = [
        dict(
            name="Combined",
            operation="compound_percent",
            drivers=[
                dict(name="Volume", percent_change="10"),
                dict(name="Price", percent_change="20"),
            ],
        ),
        dict(name="Keep baseline", operation="percent_change", value="0"),
    ]
    response = create_scenario(env, headers, root, alternatives=alternatives)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run"]["method_version"] == "compound-scenarios-v1"
    assert Decimal(body["run"]["result"]["alternatives"][0]["result"]) == Decimal("0.396")
    url = endpoint(root, body)
    assert env.client.get(url, headers=headers).json()["run"] == body["run"]
    successor = create_scenario(
        env, headers, root, alternatives=alternatives, parent_run_id=body["run"]["id"]
    )
    assert successor.status_code == 201, successor.text
    member, _ = add_member(env, headers, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404
    for qid in [
        body["run"]["evidence"]["query_id"],
        *body["run"]["evidence"]["coverage_query_ids"],
    ]:
        receipt = f"/workspaces/{wid}/queries/{qid}/replay"
        assert env.client.post(receipt, headers=headers).status_code == 200
        assert env.client.post(receipt, headers=member).status_code == 404


@pytest.mark.parametrize(
    "extra",
    [
        dict(resource_column="cost", resource_capacity="1"),
        dict(resource_column="unknown", resource_capacity="1"),
        dict(resource_column="hours"),
        dict(resource_capacity="1"),
        dict(resource_column="hours", resource_capacity="-1"),
    ],
)
def test_resource_http_contract_refuses_unsafe_constraints(integration, extra):
    headers, _, _, _, _, root = prepare(
        integration, b"city,amount,cost,hours\nKarachi,10,1,4\nLahore,8,2,1\n"
    )
    response = create(integration, headers, root, "allocations", budget="4", quantum="1", **extra)
    assert response.status_code in {409, 422}, response.text


@pytest.mark.parametrize(
    "extra",
    [
        dict(segment_column="amount"),
        dict(segment_column="missing"),
        dict(segment_column="city", minimum_segment_size=7),
    ],
)
def test_segment_http_contract_requires_valid_group_and_support(integration, extra):
    headers, _, _, _, _, root = prepare(integration)
    response = create(integration, headers, root, **extra)
    assert response.status_code == 422, response.text


def test_resource_tamper_detected_and_infeasible_plan_cannot_be_approved(integration):
    env = integration
    headers, _, _, _, _, root = prepare(
        env, b"city,amount,cost,hours\nKarachi,10,1,4\nLahore,8,2,1\n"
    )
    response = create(
        env,
        headers,
        root,
        "allocations",
        budget="4",
        quantum="1",
        resource_column="hours",
        resource_capacity="1",
        bounds=[dict(candidate="Karachi", minimum=1, maximum=1)],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    url = endpoint(root, body)
    assert body["run"]["result"]["status"] == "infeasible"
    review = dict(target="decision", status="approved", note="Not possible", expected_version=0)
    assert env.client.post(url + "/reviews", headers=headers, json=review).status_code == 409
    changed = deepcopy(body["run"]["request"])
    changed["resource_capacity"] = "99"
    with env.engine.begin() as conn:
        conn.execute(
            update(s.analysis_runs)
            .where(s.analysis_runs.c.id == UUID(body["run"]["id"]))
            .values(request=changed)
        )
    assert env.client.get(url, headers=headers).status_code == 409
