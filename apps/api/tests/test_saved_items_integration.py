"""Use case: Proves saved question/prompt/dashboard visibility and ownership rules.

What it does: Exercises private-by-default visibility, explicit sharing, and
tenant/role-scoped deletion through the HTTP API against real infrastructure.
"""

from test_analytics_integration import uploaded_dataset
from test_workspace_integration import accept, identity, invite, workspace


def create_item(env, headers, wid, did, uid, shared=False, name="My question"):
    return env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/saved-items",
        headers=headers,
        json={
            "kind": "question",
            "name": name,
            "description": "A saved question",
            "payload": {"metric": "revenue", "aggregation": "sum"},
            "shared": shared,
        },
    )


def test_private_saved_item_is_visible_only_to_its_owner(integration):
    env = integration
    owner, _owner_user = identity(env, "owner@example.test")
    member, member_user = identity(env, "member@example.test")
    wid = workspace(env, owner)
    invitation = invite(env, owner, wid, member_user.email).json()["id"]
    accept(env, member, wid, invitation)
    did, uid = uploaded_dataset(env, owner, wid)

    created = create_item(env, owner, wid, did, uid, shared=False)
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]

    listed_by_member = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/saved-items", headers=member
    )
    assert listed_by_member.json() == []

    direct_access_by_member = env.client.get(
        f"/workspaces/{wid}/saved-items/{item_id}", headers=member
    )
    assert direct_access_by_member.status_code == 404

    direct_access_by_owner = env.client.get(
        f"/workspaces/{wid}/saved-items/{item_id}", headers=owner
    )
    assert direct_access_by_owner.status_code == 200


def test_shared_saved_item_is_visible_to_other_workspace_members(integration):
    env = integration
    owner, _owner_user = identity(env, "owner@example.test")
    member, member_user = identity(env, "member@example.test")
    wid = workspace(env, owner)
    invitation = invite(env, owner, wid, member_user.email).json()["id"]
    accept(env, member, wid, invitation)
    did, uid = uploaded_dataset(env, owner, wid)

    created = create_item(env, owner, wid, did, uid, shared=True)
    item_id = created.json()["id"]

    listed_by_member = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/saved-items", headers=member
    )
    assert len(listed_by_member.json()) == 1
    assert listed_by_member.json()[0]["id"] == item_id


def test_only_owner_or_manager_can_delete_a_saved_item(integration):
    env = integration
    owner, _owner_user = identity(env, "owner@example.test")
    member, member_user = identity(env, "member@example.test")
    wid = workspace(env, owner)
    invitation = invite(env, owner, wid, member_user.email).json()["id"]
    accept(env, member, wid, invitation)
    did, uid = uploaded_dataset(env, owner, wid)

    created = create_item(env, owner, wid, did, uid, shared=True)
    item_id = created.json()["id"]

    forbidden = env.client.delete(f"/workspaces/{wid}/saved-items/{item_id}", headers=member)
    assert forbidden.status_code == 403

    allowed = env.client.delete(f"/workspaces/{wid}/saved-items/{item_id}", headers=owner)
    assert allowed.status_code == 204


def test_saved_item_is_not_reachable_from_another_workspace(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    outsider, _ = identity(env, "outsider@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    created = create_item(env, owner, wid, did, uid, shared=True)
    item_id = created.json()["id"]
    other_wid = workspace(env, outsider)

    response = env.client.get(f"/workspaces/{other_wid}/saved-items/{item_id}", headers=outsider)

    assert response.status_code == 404
