"""Use case: Runs private measured pattern scans inside existing conversations.

What it does: Binds one complete projection to source receipts and replays statistical output.
"""

import asyncio
from dataclasses import replace
from typing import Any
from uuid import UUID

from execplus.application.ports import PatternStatistics
from execplus.application.progress import activity
from execplus.application.services.analytics import AnalyticsService, UnitOfWork
from execplus.application.services.forecasts import read_complete
from execplus.domain.decision_analysis import checksum
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.evidence import receipt
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.jobs import EventStatus, JobStage
from execplus.domain.models import CalculationLineage
from execplus.domain.patterns import VERSION, pattern_plan, pattern_request, pattern_result

EVIDENCE_VERSION = "pattern-evidence-v1"


class PatternService:
    def __init__(
        self, uow: UnitOfWork, analytics: AnalyticsService, statistics: PatternStatistics
    ) -> None:
        self.uow, self.analytics, self.statistics = uow, analytics, statistics

    def _current(self, actor: User, wid: UUID, did: UUID, uid: UUID) -> None:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.upload(wid, did, uid)
            if any(
                str(feed.source["upload_id"]) != str(uid) for feed in repo.refresh_feeds(wid, did)
            ):
                raise ClarificationRequiredError(
                    "Use the current accepted file before finding new patterns."
                )

    async def discover(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        uid: UUID,
        columns: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        self._current(actor, wid, did, uid)
        context, table, scope = await read_complete(
            lambda: self.analytics.descriptive_snapshot(actor, wid, did, uid)
        )
        request = pattern_request(context, table, columns)
        view = context.view
        plan = pattern_plan(scope, did, view, request)
        lineage = CalculationLineage(
            plan.query_id,
            wid,
            did,
            context.name,
            len(table.rows),
            "Selected pattern fields",
            "analysis",
            (),
            (),
            plan.sql,
            "deterministic:" + VERSION,
        )
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, view.sources)
        )
        self._current(actor, wid, did, uid)
        await activity(JobStage.QUERY, EventStatus.STARTED)
        try:
            value = await self.analytics.executor.execute(plan, scope, table, view)
        except (Exception, asyncio.CancelledError):
            self.analytics._persist(
                actor, replace(lineage, receipt=receipt(plan, view.sources, None))
            )
            await activity(JobStage.QUERY, EventStatus.FAILED)
            raise
        self.analytics._persist(actor, replace(lineage, receipt=receipt(plan, view.sources, value)))
        await activity(JobStage.QUERY, EventStatus.COMPLETED)
        result = await read_complete(
            lambda: pattern_result(
                value,
                request,
                self.statistics.engine_version,
                self.statistics.correlations,
                self.statistics.categorical_association,
            )
        )
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, view.sources)
        )
        self._current(actor, wid, did, uid)
        return dict(
            version=EVIDENCE_VERSION,
            query_id=str(plan.query_id),
            sources=list(view.sources),
            request=request,
            engine_version=self.statistics.engine_version,
            result=result,
            request_checksum=checksum(request),
            result_checksum=checksum(result),
        )

    async def reopen(self, actor: User, wid: UUID, evidence: dict[str, Any]) -> dict[str, Any]:
        invalid = IngestionError(
            "lineage_mismatch", "The saved pattern evidence is inconsistent.", 409
        )
        try:
            if evidence["version"] != EVIDENCE_VERSION or evidence["request_checksum"] != checksum(
                evidence["request"]
            ):
                raise invalid
            if evidence["engine_version"] != self.statistics.engine_version:
                raise IngestionError(
                    "pattern_engine_changed",
                    "This saved pattern needs its original statistics version to be verified.",
                    409,
                )
            sources = evidence["sources"]
            if len(sources) != 1:
                raise invalid
            source = sources[0]
            did, uid = UUID(source["dataset_id"]), UUID(source["upload_id"])
            context = await read_complete(
                lambda: self.analytics.describe(actor, wid, did, uid, source)
            )
            _, scope, table, view = await read_complete(
                lambda: self.analytics.context_at(actor, wid, source)
            )
            request = pattern_request(context, table, tuple(evidence["request"]["selected"]))
            if request != evidence["request"]:
                raise invalid
            qid = UUID(evidence["query_id"])
            plan = replace(pattern_plan(scope, did, view, request), query_id=qid)
            with self.uow() as repo:
                repo.membership(wid, actor.id)
                record = repo.query_execution(wid, qid)
                if record.actor_id != actor.id or record.aggregation != "analysis":
                    raise IngestionError(
                        "not_found", "The private pattern evidence is unavailable.", 404
                    )
                expected = receipt(plan, view.sources, None)
                if (
                    record.dataset_id != did
                    or record.sql != plan.sql
                    or record.receipt.get("outcome") != "executed"
                    or any(
                        record.receipt.get(key) != expected[key]
                        for key in ("version", "sources", "parameters")
                    )
                ):
                    raise invalid
            value, _ = await self.analytics.replay(actor, wid, qid)
            result = await read_complete(
                lambda: pattern_result(
                    value,
                    request,
                    self.statistics.engine_version,
                    self.statistics.correlations,
                    self.statistics.categorical_association,
                )
            )
            if result != evidence["result"] or checksum(result) != evidence["result_checksum"]:
                raise invalid
            with self.uow() as repo:
                repo.membership(wid, actor.id)
                repo.upload(wid, did, uid)
            return evidence
        except (KeyError, TypeError, ValueError, IndexError):
            raise invalid from None
