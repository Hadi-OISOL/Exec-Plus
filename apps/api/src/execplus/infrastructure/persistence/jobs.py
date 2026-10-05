"""Use case: Persists workspace-scoped jobs inside the existing transaction boundary.

What it does: Supplies bounded queue discovery and tenant-qualified state, attempt and event access.
"""

from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import Connection, and_, func, or_, select, update

from execplus.domain.ingestion import IngestionError
from execplus.domain.jobs import ACTIVE_STATES, Job, JobAttempt, JobEvent
from execplus.infrastructure.persistence import schema as s


class SQLJobRepository:
    connection: Connection

    def job(self, workspace_id: UUID, job_id: UUID) -> Job:
        row = (
            self.connection.execute(
                select(s.jobs).where(s.jobs.c.workspace_id == workspace_id, s.jobs.c.id == job_id)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise IngestionError("not_found", "The work is unavailable.", 404)
        return Job(**row)

    def add_job(self, job: Job) -> None:
        self.connection.execute(s.jobs.insert().values(**asdict(job)))

    def set_job(self, job: Job) -> None:
        self.connection.execute(
            update(s.jobs)
            .where(s.jobs.c.workspace_id == job.workspace_id, s.jobs.c.id == job.id)
            .values(**asdict(job))
        )

    def job_candidates(self, now: datetime, limit: int = 100) -> tuple[tuple[UUID, UUID], ...]:
        rows = self.connection.execute(
            select(s.jobs.c.workspace_id, s.jobs.c.id)
            .where(
                or_(
                    s.jobs.c.status == "queued",
                    and_(s.jobs.c.status.in_(ACTIVE_STATES), s.jobs.c.lease_expires_at <= now),
                )
            )
            .order_by(s.jobs.c.priority.desc(), s.jobs.c.created_at, s.jobs.c.id)
            .limit(min(limit, 100))
        )
        return tuple((row.workspace_id, row.id) for row in rows)

    def workspace_job_count(self, workspace_id: UUID, statuses: tuple[str, ...]) -> int:
        return int(
            self.connection.execute(
                select(func.count())
                .select_from(s.jobs)
                .where(s.jobs.c.workspace_id == workspace_id, s.jobs.c.status.in_(statuses))
            ).scalar_one()
        )

    def add_job_attempt(self, attempt: JobAttempt) -> None:
        self.connection.execute(s.job_attempts.insert().values(**asdict(attempt)))

    def job_attempt(self, workspace_id: UUID, job_id: UUID, attempt_id: UUID) -> JobAttempt:
        row = (
            self.connection.execute(
                select(s.job_attempts).where(
                    s.job_attempts.c.workspace_id == workspace_id,
                    s.job_attempts.c.job_id == job_id,
                    s.job_attempts.c.id == attempt_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise IngestionError("not_found", "The work attempt is unavailable.", 404)
        return JobAttempt(**row)

    def set_job_attempt(self, attempt: JobAttempt) -> None:
        self.connection.execute(
            update(s.job_attempts)
            .where(
                s.job_attempts.c.workspace_id == attempt.workspace_id,
                s.job_attempts.c.job_id == attempt.job_id,
                s.job_attempts.c.id == attempt.id,
            )
            .values(**asdict(attempt))
        )

    def add_job_event(self, event: JobEvent) -> None:
        self.connection.execute(s.job_events.insert().values(**asdict(event)))

    def job_events(self, workspace_id: UUID, job_id: UUID, after: int = 0) -> tuple[JobEvent, ...]:
        rows = self.connection.execute(
            select(s.job_events)
            .where(
                s.job_events.c.workspace_id == workspace_id,
                s.job_events.c.job_id == job_id,
                s.job_events.c.sequence > after,
            )
            .order_by(s.job_events.c.sequence)
            .limit(200)
        ).mappings()
        return tuple(JobEvent(**row) for row in rows)
