"""Use case: Prevents refresh I/O from holding revocation locks or publishing stale work.

What it does: Uses independent NOWAIT transactions and exact source, authority,
feed and candidate mutations to verify two-phase refresh publication and cleanup.
"""

import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_refresh import setup, stage


def objects(env):
    result = env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket)
    return {item["Key"] for item in result.get("Contents", [])}


def mutate(env, actor, wid, did, feed, candidate, change):
    service = env.runtime.refresh
    if change in {"policy", "policy_cycle"}:
        env.runtime.access_policies.save(
            actor,
            wid,
            did,
            0,
            True,
            [
                {"user_id": str(actor.id), "columns": None, "conditions": []},
            ],
        )
        if change == "policy_cycle":
            env.runtime.access_policies.save(actor, wid, did, 1, False, [])
    elif change == "membership":
        with env.engine.begin() as connection:
            connection.execute(
                update(s.memberships)
                .where(
                    s.memberships.c.workspace_id == wid,
                    s.memberships.c.user_id == actor.id,
                )
                .values(created_at=s.memberships.c.created_at + timedelta(seconds=1))
            )
    elif change != "none":
        with service.uow() as repo:
            repo.workspace(wid, lock=True)
            if change == "feed":
                repo.set_refresh_feed(replace(feed, version=feed.version + 1))
            elif change == "meaning":
                meaning = repo.latest_understanding(wid, did)
                repo.add(replace(meaning, id=uuid4(), version=meaning.version + 1))
            elif change == "source":
                uid = UUID(feed.source["upload_id"])
                revision = repo.active_revision(wid, did, uid)
                changed = replace(revision, id=uuid4(), parent_id=revision.id)
                repo.add(changed)
                repo.set_active_revision(changed)
            elif change == "staged":
                uid = UUID(candidate.details["output_upload_id"])
                revision = repo.active_revision(wid, did, uid)
                changed = replace(revision, id=uuid4(), parent_id=revision.id)
                repo.add(changed)
                repo.set_active_revision(changed)
            elif change == "candidate":
                repo.set_refresh_candidate(replace(candidate, status="rejected"))
            else:
                raise AssertionError(change)


def operation(env, actor, wid, did, feed, candidate, name):
    refresh = env.runtime.refresh
    if name == "configure":
        source = feed.source
        return refresh.configure(
            actor,
            wid,
            did,
            UUID(source["upload_id"]),
            UUID(source["revision_id"]),
            UUID(source["understanding_id"]),
            feed.version,
            1,
            48,
            True,
            datetime.now(timezone.utc),
        )
    if name == "stage":
        return refresh.stage(
            actor,
            wid,
            did,
            uuid4(),
            feed.version,
            "replacement.csv",
            "text/csv",
            b"city,amount\nKarachi,0.40\nLahore,0.20\n",
            "replace",
            [],
            "keep_all",
            datetime.now(timezone.utc),
            None,
            None,
        )
    if name == "review":
        return refresh.review(actor, wid, candidate.id, candidate.details["definition"], False)
    return refresh.activate(actor, wid, candidate.id)


@pytest.mark.parametrize("name", ["configure", "stage", "review", "activate"])
@pytest.mark.parametrize(
    "change", ["none", "policy", "policy_cycle", "membership", "source", "meaning", "feed"]
)
def test_refresh_reads_release_lock_then_recheck_exact_state(
    integration, monkeypatch, name, change
):
    env = integration
    headers, actor, raw_wid, raw_did, _, path, _ = setup(env)
    wid, did = UUID(raw_wid), UUID(raw_did)
    cid = UUID(stage(env, headers, path).json()["id"]) if name in {"review", "activate"} else None
    with env.runtime.refresh.uow() as repo:
        feed = repo.refresh_feeds(wid, did)[0]
        candidate = repo.refresh_candidate(wid, cid) if cid else None
        candidates = repo.refresh_candidates(wid, feed.id)
    before = objects(env)
    original = env.runtime.service.storage.read
    checked = False

    def read(upload):
        nonlocal checked
        result = original(upload)
        if not checked:
            checked = True
            with env.engine.begin() as connection:
                connection.execute(
                    select(s.workspaces.c.id)
                    .where(
                        s.workspaces.c.id == wid,
                    )
                    .with_for_update(nowait=True)
                ).scalar_one()
            mutate(env, actor, wid, did, feed, candidate, change)
        return result

    monkeypatch.setattr(env.runtime.service.storage, "read", read)
    if change == "none":
        result = operation(env, actor, wid, did, feed, candidate, name)
        assert result
    else:
        with pytest.raises(IngestionError) as caught:
            operation(env, actor, wid, did, feed, candidate, name)
        assert caught.value.status in {404, 409}
        assert objects(env) == before
        with env.runtime.refresh.uow() as repo:
            assert repo.refresh_candidates(wid, feed.id) == candidates
    assert checked


