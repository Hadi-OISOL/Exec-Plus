"""Use case: Preserves source bytes when a successful commit loses its response.

What it does: Exercises real retained uploads, samples and documents under uncertain
commit, partial object writes and unavailable cleanup metadata without losing prior data.
"""

import asyncio
from contextlib import contextmanager
from io import BytesIO
from uuid import UUID

import pytest
from sqlalchemy import select

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_studies import prepare


@pytest.mark.parametrize("kind", ["upload", "sample", "document"])
@pytest.mark.parametrize("failure", ["committed", "partial_write", "unknown_metadata"])
def test_cleanup_preserves_durable_objects_and_discards_only_proven_orphans(
    integration, monkeypatch, kind, failure
):
    env = integration
    _, actor, raw_wid, raw_did, _, _ = prepare(env)
    wid, did = UUID(raw_wid), UUID(raw_did)
    service = env.runtime.knowledge if kind == "document" else env.runtime.service
    storage = service.storage
    original_uow = service.uow
    write_name = "put_document" if kind == "document" else "put"
    delete_name = "delete_document" if kind == "document" else "delete"
    write = getattr(storage, write_name)
    remove = getattr(storage, delete_name)
    captured, contents = [], []
    interrupted = False
    delete_checks = []

    def objects():
        result = env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket)
        return {item["Key"] for item in result.get("Contents", [])}

    def lookup(repo, item):
        if kind == "document":
            return repo.document(wid, item.id)
        return repo.upload(wid, item.dataset_id, item.id)

    def put(item, content):
        captured.append(item)
        if kind == "document":
            contents.append(content)
        else:
            position = content.tell()
            contents.append(content.read())
            content.seek(position)
        write(item, content)
        if failure != "committed":
            raise RuntimeError("Storage response interrupted")

    def delete(item):
        with env.engine.begin() as connection:
            connection.execute(
                select(s.workspaces.c.id)
                .where(s.workspaces.c.id == wid)
                .with_for_update(nowait=True)
            ).scalar_one()
        delete_checks.append(item.id)
        remove(item)

    @contextmanager
    def uncertain_uow():
        nonlocal interrupted
        if captured and failure == "unknown_metadata":
            raise RuntimeError("Metadata lookup unavailable")
        with original_uow() as repo:
            yield repo
        if captured and failure == "committed" and not interrupted:
            with original_uow() as repo:
                lookup(repo, captured[0])
            interrupted = True
            raise RuntimeError("Commit response interrupted after durable success")

    before = objects()
    monkeypatch.setattr(service, "uow", uncertain_uow)
    monkeypatch.setattr(storage, write_name, put)
    monkeypatch.setattr(storage, delete_name, delete)
    with pytest.raises(RuntimeError, match="response interrupted"):
        if kind == "document":
            asyncio.run(
                service.ingest(actor, wid, did, "reference.md", b"Retained evidence.", False)
            )
        elif kind == "sample":
            service.import_sample(actor, wid, "finance-v1")
        else:
            service.upload(actor, wid, did, "source.csv", "text/csv", BytesIO(b"amount\n0.10\n"))
    assert len(captured) == 1
    item = captured[0]
    after = objects()
    assert before <= after
    if failure == "partial_write":
        assert after == before and delete_checks == [item.id]
    else:
        assert len(after - before) == 1 and delete_checks == []
        restored = storage.read_document(item) if kind == "document" else storage.read(item)
        assert restored == contents[0]
    with original_uow() as repo:
        if failure == "committed":
            assert lookup(repo, item) == item
            if kind == "document":
                assert repo.document_chunks(wid, item.id)
            else:
                assert repo.active_revision(wid, item.dataset_id, item.id)
                assert repo.dataset(wid, item.dataset_id)
        else:
            with pytest.raises(IngestionError) as error:
                lookup(repo, item)
            assert error.value.status == 404
