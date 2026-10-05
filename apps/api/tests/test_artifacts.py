"""Use case: Verifies artifact metadata, capabilities and authorized lineage projections.

What it does: Covers private resources, immutable evidence, tenant isolation and traversal bounds.
"""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update

from execplus.domain.artifacts import require_acyclic
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import Revision, TableData, profile_for
from execplus.domain.quality import quality_report
from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel, prepare
from test_studies import add_member, run
from test_studies import prepare as study_prepare
from test_unified_conversation import document
from test_workspace_integration import dataset, identity, upload, workspace


def revision(table, algorithm="profile-v2"):
    return Revision(
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        None,
        algorithm,
        "a" * 64,
        table.checksum(),
        [],
        profile_for(table, algorithm),
        uuid4(),
        datetime.now(timezone.utc),
    )


def artifact_url(root, kind, identifier):
    return root.split("/uploads/")[0] + f"/artifacts/{kind}/{identifier}"


@pytest.mark.parametrize("algorithm", ["profile-v1", "profile-v2"])
def test_quality_is_versioned_source_bound_and_does_not_change_legacy_profiles(algorithm):
    table = TableData(
        ("customer_id", "amount", "constant"),
        tuple((str(i), "invalid" if i == 9 else "1", "same") for i in range(10)),
    )
    value = revision(table, algorithm)
    before = deepcopy(value.profile)
    report = quality_report(value)
    assert quality_report(value) == report
    assert value.profile == before
    assert report["profile_version"] == algorithm
    assert report["confirmed_rules"] == []
    assert report["source"]["id"] == str(value.id)
    assert report["source_checksum"] == value.source_checksum
    assert report["output_checksum"] == value.output_checksum
    findings = report["findings"]
    assert next(item for item in findings if item["code"] == "type_conflicts")["category"] == (
        "heuristic"
    )
    assert next(item for item in findings if item["code"] == "high_cardinality")["column"] == (
        "customer_id"
    )
    assert next(item for item in findings if item["code"] == "constant_column")["category"] == (
        "observed"
    )
    assert any(item["code"] == "suspected_identifier" for item in findings)
    assert (
        quality_report(replace(value, source_checksum="b" * 64))["checksum"] != report["checksum"]
    )
    assert quality_report(replace(value, id=uuid4()))["checksum"] != report["checksum"]


def test_quality_thresholds_empty_cells_and_duplicates_are_not_business_rules():
    table = TableData(("label", "amount"), (("a", ""), ("a", ""), ("b", "1")))
    report = quality_report(revision(table))
    facts = {item["code"]: item for item in report["findings"] if item["column"] is None}
    assert facts["missing_values"]["count"] == 2
    assert facts["missing_values"]["denominator"] == 6
    assert facts["duplicate_rows"]["count"] == 1
    assert facts["duplicate_rows"]["category"] == "observed"
    assert not any(item["code"] == "high_cardinality" for item in report["findings"])
    assert all(item["category"] != "confirmed_rule" for item in report["findings"])


def test_quality_rejects_incompatible_profile_versions():
    value = revision(TableData(("amount",), (("1",),)))
    with pytest.raises(IngestionError, match="unsupported"):
        quality_report(replace(value, algorithm="profile-future"))
    with pytest.raises(IngestionError, match="version does not match"):
        quality_report(replace(value, algorithm="profile-v1"))


def test_lineage_cycle_detection_accepts_diamonds_and_rejects_shared_branch_cycles():
    require_acyclic((("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")))
    with pytest.raises(IngestionError, match="cycle"):
        require_acyclic((("a", "b"), ("a", "c"), ("b", "d"), ("d", "c"), ("c", "d")))