@pytest.mark.parametrize("name", ["review", "activate"])
@pytest.mark.parametrize("change", ["staged", "candidate"])
def test_refresh_review_and_activation_recheck_staged_snapshot_and_review(
    integration,
    monkeypatch,
    name,
    change,
):
    env = integration
    headers, actor, raw_wid, raw_did, _, path, _ = setup(env)
    wid, did = UUID(raw_wid), UUID(raw_did)
    cid = UUID(stage(env, headers, path).json()["id"])
    with env.runtime.refresh.uow() as repo:
        feed = repo.refresh_feeds(wid, did)[0]
        candidate = repo.refresh_candidate(wid, cid)
    original = env.runtime.service.storage.read
    checked = False

    def read(upload):
        nonlocal checked
        result = original(upload)
        if not checked:
            checked = True
            mutate(env, actor, wid, did, feed, candidate, change)
        return result

    monkeypatch.setattr(env.runtime.service.storage, "read", read)
    with pytest.raises(IngestionError) as caught:
        operation(env, actor, wid, did, feed, candidate, name)
    assert caught.value.code == "refresh_conflict"
    assert checked
    with env.runtime.refresh.uow() as repo:
        assert repo.refresh_feed(wid, feed.id) == feed
        actual = repo.refresh_candidate(wid, cid)
        assert actual.status == ("rejected" if change == "candidate" else "queued")


@pytest.mark.parametrize("boundary", ["parse", "put", "delete"])
def test_stage_parse_write_and_cleanup_hold_no_workspace_lock(integration, monkeypatch, boundary):
    env = integration
    _, actor, raw_wid, raw_did, _, _, _ = setup(env)
    wid, did = UUID(raw_wid), UUID(raw_did)
    with env.runtime.refresh.uow() as repo:
        feed = repo.refresh_feeds(wid, did)[0]
    before = objects(env)
    target = env.runtime.service.parser if boundary == "parse" else env.runtime.service.storage
    original = getattr(target, boundary)
    checked = False

    def call(*args, **kwargs):
        nonlocal checked
        with env.engine.begin() as connection:
            connection.execute(
                select(s.workspaces.c.id)
                .where(
                    s.workspaces.c.id == wid,
                )
                .with_for_update(nowait=True)
            ).scalar_one()
        checked = True
        return original(*args, **kwargs)

    monkeypatch.setattr(target, boundary, call)
    if boundary == "delete":
        put = env.runtime.service.storage.put

        def failed_put(*args):
            put(*args)
            raise RuntimeError("private storage failure")

        monkeypatch.setattr(env.runtime.service.storage, "put", failed_put)
    result = operation(env, actor, wid, did, feed, None, "stage")
    assert checked
    assert result.status == ("failed" if boundary == "delete" else "queued")
    if boundary == "delete":
        assert objects(env) == before


