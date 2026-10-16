"""Use case: Verifies a current-version recovery in an isolated Docker network.

What it does: Checks every retained source, revision and document passage, fingerprints
all tables and replays bounded executed receipts without contacting the live services.
"""

import argparse
import asyncio
import hashlib
import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
from typing import Any, cast
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import Engine, select, text
from sqlalchemy.engine import make_url

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.analytics import UnitOfWork
from execplus.application.services.dataset_access import authorize_sources
from execplus.bootstrap import Runtime, build_runtime
from execplus.config import Settings
from execplus.domain.ingestion import IngestionError, Upload, User
from execplus.domain.knowledge import Document, document_text
from execplus.domain.profiling import Revision, reconstruct
from execplus.infrastructure.persistence import schema as s


def snapshot_reads(uow: UnitOfWork) -> UnitOfWork:
    """Keep database read-only; an exclusive restored snapshot needs no write locks."""

    class SnapshotRepository:
        def __init__(self, repo: WorkspaceRepository) -> None:
            self.repo = repo

        def workspace(self, workspace_id: UUID, lock: bool = False) -> Any:
            return self.repo.workspace(workspace_id, lock=False)

        def __getattr__(self, name: str) -> Any:
            return getattr(self.repo, name)

    @contextmanager
    def transaction() -> Iterator[WorkspaceRepository]:
        with uow() as repo:
            yield cast(WorkspaceRepository, SnapshotRepository(repo))

    return transaction


def isolated_settings(settings: Settings, name: str) -> Settings:
    """An operator-chosen label can never select the running database or storage."""
    if not re.fullmatch(r"execplus_restore_[a-f0-9]{12}", name):
        raise ValueError("Use an isolated execplus_restore_ label and twelve hex characters.")
    if settings.environment not in {"local", "test"}:
        raise ValueError("This private recovery rehearsal does not operate on production.")
    database = make_url(settings.database_url).set(
        host=name + "_db",
        port=5432,
        database=name,
        query={"options": "-c default_transaction_read_only=on"},
    )
    endpoint = "http://" + name.replace("_", "-") + "-objects:9000"
    if urlparse(endpoint).hostname == urlparse(settings.object_store_endpoint).hostname:
        raise ValueError("The restored store must be separate from the configured store.")
    return settings.model_copy(
        update={
            "database_url": database.render_as_string(hide_password=False),
            "object_store_endpoint": endpoint,
            "llm_mode": "disabled",
            "llm_selection_base_url": "",
            "llm_selection_model": "",
        }
    )


def fingerprints(engine: Engine) -> dict[str, Any]:
    result: dict[str, Any] = {}
    with engine.connect() as connection:
        for table in sorted(s.metadata.tables.values(), key=lambda item: item.name):
            digest, count = hashlib.sha256(), 0
            for row in connection.execute(
                select(table).order_by(*table.primary_key.columns)
            ).mappings():
                digest.update(
                    json.dumps(
                        dict(row),
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                        ensure_ascii=False,
                        allow_nan=False,
                    ).encode()
                )
                digest.update(b"\n")
                count += 1
            result[table.name] = {"rows": count, "sha256": digest.hexdigest()}
    return result


def verify_objects(runtime: Runtime) -> dict[str, int]:
    counts = dict(uploads=0, revisions=0, documents=0, passages=0)
    with runtime.engine.connect() as connection:
        for row in connection.execute(select(s.uploads)).mappings():
            upload = Upload(**row)
            content = runtime.analytics.storage.read(upload)
            table = runtime.analytics.parser.read_table(BytesIO(content), upload.format)
            counts["uploads"] += 1
            for revision_row in connection.execute(
                select(s.revisions).where(
                    s.revisions.c.workspace_id == upload.workspace_id,
                    s.revisions.c.upload_id == upload.id,
                )
            ).mappings():
                revision = Revision(**revision_row)
                if revision.source_checksum != upload.checksum:
                    raise ValueError("A recovered revision refers to different original bytes.")
                reconstruct(table, revision)
                counts["revisions"] += 1
        for row in connection.execute(select(s.documents)).mappings():
            document = Document(**row)
            content = runtime.knowledge.storage.read_document(document)
            body = document_text(document.name, content)
            counts["documents"] += 1
            for chunk in connection.execute(
                select(s.document_chunks).where(
                    s.document_chunks.c.workspace_id == document.workspace_id,
                    s.document_chunks.c.document_id == document.id,
                )
            ).mappings():
                if not 0 <= chunk["start"] < chunk["end"] <= len(body):
                    raise ValueError("A recovered passage has invalid source boundaries.")
                actual = hashlib.sha256(body[chunk["start"] : chunk["end"]].encode()).hexdigest()
                if actual != chunk["checksum"]:
                    raise ValueError("A recovered passage differs from its original document.")
                counts["passages"] += 1
    return counts


