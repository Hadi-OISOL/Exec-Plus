"""Use case: Runs private conversation work durably outside the HTTP request lifecycle.

What it does: Fences turn publication and records bounded activity, leases and cancellation.
"""

import asyncio
import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager, suppress
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.progress import execution_progress
from execplus.application.services.threads import ThreadService
from execplus.domain.analysis_plan import AnalysisPlan
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.jobs import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    EventStatus,
    Job,
    JobAttempt,
    JobEvent,
    JobLease,
    JobStage,
    JobState,
    ResourceBudget,
    owns_lease,
    transition,
)
from execplus.domain.threads import ThreadTurn

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class JobService:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        threads: ThreadService,
        *,
        workspace_limit: int = 2,
        lease_seconds: int = 30,
        timeout_seconds: int = 100,
        queue_limit: int = 32,
    ) -> None:
        if (
            not 1 <= workspace_limit <= 8
            or not 5 <= lease_seconds <= 120
            or not 1 <= queue_limit <= 100
        ):
            raise ValueError("Invalid worker bounds")
        self.uow = unit_of_work
        self.threads = threads
        self.workspace_limit = workspace_limit
        self.lease_seconds = lease_seconds
        self.queue_limit = queue_limit
        self.budget = ResourceBudget(wall_seconds=timeout_seconds)

    def _authorize(self, repo: WorkspaceRepository, actor: User, wid: UUID, jid: UUID) -> Job:
        repo.membership(wid, actor.id)
        job = repo.job(wid, jid)
        if job.owner_id != actor.id:
            raise IngestionError("not_found", "The work is unavailable.", 404)
        self.threads._thread(repo, actor, wid, job.thread_id)
        turn = next(
            item for item in repo.thread_turns(wid, job.thread_id) if item.id == job.turn_id
        )
        if job.payload_hash != _fingerprint(
            {"question": turn.question, "thread_id": str(job.thread_id)}
        ):
            raise IngestionError(
                "job_integrity", "The stored request failed its integrity check.", 409
            )
        if job.plan and (
            set(job.plan) != {"value", "checksum"}
            or _fingerprint(job.plan["value"]) != job.plan["checksum"]
        ):
            raise IngestionError(
                "job_integrity", "The stored plan failed its integrity check.", 409
            )
        return job

    def _event(
        self, repo: WorkspaceRepository, job: Job, stage: JobStage, status: EventStatus
    ) -> Job:
        if job.event_sequence >= 199 and stage != JobStage.FINISHED:
            raise IngestionError("job_budget", "The activity limit was reached.", 422)
        now = utcnow()
        job = replace(
            job, event_sequence=job.event_sequence + 1, current_stage=stage.value, updated_at=now
        )
        repo.add_job_event(
            JobEvent(
                uuid4(),
                job.workspace_id,
                job.id,
                job.event_sequence,
                stage.value,
                status.value,
                now,
            )
        )
        repo.set_job(job)
        return job

    def _audit(self, repo: WorkspaceRepository, job: Job, action: str) -> None:
        repo.add(
            AuditEvent(
                uuid4(), job.workspace_id, job.owner_id, f"job.{action}", "job", job.id, utcnow()
            )
        )

    def submit(self, actor: User, wid: UUID, tid: UUID, question: str, request_id: UUID) -> Job:
        with self.uow() as repo:
            thread, turn, created = self.threads.claim(
                repo, actor, wid, tid, question, request_id, accept_running=True
            )
            if not created:
                if turn.job_id is None:
                    raise IngestionError(
                        "request_conflict",
                        "This request belongs to a synchronous turn. "
                        "Reopen that turn or use a new request identifier.",
                        409,
                    )
                return self._authorize(repo, actor, wid, turn.job_id)
            if repo.workspace_job_count(wid, ("queued", *ACTIVE_STATES)) >= self.queue_limit:
                raise IngestionError(
                    "job_queue_full",
                    "This workspace has too much pending work. Try again after a request finishes.",
                    429,
                )
            upload, sources = self.threads.intent_router.analytics._current_description_source(
                repo, actor, wid, thread.dataset_id, thread.upload_id
            )
            if upload.size > self.budget.input_bytes:
                raise IngestionError(
                    "job_budget", "The source exceeds this job's input limit.", 422
                )
            now = utcnow()
            job = Job(
                uuid4(),
                wid,
                tid,
                turn.id,
                actor.id,
                request_id,
                _fingerprint({"question": question, "thread_id": str(tid)}),
                "queued",
                0,
                0,
                3,
                asdict(self.budget),
                list(sources),
                {},
                {},
                now,
                now,
                now + timedelta(minutes=10),
            )
            repo.add_job(job)
            repo.update_thread_turn(wid, replace(turn, job_id=job.id))
            job = self._event(repo, job, JobStage.QUEUED, EventStatus.COMPLETED)
            self._audit(repo, job, "submitted")
            return job

    def get(self, actor: User, wid: UUID, jid: UUID) -> Job:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            job = self._authorize(repo, actor, wid, jid)
            now = utcnow()
            return self._recover(repo, job, now)

    def events(self, actor: User, wid: UUID, jid: UUID, after: int = 0) -> tuple[JobEvent, ...]:
        if type(after) is not int or after < 0 or after > 200:
            raise IngestionError("invalid_cursor", "Use a valid activity cursor.", 422)
        with self.uow() as repo:
            self._authorize(repo, actor, wid, jid)
            return repo.job_events(wid, jid, after)

    def _close(
        self,
        repo: WorkspaceRepository,
        job: Job,
        state: JobState,
        code: str | None,
        turn: ThreadTurn | None = None,
    ) -> Job:
        transition(job, state)
        now = utcnow()
        current = next(
            item
            for item in repo.thread_turns(job.workspace_id, job.thread_id)
            if item.id == job.turn_id
        )
        refs: dict[str, Any] = {}
        if turn is not None and turn.query_id:
            refs["query_id"] = str(turn.query_id)
        if state == JobState.SUCCEEDED and turn is not None:
            actor = repo.user(job.owner_id)
            self.threads.publish(repo, actor, job.workspace_id, turn)
        elif current.status == "running":
            messages = {
                "cancelled": "This request was cancelled. No completed answer is available.",
                "source_changed": (
                    "The file or its meaning changed while this request was waiting. "
                    "Ask again using the current version."
                ),
                "interrupted": (
                    "This request was interrupted. It was not automatically executed again. "
                    "Start a new turn to retry."
                ),
                "unauthorized": "A required source is no longer accessible.",
                "timeout": "This request reached its time limit. Try a narrower question.",
                "queue_expired": (
                    "This request expired before it could start. Start a new turn to retry."
                ),
            }
            failed = (
                turn
                if turn is not None and turn.status == "failed" and state == JobState.FAILED
                else replace(
                    current,
                    status="failed",
                    query_id=None,
                    evidence={},
                    message=messages.get(
                        code or "", "This request could not complete. Start a new turn to retry."
                    ),
                )
            )
            repo.update_thread_turn(job.workspace_id, failed)
        if job.lease_id is not None:
            attempt = repo.job_attempt(job.workspace_id, job.id, job.lease_id)
            repo.set_job_attempt(
                replace(attempt, status=state.value, finished_at=now, failure_code=code)
            )
        job = replace(
            job,
            status=state.value,
            failure_code=code,
            result_refs=refs,
            lease_expires_at=None,
            updated_at=now,
        )
        event_status = (
            EventStatus.COMPLETED
            if state == JobState.SUCCEEDED
            else EventStatus.CANCELLED
            if state == JobState.CANCELLED
            else EventStatus.FAILED
        )
        job = self._event(repo, job, JobStage.FINISHED, event_status)
        self._audit(repo, job, state.value)
        return job

    def cancel(self, actor: User, wid: UUID, jid: UUID) -> Job:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            job = self._authorize(repo, actor, wid, jid)
            if job.status in TERMINAL_STATES:
                return job
            job = replace(job, cancel_requested=True, updated_at=utcnow())
            if job.status == "queued":
                return self._close(repo, job, JobState.CANCELLED, "cancelled")
            if job.status != "cancelling":
                transition(job, JobState.CANCELLING)
                job = replace(job, status="cancelling")
            repo.set_job(job)
            self._audit(repo, job, "cancellation_requested")
            return job

    async def result(self, actor: User, wid: UUID, jid: UUID) -> tuple[Any, ThreadTurn]:
        job = self.get(actor, wid, jid)
        if job.status not in TERMINAL_STATES:
            raise IngestionError("job_pending", "This request is still running.", 409)
        answer = await self.threads.resolve(actor, wid, job.thread_id, job.turn_id)
        with self.uow() as repo:
            self._authorize(repo, actor, wid, jid)
            turn = next(
                item for item in repo.thread_turns(wid, job.thread_id) if item.id == job.turn_id
            )
        return answer, turn

    def _recover(self, repo: WorkspaceRepository, job: Job, now: datetime) -> Job:
        if job.status == "queued" and job.expires_at <= now:
            return self._close(repo, job, JobState.EXPIRED, "queue_expired")
        if (
            job.status not in ACTIVE_STATES
            or job.lease_expires_at is None
            or job.lease_expires_at > now
        ):
            return job
        if (
            job.status == "claimed"
            and job.attempts < job.max_attempts
            and not job.cancel_requested
            and job.expires_at > now
        ):
            if job.lease_id:
                previous = repo.job_attempt(job.workspace_id, job.id, job.lease_id)
                repo.set_job_attempt(
                    replace(
                        previous,
                        status="expired",
                        finished_at=now,
                        failure_code="interrupted_before_start",
                    )
                )
            transition(job, JobState.QUEUED)
            job = replace(job, status="queued", lease_id=None, lease_expires_at=None)
            job = self._event(repo, job, JobStage.QUEUED, EventStatus.COMPLETED)
            self._audit(repo, job, "retry_ready")
            return job
        return self._close(
            repo,
            job,
            JobState.CANCELLED if job.cancel_requested else JobState.EXPIRED,
            "cancelled" if job.cancel_requested else "interrupted",
        )

    def claim_next(self) -> JobLease | None:
        now = utcnow()
        with self.uow() as repo:
            candidates = repo.job_candidates(now)
        for wid, jid in candidates:
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                job = repo.job(wid, jid)
                now = utcnow()
                job = self._recover(repo, job, now)
                if job.status != "queued":
                    continue
                if repo.workspace_job_count(wid, tuple(ACTIVE_STATES)) >= self.workspace_limit:
                    continue
                actor = repo.user(job.owner_id)
                try:
                    self._authorize(repo, actor, wid, jid)
                    thread = repo.thread(wid, job.thread_id)
                    upload, sources = (
                        self.threads.intent_router.analytics._current_description_source(
                            repo, actor, wid, thread.dataset_id, thread.upload_id
                        )
                    )
                    if list(sources) != job.sources:
                        self._close(repo, job, JobState.FAILED, "source_changed")
                        continue
                    if upload.size > ResourceBudget(**job.budget).input_bytes:
                        self._close(repo, job, JobState.FAILED, "job_budget")
                        continue
                except IngestionError:
                    self._close(repo, job, JobState.FAILED, "unauthorized")
                    continue
                transition(job, JobState.CLAIMED)
                attempt_id = uuid4()
                expires = now + timedelta(seconds=self.lease_seconds)
                job = replace(
                    job,
                    status="claimed",
                    attempts=job.attempts + 1,
                    lease_id=attempt_id,
                    lease_expires_at=expires,
                    updated_at=now,
                )
                repo.set_job(job)
                repo.add_job_attempt(
                    JobAttempt(attempt_id, wid, jid, job.attempts, "claimed", now, now, expires)
                )
                self._audit(repo, job, "claimed")
                return JobLease(wid, jid, attempt_id, expires)
        return None

    def heartbeat(self, lease: JobLease) -> str | None:
        with self.uow() as repo:
            repo.workspace(lease.workspace_id, lock=True)
            job = repo.job(lease.workspace_id, lease.job_id)
            now = utcnow()
            if not owns_lease(job, lease, now):
                return "lease_lost"
            if job.cancel_requested:
                return "cancelled"
            try:
                self._authorize(repo, repo.user(job.owner_id), job.workspace_id, job.id)
            except IngestionError:
                return "unauthorized"
            attempt = repo.job_attempt(job.workspace_id, job.id, lease.attempt_id)
            if (now - attempt.started_at).total_seconds() > ResourceBudget(
                **job.budget
            ).wall_seconds:
                return "timeout"
            expires = now + timedelta(seconds=self.lease_seconds)
            repo.set_job(replace(job, lease_expires_at=expires, updated_at=now))
            repo.set_job_attempt(replace(attempt, heartbeat_at=now, lease_expires_at=expires))
            return None

    async def _source_check(
        self, actor: User, wid: UUID, did: UUID, uid: UUID, sources: tuple[dict[str, str], ...]
    ) -> None:
        reading = asyncio.create_task(
            asyncio.to_thread(
                self.threads.intent_router.analytics.recheck_description,
                actor,
                wid,
                did,
                uid,
                sources,
            )
        )
        try:
            await asyncio.shield(reading)
        except asyncio.CancelledError:
            with suppress(Exception, asyncio.CancelledError):
                await reading
            raise

    async def run(self, lease: JobLease) -> None:
        with self.uow() as repo:
            repo.workspace(lease.workspace_id, lock=True)
            job = repo.job(lease.workspace_id, lease.job_id)
            if not owns_lease(job, lease, utcnow()):
                return
            if job.cancel_requested:
                self._close(repo, job, JobState.CANCELLED, "cancelled")
                return
            transition(job, JobState.RUNNING)
            job = replace(job, status="running", updated_at=utcnow())
            repo.set_job(job)
            attempt = repo.job_attempt(job.workspace_id, job.id, lease.attempt_id)
            repo.set_job_attempt(replace(attempt, status="running"))
            actor = repo.user(job.owner_id)
            thread = repo.thread(job.workspace_id, job.thread_id)
            turn = next(
                item
                for item in repo.thread_turns(job.workspace_id, job.thread_id)
                if item.id == job.turn_id
            )
        sink = JobProgress(self, lease, ResourceBudget(**job.budget))
        failure: str | None = None
        shutdown = False
        completed: ThreadTurn | None = None

        async def execute() -> ThreadTurn:
            with execution_progress(sink):
                await sink.emit(JobStage.AUTHORIZING, EventStatus.STARTED)
                self.get(actor, job.workspace_id, job.id)
                await sink.emit(JobStage.AUTHORIZING, EventStatus.COMPLETED)
                await sink.emit(JobStage.SOURCE, EventStatus.STARTED)
                await self._source_check(
                    actor, job.workspace_id, thread.dataset_id, thread.upload_id, tuple(job.sources)
                )
                await sink.emit(JobStage.SOURCE, EventStatus.COMPLETED)
                _, finished = await self.threads.run_turn(actor, job.workspace_id, thread, turn)
                await sink.emit(JobStage.VERIFYING, EventStatus.STARTED)
                await self._source_check(
                    actor, job.workspace_id, thread.dataset_id, thread.upload_id, tuple(job.sources)
                )
                await sink.emit(JobStage.VERIFYING, EventStatus.COMPLETED)
                return finished

        task = asyncio.create_task(execute())
        deadline = asyncio.get_running_loop().time() + ResourceBudget(**job.budget).wall_seconds
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=0.25)
                if done:
                    break
                failure = self.heartbeat(lease)
                if failure is None and asyncio.get_running_loop().time() >= deadline:
                    failure = "timeout"
                if failure:
                    task.cancel()
                    break
            if failure is None:
                if task.cancelled():
                    failure = self.heartbeat(lease) or "interrupted"
                else:
                    completed = task.result()
            else:
                with suppress(Exception, asyncio.CancelledError):
                    await task
        except asyncio.CancelledError:
            shutdown = True
            failure = "interrupted"
            task.cancel()
            with suppress(Exception, asyncio.CancelledError):
                await task
        except IngestionError as error:
            failure = (
                error.code
                if error.code in {"job_budget", "source_changed"}
                else "unauthorized"
                if error.status == 404
                else "execution_failed"
            )
        except Exception:
            failure = "execution_failed"
        finally:
            if not task.done():
                task.cancel()
                with suppress(Exception, asyncio.CancelledError):
                    await task
        self._finish(lease, actor, thread.dataset_id, thread.upload_id, completed, failure)
        if shutdown:
            raise asyncio.CancelledError

    def _finish(
        self,
        lease: JobLease,
        actor: User,
        dataset_id: UUID,
        upload_id: UUID,
        completed: ThreadTurn | None,
        failure: str | None,
    ) -> None:
        with self.uow() as repo:
            repo.workspace(lease.workspace_id, lock=True)
            current = repo.job(lease.workspace_id, lease.job_id)
            if not owns_lease(current, lease, utcnow()):
                return
            if current.cancel_requested or failure == "cancelled":
                self._close(repo, current, JobState.CANCELLED, "cancelled", completed)
                return
            attempt = repo.job_attempt(current.workspace_id, current.id, lease.attempt_id)
            if (utcnow() - attempt.started_at).total_seconds() >= ResourceBudget(
                **current.budget
            ).wall_seconds:
                failure = "timeout"
            if failure or completed is None or completed.status == "failed":
                self._close(
                    repo, current, JobState.FAILED, failure or "execution_failed", completed
                )
                return
            try:
                self._authorize(repo, actor, current.workspace_id, current.id)
                _, latest = self.threads.intent_router.analytics._current_description_source(
                    repo, actor, current.workspace_id, dataset_id, upload_id
                )
                if list(latest) != current.sources:
                    self._close(repo, current, JobState.FAILED, "source_changed")
                    return
                if (utcnow() - attempt.started_at).total_seconds() >= ResourceBudget(
                    **current.budget
                ).wall_seconds:
                    self._close(repo, current, JobState.FAILED, "timeout")
                    return
                self._close(repo, current, JobState.SUCCEEDED, None, completed)
            except IngestionError:
                self._close(repo, current, JobState.FAILED, "unauthorized")

    async def process(self, *, limit: int = 32, concurrency: int = 4) -> dict[str, int]:
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or type(concurrency) is not int
            or not 1 <= concurrency <= 8
        ):
            raise ValueError("Use bounded worker concurrency and batch size")
        processed = 0

        async def consume() -> None:
            nonlocal processed
            while processed < limit:
                lease = self.claim_next()
                if lease is None:
                    return
                processed += 1
                await self.run(lease)

        tasks = [asyncio.create_task(consume()) for _ in range(concurrency)]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return {"processed": processed}


