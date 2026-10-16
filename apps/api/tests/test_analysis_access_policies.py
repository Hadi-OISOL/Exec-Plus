"""Use case: Keeps analytical work useful inside explicit row/column grants.

What it does: Checks projected studies, patterns and decisions, then verifies that
policy changes hide saved metadata and block replay, review, export and publication.
"""

import asyncio
import json
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from execplus.application.services import decision_analysis as decision_module
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_decision_analysis_integration import create as create_decision
from test_decision_analysis_integration import endpoint
from test_patterns_integration import service as pattern_service
from test_scenarios_integration import create as create_scenario
from test_studies import add_member, prepare, run
from test_understanding import confirm, context


def grant(env, owner, owner_actor, wid, did, actor, columns, condition):
    path = f"/workspaces/{wid}/datasets/{did}/access-policy"
    body = {
        "expected_version": 0,
        "enabled": True,
        "grants": [
            {"user_id": str(owner_actor.id), "columns": None, "conditions": []},
            {"user_id": str(actor.id), "columns": columns, "conditions": [condition]},
        ],
    }
    response = env.client.put(path, headers=owner, json=body)
    assert response.status_code == 200, response.text
    return path, body


def revise(env, owner, path, body):
    body["expected_version"] += 1
    with env.runtime.access_policies.uow() as repo:
        actor = repo.user(UUID(body["grants"][0]["user_id"]))
    result = env.runtime.access_policies.save(
        actor,
        UUID(path.split("/")[2]),
        UUID(path.split("/")[4]),
        body["expected_version"],
        body["enabled"],
        body["grants"],
    )
    assert result["version"] == body["expected_version"] + 1


def study_fixture(env):
    owner, owner_actor, wid, did, _, root = prepare(env)
    member, actor = add_member(env, owner, wid)
    current = context(env, owner, root)
    current["definition"]["description"] = "Private whole-source description"
    assert confirm(env, owner, root, current).status_code == 201
    path, body = grant(
        env,
        owner,
        owner_actor,
        wid,
        did,
        actor,
        ["city", "amount"],
        {"column": "city", "operator": "eq", "value": "Karachi"},
    )
    return owner, member, actor, wid, did, root, path, body


def test_restricted_study_and_board_keep_exact_view_and_hide_other_actor_or_revised_policy(
    integration,
):
    env = integration
    owner, member, _, wid, did, root, policy, body = study_fixture(env)
    suggested = env.client.get(root + "/adaptive-views", headers=member)
    assert suggested.status_code == 200, suggested.text
    assert {column["name"] for column in suggested.json()["columns"]} == {"city", "amount"}
    created = run(env, member, root)
    assert created.status_code == 201, created.text
    saved = created.json()
    version = saved["version"]
    assert version["evidence"]["definition"]["description"] == ""
    assert {column["name"] for column in version["evidence"]["definition"]["columns"]} == {
        "city",
        "amount",
    }
    assert version["evidence"]["preparation"] == []
    assert "Private whole-source description" not in created.text
    assert "0.100000000000" in created.text and "0.300000000000" not in created.text
    assert all(item["records_analyzed"] == 1 for item in saved["results"])
    hidden = run(env, member, root, {"kind": "metric", "column": "cost", "aggregation": "sum"})
    assert hidden.status_code == 422
    base = f"/workspaces/{wid}"
    version_path = base + f"/study-versions/{version['id']}"
    assert env.client.get(version_path, headers=member).json() == saved
    sid = saved["study"]["id"]
    assert (
        env.client.patch(
            base + f"/studies/{sid}", headers=member, json={"shared": True}
        ).status_code
        == 204
    )
    board = env.client.post(
        base + "/study-boards",
        headers=member,
        json={"name": "Restricted saved dashboard", "shared": True, "pins": [version["id"]]},
    )
    assert board.status_code == 201, board.text
    board_path = base + f"/study-boards/{board.json()['id']}"
    assert env.client.get(board_path, headers=member).status_code == 200
    assert env.client.get(version_path + "/export.xlsx", headers=member).status_code == 200
    assert env.client.get(version_path, headers=owner).status_code == 404
    assert env.client.get(base + f"/datasets/{did}/studies", headers=owner).json() == []
    assert env.client.get(base + "/study-boards", headers=owner).json() == []
    revise(env, owner, policy, body)
    assert env.client.get(base + f"/datasets/{did}/studies", headers=member).json() == []
    assert env.client.get(base + "/study-boards", headers=member).json() == []
    for path in (version_path, version_path + "/export.xlsx", board_path):
        assert env.client.get(path, headers=member).status_code == 404
    assert (
        env.client.patch(
            base + f"/studies/{sid}", headers=member, json={"shared": False}
        ).status_code
        == 404
    )


