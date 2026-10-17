"""Use case: Collects redacted operational failures and administers incident state.

What it does: Keeps request failures off the persistence path, polls durable failures,
reports bounded-queue/storage outages and requires audited active staff-admin access.
"""

import asyncio
import logging
from collections import deque
from contextlib import suppress
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from execplus.application.incident_ports import IncidentRepository, IncidentStore
from execplus.domain.incidents import IncidentOccurrence, transition
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.operational_metrics import (
    CATEGORIES,
    MAX_PENDING_BUCKETS,
    AlertPolicy,
    ObservationBatch,
    RequestObservation,
    assess,
)
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
        self.observations: dict[tuple[datetime, str], RequestObservation] = {}
        self.observation_batch: ObservationBatch | None = None
        self.metrics_dropped = 0
        self.metrics_last_gap: datetime | None = None
        self.metrics_capacity_limited = False
        self.collector_extras: dict[str, IncidentOccurrence] = {}

    def record_http_failure(self, request_id: UUID | None = None, category: str = "other") -> None:
        if len(self.pending) >= self.queue_limit:
            self.dropped = min(1_000_000, self.dropped + 1)
            return
        self.pending.append(
            IncidentOccurrence(
                "http",
                request_id or uuid4(),
                datetime.now(timezone.utc),
                {
                    "ingestion": "ingestion_failed",
                    "exports": "export_failed",
                    "queue": "queue_failed",
                }.get(category, "http_failed"),
            )
        )

    def record_request(
        self, category: str, status: int, elapsed_ms: int, *, now: datetime | None = None
    ) -> None:
        """Keep actual response-header outcomes off the SQL request path."""
        if category not in CATEGORIES or not 100 <= status <= 599:
            raise ValueError("Invalid fixed request category or status")
        stamp = now or datetime.now(timezone.utc)
        minute = stamp.replace(second=0, microsecond=0)
        key = minute, category
        previous = self.observations.get(key)
        if (previous is None and len(self.observations) >= MAX_PENDING_BUCKETS) or (
            previous is not None and previous.requests >= 1_000_000_000
        ):
            self.metrics_dropped += 1
            self.metrics_last_gap = stamp
            return
        elapsed = max(0, min(86_400_000, elapsed_ms))
        if previous is None:
            value = RequestObservation(
                minute, category, 1, int(400 <= status < 500), int(status >= 500), elapsed, elapsed
            )
        else:
            value = replace(
                previous,
                requests=previous.requests + 1,
                rejected=previous.rejected + int(400 <= status < 500),
                failed=previous.failed + int(status >= 500),
                response_start_ms=previous.response_start_ms + elapsed,
                maximum_response_start_ms=max(previous.maximum_response_start_ms, elapsed),
            )
        self.observations[key] = value

    async def collect_once(self) -> bool:
        async with self.collect_lock:
            now = datetime.now(timezone.utc)
            if self.observation_batch is None and self.observations:
                self.observation_batch = ObservationBatch(
                    uuid4(), now, tuple(self.observations.values())
                )
                self.observations.clear()
            queued = tuple(self.pending)
            for code, count in (
                ("queue_overflow", self.dropped),
                ("collector_recovered", self.outages),
            ):
                if count and code not in self.collector_extras:
                    self.collector_extras[code] = IncidentOccurrence(
                        "collector", uuid4(), now, code, count
                    )
            extra = tuple(self.collector_extras.values())
            try:
                pending = asyncio.create_task(
                    asyncio.to_thread(
                        self.store.collect, queued + tuple(extra), now, self.observation_batch
                    )
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
            for item in extra:
                if item.code == "queue_overflow":
                    self.dropped -= item.count
                elif item.code == "collector_recovered":
                    self.outages -= item.count
            self.collector_extras.clear()
            self.capacity_limited = bool(result["capacity_limited"])
            self.last_success = now
            self.metrics_capacity_limited = bool(result.get("metrics_capacity_limited", 0))
            if result.get("metrics_accepted"):
                self.observation_batch = None
            expired = result.get("metrics_expired", 0)
            if expired:
                self.metrics_dropped += expired
                self.metrics_last_gap = now
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
            "metric_pending_buckets": len(self.observations)
            + (len(self.observation_batch.observations) if self.observation_batch else 0),
            "metric_dropped_or_expired_requests": self.metrics_dropped,
            "metric_last_gap": self.metrics_last_gap,
            "metric_capacity_limited": self.metrics_capacity_limited,
        }

    def _authorize(self, repo: IncidentRepository, actor: User) -> None:
        repo.require_active_actor(actor.id, lock=True)
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
                now = datetime.now(timezone.utc)
                observations = repo.metric_observations(now - timedelta(minutes=61))
                policies = {value.category: value for value in repo.alert_policies()}
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
        return {
            "incidents": [value.public() for value in values],
            "collector": self.health(),
            "metrics": [
                assess(policies.get(category, AlertPolicy(category)), observations, now)
                for category in CATEGORIES
            ],
        }

    def change_threshold(self, actor: User, policy: AlertPolicy) -> dict[str, object]:
        try:
            with self.store.transaction() as repo:
                self._authorize(repo, actor)
                value = replace(
                    policy,
                    version=policy.version + 1,
                    updated_at=datetime.now(timezone.utc),
                    updated_by=actor.id,
                )
                repo.save_alert_policy(value, policy.version)
                repo.add_staff_audit(
                    StaffAudit(
                        uuid4(),
                        actor.id,
                        f"incident_threshold.{value.category}.changed",
                        "api",
                        "success",
                        datetime.now(timezone.utc),
                    )
                )
        except IngestionError as error:
            if error.status == 403:
                self._denied(actor, "incident_threshold.changed")
            raise
        return asdict(value)

    def references(self, actor: User, incident_id: UUID) -> dict[str, object]:
        try:
            with self.store.transaction() as repo:
                self._authorize(repo, actor)
                incident = repo.incident(incident_id)
                values = repo.occurrence_references(incident.code, 50)
                repo.add_staff_audit(
                    StaffAudit(
                        uuid4(),
                        actor.id,
                        "incident.references_read",
                        "api",
                        "success",
                        datetime.now(timezone.utc),
                        resource_id=incident_id,
                    )
                )
        except IngestionError as error:
            if error.status == 403:
                self._denied(actor, "incident.references_read")
            raise
        return {
            "references": values,
            "limit": 50,
            "notice": (
                "Opaque request or job references only. "
                "Earlier occurrences may not have a recorded category."
            ),
        }

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
