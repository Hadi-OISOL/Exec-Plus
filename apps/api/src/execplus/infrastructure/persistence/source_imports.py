"""Use case: Persists immutable source versions and idempotent import state.

What it does: Uses the caller's workspace transaction to bind retained uploads to
source, actor and selection versions without opening external source connections.
"""

from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, func, insert, select, update

from execplus.domain.source_imports import (
    ImportSelection,
    PostgresSource,
    RegisteredSource,
    SourceImport,
    SourceTable,
    invalid,
)
from execplus.infrastructure.persistence import schema as s


def source_record(raw: Any) -> RegisteredSource:
    data = dict(raw)
    config = dict(data.pop("configuration"))
    config["tables"] = tuple(
        SourceTable(item["schema"], item["table"], tuple(item["columns"]))
        for item in config["tables"]
    )
    source = PostgresSource(data.pop("id"), data.pop("workspace_id"), data.pop("version"), **config)
    return RegisteredSource(source, **data)


def import_record(raw: Any) -> SourceImport:
    data = dict(raw)
    chosen = dict(data.pop("selection"))
    table = chosen.pop("table")
    chosen["table"] = SourceTable(table["schema"], table["table"], tuple(table["columns"]))
    chosen.update(
        source_id=data.pop("source_id"),
        source_version=data.pop("source_version"),
        dataset_id=data.pop("dataset_id"),
    )
    return SourceImport(**data, selection=ImportSelection(**chosen))


def import_values(value: SourceImport) -> dict[str, Any]:
    raw = asdict(value)
    chosen = raw.pop("selection")
    for key in ("source_id", "source_version", "dataset_id"):
        raw[key] = chosen.pop(key)
    raw["selection"] = chosen
    return raw


class SQLSourceMetadataRepository:
    connection: Connection

    def registered_sources(self, workspace_id: UUID) -> tuple[RegisteredSource, ...]:
        rows = self.connection.execute(
            select(s.registered_sources)
            .where(
                s.registered_sources.c.workspace_id == workspace_id,
            )
            .distinct(s.registered_sources.c.id)
            .order_by(
                s.registered_sources.c.id,
                s.registered_sources.c.version.desc(),
            )
        ).mappings()
        return tuple(source_record(row) for row in rows)

    def registered_source(
        self,
        workspace_id: UUID,
        source_id: UUID,
        version: int | None = None,
    ) -> RegisteredSource:
        query = select(s.registered_sources).where(
            s.registered_sources.c.workspace_id == workspace_id,
            s.registered_sources.c.id == source_id,
        )
        if version is not None:
            query = query.where(s.registered_sources.c.version == version)
        row = (
            self.connection.execute(
                query.order_by(
                    s.registered_sources.c.version.desc(),
                ).limit(1)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise invalid("source_unavailable", "This source is unavailable.", 404)
        return source_record(row)

    def add_registered_source(self, value: RegisteredSource) -> None:
        config = asdict(value.source)
        identity = {key: config.pop(key) for key in ("workspace_id", "id", "version")}
        self.connection.execute(
            insert(s.registered_sources).values(
                **identity,
                configuration=config,
                created_by=value.created_by,
                created_at=value.created_at,
            )
        )

    def source_import_request(
        self,
        workspace_id: UUID,
        actor_id: UUID,
        request_id: UUID,
    ) -> SourceImport | None:
        row = (
            self.connection.execute(
                select(s.source_imports).where(
                    s.source_imports.c.workspace_id == workspace_id,
                    s.source_imports.c.actor_id == actor_id,
                    s.source_imports.c.request_id == request_id,
                )
            )
            .mappings()
            .first()
        )
        return import_record(row) if row else None

    def source_import(self, workspace_id: UUID, actor_id: UUID, import_id: UUID) -> SourceImport:
        row = (
            self.connection.execute(
                select(s.source_imports).where(
                    s.source_imports.c.workspace_id == workspace_id,
                    s.source_imports.c.actor_id == actor_id,
                    s.source_imports.c.id == import_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise invalid("not_found", "This import is unavailable.", 404)
        return import_record(row)

    def source_imports(
        self,
        workspace_id: UUID,
        actor_id: UUID,
        dataset_id: UUID,
    ) -> tuple[SourceImport, ...]:
        rows = self.connection.execute(
            select(s.source_imports)
            .where(
                s.source_imports.c.workspace_id == workspace_id,
                s.source_imports.c.actor_id == actor_id,
                s.source_imports.c.dataset_id == dataset_id,
            )
            .order_by(s.source_imports.c.created_at.desc())
            .limit(100)
        ).mappings()
        return tuple(import_record(row) for row in rows)

    def pending_source_imports(self, workspace_id: UUID) -> tuple[SourceImport, ...]:
        rows = self.connection.execute(
            select(s.source_imports)
            .where(
                s.source_imports.c.workspace_id == workspace_id,
                s.source_imports.c.status == "extracting",
            )
            .order_by(s.source_imports.c.created_at)
            .limit(100)
        ).mappings()
        return tuple(import_record(row) for row in rows)

    def source_import_for_recovery(self, workspace_id: UUID, import_id: UUID) -> SourceImport:
        row = (
            self.connection.execute(
                select(s.source_imports).where(
                    s.source_imports.c.workspace_id == workspace_id,
                    s.source_imports.c.id == import_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise invalid("not_found", "This import is unavailable.", 404)
        return import_record(row)

    def active_source_import_count(self, workspace_id: UUID) -> int:
        return int(
            self.connection.execute(
                select(func.count())
                .select_from(s.source_imports)
                .where(
                    s.source_imports.c.workspace_id == workspace_id,
                    s.source_imports.c.status == "extracting",
                )
            ).scalar_one()
        )

    def add_source_import(self, value: SourceImport) -> None:
        self.connection.execute(insert(s.source_imports).values(**import_values(value)))

    def complete_source_import(self, value: SourceImport) -> None:
        raw = import_values(value)
        result = self.connection.execute(
            update(s.source_imports)
            .where(
                s.source_imports.c.workspace_id == value.workspace_id,
                s.source_imports.c.actor_id == value.actor_id,
                s.source_imports.c.id == value.id,
                s.source_imports.c.status == "extracting",
            )
            .values(
                **{
                    key: raw[key]
                    for key in (
                        "status",
                        "completed_at",
                        "upload_id",
                        "candidate_id",
                        "snapshot",
                        "failure_code",
                    )
                }
            )
        )
        if result.rowcount != 1:
            raise invalid("source_import_conflict", "The import state changed; reopen it.", 409)
