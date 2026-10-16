"""Use case: Verifies source metadata and atomic upload publication with real persistence.

What it does: Exercises retained snapshots, idempotency, private authority epochs and
staged refresh while proving no external extraction runs inside a workspace lock.
"""

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from execplus.application.services.source_imports import SourceImportService
from execplus.domain.ingestion import IngestionError
from execplus.domain.source_imports import (
    ImportSelection,
    PostgresSource,
    SourceSnapshot,
    SourceTable,
)
from execplus.infrastructure.persistence import schema as s
from test_postgres_source import source_db as source_db
from test_studies import add_member, prepare


def setup(env):
    headers, actor, wid, did, uid, root = prepare(env)
    wid, did = UUID(wid), UUID(did)
    env.runtime.operations.change_staff(actor.email, "admin")
    table = SourceTable("public", "sales", ("city", "amount", "cost"))
    source = PostgresSource(
        uuid4(),
        wid,
        1,
        "Approved sales",
        "db.example.test",
        "192.0.2.42",
        5432,
        "warehouse",
        "secret-reference",
        (table,),
    )
    content = b"city,amount,cost\nKarachi,0.100000000000,0.05\nLahore,0.2,0.15\n"
    calls = []

    def read(config, selected):
        with env.engine.begin() as connection:
            connection.execute(
                select(s.workspaces.c.id)
                .where(s.workspaces.c.id == wid)
                .with_for_update(nowait=True)
            ).scalar_one()
        calls.append((config.id, selected))
        return SourceSnapshot(
            content,
            (("city", "text"), ("amount", "numeric"), ("cost", "numeric")),
            2,
            datetime.now(timezone.utc),
            config.version,
            hashlib.sha256(content).hexdigest(),
        )

    extractor = SimpleNamespace(read=read)
    service = SourceImportService(
        env.runtime.service.uow, extractor, env.runtime.service, env.runtime.refresh
    )
    result = service.register(actor, source, 0)
    assert "host" not in result and "secret_ref" not in result
    selection = ImportSelection(source.id, 1, did, table)
    return SimpleNamespace(
        service=service,
        source=source,
        selection=selection,
        headers=headers,
        actor=actor,
        wid=wid,
        did=did,
        uid=UUID(uid),
        root=root,
        content=content,
        calls=calls,
        extractor=extractor,
    )


def test_complete_import_is_exact_idempotent_private_and_unconfirmed(integration):
    env = integration
    f = setup(env)
    request_id = uuid4()
    result = f.service.start(f.actor, f.wid, request_id, f.selection)
    assert result.status == "imported" and result.upload_id is not None
    assert len(f.calls) == 1
    assert f.service.start(f.actor, f.wid, request_id, f.selection) == result
    assert len(f.calls) == 1
    assert env.runtime.service.download(f.actor, f.wid, f.did, result.upload_id) == f.content
    assert f.service.open(f.actor, f.wid, result.id) == result
    with env.runtime.service.uow() as repo:
        assert repo.latest_understanding(f.wid, f.did).upload_id == f.uid
    with pytest.raises(IngestionError) as conflict:
        f.service.start(f.actor, f.wid, request_id, replace(f.selection, source_version=2))
    assert conflict.value.code == "idempotency_conflict"
    _, member = add_member(env, f.headers, str(f.wid), "admin")
    with pytest.raises(IngestionError):
        f.service.open(member, f.wid, result.id)
    with pytest.raises(IngestionError):
        f.service.catalog(member, f.wid)


