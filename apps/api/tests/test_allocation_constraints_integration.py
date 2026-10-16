"""Use case: Verifies selection rules through private HTTP and retained exact evidence.

What it does: Checks old contracts, owner boundaries, freshness, refusal and tamper detection.
"""

from copy import deepcopy
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update

from execplus.application.services import decision_analysis as service_module
from execplus.domain.allocation_constraints import RULE_METHOD
from execplus.domain.decision_analysis import checksum
from execplus.infrastructure.persistence import schema as s
from test_decision_analysis_integration import create, endpoint
from test_studies import add_member, prepare
from test_understanding import confirm, context

DATA = b"city,amount,cost,hours\nA,10,1,1\nB,2,1,1\n"
RULES = dict(prerequisites=[dict(candidate="A", requires="B")])


def rules_create(env, headers, root, **extra):
    return create(
        env,
        headers,
        root,
        "allocations",
        **{
            "budget": "2",
            "quantum": "1",
            **RULES,
            **extra,
        },
    )


@pytest.mark.parametrize("resource", [False, True])
def test_rule_allocation_exact_replay_private_receipt_and_current_approval(integration, resource):
    env = integration
    owner, _, wid, _, _, root = prepare(env, DATA)
    extra = dict(resource_column="hours", resource_capacity="1") if resource else {}
    response = rules_create(env, owner, root, **extra)
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert body["run"]["method_version"] == RULE_METHOD
    assert result["benefit"] == ("2" if resource else "12")
    assert result["verification"]["selection_rules"] == "passed"
    url = endpoint(root, body)
    assert env.client.get(url, headers=owner).json()["run"] == body["run"]
    review = dict(
        target="decision", status="approved", note="Checked declared rules", expected_version=0
    )
    approved = env.client.post(url + "/reviews", headers=owner, json=review)
    assert approved.status_code == 201, approved.text
    assert approved.json()["approval_effective"] is True
    peer, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(url, headers=peer).status_code == 404
    assert env.client.post(url + "/reviews", headers=peer, json=review).status_code == 404
    assert env.client.get(url.rsplit("/", 1)[0], headers=peer).json() == []
    receipt_url = f"/workspaces/{wid}/queries/{body['run']['evidence']['query_id']}"
    assert env.client.post(receipt_url + "/replay", headers=owner).status_code == 200
    assert env.client.get(receipt_url, headers=peer).status_code == 404
    assert env.client.post(receipt_url + "/replay", headers=peer).status_code == 404
    current = context(env, owner, root)
    current["definition"]["columns"][1]["meaning"] = "Revised assumed benefit"
    assert confirm(env, owner, root, current).status_code == 201
    old = env.client.get(url, headers=owner)
    assert old.status_code == 200, old.text
    assert old.json()["run"] == body["run"]
    assert old.json()["current"] is False and old.json()["approval_effective"] is False
    review.update(status="pending", expected_version=1)
    assert env.client.post(url + "/reviews", headers=owner, json=review).status_code == 201
    review.update(status="approved", expected_version=2)
    assert env.client.post(url + "/reviews", headers=owner, json=review).status_code == 409


@pytest.mark.parametrize("resource", [False, True])
def test_empty_new_fields_preserve_legacy_request_and_result_serialization(integration, resource):
    env = integration
    headers, _, _, _, _, root = prepare(env, DATA)
    extra = dict(resource_column="hours", resource_capacity="1") if resource else {}
    legacy = create(env, headers, root, "allocations", budget="2", quantum="1", **extra)
    explicit_empty = create(
        env,
        headers,
        root,
        "allocations",
        budget="2",
        quantum="1",
        prerequisites=[],
        exclusions=[],
        **extra,
    )
    assert legacy.status_code == explicit_empty.status_code == 201
    first, second = legacy.json()["run"], explicit_empty.json()["run"]
    assert first["request"] == second["request"]
    assert "prerequisites" not in first["request"] and "exclusions" not in first["request"]
    assert first["result"] == second["result"]
    assert first["method_version"] == (
        "two-resource-enumeration-v1" if resource else "integer-budget-v1"
    )
    assert env.client.get(endpoint(root, legacy.json()), headers=headers).json()["run"] == first


@pytest.mark.parametrize(
    "extra",
    [
        dict(prerequisites=[dict(candidate="A", requires="A")]),
        dict(prerequisites=[dict(candidate="A", requires="missing")]),
        dict(prerequisites=[dict(candidate="A", requires="B"), dict(candidate="B", requires="A")]),
        dict(prerequisites=[dict(candidate="A", requires="B")] * 2),
        dict(exclusions=[dict(first="A", second="B"), dict(first="B", second="A")]),
        dict(exclusions=[dict(first="A", second="B")] * 41),
        dict(prerequisites=[dict(candidate="A", requires="B", silent=True)]),
        dict(prerequisites=[dict(candidate="A", requires=1)]),
        dict(filters=[dict(column="city", operator="eq", value="A")]),
    ],
)
def test_invalid_rules_and_filtered_out_actions_never_create_recommendations(integration, extra):
    env = integration
    headers, _, _, _, _, root = prepare(env, DATA)
    response = rules_create(env, headers, root, **extra)
    assert response.status_code == 422, response.text
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=headers).json()
        == []
    )