def test_activation_rechecks_candidate_creator_membership_epoch(integration, monkeypatch):
    from test_studies import add_member

    env = integration
    owner, actor, raw_wid, raw_did, _, path, _ = setup(env)
    teammate, creator = add_member(env, owner, raw_wid, "admin")
    cid = UUID(stage(env, teammate, path).json()["id"])
    wid, did = UUID(raw_wid), UUID(raw_did)
    read = env.runtime.service.storage.read

    def change(upload):
        result = read(upload)
        with env.engine.begin() as connection:
            connection.execute(
                update(s.memberships)
                .where(
                    s.memberships.c.workspace_id == wid,
                    s.memberships.c.user_id == creator.id,
                )
                .values(created_at=s.memberships.c.created_at + timedelta(seconds=1))
            )
        return result

    monkeypatch.setattr(env.runtime.service.storage, "read", change)
    with pytest.raises(IngestionError) as caught:
        env.runtime.refresh.activate(actor, wid, cid)
    assert caught.value.status == 404
    with env.runtime.refresh.uow() as repo:
        assert repo.refresh_candidate(wid, cid).status == "queued"
        assert repo.refresh_feeds(wid, did)[0].version == 1


def test_concurrent_stage_publishes_once_and_cleans_only_its_duplicate_objects(
    integration, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    env = integration
    _, actor, raw_wid, raw_did, _, _, _ = setup(env)
    wid, did = UUID(raw_wid), UUID(raw_did)
    before = objects(env)
    barrier = Barrier(2)
    put = env.runtime.service.storage.put

    def write(*args):
        result = put(*args)
        barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(env.runtime.service.storage, "put", write)
    request_id, as_of = uuid4(), datetime.now(timezone.utc)

    def run(_):
        return env.runtime.refresh.stage(
            actor,
            wid,
            did,
            request_id,
            1,
            "refresh.csv",
            "text/csv",
            b"city,amount\nKarachi,0.4\n",
            "replace",
            [],
            "keep_all",
            as_of,
            None,
            None,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(run, range(2)))
    serialized = [json.loads(json.dumps(asdict(value), default=str)) for value in values]
    assert serialized[0] == serialized[1]
    assert values[0].status == "queued"
    after = objects(env)
    assert before < after and len(after - before) == 1
    with env.runtime.refresh.uow() as repo:
        assert len(repo.refresh_candidates(wid, values[0].feed_id)) == 1
        retained = repo.upload(wid, did, UUID(values[0].details["output_upload_id"]))
    assert retained.storage_key in after


def test_unpublished_partial_storage_error_does_not_leave_orphan_object(integration, monkeypatch):
    env = integration
    _, actor, raw_wid, raw_did, _, _, _ = setup(env)
    wid, did = UUID(raw_wid), UUID(raw_did)
    before = objects(env)
    put = env.runtime.service.storage.put

    def write(*args):
        put(*args)
        raise IngestionError("unsupported_file", "No record may refer to this object.", 422)

    monkeypatch.setattr(env.runtime.service.storage, "put", write)
    with env.runtime.refresh.uow() as repo:
        feed = repo.refresh_feeds(wid, did)[0]
    result = operation(env, actor, wid, did, feed, None, "stage")
    assert result.status == "failed"
    assert objects(env) == before
    assert "output_upload_id" not in result.details and "input_upload_id" not in result.details


def test_unknown_commit_outcome_keeps_the_retained_candidate_object(integration, monkeypatch):
    from contextlib import contextmanager

    env = integration
    _, actor, raw_wid, raw_did, _, _, _ = setup(env)
    wid, did = UUID(raw_wid), UUID(raw_did)
    service = env.runtime.refresh
    original = service.uow
    raised = False
    with original() as repo:
        feed = repo.refresh_feeds(wid, did)[0]

    @contextmanager
    def uncertain_commit():
        nonlocal raised
        with original() as repo:
            yield repo
        if not raised:
            with original() as repo:
                retained = repo.refresh_candidates(wid, feed.id)
            if retained:
                raised = True
                raise RuntimeError("Commit response was interrupted after durable success")

    monkeypatch.setattr(service, "uow", uncertain_commit)
    with pytest.raises(RuntimeError, match="Commit response"):
        operation(env, actor, wid, did, feed, None, "stage")
    assert raised
    with original() as repo:
        candidates = repo.refresh_candidates(wid, feed.id)
        assert len(candidates) == 1
        candidate = candidates[0]
        retained = repo.upload(wid, did, UUID(candidate.details["output_upload_id"]))
    assert retained.storage_key in objects(env)
    assert service.activate(actor, wid, candidate.id).status == "activated"