@pytest.mark.parametrize("change", ["source", "disconnect", "policy", "membership"])
def test_changed_import_authority_never_publishes_upload(integration, monkeypatch, change):
    from datetime import timedelta

    from sqlalchemy import update

    env = integration
    f = setup(env)
    read = f.extractor.read

    def changed(*args):
        result = read(*args)
        if change == "source":
            f.service.register(f.actor, replace(f.source, version=2), 1)
        elif change == "disconnect":
            f.service.disconnect(f.actor, f.wid, f.source.id, 1)
        elif change == "policy":
            env.runtime.access_policies.save(
                f.actor,
                f.wid,
                f.did,
                0,
                True,
                [
                    {"user_id": str(f.actor.id), "columns": None, "conditions": []},
                ],
            )
        else:
            with env.engine.begin() as connection:
                connection.execute(
                    update(s.memberships)
                    .where(
                        s.memberships.c.workspace_id == f.wid,
                        s.memberships.c.user_id == f.actor.id,
                    )
                    .values(created_at=s.memberships.c.created_at + timedelta(seconds=1))
                )
        return result

    monkeypatch.setattr(f.extractor, "read", changed)
    with pytest.raises(IngestionError):
        f.service.start(f.actor, f.wid, uuid4(), f.selection)
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.uploads.c.id)).all()) == 1
        assert connection.execute(select(s.source_imports.c.status)).scalar_one() == "failed"
    objects = env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket)
    assert len(objects.get("Contents", [])) == 1


def test_extraction_failure_has_no_upload_and_never_repeats_implicitly(integration, monkeypatch):
    env = integration
    f = setup(env)
    calls = 0

    def broken(*args):
        nonlocal calls
        calls += 1
        raise RuntimeError("SECRET provider hostname and password")

    monkeypatch.setattr(f.extractor, "read", broken)
    request_id = uuid4()
    with pytest.raises(IngestionError) as caught:
        f.service.start(f.actor, f.wid, request_id, f.selection)
    assert "SECRET" not in str(caught.value)
    again = f.service.start(f.actor, f.wid, request_id, f.selection)
    assert again.status == "failed" and again.failure_code == "source_import_failed"
    assert calls == 1


def test_source_refresh_is_staged_then_explicitly_activated(integration):
    env = integration
    f = setup(env)
    with env.runtime.service.uow() as repo:
        revision = repo.active_revision(f.wid, f.did, f.uid)
        meaning = repo.latest_understanding(f.wid, f.did)
    feed = env.runtime.refresh.configure(
        f.actor,
        f.wid,
        f.did,
        f.uid,
        revision.id,
        meaning.id,
        0,
        1,
        48,
        True,
        datetime.now(timezone.utc),
    )
    chosen = replace(f.selection, mode="refresh", expected_feed_version=feed.version)
    result = f.service.start(f.actor, f.wid, uuid4(), chosen)
    assert result.status == "staged" and result.candidate_id is not None
    with env.runtime.service.uow() as repo:
        assert repo.refresh_feed(f.wid, feed.id).source["upload_id"] == str(f.uid)
        candidate = repo.refresh_candidate(f.wid, result.candidate_id)
        assert candidate.status == "queued"
        assert candidate.details["input_upload_id"] == str(result.upload_id)
        assert repo.latest_understanding(f.wid, f.did) == meaning
    env.runtime.refresh.activate(f.actor, f.wid, result.candidate_id)
    with env.runtime.service.uow() as repo:
        assert repo.refresh_feed(f.wid, feed.id).source["upload_id"] == str(result.upload_id)
    assert env.runtime.service.download(f.actor, f.wid, f.did, result.upload_id) == f.content


def test_snapshot_header_mismatch_rolls_back_entire_upload(integration, monkeypatch):
    env = integration
    f = setup(env)
    read = f.extractor.read

    def wrong(*args):
        snapshot = read(*args)
        content = snapshot.content.replace(b"city,amount,cost", b"city,salary,cost")
        return replace(snapshot, content=content, checksum=hashlib.sha256(content).hexdigest())

    monkeypatch.setattr(f.extractor, "read", wrong)
    with pytest.raises(IngestionError):
        f.service.start(f.actor, f.wid, uuid4(), f.selection)
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.uploads.c.id)).all()) == 1
    objects = env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket)
    assert len(objects.get("Contents", [])) == 1


