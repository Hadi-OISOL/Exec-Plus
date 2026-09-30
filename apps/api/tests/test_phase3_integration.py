"""Use case: Verifies Phase 3 against real PostgreSQL and object storage.

What it does: Tests observations, privacy boundaries, scoped citations and report failures.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from execplus.domain.activation import comparison
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_workspace_integration import accept, dataset, identity, invite, upload, workspace


def setup(env):
    owner, actor = identity(env, "phase3-owner@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    uid = upload(
        env,
        owner,
        wid,
        did,
        content=b"date,region,amount\n2026-01-01,East,0.1\n2026-01-02,West,0.2\n",
    ).json()["id"]
    return owner, actor, wid, did, uid, f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"


def analysis(env, owner, root):
    query = env.client.post(
        root + "/query", headers=owner, json={"metric": "amount", "aggregation": "sum"}
    )
    assert query.status_code == 200, query.text
    saved = env.client.post(
        root + "/saved-items",
        headers=owner,
        json={
            "kind": "analysis",
            "name": "Verified amount",
            "payload": {"query_id": query.json()["lineage"]["query_id"]},
            "shared": True,
        },
    )
    assert saved.status_code == 201, saved.text
    return saved.json(), query.json()


def test_observations_feedback_onboarding_and_usage_are_reproducible_and_private(integration):
    env = integration
    owner, _actor, wid, _did, _uid, root = setup(env)
    facts = env.client.get(root + "/insights", headers=owner)
    assert facts.status_code == 200, facts.text
    assert len(facts.json()) == 3
    assert [item["rank"] for item in facts.json()] == [1, 2, 3]
    assert env.client.get(root + "/insights", headers=owner).json() == facts.json()
    feedback = f"/workspaces/{wid}/feedback"
    assert (
        env.client.post(
            feedback,
            headers=owner,
            json={"feature": "dashboard", "category": "helpful", "rating": 5},
        ).status_code
        == 201
    )
    assert (
        env.client.post(
            feedback,
            headers=owner,
            json={
                "feature": "dashboard",
                "category": "helpful",
                "rating": 5,
                "text": "secret source passage",
            },
        ).status_code
        == 422
    )
    assert (
        env.client.post(
            feedback,
            headers=owner,
            json={"feature": "secret value", "category": "helpful", "rating": 5},
        ).status_code
        == 422
    )
    overview = env.client.get(f"/workspaces/{wid}/usage-analytics", headers=owner)
    assert overview.status_code == 200
    assert {item["id"]: item["complete"] for item in overview.json()["checklist"]}["upload"]
    assert "0.1" not in overview.text and "East" not in overview.text
    outsider, _ = identity(env, "phase3-outsider@example.test")
    assert env.client.get(root + "/insights", headers=outsider).status_code == 404
    assert (
        env.client.post(
            feedback,
            headers=outsider,
            json={"feature": "dashboard", "category": "helpful", "rating": 5},
        ).status_code
        == 404
    )
    member, _ = identity(env, "phase3-member@example.test")
    invitation = invite(env, owner, wid, "phase3-member@example.test").json()
    assert accept(env, member, wid, invitation["id"]).status_code == 200
    assert env.client.get(f"/workspaces/{wid}/usage-analytics", headers=member).status_code == 403
    assert env.client.get(f"/workspaces/{wid}/onboarding", headers=member).status_code == 200
    with env.engine.connect() as connection:
        stored = connection.execute(select(s.feedback)).mappings().one()
    assert stored["release"] and set(stored) == {
        "id",
        "workspace_id",
        "actor_id",
        "feature",
        "rating",
        "category",
        "release",
        "created_at",
    }


def test_comparison_replays_exact_values_and_does_not_claim_a_cause(integration):
    env = integration
    owner, _actor, wid, _did, _uid, root = setup(env)
    saved, previous = analysis(env, owner, root)
    current = env.client.post(
        root + "/query",
        headers=owner,
        json={
            "metric": "amount",
            "aggregation": "sum",
            "filters": [{"column": "region", "operator": "eq", "value": "West"}],
        },
    ).json()
    response = env.client.post(
        f"/workspaces/{wid}/comparisons",
        headers=owner,
        json={
            "current_query_id": current["lineage"]["query_id"],
            "previous_query_id": previous["lineage"]["query_id"],
        },
    )
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["delta"]) == Decimal("-0.1")
    assert response.json()["percent_change"] == "-33.33"
    assert "does not establish why" in response.json()["interpretation"]
    assert len(response.json()["evidence_ids"]) == 2
    repeated = env.client.post(
        f"/workspaces/{wid}/comparisons",
        headers=owner,
        json={
            "current_query_id": current["lineage"]["query_id"],
            "previous_query_id": previous["lineage"]["query_id"],
        },
    )
    assert repeated.status_code == 200
    with env.engine.connect() as connection:
        receipt = connection.execute(
            select(s.query_executions.c.receipt).where(
                s.query_executions.c.id == UUID(previous["lineage"]["query_id"])
            )
        ).scalar_one()
    assert len(receipt["narratives"]) == 2
    assert receipt["narratives"][0]["id"] != receipt["narratives"][1]["id"]
    run = env.client.post(f"/workspaces/{wid}/saved-items/{saved['id']}/run", headers=owner)
    assert run.status_code == 200 and run.json()["rows"] == previous["rows"]


def test_zero_and_negative_baseline_comparison():
    assert comparison(Decimal("1"), 0, UUID(int=1), UUID(int=2))["percent_change"] is None
    assert comparison(-5, -10, UUID(int=1), UUID(int=2))["percent_change"] == "50.00"


def test_document_filtering_precedes_ranker_and_citations_recheck_access(integration, monkeypatch):
    env = integration
    owner, _actor, wid, did, _uid, _root = setup(env)
    member, member_actor = identity(env, "reader@example.test")
    invitation = invite(env, owner, wid, "reader@example.test").json()
    assert accept(env, member, wid, invitation["id"]).status_code == 200
    base = f"/workspaces/{wid}/datasets/{did}"
    for shared, name, content in [
        (False, "private.txt", b"Private refund secret."),
        (True, "public.md", b"Refund requests require a receipt. Keep the receipt for review."),
    ]:
        response = env.client.post(
            base + f"/documents?name={name}&shared={str(shared).lower()}",
            headers=owner,
            content=content,
        )
        assert response.status_code == 201, response.text
    seen = []
    original = env.runtime.knowledge.ranker.rank

    def spy(query, chunks, limit):
        seen.extend(chunk.text for chunk in chunks)
        return original(query, chunks, limit)

    monkeypatch.setattr(env.runtime.knowledge.ranker, "rank", spy)
    response = env.client.post(
        base + "/knowledge/search", headers=member, json={"query": "refund receipt"}
    )
    assert response.status_code == 200, response.text
    hits = response.json()["passages"]
    assert len(hits) == 1 and all("secret" not in passage for passage in seen)
    citation = hits[0]["citation_url"]
    assert env.client.get(citation, headers=member).json()["text"] == hits[0]["text"]
    outsider, _ = identity(env, "doc-outsider@example.test")
    assert env.client.get(citation, headers=outsider).status_code == 404
    assert (
        env.client.post(
            base + "/knowledge/search", headers=outsider, json={"query": "secret"}
        ).status_code
        == 404
    )
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{member_actor.id}", headers=owner).status_code
        == 204
    )
    assert env.client.get(citation, headers=member).status_code == 404
    assert (
        env.client.delete(
            f"/workspaces/{wid}/documents/{hits[0]['document_id']}", headers=owner
        ).status_code
        == 204
    )
    assert env.client.get(citation, headers=owner).status_code == 404
    with env.engine.connect() as connection:
        assert "refund" not in str(connection.execute(select(s.audit_events)).all()).lower()


@pytest.mark.parametrize(
    "name,content",
    [
        ("bad.pdf", b"pdf"),
        ("bad.txt", b"\xff"),
        ("../bad.txt", b"text"),
        ("bad.md", b"\x00"),
        ("empty.txt", b" "),
    ],
)
def test_invalid_documents_are_rejected_without_metadata(integration, name, content):
    env = integration
    owner, _, wid, did, _, _ = setup(env)
    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/documents",
        params={"name": name},
        headers=owner,
        content=content,
    )
    assert response.status_code == 422
    assert env.client.get(f"/workspaces/{wid}/datasets/{did}/documents", headers=owner).json() == []


class CapturingEmail:
    def __init__(self):
        self.messages = []
        self.fail = False

    def send(self, recipient, subject, body, delivery_id):
        if self.fail:
            raise RuntimeError("provider error with a secret which must not be stored")
        self.messages.append((recipient, subject, body, delivery_id))


def test_report_delivers_once_and_unsubscribe_and_failure_are_audited(integration):
    env = integration
    owner, _actor, wid, _did, _uid, root = setup(env)
    saved, _result = analysis(env, owner, root)
    mail = CapturingEmail()
    env.runtime.reports.email = mail
    response = env.client.post(
        f"/workspaces/{wid}/report-schedules",
        headers=owner,
        json={"item_id": saved["id"], "interval_hours": 1},
    )
    assert response.status_code == 201, response.text
    schedule = response.json()
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    assert asyncio.run(env.runtime.reports.deliver_due(now))["sent"] == 1
    assert asyncio.run(env.runtime.reports.deliver_due(now))["sent"] == 0
    assert len(mail.messages) == 1
    assert "0.300000000000" in mail.messages[0][2] and "unsubscribe" in mail.messages[0][2]
    mail.fail = True
    assert asyncio.run(env.runtime.reports.deliver_due(now + timedelta(hours=2)))["failed"] == 1
    with env.engine.connect() as connection:
        deliveries = connection.execute(select(s.report_deliveries)).mappings().all()
    assert {item["status"] for item in deliveries} == {"sent", "failed"}
    assert "secret" not in str(deliveries)
    assert (
        env.client.delete(
            f"/workspaces/{wid}/report-schedules/{schedule['id']}", headers=owner
        ).status_code
        == 204
    )
    assert asyncio.run(env.runtime.reports.deliver_due(now + timedelta(hours=4)))["sent"] == 0
    actions = [
        item["action"]
        for item in env.client.get(f"/workspaces/{wid}/audit-events", headers=owner).json()
    ]
    assert {"report.sent", "report.failed", "report.unsubscribed"} <= set(actions)


def test_report_rechecks_authorization_after_replay(integration, monkeypatch):
    env = integration
    owner, _actor, wid, _did, _uid, root = setup(env)
    saved, _ = analysis(env, owner, root)
    member, member_actor = identity(env, "report-reader@example.test")
    invitation = invite(env, owner, wid, "report-reader@example.test").json()
    assert accept(env, member, wid, invitation["id"]).status_code == 200
    response = env.client.post(
        f"/workspaces/{wid}/report-schedules",
        headers=member,
        json={"item_id": saved["id"], "interval_hours": 1},
    )
    assert response.status_code == 201
    mail = CapturingEmail()
    env.runtime.reports.email = mail
    original = env.runtime.analytics.replay

    async def revoke(*args):
        result = await original(*args)
        with env.runtime.service.uow() as repo:
            repo.workspace(UUID(wid), lock=True)
            repo.remove_member(UUID(wid), member_actor.id)
        return result

    monkeypatch.setattr(env.runtime.analytics, "replay", revoke)
    result = asyncio.run(
        env.runtime.reports.deliver_due(datetime.now(timezone.utc) + timedelta(hours=2))
    )
    assert result["unauthorized"] == 1 and mail.messages == []
    with env.engine.connect() as connection:
        assert connection.execute(select(s.report_schedules.c.enabled)).scalar_one() is False


def test_retrieval_rejects_adapter_injected_passages(integration, monkeypatch):
    from execplus.application.contracts import KnowledgeChunk, RetrievalHit

    env = integration
    owner, _, wid, did, _, _root = setup(env)

    def malicious(*args):
        return (
            RetrievalHit(KnowledgeChunk(UUID(int=1), UUID(int=2), UUID(int=3), "secret", {}), 1),
        )

    monkeypatch.setattr(env.runtime.knowledge.ranker, "rank", malicious)
    with pytest.raises(IngestionError, match="could not be verified"):
        asyncio.run(
            env.runtime.knowledge.search(
                env.runtime.identity.authenticate(owner["Authorization"].split()[1]),
                UUID(wid),
                UUID(did),
                "test",
            )
        )


def test_document_limit_and_checksum_mismatch_fail_closed(integration):
    env = integration
    owner, _, wid, did, _, _ = setup(env)
    base = f"/workspaces/{wid}/datasets/{did}"
    too_large = env.client.post(
        base + "/documents?name=large.txt", headers=owner, content=b"x" * (1024 * 1024 + 1)
    )
    assert too_large.status_code == 413
    response = env.client.post(
        base + "/documents?name=policy.txt", headers=owner, content=b"A receipt is required."
    )
    document = response.json()
    storage = env.runtime.service.storage
    storage.client.put_object(
        Bucket=env.bucket,
        Key=f"workspaces/{wid}/documents/{document['id']}/original",
        Body=b"Changed text",
    )
    result = env.client.post(base + "/knowledge/search", headers=owner, json={"query": "receipt"})
    assert result.status_code == 503 and result.json()["error"]["code"] == "storage_integrity"


def test_disabled_email_reports_failure_without_sending(integration):
    env = integration
    owner, _, wid, _, _, root = setup(env)
    saved, _ = analysis(env, owner, root)
    env.client.post(
        f"/workspaces/{wid}/report-schedules",
        headers=owner,
        json={"item_id": saved["id"], "interval_hours": 1},
    )
    assert (
        asyncio.run(
            env.runtime.reports.deliver_due(datetime.now(timezone.utc) + timedelta(hours=2))
        )["failed"]
        == 1
    )


def test_synthetic_retrieval_evaluation_has_no_external_requests():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "scripts" / "evaluate_phase3.py"
    spec = importlib.util.spec_from_file_location("evaluation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.evaluate(
        {
            "documents": [
                {"id": "one", "text": "refund receipt policy"},
                {"id": "two", "text": "inventory counts"},
            ],
            "questions": [{"query": "refund receipt", "relevant_ids": ["one"]}],
        }
    )
    assert result["mean_reciprocal_rank_at_3"] == 1
    assert result["external_requests"] == 0 and not result["production_provider_selected"]


def test_ingestion_cleans_object_after_database_commit_failure(integration, monkeypatch):
    from contextlib import contextmanager

    env = integration
    _owner, actor, wid, did, _, _ = setup(env)
    original = env.runtime.knowledge.uow

    @contextmanager
    def fail_commit():
        with original() as repo:
            yield repo
            raise RuntimeError("commit failed")

    monkeypatch.setattr(env.runtime.knowledge, "uow", fail_commit)
    with pytest.raises(RuntimeError, match="commit failed"):
        asyncio.run(
            env.runtime.knowledge.ingest(
                actor, UUID(wid), UUID(did), "policy.txt", b"refund policy", False
            )
        )
    storage = env.runtime.service.storage
    assert not storage.client.list_objects_v2(
        Bucket=env.bucket, Prefix=f"workspaces/{wid}/documents/"
    ).get("Contents")
    with env.engine.connect() as connection:
        assert connection.execute(select(s.documents)).first() is None


def test_deleted_analysis_cancels_report_during_replay(integration, monkeypatch):
    env = integration
    owner, _, wid, _, _, root = setup(env)
    saved, _ = analysis(env, owner, root)
    env.client.post(
        f"/workspaces/{wid}/report-schedules",
        headers=owner,
        json={"item_id": saved["id"], "interval_hours": 1},
    )
    mail = CapturingEmail()
    env.runtime.reports.email = mail
    original = env.runtime.analytics.replay

    async def delete(*args):
        result = await original(*args)
        with env.runtime.service.uow() as repo:
            repo.workspace(UUID(wid), lock=True)
            repo.delete_saved_item(UUID(wid), UUID(saved["id"]))
        return result

    monkeypatch.setattr(env.runtime.analytics, "replay", delete)
    counts = asyncio.run(
        env.runtime.reports.deliver_due(datetime.now(timezone.utc) + timedelta(hours=2))
    )
    assert counts["cancelled"] == 1 and mail.messages == []
