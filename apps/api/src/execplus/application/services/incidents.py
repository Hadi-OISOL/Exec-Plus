"""Use case: Collects redacted operational failures and administers incident state.

What it does: Keeps request failures off the persistence path, polls durable failures,
reports bounded-queue/storage outages and requires audited active staff-admin access.
"""

import asyncio
import logging
from collections import deque
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID, uuid4

from execplus.application.incident_ports import IncidentRepository, IncidentStore
from execplus.domain.incidents import IncidentOccurrence, transition
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.operations import StaffAudit

logger = logging.getLogger(__name__)


class IncidentService:
    def __init__(self, store: IncidentStore, queue_limit: int = 256, interval: float = 30) -> None:
        self.store, self.queue_limit, self.interval = store, queue_limit, interval
        self.pending: deque[IncidentOccurrence] = deque()
        self.dropped = 0
        self.outages = 0
        self.last_success: datetime | None = None
        self.last_failure: datetime | None = None
        self.capacity_limited = False
        self.running = False
        self.stop = asyncio.Event()
        self.collect_lock = asyncio.Lock()

    def record_http_failure(self) -> None:
        if len(self.pending) >= self.queue_limit:
            self.dropped = min(1_000_000, self.dropped + 1)
            return
        self.pending.append(
            IncidentOccurrence("http", uuid4(), datetime.now(timezone.utc), "http_failed")
        )

    async def collect_once(self) -> bool:
        async with self.collect_lock:
            now = datetime.now(timezone.utc)
            queued = tuple(self.pending)
            dropped, outages = self.dropped, self.outages
            extra = []
            if dropped:
                extra.append(
                    IncidentOccurrence("collector", uuid4(), now, "queue_overflow", dropped)
                )
            if outages:
                extra.append(
                    IncidentOccurrence("collector", uuid4(), now, "collector_recovered", outages)
                )
            try:
                pending = asyncio.create_task(
                    asyncio.to_thread(self.store.collect, queued + tuple(extra), now)
                )
                try:
                    result = await asyncio.shield(pending)
                except asyncio.CancelledError:
                    with suppress(Exception, asyncio.CancelledError):
                        await pending
                    raise
            except Exception:
                self.outages = min(1_000_000, self.outages + 1)
                self.last_failure = now
                logger.warning("incident_collector_unavailable")
                return False
            for _ in queued:
                self.pending.popleft()
            self.dropped -= dropped
            self.outages = 0
            self.capacity_limited = bool(result["capacity_limited"])
            self.last_success = now
            return True

    async def run(self) -> None:
        self.running = True
        try:
            while not self.stop.is_set():
                await self.collect_once()
                with suppress(TimeoutError):
                    await asyncio.wait_for(self.stop.wait(), timeout=self.interval)
        finally:
            self.running = False

    def health(self) -> dict[str, object]:
        return {
            "running": self.running,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "pending": len(self.pending),
            "overflow_pending": self.dropped,
            "storage_failures_pending": self.outages,
            "capacity_limited": self.capacity_limited,
            "poll_seconds": self.interval,
        }

    def _authorize(self, repo: IncidentRepository, actor: User) -> None:
        grant = repo.staff_grant(actor.id, lock=True)
        if not grant or grant.revoked_at is not None or grant.role != "admin":
            raise IngestionError(
                "staff_required", "This action requires active staff admin access.", 403
            )

    def _denied(self, actor: User, action: str) -> None:
        with self.store.transaction() as repo:
            repo.add_staff_audit(
                StaffAudit(uuid4(), actor.id, action, "api", "denied", datetime.now(timezone.utc))
            )

    def list(self, actor: User, status: str = "active", limit: int = 50) -> dict[str, object]:
        if (
            status not in {"active", "open", "acknowledged", "resolved", "all"}
            or not 1 <= limit <= 100
        ):
            raise IngestionError(
                "invalid_incident_filter", "Choose a valid incident filter and page size.", 422
            )
        try:
            with self.store.transaction() as repo:
                self._authorize(repo, actor)
                values = repo.list_incidents(status, limit)
                repo.add_staff_audit(
                    StaffAudit(
                        uuid4(),
                        actor.id,
                        "incidents.listed",
                        "api",
                        "success",
                        datetime.now(timezone.utc),
                    )
                )
        except IngestionError as error:
            if error.status == 403:
                self._denied(actor, "incidents.listed")
            raise
        return {"incidents": [value.public() for value in values], "collector": self.health()}

    def change(
        self, actor: User, incident_id: UUID, expected: int, status: str
    ) -> dict[str, object]:
        try:
            with self.store.transaction() as repo:
                self._authorize(repo, actor)
                previous = repo.incident(incident_id)
                value = transition(previous, expected, status, datetime.now(timezone.utc))
                repo.update_incident(value, expected)
                repo.add_staff_audit(
                    StaffAudit(
                        uuid4(),
                        actor.id,
                        f"incident.{status}",
                        "api",
                        "success",
                        datetime.now(timezone.utc),
                        resource_id=incident_id,
                    )
                )
        except IngestionError as error:
            if error.status == 403:
                self._denied(actor, "incident.updated")
            raise
        return {**asdict(value), "title": value.public()["title"]}