class JobProgress:
    def __init__(self, service: JobService, lease: JobLease, budget: ResourceBudget) -> None:
        self.service = service
        self.lease = lease
        self.budget = budget
        self.model_calls = 0
        self.provider_attempts = 0
        self.queries = 0
        self.retrievals = 0

    def _job(self, repo: WorkspaceRepository) -> Job:
        repo.workspace(self.lease.workspace_id, lock=True)
        job = repo.job(self.lease.workspace_id, self.lease.job_id)
        if not owns_lease(job, self.lease, utcnow()) or job.cancel_requested:
            raise asyncio.CancelledError
        self.service._authorize(repo, repo.user(job.owner_id), job.workspace_id, job.id)
        return job

    async def emit(self, stage: JobStage, status: EventStatus) -> None:
        if status == EventStatus.STARTED:
            if stage == JobStage.QUERY:
                self.queries += 1
            if stage == JobStage.RETRIEVAL:
                self.retrievals += 1
            if (
                self.queries > self.budget.max_queries
                or self.retrievals > self.budget.max_retrievals
            ):
                raise IngestionError(
                    "job_budget", "This request exceeds supported work limits.", 422
                )
        with self.service.uow() as repo:
            job = self._job(repo)
            self.service._event(repo, job, stage, status)

    async def planned(self, plan: AnalysisPlan) -> None:
        if len(plan.steps) > self.budget.max_steps:
            raise IngestionError("job_budget", "The plan exceeds its step budget.", 422)
        body = json.loads(json.dumps(plan.body()))
        with self.service.uow() as repo:
            job = self._job(repo)
            saved = {"value": body, "checksum": _fingerprint(body)}
            if job.plan and job.plan != saved:
                raise IngestionError(
                    "job_conflict", "The validated plan changed during execution.", 409
                )
            repo.set_job(replace(job, plan=saved))

    async def model_call(self) -> None:
        self.model_calls += 1
        if self.model_calls > self.budget.max_model_calls:
            raise IngestionError("job_budget", "This request reached its model-call limit.", 422)
        with self.service.uow() as repo:
            self._job(repo)

    async def provider_attempt(self) -> None:
        self.provider_attempts += 1
        if self.provider_attempts > self.budget.max_provider_attempts:
            raise IngestionError(
                "job_budget", "This request reached its provider-attempt limit.", 422
            )
        with self.service.uow() as repo:
            self._job(repo)
