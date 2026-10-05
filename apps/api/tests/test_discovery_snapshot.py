"""Use case: Keeps concurrent discovery responsive without weakening retained evidence checks.

What it does: Proves one parsed snapshot, worker-thread I/O and post-execution integrity checks.
"""

import asyncio
import threading
from uuid import UUID

import pytest
from sqlalchemy import delete

from execplus.infrastructure.persistence import schema as s
from test_discovery import setup
from test_understanding import confirm, context


def test_discovery_parses_once_and_io_does_not_run_on_the_query_event_loop(
    integration, monkeypatch
):
    env = integration
    owner, _, root, _ = setup(env)
    service = env.runtime.analytics
    calls = []
    loop_threads = []
    read_table, parse = service.parser.read_table, service.parser.parse
    source_read = service.storage.read
    execute = service.executor.execute

    def tracked_parse(*args, **kwargs):
        calls.append(("validate", threading.get_ident()))
        return parse(*args, **kwargs)

    def tracked_table(*args, **kwargs):
        calls.append(("table", threading.get_ident()))
        return read_table(*args, **kwargs)

    def tracked_source(*args, **kwargs):
        calls.append(("source", threading.get_ident()))
        return source_read(*args, **kwargs)

    async def tracked_execute(*args, **kwargs):
        loop_threads.append(threading.get_ident())
        return await execute(*args, **kwargs)

    monkeypatch.setattr(service.parser, "parse", tracked_parse)
    monkeypatch.setattr(service.parser, "read_table", tracked_table)
    monkeypatch.setattr(service.storage, "read", tracked_source)
    monkeypatch.setattr(service.executor, "execute", tracked_execute)
    response = env.client.get(root + "/discovery", headers=owner)
    assert response.status_code == 200, response.text
    assert len(response.json()["findings"]) == 7
    assert [kind for kind, _ in calls].count("validate") == 1
    assert [kind for kind, _ in calls].count("table") == 1
    assert [kind for kind, _ in calls].count("source") == 2
    assert len(loop_threads) == 7
    assert all(thread != loop_threads[0] for _, thread in calls)


@pytest.mark.parametrize("mutation", ["delete_object", "replace_object", "revoke", "revision"])
def test_last_query_cannot_publish_findings_after_source_or_access_changes(
    integration, monkeypatch, mutation
):
    env = integration
    owner, wid, root, _ = setup(env)
    service = env.runtime.analytics
    uid, did = UUID(root.split("/")[6]), UUID(root.split("/")[4])
    revision = env.client.get(root + "/profile", headers=owner).json()
    with service.uow() as repo:
        stored = repo.upload(UUID(wid), did, uid)
    original = service.executor.execute
    completed = 0

    def mutate():
        if mutation == "delete_object":
            service.storage.delete(stored)
        elif mutation == "replace_object":
            service.storage.client.put_object(
                Bucket=env.bucket, Key=stored.storage_key, Body=b"changed-private-bytes"
            )
        elif mutation == "revoke":
            with env.engine.begin() as connection:
                connection.execute(
                    delete(s.memberships).where(s.memberships.c.workspace_id == UUID(wid))
                )
        else:
            changed = env.client.post(
                root + "/cleaning/apply",
                headers=owner,
                json={"expected_revision_id": revision["id"], "trim": True},
            )
            assert changed.status_code == 201, changed.text

    async def changing_execute(*args, **kwargs):
        nonlocal completed
        result = await original(*args, **kwargs)
        completed += 1
        if completed == 7:
            await asyncio.to_thread(mutate)
        return result

    monkeypatch.setattr(service.executor, "execute", changing_execute)
    response = env.client.get(root + "/discovery", headers=owner)
    assert (
        response.status_code
        == {"delete_object": 503, "replace_object": 503, "revoke": 404, "revision": 422}[mutation]
    ), response.text
    assert "findings" not in response.json()
    assert "changed-private-bytes" not in response.text


def test_recheck_detects_definition_change_during_final_object_read(integration, monkeypatch):
    env = integration
    owner, _, root, _ = setup(env)
    service = env.runtime.analytics
    definition = context(env, owner, root)
    read = service.storage.read
    source_reads = 0
    changed = False

    def changing_read(*args, **kwargs):
        nonlocal source_reads, changed
        content = read(*args, **kwargs)
        source_reads += 1
        if source_reads == 2 and not changed:
            changed = True
            response = confirm(env, owner, root, definition)
            assert response.status_code == 201
        return content

    monkeypatch.setattr(service.storage, "read", changing_read)
    response = env.client.get(root + "/discovery", headers=owner)
    assert changed
    assert response.status_code == 422
    assert "meaning changed" in response.text


def test_uncertain_definition_still_rechecks_source_before_returning_profile_only(
    integration, monkeypatch
):
    env = integration
    owner, wid, root, _ = setup(env)
    proposed = context(env, owner, root)
    assert (
        confirm(env, owner, root, proposed, proposed["definition"], state="inferred").status_code
        == 201
    )
    service = env.runtime.analytics
    snapshot = service.descriptive_snapshot

    def deleted_after_snapshot(*args, **kwargs):
        result = snapshot(*args, **kwargs)
        with service.uow() as repo:
            stored = repo.upload(UUID(wid), UUID(root.split("/")[4]), UUID(root.split("/")[6]))
        service.storage.delete(stored)
        return result

    monkeypatch.setattr(service, "descriptive_snapshot", deleted_after_snapshot)
    response = env.client.get(root + "/discovery", headers=owner)
    assert response.status_code == 503


def test_final_object_read_cannot_race_membership_revocation(integration, monkeypatch):
    env = integration
    owner, wid, root, _ = setup(env)
    service = env.runtime.analytics
    read = service.storage.read
    source_reads = 0

    def revoke_during_read(*args, **kwargs):
        nonlocal source_reads
        content = read(*args, **kwargs)
        source_reads += 1
        if source_reads == 2:
            with env.engine.begin() as connection:
                connection.execute(
                    delete(s.memberships).where(s.memberships.c.workspace_id == UUID(wid))
                )
        return content

    monkeypatch.setattr(service.storage, "read", revoke_during_read)
    response = env.client.get(root + "/discovery", headers=owner)
    assert source_reads == 2
    assert response.status_code == 404
    assert "findings" not in response.json()
