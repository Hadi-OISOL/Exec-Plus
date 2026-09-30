"""Use case: Verifies discovery reflects current source definitions and access.

What it does: Covers stale revisions, private metadata and revocation without cached evidence.
"""

from uuid import UUID

from sqlalchemy import delete

from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel, prepare
from test_understanding import confirm, context
from test_unified_conversation import document
from test_workspace_integration import accept, identity, invite, upload


def test_catalog_tracks_definitions_revisions_and_document_deletion(integration):
    env = integration
    owner, wid, root = prepare(env, ScriptedModel())
    url = f"/workspaces/{wid}/catalog"
    current = context(env, owner, root)
    current["definition"]["description"] = "Receivables from retail branches"
    saved = confirm(env, owner, root, current).json()
    doc = document(env, owner, root, name="receipts.md")
    response = env.client.get(url, params={"q": "receivables retail"}, headers=owner)
    assert response.status_code == 200, response.text
    entry = response.json()[0]
    assert entry["understanding_id"] == saved["id"]
    assert entry["state"] == "confirmed"
    assert entry["source_uploaded_at"] and entry["source_revised_at"]
    assert entry["availability"] == "metadata_only"
    assert entry["documents"][0]["id"] == doc["id"]
    assert env.client.get(url, params={"q": "unrelated"}, headers=owner).json() == []
    env.client.delete(f"/workspaces/{wid}/documents/{doc['id']}", headers=owner)
    assert env.client.get(url, params={"q": "receipts"}, headers=owner).json() == []
    did = entry["dataset_id"]
    newer = upload(env, owner, wid, did, b"city,revenue\nKarachi,0.1\n").json()
    changed = env.client.get(url, headers=owner).json()[0]
    assert changed["upload_id"] == newer["id"]
    assert changed["state"] == "needs_review"
    assert changed["understanding_id"] == saved["id"]


def test_catalog_never_indexes_private_goals_or_another_owners_documents(integration):
    env = integration
    owner, wid, root = prepare(env, ScriptedModel())
    document(env, owner, root, name="confidential-project.md", shared=False)
    member, user = identity(env, "catalog-member@example.test")
    iid = invite(env, owner, wid, user.email).json()["id"]
    accept(env, member, wid, iid)
    preference = env.client.post(
        root.split("/uploads/")[0] + "/preferences",
        headers=owner,
        json={"domain_hint": "sales", "goal": "private-goal-xyz"},
    )
    assert preference.status_code == 200, preference.text
    url = f"/workspaces/{wid}/catalog"
    assert "private-goal-xyz" not in env.client.get(url, headers=owner).text
    assert env.client.get(url, params={"q": "confidential"}, headers=member).json() == []
    assert len(env.client.get(url, headers=member).json()) == 1
    stranger, _ = identity(env, "catalog-stranger@example.test")
    assert env.client.get(url, headers=stranger).status_code == 404
    with env.engine.begin() as connection:
        connection.execute(
            delete(s.memberships).where(
                s.memberships.c.workspace_id == UUID(wid), s.memberships.c.user_id == user.id
            )
        )
    assert env.client.get(url, headers=member).status_code == 404
    assert env.client.get(url, params={"q": "x" * 201}, headers=owner).status_code == 422
