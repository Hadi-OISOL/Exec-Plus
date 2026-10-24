"""Use case: Proves each person's chat history is private, reopenable and continuable.

What it does: Lists owner chats across the workspace, checks other members cannot list, open,
continue, rename or hide them, replays saved answers unchanged and keeps follow-up context.
"""

import pytest
from sqlalchemy import text

from test_analytics_integration import uploaded_dataset
from test_studies import add_member
from test_threads_integration import _wire_fake_thread_service
from test_usage_migration import migrate
from test_workspace_integration import identity, workspace


def _chat(env, headers, wid, did, uid, questions):
    thread_id = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/threads", headers=headers
    ).json()["id"]
    replies = []
    for question in questions:
        reply = env.client.post(
            f"/workspaces/{wid}/threads/{thread_id}/ask",
            headers=headers,
            json={"question": question},
        )
        assert reply.status_code == 200, reply.text
        replies.append(reply.json())
    return thread_id, replies


def test_owner_lists_chats_newest_first_with_titles_sources_and_search(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    _wire_fake_thread_service(env)
    older, _ = _chat(env, owner, wid, did, uid, ["What is total revenue?"])
    newer, _ = _chat(env, owner, wid, did, uid, ["  What   is total revenue by region? "])
    empty = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/threads", headers=owner
    ).json()["id"]
    env.client.post(
        f"/workspaces/{wid}/threads/{older}/ask",
        headers=owner,
        json={"question": "and by region?"},
    )

    chats = env.client.get(f"/workspaces/{wid}/threads", headers=owner)

    assert chats.status_code == 200, chats.text
    body = chats.json()
    assert [item["id"] for item in body] == [older, empty, newer]
    first = body[0]
    assert first["title"] == "Total revenue — Sales"
    assert first["named"] is False
    assert first["dataset_name"] == "Sales"
    assert first["filename"] == "revenue.csv"
    assert first["turn_count"] == 2
    assert body[1]["title"] == "New chat"
    assert body[2]["title"] == "Total revenue — Sales"
    assert first["last_activity"] > body[2]["last_activity"]
    assert env.client.get(f"/workspaces/{wid}/threads", headers=owner).json() == body
    found = env.client.get(f"/workspaces/{wid}/threads?q=by%20region", headers=owner).json()
    assert {item["id"] for item in found} == {older, newer}
    assert env.client.get(f"/workspaces/{wid}/threads?q=100%25", headers=owner).json() == []
    assert len(env.client.get(f"/workspaces/{wid}/threads?limit=1", headers=owner).json()) == 1