def test_real_readonly_database_snapshot_reaches_retained_upload(integration, source_db):
    env = integration
    f = setup(env)
    f.service.extractor = source_db.adapter
    actual = replace(source_db.source, workspace_id=f.wid)
    f.service.register(f.actor, actual, 0)
    selected = ImportSelection(actual.id, actual.version, f.did, source_db.selection)
    before = source_db.admin.execute("SELECT * FROM samples ORDER BY id").fetchall()
    result = f.service.start(f.actor, f.wid, uuid4(), selected)
    content = env.runtime.service.download(f.actor, f.wid, f.did, result.upload_id)
    assert b"0.100000000000" in content
    assert result.snapshot["row_count"] == 2
    assert source_db.admin.execute("SELECT * FROM samples ORDER BY id").fetchall() == before


def test_recovery_requires_time_and_blocks_late_publication(integration, monkeypatch):
    from datetime import timedelta

    import execplus.application.services.source_imports as module

    env = integration
    f = setup(env)
    read = f.extractor.read
    recovered = False

    def interrupted(*args):
        nonlocal recovered
        snapshot = read(*args)
        with env.runtime.service.uow() as repo:
            attempt = repo.source_imports(f.wid, f.actor.id, f.did)[0]
        with pytest.raises(IngestionError) as pending:
            f.service.recover(f.actor, f.wid, attempt.id)
        assert pending.value.code == "source_import_pending"
        monkeypatch.setattr(module, "now", lambda: attempt.created_at + timedelta(minutes=6))
        assert f.service.recover(f.actor, f.wid, attempt.id).failure_code == "source_interrupted"
        recovered = True
        return snapshot

    monkeypatch.setattr(f.extractor, "read", interrupted)
    with pytest.raises(IngestionError):
        f.service.start(f.actor, f.wid, uuid4(), f.selection)
    assert recovered
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.uploads.c.id)).all()) == 1
        assert (
            connection.execute(select(s.source_imports.c.failure_code)).scalar_one()
            == "source_interrupted"
        )


def test_owner_api_never_exposes_connection_material_and_rechecks_role(integration):
    import json

    env = integration
    f = setup(env)
    env.runtime.source_imports = f.service
    path = f"/workspaces/{f.wid}"
    response = env.client.get(path + "/sources", headers=f.headers)
    assert response.status_code == 200
    body = json.dumps(response.json())
    assert all(
        value not in body
        for value in ["db.example.test", "192.0.2.42", "warehouse", "secret-reference"]
    )
    request = dict(
        request_id=str(uuid4()),
        source_id=str(f.source.id),
        source_version=1,
        schema_name="public",
        table="sales",
        columns=list(f.selection.table.columns),
    )
    imported = env.client.post(
        path + f"/datasets/{f.did}/source-imports", headers=f.headers, json=request
    )
    assert imported.status_code == 201, imported.text
    saved = imported.json()
    assert saved["status"] == "imported" and "access_reference" not in saved
    assert (
        env.client.get(path + "/source-imports/" + saved["id"], headers=f.headers).json() == saved
    )
    assert env.client.get(path + f"/datasets/{f.did}/source-imports", headers=f.headers).json()[
        "imports"
    ] == [saved]
    member, _ = add_member(env, f.headers, str(f.wid), "admin")
    assert env.client.get(path + "/sources", headers=member).status_code == 403
    assert (
        env.client.get(path + "/source-imports/" + saved["id"], headers=member).status_code == 404
    )
    assert (
        env.client.post(
            path + f"/datasets/{f.did}/source-imports", headers=member, json=request
        ).status_code
        == 403
    )
    env.runtime.operations.change_staff(f.actor.email, None)
    assert (
        env.client.get(
            f"/admin/workspaces/{f.wid}/source-imports/pending", headers=f.headers
        ).status_code
        == 403
    )
    assert (
        env.client.post(
            path + f"/sources/{f.source.id}/disconnect",
            headers=f.headers,
            json={"expected_version": 1},
        ).status_code
        == 200
    )
    assert (
        env.client.get(path + "/source-imports/" + saved["id"], headers=f.headers).status_code
        == 200
    )
    assert (
        env.client.post(
            path + f"/datasets/{f.did}/source-imports",
            headers=f.headers,
            json=request | {"request_id": str(uuid4()), "source_version": 2},
        ).status_code
        == 404
    )