def test_enabling_policy_hides_pre_policy_studies_and_boards_but_allows_new_scoped_work(
    integration,
):
    env = integration
    owner, owner_actor, wid, did, _, root = prepare(env)
    member, actor = add_member(env, owner, wid)
    old = run(env, member, root).json()
    base = f"/workspaces/{wid}"
    board = env.client.post(
        base + "/study-boards",
        headers=member,
        json={"name": "Earlier full result", "shared": False, "pins": [old["version"]["id"]]},
    )
    assert board.status_code == 201
    grant(
        env,
        owner,
        owner_actor,
        wid,
        did,
        actor,
        ["city", "amount"],
        {"column": "city", "operator": "eq", "value": "Karachi"},
    )
    assert env.client.get(base + f"/datasets/{did}/studies", headers=member).json() == []
    assert env.client.get(base + "/study-boards", headers=member).json() == []
    assert (
        env.client.get(base + f"/study-versions/{old['version']['id']}", headers=member).status_code
        == 404
    )
    newer = run(env, member, root)
    assert newer.status_code == 201, newer.text
    listing = env.client.get(base + f"/datasets/{did}/studies", headers=member).json()
    assert [item["id"] for item in listing] == [newer.json()["study"]["id"]]
    assert len(listing[0]["versions"]) == 1


def test_restricted_recommendation_dismissal_succeeds_then_refuses_mid_save_policy_change(
    integration, monkeypatch
):
    env = integration
    owner, member, _, _, _, root, path, body = study_fixture(env)
    suggested = env.client.get(root + "/adaptive-views", headers=member).json()
    choice = suggested["recommendations"][0]["id"]
    payload = {"understanding_id": suggested["understanding_id"], "dismissed": [choice]}
    assert (
        env.client.post(
            root + "/adaptive-views/dismissals", headers=member, json=payload
        ).status_code
        == 204
    )
    original = env.runtime.studies.suggest

    def suggest(*args, **kwargs):
        value = original(*args, **kwargs)
        revise(env, owner, path, body)
        return value

    monkeypatch.setattr(env.runtime.studies, "suggest", suggest)
    response = env.client.post(root + "/adaptive-views/dismissals", headers=member, json=payload)
    assert response.status_code == 404


@pytest.mark.parametrize("phase", ["create", "open"])
def test_study_policy_change_after_last_query_prevents_publication_or_return(
    integration, monkeypatch, phase
):
    env = integration
    owner, member, _, wid, _, root, path, body = study_fixture(env)
    calls = 0
    if phase == "create":
        original = env.runtime.analytics._persist

        def persist(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 3:
                revise(env, owner, path, body)
            return result

        monkeypatch.setattr(env.runtime.analytics, "_persist", persist)
        response = run(env, member, root)
        with env.engine.connect() as connection:
            assert connection.execute(select(s.study_versions.c.id)).all() == []
    else:
        created = run(env, member, root).json()
        original = env.runtime.analytics.replay

        async def replay(*args, **kwargs):
            nonlocal calls
            result = await original(*args, **kwargs)
            calls += 1
            if calls == 3:
                revise(env, owner, path, body)
            return result

        monkeypatch.setattr(env.runtime.analytics, "replay", replay)
        response = env.client.get(
            f"/workspaces/{wid}/study-versions/{created['version']['id']}", headers=member
        )
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("kind", ["anomalies", "allocations", "scenarios"])
def test_restricted_decisions_compute_only_granted_rows_then_refuse_old_review_and_exports(
    integration, kind
):
    env = integration
    content = (
        b"city,amount,cost,hidden\n"
        + b"Karachi,10,1,secret\n" * 8
        + b"Karachi,100,1,secret\nLahore,999,1,secret\n"
        if kind == "anomalies"
        else b"city,amount,cost,hidden\nKarachi,10,1,secret\nLahore,999,1,secret\n"
    )
    owner, owner_actor, wid, did, _, root = prepare(env, content)
    member, actor = add_member(env, owner, wid)
    path, body = grant(
        env,
        owner,
        owner_actor,
        wid,
        did,
        actor,
        ["city", "amount", "cost"],
        {"column": "city", "operator": "eq", "value": "Karachi"},
    )
    response = (
        create_scenario(env, member, root)
        if kind == "scenarios"
        else create_decision(
            env,
            member,
            root,
            kind,
            **({"budget": "1", "quantum": "1"} if kind == "allocations" else {}),
        )
    )
    assert response.status_code == 201, response.text
    saved = response.json()
    result = saved["run"]["result"]
    assert "secret" not in response.text and '"hidden"' not in response.text
    assert Decimal(result["benefit"] if kind == "allocations" else result["baseline"]) == 10
    if kind == "anomalies":
        assert result["sample_count"] == 9
        assert result["findings"][0]["value"] == "100"
    url = endpoint(root, saved)
    assert env.client.get(url, headers=member).json()["run"] == saved["run"]
    assert env.client.get(url, headers=owner).status_code == 404
    if kind != "scenarios":
        review = {
            "expected_version": 0,
            "target": "decision" if kind == "allocations" else result["findings"][0]["id"],
            "status": "approved" if kind == "allocations" else "investigate",
            "note": "Review within granted view",
        }
        assert env.client.post(url + "/reviews", headers=member, json=review).status_code == 201
    revise(env, owner, path, body)
    assert env.client.get(url.rsplit("/", 1)[0], headers=member).json() == []
    assert env.client.get(url, headers=member).status_code == 404
    if kind != "scenarios":
        assert (
            env.client.post(
                url + "/reviews", headers=member, json={**review, "expected_version": 1}
            ).status_code
            == 404
        )
    export_kind = {"anomalies": "anomaly", "allocations": "allocation", "scenarios": "scenario"}[
        kind
    ]
    exported = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/analyses/{saved['run']['id']}/export.xlsx?kind={export_kind}",
        headers=member,
    )
    assert exported.status_code == 404


