"""Use case: Saves and reopens private "Build a prediction model" results.

What it does: Runs one governed projection with a receipt, trains the fixed recipe on the
server and stores an immutable owner-private run that reopening recomputes exactly.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from execplus.application.ports import PredictionTrainer
from execplus.application.services.dataset_access import authorize_sources
from execplus.application.services.forecasts import read_complete
from execplus.application.services.patterns import sampled_input, sampled_view, with_sample
from execplus.application.services.studies import audit
from execplus.application.services.workspaces import checked_name
from execplus.domain.decision_analysis import AnalysisRun, checksum
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.evidence import receipt
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.models import CalculationLineage
from execplus.domain.prediction_models import (
    METHOD,
    prediction_plan,
    prediction_request,
    prediction_result,
)

if TYPE_CHECKING:
    from execplus.application.services.decision_analysis import DecisionAnalysisService

LIMIT = IngestionError("analysis_limit", "Use at most 50 saved analyses per dataset/person.", 409)


class PredictionModels:
    def __init__(self, service: DecisionAnalysisService) -> None:
        self.service = service
        self.uow, self.analytics = service.uow, service.analytics

    def trainer(self) -> PredictionTrainer:
        if self.service.prediction_trainer is None:
            raise IngestionError(
                "prediction_unavailable", "Prediction models are not configured.", 503
            )
        return self.service.prediction_trainer

    async def create(
        self, actor: User, wid: UUID, did: UUID, uid: UUID, raw: dict[str, Any]
    ) -> dict[str, Any]:
        name = checked_name(raw["name"])
        trainer = self.trainer()
        self.service._current(actor, wid, did, uid, raw)
        with self.uow() as repo:
            if len(repo.analysis_runs(wid, did, actor.id)) >= 50:
                raise LIMIT
        context, table, scope = await read_complete(
            lambda: self.analytics.descriptive_snapshot(actor, wid, did, uid)
        )
        view = context.view
        source = view.sources[0]
        if (
            source["revision_id"] != raw["revision_id"]
            or source.get("understanding_id") != raw["understanding_id"]
        ):
            raise ClarificationRequiredError("The source changed. Reload prediction options.")
        request = with_sample(table, prediction_request(context, table, raw))
        run_table, run_view = sampled_input(table, view, request)
        plan = prediction_plan(scope, did, view, request)
        lineage = CalculationLineage(
            plan.query_id,
            wid,
            did,
            context.name,
            run_table.row_count,
            request["target"],
            "analysis",
            (),
            (),
            plan.sql,
            f"deterministic:{METHOD}",
        )
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, view.sources)
        )
        self.service._current(actor, wid, did, uid, raw)
        try:
            value = await self.analytics.executor.execute(plan, scope, run_table, run_view)
        except (Exception, asyncio.CancelledError):
            self.analytics._persist(
                actor, replace(lineage, receipt=receipt(plan, run_view.sources, None))
            )
            raise
        self.analytics._persist(
            actor, replace(lineage, receipt=receipt(plan, run_view.sources, value))
        )
        self.service._admit_model(actor, wid, did, uid, raw, view.sources)
        result = await read_complete(
            lambda: prediction_result(value, request, trainer.fit, trainer.engine_version)
        )
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, view.sources)
        )
        evidence = dict(
            query_id=str(plan.query_id),
            sources=list(view.sources),
            definition=view.definition,
            units={request["target"]: request["target_unit"]} if request["target_unit"] else {},
            request=request,
            engine_version=trainer.engine_version,
            request_checksum=checksum(raw),
            result_checksum=checksum(result),
        )
        run = AnalysisRun(
            uuid4(),
            wid,
            did,
            actor.id,
            uid,
            UUID(raw["revision_id"]),
            UUID(raw["understanding_id"]),
            name,
            raw["kind"],
            METHOD,
            raw,
            evidence,
            result,
            datetime.now(timezone.utc),
        )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self.service._current(actor, wid, did, uid, raw)
            authorize_sources(repo, actor, wid, evidence["sources"], did)
            if len(repo.analysis_runs(wid, did, actor.id)) >= 50:
                raise LIMIT
            repo.add(run)
            audit(repo, actor, wid, "analysis.created", run.id)
        return await self.service._body(actor, run)

    async def open(self, actor: User, run: AnalysisRun) -> dict[str, Any]:
        invalid = IngestionError(
            "lineage_mismatch", "The saved prediction model evidence is inconsistent.", 409
        )
        trainer = self.trainer()
        wid, did = run.workspace_id, run.dataset_id
        try:
            raw, evidence = run.request, run.evidence
            if run.method_version != METHOD or checksum(raw) != evidence["request_checksum"]:
                raise invalid
            if evidence["engine_version"] != trainer.engine_version:
                raise IngestionError(
                    "prediction_engine_changed",
                    "This saved model needs its original statistics version to be verified.",
                    409,
                )
            sources = evidence["sources"]
            if len(sources) != 1:
                raise invalid
            source = sources[0]
            if any(
                source[key] != str(value)
                for key, value in (
                    ("dataset_id", did),
                    ("upload_id", run.upload_id),
                    ("revision_id", run.revision_id),
                    ("understanding_id", run.understanding_id),
                )
            ):
                raise invalid
            context, table, scope = await read_complete(
                lambda: self.analytics.descriptive_snapshot(actor, wid, did, run.upload_id, source)
            )
            view = context.view
            request = with_sample(table, prediction_request(context, table, raw))
            if request != evidence["request"] or evidence["definition"] != view.definition:
                raise invalid
            run_table, run_view = sampled_input(table, view, request)
            plan = replace(
                prediction_plan(scope, did, view, request), query_id=UUID(evidence["query_id"])
            )
            with self.uow() as repo:
                record = repo.query_execution(wid, plan.query_id)
            saved = record.receipt
            expected = receipt(plan, sampled_view(view, request).sources, None)
            if (
                record.actor_id != run.owner_id
                or record.dataset_id != did
                or record.aggregation != "analysis"
                or record.sql != plan.sql
                or saved.get("outcome") != "executed"
                or any(
                    saved.get(key) != expected[key] for key in ("version", "sources", "parameters")
                )
            ):
                raise invalid
            value = await self.analytics.executor.execute(plan, scope, run_table, run_view)
            if receipt(plan, run_view.sources, value) != saved:
                raise invalid
            result = await read_complete(
                lambda: prediction_result(value, request, trainer.fit, trainer.engine_version)
            )
            if result != run.result or checksum(result) != evidence["result_checksum"]:
                raise invalid
        except (KeyError, TypeError, ValueError, IndexError):
            raise invalid from None
        self.service._owned(actor, wid, did, run.id)
        return await self.service._body(actor, run)
