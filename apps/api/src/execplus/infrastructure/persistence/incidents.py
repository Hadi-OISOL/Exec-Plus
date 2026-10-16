"""Use case: Persists bounded operational incidents without customer content.

What it does: Deduplicates fixed-code occurrences, polls durable failures atomically,
retains thirty days of occurrence keys and serializes concurrent collectors.
"""

from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from time import monotonic
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, delete, exists, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert

from execplus.application.incident_ports import IncidentRepository
from execplus.domain.incidents import (
    COLLECT_BATCH,
    MAX_OCCURRENCES,
    RETENTION_DAYS,
    Incident,
    IncidentOccurrence,
    observe,
)
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.operations import SQLOperationsRepository


class SQLIncidentRepository(SQLOperationsRepository):
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def list_incidents(self, status: str, limit: int) -> tuple[Incident, ...]:
        statement = select(s.incidents)
        if status == "active":
            statement = statement.where(s.incidents.c.status != "resolved")
        elif status != "all":
            statement = statement.where(s.incidents.c.status == status)
        rows = self.connection.execute(
            statement.order_by(s.incidents.c.last_seen.desc()).limit(limit)
        ).mappings()
        return tuple(Incident(**row) for row in rows)

    def incident(self, incident_id: UUID) -> Incident:
        row = (
            self.connection.execute(
                select(s.incidents).where(s.incidents.c.id == incident_id).with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise IngestionError("not_found", "This incident is unavailable.", 404)
        return Incident(**row)

    def update_incident(self, value: Incident, expected_version: int) -> None:
        result = self.connection.execute(
            update(s.incidents)
            .where(s.incidents.c.id == value.id, s.incidents.c.version == expected_version)
            .values(**asdict(value))
        )
        if result.rowcount != 1:
            raise IngestionError(
                "incident_conflict", "This incident changed. Reload it first.", 409
            )


class SQLIncidentStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def transaction(self) -> Iterator[IncidentRepository]:
        with self.engine.begin() as connection:
            yield SQLIncidentRepository(connection)

    def _budget(self, connection: Connection, deadline: float) -> None:
        remaining = int((deadline - monotonic()) * 1000)
        if remaining <= 0:
            raise TimeoutError("Incident collection budget exhausted")
        connection.execute(
            select(
                func.set_config("statement_timeout", str(remaining), True),
                func.set_config("lock_timeout", str(min(1000, remaining)), True),
            )
        )

    def _observe(
        self, connection: Connection, occurrences: tuple[IncidentOccurrence, ...], deadline: float
    ) -> None:
        self._budget(connection, deadline)
        occurrence = max(occurrences, key=lambda item: item.occurred_at)
        row = (
            connection.execute(
                select(s.incidents).where(s.incidents.c.code == occurrence.code).with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        previous = Incident(**row) if row else None
        value = observe(previous, occurrence)
        value = replace(
            value,
            occurrences=(previous.occurrences if previous else 0)
            + sum(item.count for item in occurrences),
            first_seen=min(value.first_seen, *(item.occurred_at for item in occurrences)),
            version=(previous.version if previous else 0) + len(occurrences),
        )
        self._budget(connection, deadline)
        if previous:
            SQLIncidentRepository(connection).update_incident(value, previous.version)
        else:
            connection.execute(insert(s.incidents).values(**asdict(value)))

    def _durable(
        self, connection: Connection, cutoff: datetime, deadline: float
    ) -> tuple[IncidentOccurrence, ...]:
        events = []
        configurations = (
            (s.jobs, "job", "updated_at", s.jobs.c.status.in_(("failed", "expired"))),
            (s.report_deliveries, "report", "created_at", s.report_deliveries.c.status == "failed"),
            (
                s.audit_events,
                "refresh",
                "created_at",
                s.audit_events.c.action == "refresh.activation_failed",
            ),
        )
        for table, kind, stamp, condition in configurations:
            self._budget(connection, deadline)
            seen = exists(
                select(s.incident_occurrences.c.source_id).where(
                    s.incident_occurrences.c.source_kind == kind,
                    s.incident_occurrences.c.source_id == table.c.id,
                    s.incident_occurrences.c.occurred_at == table.c[stamp],
                )
            )
            selected = [table.c.id, table.c[stamp]]
            if kind == "job":
                selected.extend((table.c.status, table.c.failure_code))
            rows = connection.execute(
                select(*selected)
                .where(condition, table.c[stamp] >= cutoff, ~seen)
                .order_by(table.c[stamp], table.c.id)
                .limit(COLLECT_BATCH)
            ).mappings()
            for row in rows:
                if kind == "job":
                    code = (
                        "job_expired"
                        if row["status"] == "expired"
                        else {
                            "timeout": "job_timeout",
                            "queue_expired": "job_expired",
                            "interrupted": "job_interrupted",
                            "interrupted_before_start": "job_interrupted",
                            "lease_lost": "job_interrupted",
                        }.get(row["failure_code"], "job_failed")
                    )
                else:
                    code = "report_failed" if kind == "report" else "refresh_failed"
                events.append(IncidentOccurrence(kind, row["id"], row[stamp], code))
        return tuple(events)

    def collect(self, queued: tuple[IncidentOccurrence, ...], now: datetime) -> dict[str, int]:
        cutoff = now - timedelta(days=RETENTION_DAYS)
        with self.engine.begin() as connection:
            deadline = monotonic() + 5
            self._budget(connection, deadline)
            connection.execute(select(func.pg_advisory_xact_lock(619_832_043)))
            self._budget(connection, deadline)
            connection.execute(
                delete(s.incident_occurrences).where(s.incident_occurrences.c.occurred_at < cutoff)
            )
            self._budget(connection, deadline)
            connection.execute(
                delete(s.incidents).where(
                    s.incidents.c.status == "resolved", s.incidents.c.last_seen < cutoff
                )
            )
            self._budget(connection, deadline)
            count = connection.execute(
                select(func.count()).select_from(s.incident_occurrences)
            ).scalar_one()
            events = queued + self._durable(connection, cutoff, deadline)
            unique = {
                (item.source_kind, item.source_id, item.occurred_at): item
                for item in events
                if item.occurred_at >= cutoff
            }
            columns = (
                s.incident_occurrences.c.source_kind,
                s.incident_occurrences.c.source_id,
                s.incident_occurrences.c.occurred_at,
            )
            self._budget(connection, deadline)
            seen = (
                set(
                    connection.execute(
                        select(*columns).where(tuple_(*columns).in_(tuple(unique)))
                    ).all()
                )
                if unique
                else set()
            )
            fresh = [item for key, item in unique.items() if key not in seen]
            selected = fresh[: max(0, MAX_OCCURRENCES - count)]
            capped = sum(item.count for item in fresh[len(selected) :])
            if selected:
                self._budget(connection, deadline)
                connection.execute(
                    insert(s.incident_occurrences),
                    [
                        dict(
                            source_kind=item.source_kind,
                            source_id=item.source_id,
                            occurred_at=item.occurred_at,
                        )
                        for item in selected
                    ],
                )
                groups: dict[str, list[IncidentOccurrence]] = defaultdict(list)
                for item in selected:
                    groups[item.code].append(item)
                for items in groups.values():
                    self._observe(connection, tuple(items), deadline)
            if capped:
                self._observe(
                    connection,
                    (
                        IncidentOccurrence(
                            "collector", uuid4(), now, "retention_capacity", min(capped, 1_000_000)
                        ),
                    ),
                    deadline,
                )
            return {"accepted": len(selected), "capacity_limited": int(bool(capped))}