def test_upload_artifact_quality_and_catalog_contracts_are_metadata_only(integration, monkeypatch):
    env = integration
    owner, wid, root = prepare(env, ScriptedModel())
    original = env.client.get(root + "/profile", headers=owner).json()
    with env.engine.connect() as connection:
        queries_before = connection.execute(select(s.query_executions)).all()
    monkeypatch.setattr(
        env.runtime.service.storage, "read", lambda *args: pytest.fail("source read")
    )
    response = env.client.get(root + "/artifacts", headers=owner)
    assert response.status_code == 200, response.text
    artifacts = {item["reference"]["kind"]: item for item in response.json()["artifacts"]}
    assert set(artifacts) == {"raw_asset", "dataset_snapshot", "profile", "quality_report"}
    assert set(artifacts["dataset_snapshot"]["capabilities"]) == {
        "inspect",
        "profile",
        "query",
        "transform",
        "visualize",
        "join",
    }
    assert all(item["availability"] == "metadata_only" for item in artifacts.values())
    assert artifacts["dataset_snapshot"]["checksum"] == original["output_checksum"]
    assert artifacts["profile"]["method_version"] == original["algorithm"]
    quality = env.client.get(root + "/quality", headers=owner)
    assert quality.status_code == 200, quality.text
    assert quality.json()["checksum"] == artifacts["quality_report"]["checksum"]
    assert all(
        token not in response.text + quality.text
        for token in ("storage_key", "PrivateCustomerA", "PrivateCustomerB", "PrivateCustomerC")
    )
    catalog = env.client.get(f"/workspaces/{wid}/catalog", headers=owner).json()[0]
    assert catalog["asset_kinds"] == ["tabular"]
    assert catalog["artifact_refs"] == [item["reference"] for item in artifacts.values()]
    assert env.client.get(root + "/profile", headers=owner).json() == original
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).all() == queries_before


def test_artifact_routes_reject_cross_tenant_mixed_ids_and_revocation(integration):
    env = integration
    owner, wid, root = prepare(env, ScriptedModel())
    other, _ = identity(env, "artifact-other@example.test")
    foreign_wid = workspace(env, other)
    foreign_did = dataset(env, other, foreign_wid)
    uid = root.rsplit("/", 1)[-1]
    foreign_uid = upload(env, other, foreign_wid, foreign_did).json()["id"]
    original = env.client.get(root + "/profile", headers=owner).json()
    for suffix in ("/artifacts", "/quality"):
        assert env.client.get(root + suffix, headers=other).status_code == 404
        assert (
            env.client.get(root.replace(uid, foreign_uid) + suffix, headers=owner).status_code
            == 404
        )
    url = artifact_url(root, "profile", original["id"])
    assert env.client.get(url, headers=owner).status_code == 422
    assert env.client.get(url, params={"upload_id": foreign_uid}, headers=owner).status_code == 404
    assert env.client.get(url, params={"upload_id": uid}, headers=owner).status_code == 200
    member, user = add_member(env, owner, wid)
    assert env.client.get(root + "/quality", headers=member).status_code == 200
    with env.engine.begin() as connection:
        connection.execute(
            delete(s.memberships).where(
                s.memberships.c.workspace_id == UUID(wid), s.memberships.c.user_id == user.id
            )
        )
    assert env.client.get(root + "/artifacts", headers=member).status_code == 404
    assert (
        env.client.get(url + "/lineage", params={"upload_id": uid}, headers=member).status_code
        == 404
    )


def test_document_artifacts_keep_private_access_and_do_not_claim_sql_capabilities(integration):
    env = integration
    owner, wid, root = prepare(env, ScriptedModel())
    private = document(env, owner, root, name="private-note.md", shared=False)
    shared = document(env, owner, root, name="shared-note.md", shared=True)
    member, _ = add_member(env, owner, wid)
    private_url = artifact_url(root, "document", private["id"])
    for suffix in ("", "/lineage"):
        assert env.client.get(private_url + suffix, headers=member).status_code == 404
        assert env.client.get(private_url + suffix, headers=owner).status_code == 200
    response = env.client.get(artifact_url(root, "document", shared["id"]), headers=member)
    assert response.status_code == 200, response.text
    assert response.json()["asset_kind"] == "document"
    assert response.json()["capabilities"] == ["inspect", "text_search"]
    refs = env.client.get(f"/workspaces/{wid}/catalog", headers=member).json()[0]["artifact_refs"]
    assert {item["id"] for item in refs if item["kind"] == "document"} == {shared["id"]}
    env.client.delete(f"/workspaces/{wid}/documents/{shared['id']}", headers=owner)
    assert (
        env.client.get(artifact_url(root, "document", shared["id"]), headers=member).status_code
        == 404
    )