async def verify_receipts(runtime: Runtime, limit: int) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise ValueError("Choose one to one hundred restored receipt replays.")
    with runtime.engine.connect() as connection:
        candidates = list(
            connection.execute(
                select(s.query_executions)
                .join(
                    s.memberships,
                    (
                        (s.memberships.c.workspace_id == s.query_executions.c.workspace_id)
                        & (s.memberships.c.user_id == s.query_executions.c.actor_id)
                    ),
                )
                .order_by(s.query_executions.c.created_at.desc())
            ).mappings()
        )
        users = {row["id"]: User(**row) for row in connection.execute(select(s.users)).mappings()}
    usable = [
        row
        for row in candidates
        if row["receipt"].get("version") == "execution-v1"
        and row["receipt"].get("outcome", "executed") == "executed"
    ]
    chosen: list[Any] = []
    methods: set[str] = set()
    for row in usable:
        if row["aggregation"] not in methods:
            chosen.append(row)
            methods.add(row["aggregation"])
            if len(chosen) == limit:
                break
    chosen_ids = {row["id"] for row in chosen}
    chosen.extend(row for row in usable if row["id"] not in chosen_ids)
    executed: dict[str, int] = {}
    denied = 0
    checked = 0
    for row in chosen:
        if sum(executed.values()) >= limit or checked >= 100:
            break
        checked += 1
        actor = users[row["actor_id"]]
        sources = row["receipt"].get("sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError("An executed recovery receipt has no recorded sources.")
        with runtime.service.uow() as repo:
            for source in sources:
                repo.dataset(row["workspace_id"], UUID(source["dataset_id"]))
            try:
                authorize_sources(repo, actor, row["workspace_id"], sources)
            except IngestionError as error:
                if error.code != "not_found":
                    raise
                permission_denied = True
            else:
                permission_denied = False
        if permission_denied:
            try:
                await runtime.analytics.replay(actor, row["workspace_id"], row["id"])
            except IngestionError as error:
                if error.code != "not_found":
                    raise
                denied += 1
                continue
            raise ValueError("A restored receipt bypassed its current access policy.")
        await runtime.analytics.replay(actor, row["workspace_id"], row["id"])
        executed[row["aggregation"]] = executed.get(row["aggregation"], 0) + 1
    return {
        "eligible_receipts": len(usable),
        "replayed": sum(executed.values()),
        "operations": executed,
        "permission_denials_verified": denied,
        "candidates_checked": checked,
        "candidate_check_limit": 100,
    }


async def verify(settings: Settings, expected_migration: str, limit: int) -> dict[str, Any]:
    if not re.fullmatch(
        r"execplus_restore_[a-f0-9]{12}", make_url(settings.database_url).database or ""
    ):
        raise ValueError("Snapshot replay requires an isolated restored database.")
    runtime = build_runtime(settings)
    runtime.analytics.uow = snapshot_reads(runtime.analytics.uow)
    try:
        with runtime.engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        if version != expected_migration:
            raise ValueError("The restored schema does not match the declared application version.")
        before = fingerprints(runtime.engine)
        objects = verify_objects(runtime)
        receipts = await verify_receipts(runtime, limit)
        if fingerprints(runtime.engine) != before:
            raise ValueError("Verification changed the restored database unexpectedly.")
        return {
            "scope": "isolated-private-demo-recovery",
            "migration": version,
            "tables": before,
            "verified_objects": objects,
            "receipts": receipts,
            "database_unchanged": True,
            "passed": True,
        }
    finally:
        runtime.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--expected-migration", required=True)
    parser.add_argument("--replay-limit", type=int, default=20)
    args = parser.parse_args()
    settings = isolated_settings(Settings(), args.name)
    print(json.dumps(asyncio.run(verify(settings, args.expected_migration, args.replay_limit))))


if __name__ == "__main__":
    main()
