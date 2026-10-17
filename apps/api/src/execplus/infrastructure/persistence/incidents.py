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
from execplus.domain.operational_metrics import (
    MAX_METRIC_BATCHES,
    METRIC_RETENTION_DAYS,
    AlertPolicy,
    ObservationBatch,
    RequestObservation,
)
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.operations import SQLOperationsRepository
from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository


class SQLIncidentRepository(SQLOperationsRepository):
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def require_active_actor(self, user_id: UUID, *, lock: bool = True) -> None:
        SQLWorkspaceRepository(self.connection).require_active_actor(user_id, lock=lock)

    def metric_observations(self, since: datetime) -> tuple[RequestObservation, ...]:
        rows = self.connection.execute(
            select(s.request_metrics)
            .where(s.request_metrics.c.minute >= since)
            .order_by(s.request_metrics.c.minute, s.request_metrics.c.category)
        ).mappings()
        return tuple(RequestObservation(**row) for row in rows)

    def alert_policies(self) -> tuple[AlertPolicy, ...]:
        return tuple(
            AlertPolicy(**row)
            for row in self.connection.execute(select(s.incident_alert_policies)).mappings()
        )

    def save_alert_policy(self, value: AlertPolicy, expected_version: int) -> None:
        table = s.incident_alert_policies
        if expected_version == 0:
            changed = self.connection.execute(
                insert(table)
                .values(**asdict(value))
                .on_conflict_do_nothing(index_elements=[table.c.category])
                .returning(table.c.category)
            )
        else:
            changed = self.connection.execute(
                update(table)
                .where(table.c.category == value.category, table.c.version == expected_version)
                .values(**asdict(value))
                .returning(table.c.category)
            )
        if changed.scalar_one_or_none() is None:
            raise IngestionError(
                "alert_conflict", "These alert settings changed. Reload them first.", 409
            )

    def occurrence_references(self, code: str, limit: int) -> tuple[dict[str, object], ...]:
        table = s.incident_occurrences
        return tuple(
            dict(row)
            for row in self.connection.execute(
                select(table.c.source_kind, table.c.source_id, table.c.occurred_at)
                .where(table.c.code == code)
                .order_by(table.c.occurred_at.desc(), table.c.source_id)
                .limit(limit)
            ).mappings()
        )

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

    def _metrics(
        self,
        connection: Connection,
        batch: ObservationBatch | None,
        now: datetime,
        deadline: float,
    ) -> dict[str, int]:
        cutoff = now - timedelta(days=METRIC_RETENTION_DAYS)
        self._budget(connection, deadline)
        connection.execute(delete(s.request_metrics).where(s.request_metrics.c.minute < cutoff))
        connection.execute(
            delete(s.request_metric_batches).where(s.request_metric_batches.c.created_at < cutoff)
        )
        if batch is None:
            return {}
        # A retry older than the deduplication horizon is never counted again.
        if batch.created_at < cutoff:
            return {
                "metrics_accepted": 1,
                "metrics_expired": sum(item.requests for item in batch.observations),
                "metrics_capacity_limited": 0,
            }
        if connection.execute(
            select(s.request_metric_batches.c.id).where(s.request_metric_batches.c.id == batch.id)
        ).first():
            return {"metrics_accepted": 1, "metrics_expired": 0, "metrics_capacity_limited": 0}
        count = connection.execute(
            select(func.count()).select_from(s.request_metric_batches)
        ).scalar_one()
        if count >= MAX_METRIC_BATCHES:
            return {"metrics_accepted": 0, "metrics_expired": 0, "metrics_capacity_limited": 1}
        connection.execute(
            insert(s.request_metric_batches).values(id=batch.id, created_at=batch.created_at)
        )
        for item in batch.observations:
            self._budget(connection, deadline)
            if item.minute < cutoff:
                continue
            table = s.request_metrics
            statement = insert(table).values(**asdict(item))
            connection.execute(
                statement.on_conflict_do_update(
                    index_elements=[table.c.minute, table.c.category],
                    set_={
                        **{
                            name: table.c[name] + statement.excluded[name]
                            for name in ("requests", "rejected", "failed", "response_start_ms")
                        },
                        "maximum_response_start_ms": func.greatest(
                            table.c.maximum_response_start_ms,
                            statement.excluded.maximum_response_start_ms,
                        ),
                    },
                )
            )
        expired = sum(item.requests for item in batch.observations if item.minute < cutoff)
        return {"metrics_accepted": 1, "metrics_expired": expired, "metrics_capacity_limited": 0}

    def collect(
        self,
        queued: tuple[IncidentOccurrence, ...],
        now: datetime,
        observations: ObservationBatch | None = None,
    ) -> dict[str, int]:
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
                            code=item.code,
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
            metrics = self._metrics(connection, observations, now, deadline)
            return {"accepted": len(selected), "capacity_limited": int(bool(capped)), **metrics}