def test_authority_change_during_object_write_rolls_back_both_publications(
    integration, monkeypatch
):
    env = integration
    f = setup(env)
    original = env.runtime.service.storage.put
    changed = False

    def write(*args):
        nonlocal changed
        original(*args)
        if not changed:
            changed = True
            f.service.disconnect(f.actor, f.wid, f.source.id, 1)

    monkeypatch.setattr(env.runtime.service.storage, "put", write)
    with pytest.raises(IngestionError):
        f.service.start(f.actor, f.wid, uuid4(), f.selection)
    assert changed
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.uploads.c.id)).all()) == 1
        assert connection.execute(select(s.source_imports.c.status)).scalar_one() == "failed"
    assert (
        len(env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket)["Contents"]) == 1
    )


def test_uncertain_upload_commit_reopens_the_atomic_import_and_retains_bytes(
    integration, monkeypatch
):
    from contextlib import contextmanager

    env = integration
    f = setup(env)
    uploads = env.runtime.service
    original = uploads.uow
    interrupted = False

    @contextmanager
    def uncertain():
        nonlocal interrupted
        with original() as repo:
            yield repo
        with original() as repo:
            records = repo.source_imports(f.wid, f.actor.id, f.did)
        if not interrupted and records and records[0].status == "imported":
            interrupted = True
            raise RuntimeError("Commit succeeded before connection loss")

    monkeypatch.setattr(uploads, "uow", uncertain)
    result = f.service.start(f.actor, f.wid, uuid4(), f.selection)
    assert interrupted and result.status == "imported"
    assert uploads.download(f.actor, f.wid, f.did, result.upload_id) == f.content
    assert len(f.calls) == 1


def test_concurrent_same_request_extracts_once_and_can_reopen(integration, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    env = integration
    f = setup(env)
    started, release = Event(), Event()
    read = f.extractor.read

    def wait(*args):
        started.set()
        assert release.wait(timeout=5)
        return read(*args)

    monkeypatch.setattr(f.extractor, "read", wait)
    request_id = uuid4()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(f.service.start, f.actor, f.wid, request_id, f.selection)
        try:
            assert started.wait(timeout=5)
            with pytest.raises(IngestionError) as pending:
                f.service.start(f.actor, f.wid, request_id, f.selection)
            assert pending.value.code == "source_import_pending"
        finally:
            release.set()
        result = future.result(timeout=5)
    assert len(f.calls) == 1
    assert f.service.start(f.actor, f.wid, request_id, f.selection) == result


def test_capacity_and_operator_recovery_preserve_unknown_attempts(integration):
    from datetime import timedelta

    from execplus.domain.source_imports import SourceImport

    env = integration
    f = setup(env)
    created = datetime.now(timezone.utc) - timedelta(minutes=6)
    with env.runtime.service.uow() as repo:
        epoch = repo.membership(f.wid, f.actor.id).created_at
        for _ in range(4):
            repo.add_source_import(
                SourceImport(
                    uuid4(),
                    f.wid,
                    f.actor.id,
                    epoch,
                    uuid4(),
                    f.selection,
                    {},
                    "extracting",
                    created,
                )
            )
    with pytest.raises(IngestionError) as busy:
        f.service.start(f.actor, f.wid, uuid4(), f.selection)
    assert busy.value.code == "source_import_busy" and not f.calls
    pending = f.service.pending(f.actor, f.wid)
    assert len(pending) == 4
    assert set(pending[0]) == {"id", "dataset_id", "created_at", "status"}
    env.runtime.access_policies.save(
        f.actor,
        f.wid,
        f.did,
        0,
        True,
        [
            {"user_id": str(f.actor.id), "columns": None, "conditions": []},
        ],
    )
    recovered = f.service.recover(f.actor, f.wid, UUID(pending[0]["id"]))
    assert recovered.failure_code == "source_interrupted"
    assert len(f.service.pending(f.actor, f.wid)) == 3