def test_historical_quality_and_bounded_lineage_keep_original_revisions(integration):
    env = integration
    owner, _, root = prepare(env, ScriptedModel())
    original = env.client.get(root + "/profile", headers=owner).json()
    old_quality = env.client.get(root + "/quality", headers=owner).json()
    current = original
    for _ in range(10):
        response = env.client.post(
            root + "/cleaning/apply",
            headers=owner,
            json={
                "expected_revision_id": current["id"],
                "trim": True,
            },
        )
        assert response.status_code == 201, response.text
        current = response.json()["revision"]
    assert (
        env.client.get(
            root + "/quality", headers=owner, params={"revision_id": original["id"]}
        ).json()
        == old_quality
    )
    graph = env.client.get(
        artifact_url(root, "quality_report", current["id"]) + "/lineage",
        headers=owner,
        params={"upload_id": root.rsplit("/", 1)[-1]},
    )
    assert graph.status_code == 200, graph.text
    body = graph.json()
    assert body["truncated"] is True
    assert len(body["nodes"]) <= body["limits"]["nodes"]
    assert all(item["availability"] == "metadata_only" for item in body["nodes"])
    keys = {item["key"] for item in body["nodes"]}
    assert all(edge["source"] in keys and edge["target"] in keys for edge in body["edges"])


def test_query_artifact_preserves_exact_receipt_and_checks_each_original_source(integration):
    env = integration
    owner, _, root = prepare(env, ScriptedModel())
    answer = env.client.post(
        root + "/query", headers=owner, json={"metric": "revenue", "aggregation": "sum"}
    )
    assert answer.status_code == 200, answer.text
    query_id = answer.json()["lineage"]["query_id"]
    url = artifact_url(root, "query_result", query_id)
    response = env.client.get(url + "/lineage", headers=owner)
    assert response.status_code == 200, response.text
    assert response.json()["truncated"] is False
    query = next(
        item for item in response.json()["nodes"] if item["reference"]["kind"] == "query_result"
    )
    assert "replay" in query["capabilities"]
    assert query["checksum"] == answer.json()["lineage"]["receipt"]["result_checksum"]
    assert "sql" not in query["metadata"] and "answer" not in query["metadata"]
    with env.engine.begin() as connection:
        stored = connection.execute(
            select(s.query_executions.c.receipt).where(s.query_executions.c.id == UUID(query_id))
        ).scalar_one()
        assert stored == answer.json()["lineage"]["receipt"]
        changed = deepcopy(stored)
        changed["sources"][0]["output_checksum"] = "f" * 64
        connection.execute(
            update(s.query_executions)
            .where(s.query_executions.c.id == UUID(query_id))
            .values(receipt=changed)
        )
    assert env.client.get(url, headers=owner).status_code == 409


def test_study_artifacts_honor_sharing_and_reference_real_methods(integration):
    env = integration
    owner, _, wid, _, _, root = study_prepare(env)
    study = run(env, owner, root)
    assert study.status_code == 201, study.text
    body = study.json()
    url = artifact_url(root, "study_version", body["version"]["id"])
    member, _ = add_member(env, owner, wid)
    assert env.client.get(url, headers=member).status_code in {403, 404}
    assert env.client.get(url + "/lineage", headers=member).status_code in {403, 404}
    shared = env.client.patch(
        f"/workspaces/{wid}/studies/{body['study']['id']}",
        headers=owner,
        json={"shared": True},
    )
    assert shared.status_code in {200, 204}, shared.text
    response = env.client.get(url + "/lineage", headers=member)
    assert response.status_code == 200, response.text
    root_node = next(
        item for item in response.json()["nodes"] if item["reference"]["kind"] == "study_version"
    )
    assert root_node["method_version"] == body["version"]["evidence"]["method_version"]
    assert root_node["authorization_scope"] == "workspace"
    assert any(item["reference"]["kind"] == "definition" for item in response.json()["nodes"])
    env.client.patch(
        f"/workspaces/{wid}/studies/{body['study']['id']}",
        headers=owner,
        json={"shared": False},
    )
    assert env.client.get(url + "/lineage", headers=member).status_code in {403, 404}