def test_chat_pages_follow_last_activity_with_a_stable_cursor(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    _wire_fake_thread_service(env)
    created = [_chat(env, owner, wid, did, uid, ["What is total revenue?"])[0] for _ in range(5)]
    hidden = created[1]
    assert env.client.delete(f"/workspaces/{wid}/threads/{hidden}", headers=owner).status_code
    root = f"/workspaces/{wid}/threads"

    seen, cursor = [], ""
    while True:
        page = env.client.get(root, headers=owner, params={"limit": 2, "after": cursor})
        assert page.status_code == 200, page.text
        seen += page.json()
        if len(page.json()) < 2:
            break
        cursor = f"{page.json()[-1]['last_activity']}|{page.json()[-1]['id']}"

    assert [item["id"] for item in seen] == [item for item in reversed(created) if item != hidden]
    assert env.client.get(root, headers=owner, params={"after": "yesterday"}).status_code == 422
    naive = f"2026-10-24T10:00:00|{created[0]}"
    assert env.client.get(root, headers=owner, params={"after": naive}).status_code == 422


def test_untitled_chat_without_a_calculation_uses_its_first_question(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    _wire_fake_thread_service(env)
    _chat(env, owner, wid, did, uid, ["Please explain what this file is about for my team"])

    listed = env.client.get(f"/workspaces/{wid}/threads", headers=owner).json()

    assert listed[0]["title"] == "Please explain what this file is about…"
    assert listed[0]["named"] is False


def test_other_members_cannot_list_open_continue_rename_or_hide_a_chat(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    _wire_fake_thread_service(env)
    thread_id, _ = _chat(env, owner, wid, did, uid, ["What is total revenue?"])
    admin, _ = add_member(env, owner, wid, role="admin")
    outsider, _ = identity(env, "outsider@example.test")
    root = f"/workspaces/{wid}/threads/{thread_id}"

    assert env.client.get(f"/workspaces/{wid}/threads", headers=admin).json() == []
    assert env.client.get(f"/workspaces/{wid}/threads", headers=outsider).status_code in {403, 404}
    for headers in (admin, outsider):
        assert env.client.get(root, headers=headers).status_code == 404
        assert (
            env.client.post(
                f"{root}/ask", headers=headers, json={"question": "and by region?"}
            ).status_code
            == 404
        )
        assert env.client.patch(root, headers=headers, json={"title": "Mine"}).status_code == 404
        assert env.client.delete(root, headers=headers).status_code == 404
    assert len(env.client.get(root, headers=owner).json()["turns"]) == 1


def test_reopened_answers_are_identical_and_continuing_keeps_context(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    _wire_fake_thread_service(env)
    thread_id, [first] = _chat(env, owner, wid, did, uid, ["What is total revenue?"])
    turn_id = first["turn"]["id"]
    answer_path = f"/workspaces/{wid}/threads/{thread_id}/turns/{turn_id}/answer"

    reopened = env.client.get(answer_path, headers=owner)
    again = env.client.get(answer_path, headers=owner)

    assert reopened.status_code == 200, reopened.text
    assert reopened.content == again.content
    assert reopened.json() == first["answer"]
    listed = env.client.get(f"/workspaces/{wid}/threads", headers=owner).json()
    assert listed[0]["id"] == thread_id
    follow_up = env.client.post(
        f"/workspaces/{wid}/threads/{listed[0]['id']}/ask",
        headers=owner,
        json={"question": "and by region?"},
    )
    assert follow_up.status_code == 200, follow_up.text
    assert follow_up.json()["answer"]["lineage"]["grouping"] == ["region"]
    assert env.client.get(answer_path, headers=owner).content == reopened.content
    turns = env.client.get(f"/workspaces/{wid}/threads/{thread_id}", headers=owner).json()["turns"]
    assert [turn["question"] for turn in turns] == ["What is total revenue?", "and by region?"]


def test_rename_and_hide_are_owner_only_and_keep_audit_history(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    _wire_fake_thread_service(env)
    thread_id, _ = _chat(env, owner, wid, did, uid, ["What is total revenue?"])
    root = f"/workspaces/{wid}/threads/{thread_id}"

    renamed = env.client.patch(root, headers=owner, json={"title": "  Revenue   check "})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Revenue check"
    listed = env.client.get(f"/workspaces/{wid}/threads", headers=owner).json()
    assert (listed[0]["title"], listed[0]["named"]) == ("Revenue check", True)
    assert env.client.get(f"/workspaces/{wid}/threads?q=revenue%20check", headers=owner).json()
    assert env.client.patch(root, headers=owner, json={"title": "   "}).status_code == 422

    assert env.client.delete(root, headers=owner).status_code == 204
    assert env.client.get(f"/workspaces/{wid}/threads", headers=owner).json() == []
    assert (
        env.client.get(
            f"/workspaces/{wid}/datasets/{did}/uploads/{uid}/threads", headers=owner
        ).json()
        == []
    )
    assert env.client.get(root, headers=owner).status_code == 404
    assert (
        env.client.post(f"{root}/ask", headers=owner, json={"question": "again?"}).status_code
        == 404
    )
    with env.runtime.engine.connect() as connection:
        actions = set(
            connection.execute(
                text("SELECT action FROM audit_events WHERE workspace_id = :wid"),
                {"wid": wid},
            ).scalars()
        )
        turns = connection.execute(
            text("SELECT count(*) FROM thread_turns WHERE thread_id = :tid"), {"tid": thread_id}
        ).scalar_one()
    assert {"conversation.renamed", "conversation.hidden", "conversation.complete"} <= actions
    assert turns == 1


def test_thread_title_migration_downgrades_only_without_names_or_hidden_chats(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    wid = workspace(env, owner)
    did, uid = uploaded_dataset(env, owner, wid)
    _wire_fake_thread_service(env)
    thread_id, _ = _chat(env, owner, wid, did, uid, ["What is total revenue?"])
    migrate(env, "downgrade", "0030")
    migrate(env, "upgrade", "head")
    assert len(env.client.get(f"/workspaces/{wid}/threads", headers=owner).json()) == 1
    root = f"/workspaces/{wid}/threads/{thread_id}"
    assert env.client.patch(root, headers=owner, json={"title": "Kept"}).status_code == 200
    with pytest.raises(RuntimeError, match="refusing to discard"):
        migrate(env, "downgrade", "0030")
    assert env.client.get(f"/workspaces/{wid}/threads", headers=owner).json()[0]["title"] == "Kept"