def test_policy_change_during_decision_math_prevents_saved_analysis(integration, monkeypatch):
    env = integration
    owner, member, _, _, _, root, path, body = study_fixture(env)
    original = decision_module.calculate

    def calculate(*args, **kwargs):
        result = original(*args, **kwargs)
        revise(env, owner, path, body)
        return result

    monkeypatch.setattr(decision_module, "calculate", calculate)
    response = create_scenario(env, member, root)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "clarification_required"
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []


def pattern_fixture(env):
    content = (
        "group,amount,reading,region,hidden\n"
        + "".join(
            f"{group},{i},{i * 2},{region},secret\n"
            for region in ("Allowed", "Hidden")
            for group in ("A", "B")
            for i in range(1, 21)
        )
    ).encode()
    owner, owner_actor, wid, did, uid, _ = prepare(env, content)
    member, actor = add_member(env, owner, wid)
    path, body = grant(
        env,
        owner,
        owner_actor,
        wid,
        did,
        actor,
        ["group", "amount", "reading"],
        {"column": "region", "operator": "eq", "value": "Allowed"},
    )
    return owner, member, actor, wid, did, uid, path, body


@pytest.mark.parametrize("grouped", [False, True])
def test_restricted_patterns_and_group_comparisons_are_measured_private_and_policy_bound(
    integration, grouped
):
    env = integration
    owner, member, actor, wid, did, uid, path, body = pattern_fixture(env)
    service = pattern_service(env)
    evidence = asyncio.run(
        service.discover(
            actor,
            UUID(wid),
            UUID(did),
            UUID(uid),
            ("amount", "reading"),
            group_by="group" if grouped else None,
        )
    )
    assert "secret" not in json.dumps(evidence) and '"hidden"' not in json.dumps(evidence)
    assert (
        evidence["result"]["pooled"]["support"]
        if grouped
        else evidence["result"]["coverage"]["filtered_rows"]
    ) == 40
    assert asyncio.run(service.reopen(actor, UUID(wid), evidence)) == evidence
    receipt = f"/workspaces/{wid}/queries/{evidence['query_id']}"
    assert env.client.post(receipt + "/replay", headers=member).status_code == 200
    assert env.client.post(receipt + "/replay", headers=owner).status_code == 404
    revise(env, owner, path, body)
    with pytest.raises(IngestionError) as error:
        asyncio.run(service.reopen(actor, UUID(wid), evidence))
    assert error.value.status == 404
    assert env.client.post(receipt + "/replay", headers=member).status_code == 404


@pytest.mark.parametrize("phase", ["create", "open"])
def test_pattern_policy_change_during_statistics_blocks_final_response(
    integration, monkeypatch, phase
):
    env = integration
    owner, _, actor, wid, did, uid, path, body = pattern_fixture(env)
    service = pattern_service(env)
    args = (actor, UUID(wid), UUID(did), UUID(uid), ("amount", "reading"))
    evidence = asyncio.run(service.discover(*args)) if phase == "open" else None
    original = service._result

    def result(*args, **kwargs):
        value = original(*args, **kwargs)
        revise(env, owner, path, body)
        return value

    monkeypatch.setattr(service, "_result", result)
    with pytest.raises((IngestionError, ClarificationRequiredError)) as error:
        asyncio.run(
            service.reopen(actor, UUID(wid), evidence) if evidence else service.discover(*args)
        )
    if isinstance(error.value, IngestionError):
        assert error.value.status == 404