def test_contradictory_mandatory_rules_save_only_infeasibility_and_refuse_approval(integration):
    env = integration
    headers, _, _, _, _, root = prepare(env, DATA)
    response = rules_create(
        env,
        headers,
        root,
        exclusions=[dict(first="A", second="B")],
        bounds=[dict(candidate="A", minimum=1, maximum=2)],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run"]["result"]["status"] == "infeasible"
    assert body["run"]["result"]["allocations"] == []
    assert body["run"]["result"]["benefit"] is None
    url = endpoint(root, body)
    assert env.client.get(url, headers=headers).json()["run"] == body["run"]
    approved = env.client.post(
        url + "/reviews",
        headers=headers,
        json=dict(
            target="decision",
            status="approved",
            note="Impossible",
            expected_version=0,
        ),
    )
    assert approved.status_code == 409, approved.text


@pytest.mark.parametrize("target", ["request", "result", "method", "receipt"])
def test_rule_evidence_tampering_refuses_even_rechecksummed_result(integration, target):
    env = integration
    headers, _, _, _, _, root = prepare(env, DATA)
    response = rules_create(env, headers, root)
    assert response.status_code == 201, response.text
    body = response.json()
    run = deepcopy(body["run"])
    with env.engine.begin() as conn:
        if target == "receipt":
            row = (
                conn.execute(
                    select(s.query_executions).where(
                        s.query_executions.c.id == UUID(run["evidence"]["query_id"])
                    )
                )
                .mappings()
                .one()
            )
            value = deepcopy(row["receipt"])
            value["answer"]["records_analyzed"] += 1
            conn.execute(
                update(s.query_executions)
                .where(s.query_executions.c.id == row["id"])
                .values(receipt=value)
            )
        else:
            if target == "request":
                run["request"]["prerequisites"] = [dict(candidate="B", requires="A")]
                run["evidence"]["request_checksum"] = checksum(run["request"])
                change = dict(request=run["request"], evidence=run["evidence"])
            elif target == "method":
                change = dict(method_version="integer-budget-v1")
            else:
                run["result"]["allocations"][1]["quantity"] = 0
                run["evidence"]["result_checksum"] = checksum(run["result"])
                change = dict(result=run["result"], evidence=run["evidence"])
            conn.execute(
                update(s.analysis_runs)
                .where(s.analysis_runs.c.id == UUID(run["id"]))
                .values(**change)
            )
    assert env.client.get(endpoint(root, body), headers=headers).status_code == 409


def test_failed_independent_verification_withholds_recommendation(integration, monkeypatch):
    env = integration
    headers, _, _, _, _, root = prepare(env, DATA)
    original = service_module.allocate_selection_rules

    def corrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        result["cost"] = "0"
        return result

    monkeypatch.setattr(service_module, "allocate_selection_rules", corrupted)
    response = rules_create(env, headers, root)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "allocation_verification_failed"
    with env.engine.connect() as conn:
        assert conn.execute(select(s.analysis_runs)).all() == []


def test_rule_membership_revoked_during_compute_prevents_publication(integration, monkeypatch):
    env = integration
    owner, _, wid, _, _, root = prepare(env, DATA)
    member, actor = add_member(env, owner, wid)
    original = service_module.calculate

    def revoke(raw, value):
        calculated = original(raw, value)
        with env.engine.begin() as conn:
            conn.execute(
                delete(s.memberships).where(
                    s.memberships.c.workspace_id == UUID(wid),
                    s.memberships.c.user_id == actor.id,
                )
            )
        return calculated

    monkeypatch.setattr(service_module, "calculate", revoke)
    response = rules_create(env, member, root)
    assert response.status_code == 404, response.text
    with env.engine.connect() as conn:
        assert conn.execute(select(s.analysis_runs)).all() == []


@pytest.mark.parametrize("change", ["meaning", "source_bytes"])
def test_rule_source_change_during_compute_prevents_publication(integration, monkeypatch, change):
    env = integration
    headers, _, wid, did, uid, root = prepare(env, DATA)
    original = service_module.calculate

    def changed(raw, value):
        calculated = original(raw, value)
        if change == "meaning":
            current = context(env, headers, root)
            current["definition"]["columns"][1]["meaning"] = "Changed during computation"
            assert confirm(env, headers, root, current).status_code == 201
        else:
            with env.runtime.service.uow() as repo:
                stored = repo.upload(UUID(wid), UUID(did), UUID(uid))
            env.runtime.service.storage.client.put_object(
                Bucket=env.bucket,
                Key=stored.storage_key,
                Body=b"city,amount,cost,hours\nA,999,1,1\nB,2,1,1\n",
            )
        return calculated

    monkeypatch.setattr(service_module, "calculate", changed)
    response = rules_create(env, headers, root)
    assert response.status_code == (422 if change == "meaning" else 503), response.text
    assert response.json()["error"]["code"] == (
        "clarification_required" if change == "meaning" else "storage_integrity"
    )
    with env.engine.connect() as conn:
        assert conn.execute(select(s.analysis_runs)).all() == []
