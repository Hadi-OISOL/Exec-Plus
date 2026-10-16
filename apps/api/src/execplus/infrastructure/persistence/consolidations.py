"""Use case: Persists immutable private company worksheets on PostgreSQL.

What it does: Provides owner-scoped records and bounded transactions that can lock
participating workspaces in application-defined stable order.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from uuid import UUID

from sqlalchemy import Engine, insert, select, text

from execplus.application.consolidation_ports import ConsolidationRepository
from execplus.domain.consolidation_records import ConsolidationRun
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository


class SQLConsolidationRepository(SQLWorkspaceRepository):
    def lock_consolidation_owner(self, oid: UUID, owner_id: UUID) -> None:
        self.connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": f"execplus:consolidation:{oid}:{owner_id}"},
        )

    def consolidation_runs(self, oid: UUID, owner_id: UUID) -> tuple[ConsolidationRun, ...]:
        rows = self.connection.execute(
            select(s.consolidation_runs)
            .where(
                s.consolidation_runs.c.organization_id == oid,
                s.consolidation_runs.c.owner_id == owner_id,
            )
            .order_by(s.consolidation_runs.c.created_at.desc(), s.consolidation_runs.c.id)
        ).mappings()
        return tuple(ConsolidationRun(**row) for row in rows)

    def consolidation_run(self, oid: UUID, rid: UUID, owner_id: UUID) -> ConsolidationRun:
        row = (
            self.connection.execute(
                select(s.consolidation_runs).where(
                    s.consolidation_runs.c.organization_id == oid,
                    s.consolidation_runs.c.id == rid,
                    s.consolidation_runs.c.owner_id == owner_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise IngestionError("not_found", "This private worksheet is unavailable.", 404)
        return ConsolidationRun(**row)

    def add_consolidation_run(self, value: ConsolidationRun) -> None:
        self.connection.execute(insert(s.consolidation_runs).values(**asdict(value)))


class SQLConsolidationStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def transaction(self) -> Iterator[ConsolidationRepository]:
        with self.engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout = '5s'"))
            connection.execute(text("SET LOCAL lock_timeout = '1s'"))
            yield SQLConsolidationRepository(connection)