@pytest.mark.parametrize("receipt", [{}, {"version": "execution-v1", "outcome": "failed"}])
def test_legacy_or_failed_execution_artifacts_never_advertise_replay(integration, receipt):
    env = integration
    owner, _, root = prepare(env, ScriptedModel())
    answer = env.client.post(
        root + "/query", headers=owner, json={"metric": "revenue", "aggregation": "sum"}
    ).json()
    query_id = answer["lineage"]["query_id"]
    with env.engine.begin() as connection:
        connection.execute(
            update(s.query_executions)
            .where(s.query_executions.c.id == UUID(query_id))
            .values(receipt=receipt)
        )
    response = env.client.get(artifact_url(root, "query_result", query_id), headers=owner)
    assert response.status_code == 200, response.text
    assert response.json()["capabilities"] == ["inspect"]
    assert response.json()["checksum"] is None


def test_cyclic_retained_lineage_fails_explicitly(integration):
    env = integration
    owner, _, root = prepare(env, ScriptedModel())
    original = env.client.get(root + "/profile", headers=owner).json()
    with env.engine.begin() as connection:
        connection.execute(
            update(s.revisions)
            .where(s.revisions.c.id == UUID(original["id"]))
            .values(parent_id=UUID(original["id"]))
        )
    response = env.client.get(
        artifact_url(root, "dataset_snapshot", original["id"]) + "/lineage",
        headers=owner,
        params={"upload_id": root.rsplit("/", 1)[-1]},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "lineage_mismatch"


def test_artifact_lineage_refuses_a_query_with_foreign_tenant_sources(integration):
    env = integration
    owner, _, root = prepare(env, ScriptedModel())
    other, _ = identity(env, "artifact-foreign-source@example.test")
    foreign_wid = workspace(env, other)
    foreign_did = dataset(env, other, foreign_wid)
    foreign_uid = upload(env, other, foreign_wid, foreign_did).json()["id"]
    foreign_root = f"/workspaces/{foreign_wid}/datasets/{foreign_did}/uploads/{foreign_uid}"
    foreign_profile = env.client.get(foreign_root + "/profile", headers=other).json()
    query = env.client.post(
        root + "/query", headers=owner, json={"metric": "revenue", "aggregation": "sum"}
    ).json()["lineage"]
    changed = deepcopy(query["receipt"])
    changed["sources"] = [
        {
            "dataset_id": foreign_did,
            "upload_id": foreign_uid,
            "revision_id": foreign_profile["id"],
            "source_checksum": foreign_profile["source_checksum"],
            "output_checksum": foreign_profile["output_checksum"],
        }
    ]
    with env.engine.begin() as connection:
        connection.execute(
            update(s.query_executions)
            .where(s.query_executions.c.id == UUID(query["query_id"]))
            .values(receipt=changed)
        )
    response = env.client.get(
        artifact_url(root, "query_result", query["query_id"]) + "/lineage",
        headers=owner,
    )
    assert response.status_code == 404
    assert foreign_profile["source_checksum"] not in response.text


def test_capabilities_do_not_advertise_malformed_receipt_as_replayable(integration):
    env = integration
    owner, _, root = prepare(env, ScriptedModel())
    query = env.client.post(
        root + "/query", headers=owner, json={"metric": "revenue", "aggregation": "sum"}
    ).json()["lineage"]
    changed = deepcopy(query["receipt"])
    changed["result_checksum"] = None
    with env.engine.begin() as connection:
        connection.execute(
            update(s.query_executions)
            .where(s.query_executions.c.id == UUID(query["query_id"]))
            .values(receipt=changed)
        )
    url = artifact_url(root, "query_result", query["query_id"])
    assert env.client.get(url, headers=owner).json()["capabilities"] == ["inspect"]
    response = env.client.get(url, headers=owner, params={"upload_id": str(uuid4())})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_artifact_reference"
