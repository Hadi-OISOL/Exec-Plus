"""Use case: Verifies document I/O never holds the workspace authorization lock.

What it does: Uses a second database connection and mid-operation policy changes
to prove stale passages and newly written documents cannot be published.
"""

from uuid import UUID

import pytest
from sqlalchemy import delete, select

from execplus.infrastructure.persistence import schema as s
from test_dataset_access import fixture


@pytest.mark.parametrize("operation", ["ingest", "citation", "search_read", "search_rank"])
@pytest.mark.parametrize("change", ["none", "epoch", "membership"])
def test_document_external_operations_release_lock_and_recheck_access(
    integration, monkeypatch, operation, change
):
    env = integration
    owner, actor, _, _, wid, did, _, _, _, raw = fixture(env)
    base = f"/workspaces/{wid}/datasets/{did}"
    service = env.runtime.knowledge
    docid = None
    chunkid = None
    if operation != "ingest":
        response = env.client.post(
            base + "/documents?name=reference.md&shared=false",
            headers=owner,
            content=b"Refund requests require a receipt.",
        )
        assert response.status_code == 201, response.text
        docid = UUID(response.json()["id"])
        with service.uow() as repo:
            chunkid = repo.document_chunks(UUID(wid), docid)[0].id
    target, method = (
        (service.ranker, "rank")
        if operation == "search_rank"
        else (service.storage, "put_document" if operation == "ingest" else "read_document")
    )
    original = getattr(target, method)
    calls = 0
    ranks = []
    deleted = []
    rank = service.ranker.rank
    remove = service.storage.delete_document

    def rank_spy(*args):
        ranks.append(args)
        return rank(*args)

    def remove_spy(document):
        deleted.append(document.id)
        return remove(document)

    def external(*args):
        nonlocal calls
        result = original(*args)
        with env.engine.begin() as connection:
            connection.execute(
                select(s.workspaces.c.id)
                .where(s.workspaces.c.id == UUID(wid))
                .with_for_update(nowait=True)
            ).scalar_one()
        calls += 1
        if calls == 1 and change == "epoch":
            env.runtime.access_policies.save(actor, UUID(wid), UUID(did), 1, True, raw["grants"])
        if calls == 1 and change == "membership":
            with env.engine.begin() as connection:
                connection.execute(
                    delete(s.memberships).where(
                        s.memberships.c.workspace_id == UUID(wid),
                        s.memberships.c.user_id == actor.id,
                    )
                )
        return result

    monkeypatch.setattr(service.storage, "delete_document", remove_spy)
    if operation != "search_rank":
        monkeypatch.setattr(service.ranker, "rank", rank_spy)
    monkeypatch.setattr(target, method, external)
    if operation == "ingest":
        response = env.client.post(
            base + "/documents?name=reference.md&shared=false",
            headers=owner,
            content=b"Refund requests require a receipt.",
        )
    elif operation == "citation":
        response = env.client.get(
            f"/workspaces/{wid}/documents/{docid}/chunks/{chunkid}", headers=owner
        )
    else:
        response = env.client.post(
            base + "/knowledge/search", headers=owner, json={"query": "refund receipt"}
        )
    assert calls >= 1
    if change == "none":
        assert response.status_code == (201 if operation == "ingest" else 200), response.text
        assert not deleted
    else:
        assert response.status_code == 404, response.text
        assert "Refund requests" not in response.text
        if operation == "search_read":
            assert not ranks
        with env.engine.connect() as connection:
            assert not connection.execute(
                select(s.audit_events.c.id).where(s.audit_events.c.action == "knowledge.searched")
            ).all()
            if operation == "ingest":
                assert not connection.execute(select(s.documents.c.id)).all()
                assert len(deleted) == 1
