"""Use case: Saves and replays private seasonal and calendar-distribution analyses.

What it does: Retains every authorized calendar receipt, immutable method output
and projected source definition while preserving current policy and source checks.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

from execplus.application.services.dataset_access import authorize_sources
from execplus.application.services.forecasts import read_complete
from execplus.application.services.studies import audit
from execplus.application.services.workspaces import checked_name
from execplus.domain.calendar_anomaly_requests import calculate_calendar, calendar_windows
from execplus.domain.decision_analysis import AnalysisRun, checksum
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.evidence import receipt
from execplus.domain.forecast_series import series_plan, series_request
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.models import CalculationLineage, QueryResult
from execplus.domain.rolling_anomalies import METHOD as ROLLING_METHOD

if TYPE_CHECKING:
    from execplus.application.services.decision_analysis import DecisionAnalysisService

COVERAGE_DECLARATION = "The user explicitly confirmed complete coverage for each chosen window."


class CalendarAnalysis:
    def __init__(self, service: DecisionAnalysisService) -> None:
        self.service = service
        self.uow, self.analytics = service.uow, service.analytics

    async def create(
        self, actor: User, wid: UUID, did: UUID, uid: UUID, raw: dict[str, Any]
    ) -> dict[str, Any]:
        name = checked_name(raw["name"])
        windows = calendar_windows(raw)
        self.service._current(actor, wid, did, uid, raw)
        with self.uow() as repo:
            if len(repo.analysis_runs(wid, did, actor.id)) >= 50:
                raise IngestionError(
                    "analysis_limit", "Use at most 50 saved analyses per dataset/person.", 409
                )
        dataset_name, scope, table, view = await read_complete(
            lambda: self.analytics._context(actor, wid, did, uid)
        )
        source = view.sources[0]
        if (
            source["revision_id"] != raw["revision_id"]
            or source.get("understanding_id") != raw["understanding_id"]
        ):
            raise ClarificationRequiredError(
                "The source changed. Reload calendar analysis options."
            )
        definition = view.definition or {}
        column = next(
            (item for item in definition.get("columns", []) if item["name"] == raw["metric"]), None
        )
        if (
            not column
            or not (column.get("currency") or column.get("unit"))
            or column.get("unit_column")
        ):
            raise IngestionError(
                "unit_required", "Choose a measure with a confirmed fixed unit.", 422
            )
        unit = column.get("currency") or column["unit"]
        results: list[list[QueryResult]] = []
        query_ids: list[list[str]] = []
        for window in windows:
            request = series_request(window, table, view)
            window_results = []
            window_ids = []
            for kind in ("value", "present", "samples"):
                plan = replace(
                    series_plan(scope, did, view, request, raw["frequency"], kind),
                    question="Private calendar analysis evidence",
                )
                lineage = CalculationLineage(
                    plan.query_id,
                    wid,
                    did,
                    dataset_name,
                    len(table.rows),
                    raw["metric"],
                    "analysis",
                    (),
                    (),
                    plan.sql,
                    f"deterministic:{raw['model']}",
                )
                self.service._current(actor, wid, did, uid, raw)
                try:
                    result = await self.analytics.executor.execute(plan, scope, table, view)
                except (Exception, asyncio.CancelledError):
                    self.analytics._persist(
                        actor, replace(lineage, receipt=receipt(plan, view.sources, None))
                    )
                    raise
                self.analytics._persist(
                    actor, replace(lineage, receipt=receipt(plan, view.sources, result))
                )
                window_results.append(result)
                window_ids.append(str(plan.query_id))
            results.append(window_results)
            query_ids.append(window_ids)
        if raw["model"] == ROLLING_METHOD:
            self.service._admit_model(actor, wid, did, uid, raw, view.sources)
        calculated = await read_complete(lambda: calculate_calendar(raw, results))
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, view.sources)
        )
        evidence = dict(
            query_id=query_ids[0][0],
            calendar_query_ids=query_ids,
            sources=list(view.sources),
            definition=view.definition,
            units={raw["metric"]: unit},
            series_version="calendar-v1",
            request_checksum=checksum(raw),
            result_checksum=checksum(calculated),
            matching_records=sum(cast(int, row[1]) for values in results for row in values[2].rows),
            coverage_declaration=COVERAGE_DECLARATION,
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
            "robust_distribution",
            raw["model"],
            raw,
            evidence,
            calculated,
            datetime.now(timezone.utc),
        )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self.service._current(actor, wid, did, uid, raw)
            authorize_sources(repo, actor, wid, evidence["sources"], did)
            if len(repo.analysis_runs(wid, did, actor.id)) >= 50:
                raise IngestionError(
                    "analysis_limit", "Use at most 50 saved analyses per dataset/person.", 409
                )
            repo.add(run)
            audit(repo, actor, wid, "analysis.created", run.id)
        return await self.service._body(actor, run)

    async def open(self, actor: User, run: AnalysisRun) -> dict[str, Any]:
        invalid = IngestionError(
            "lineage_mismatch", "The saved calendar analysis evidence is inconsistent.", 409
        )
        wid, did = run.workspace_id, run.dataset_id
        try:
            raw, evidence = run.request, run.evidence
            if (
                run.kind != raw["kind"]
                or run.method_version != raw["model"]
                or checksum(raw) != evidence["request_checksum"]
            ):
                raise invalid
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
            if raw["revision_id"] != str(run.revision_id) or raw["understanding_id"] != str(
                run.understanding_id
            ):
                raise invalid
            _, scope, table, view = await read_complete(
                lambda: self.analytics.context_at(actor, wid, source)
            )
            column = next(
                item for item in (view.definition or {})["columns"] if item["name"] == raw["metric"]
            )
            if (
                evidence["definition"] != view.definition
                or evidence["units"] != {raw["metric"]: column["currency"] or column["unit"]}
                or evidence["series_version"] != "calendar-v1"
                or evidence["coverage_declaration"] != COVERAGE_DECLARATION
            ):
                raise invalid
            windows = calendar_windows(raw)
            identifiers = evidence["calendar_query_ids"]
            if len(identifiers) != len(windows) or any(len(items) != 3 for items in identifiers):
                raise invalid
            all_ids = [value for items in identifiers for value in items]
            if len(set(all_ids)) != len(windows) * 3 or evidence["query_id"] != all_ids[0]:
                raise invalid
            results: list[list[QueryResult]] = []
            for window, ids in zip(windows, identifiers, strict=True):
                request = series_request(window, table, view)
                window_results = []
                for kind, identifier in zip(("value", "present", "samples"), ids, strict=True):
                    plan = replace(
                        series_plan(scope, did, view, request, raw["frequency"], kind),
                        query_id=UUID(identifier),
                        question="Private calendar analysis evidence",
                    )
                    with self.uow() as repo:
                        record = repo.query_execution(wid, plan.query_id)
                    expected = receipt(plan, view.sources, None)
                    saved = record.receipt
                    if (
                        record.actor_id != run.owner_id
                        or record.dataset_id != did
                        or record.aggregation != "analysis"
                        or record.model_route != f"deterministic:{raw['model']}"
                        or record.sql != plan.sql
                        or saved.get("outcome") != "executed"
                        or any(
                            saved.get(key) != expected[key]
                            for key in ("version", "sources", "parameters")
                        )
                    ):
                        raise invalid
                    result = await self.analytics.executor.execute(plan, scope, table, view)
                    if receipt(plan, view.sources, result) != saved:
                        raise invalid
                    window_results.append(result)
                results.append(window_results)
            rebuilt = await read_complete(lambda: calculate_calendar(raw, results))
            if (
                rebuilt != run.result
                or checksum(rebuilt) != evidence["result_checksum"]
                or evidence["matching_records"]
                != sum(cast(int, row[1]) for values in results for row in values[2].rows)
            ):
                raise invalid
        except (KeyError, TypeError, ValueError, IndexError, StopIteration):
            raise invalid from None
        with self.uow() as repo:
            upload = repo.upload(wid, did, run.upload_id)
        await read_complete(lambda: self.analytics.storage.read(upload))
        self.service._owned(actor, wid, did, run.id)
        return await self.service._body(actor, run)
