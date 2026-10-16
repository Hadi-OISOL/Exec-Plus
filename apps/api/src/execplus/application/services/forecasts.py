"""Use case: Creates private forecasts and compares them with authorized later actuals.

What it does: Governs calendar queries, retains immutable evidence and renders grounded commentary.
"""

import asyncio
import hashlib
import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from typing import Any, TypeVar
from uuid import UUID, uuid4

from execplus.application.services.analytics import AnalyticsService, UnitOfWork
from execplus.application.services.dataset_access import authorize_sources, dataset_access
from execplus.application.services.studies import audit
from execplus.application.services.workspaces import checked_name
from execplus.domain.advanced_forecasting import (
    ENGINE as ADVANCED_ENGINE,
)
from execplus.domain.advanced_forecasting import (
    METHOD_CATALOG,
    advanced_forecast,
    compare_advanced_forecast,
    minimum_history,
)
from execplus.domain.advanced_forecasting import (
    VERSION as ADVANCED_VERSION,
)
from execplus.domain.analysis_readiness import forecast_options
from execplus.domain.errors import AuthorizationError, ClarificationRequiredError
from execplus.domain.evidence import receipt, result_evidence, scalar_record
from execplus.domain.forecast_records import ForecastComparison, ForecastRun
from execplus.domain.forecast_series import series_plan, series_request, series_values
from execplus.domain.forecasting import (
    VERSION,
    ForecastPoint,
    ForecastRequest,
    compare_forecast,
    forecast,
)
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.models import CalculationLineage, QueryResult, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView

T = TypeVar("T")


async def read_complete(call: Callable[[], T]) -> T:
    pending = asyncio.create_task(asyncio.to_thread(call))
    try:
        return await asyncio.shield(pending)
    except asyncio.CancelledError:
        with suppress(Exception, asyncio.CancelledError):
            await pending
        raise


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def engine_version(raw: dict[str, Any]) -> str:
    engine = raw.get("engine", "basic-v1")
    if engine not in {"basic-v1", ADVANCED_ENGINE}:
        raise IngestionError("forecast_engine", "Choose a supported forecast engine.", 422)
    if engine == "basic-v1" and raw.get("method_family", "auto") != "auto":
        raise IngestionError(
            "forecast_method", "Specific smoothing methods require Advanced forecasting.", 422
        )
    if engine == ADVANCED_ENGINE:
        minimum_history(
            ForecastRequest(raw["frequency"], raw["horizon"], raw.get("season_length")),
            raw.get("method_family", "auto"),
        )
    return ADVANCED_VERSION if engine == ADVANCED_ENGINE else VERSION


def calculate_forecast(points: tuple[ForecastPoint, ...], raw: dict[str, Any]) -> dict[str, Any]:
    request = ForecastRequest(raw["frequency"], raw["horizon"], raw.get("season_length"))
    return (
        advanced_forecast(points, request, raw.get("method_family", "auto"))
        if engine_version(raw) == ADVANCED_VERSION
        else forecast(points, request)
    ).to_record()


def calculate_comparison(
    result: dict[str, Any], points: tuple[ForecastPoint, ...]
) -> dict[str, Any]:
    return (
        compare_advanced_forecast(result, points)
        if result.get("version") == ADVANCED_VERSION
        else compare_forecast(result, points)
    )


def commentary(result: dict[str, Any], metric: str, unit: str) -> list[str]:
    last = result["history"][-1]
    first = result["predictions"][0]
    accuracy = result["accuracy"]
    previous = result["history"][-2]
    with localcontext() as context:
        context.prec = 128
        change = Decimal(last["actual"]) - Decimal(previous["actual"])
    direction = "increased by" if change > 0 else "decreased by" if change < 0 else "changed by"
    range_label = (
        "empirical validation-error" if result["version"] == ADVANCED_VERSION else "heuristic"
    )
    return [
        f"The last complete period ({last['period']}) recorded "
        f"{last['actual']} {unit} for {metric}.",
        f"Compared with {previous['period']} ({previous['actual']} {unit}), "
        f"the actual {direction} {format(abs(change), 'f')} {unit}. "
        "This is a measured period difference, not an explanation of its cause.",
        f"The next-period estimate ({first['period']}) is {first['estimate']} {unit}, using "
        f"{result['method']['id'].replace('_', ' ')}. Its {range_label} range is "
        f"{first['lower']} to {first['upper']} {unit}; it is not guaranteed.",
        f"On {accuracy['count']} untouched historical test periods, mean absolute error was "
        f"{accuracy['mae']} {unit}. This describes past test error, "
        "not a percentage guarantee of future accuracy.",
        "Review the source coverage and business context before making decisions. "
        "This forecast does not establish causes or prescribe actions.",
    ]


def comparison_commentary(result: dict[str, Any], unit: str) -> list[str]:
    metrics = result["metrics"]
    return [
        f"Actuals are available for {result['observed_count']} forecast periods; "
        f"{result['pending_count']} periods remain pending. "
        "Missing periods are not treated as zero.",
        (
            f"Observed mean absolute error is {metrics['mae']} {unit}; "
            f"root mean squared error is {metrics['rmse']} {unit}."
        )
        if metrics["count"]
        else "No complete matching actual period is available to score yet.",
        "The original forecast is unchanged. Differences measure forecast error, not its cause.",
    ]


class ForecastService:
    def __init__(self, uow: UnitOfWork, analytics: AnalyticsService) -> None:
        self.uow, self.analytics = uow, analytics

    async def options(self, actor: User, wid: UUID, did: UUID, uid: UUID) -> dict[str, Any]:
        context = await read_complete(lambda: self.analytics.describe(actor, wid, did, uid))
        return {**forecast_options(context), "advanced_methods": list(METHOD_CATALOG)}

    def _current(self, actor: User, wid: UUID, did: UUID, uid: UUID, raw: dict[str, Any]) -> None:
        with self.uow() as repo:
            dataset_access(repo, actor, wid, did)
            repo.upload(wid, did, uid)
            revision = repo.active_revision(wid, did, uid)
            meaning = repo.latest_understanding(wid, did)
            if (
                not revision
                or str(revision.id) != raw["revision_id"]
                or not meaning
                or meaning.revision_id != revision.id
                or meaning.state != "confirmed"
                or str(meaning.id) != raw["understanding_id"]
            ):
                raise ClarificationRequiredError(
                    "Review the current source and confirmed meaning before forecasting."
                )

    def _owned(self, actor: User, wid: UUID, did: UUID, fid: UUID) -> ForecastRun:
        with self.uow() as repo:
            dataset_access(repo, actor, wid, did)
            run = repo.forecast_run(wid, fid, actor.id)
            if run.dataset_id != did:
                raise AuthorizationError("Forecast source mismatch")
            repo.upload(wid, did, run.upload_id)
            authorize_sources(repo, actor, wid, run.evidence.get("sources"), did)
            return run

    async def _series(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        uid: UUID,
        raw: dict[str, Any],
        expected_definition: dict[str, Any] | None = None,
    ) -> tuple[list[QueryResult], dict[str, Any]]:
        self._current(actor, wid, did, uid, raw)
        name, scope, table, view = await read_complete(
            lambda: self.analytics._context(actor, wid, did, uid)
        )
        if (
            view.sources[0].get("revision_id") != raw["revision_id"]
            or view.sources[0].get("understanding_id") != raw["understanding_id"]
        ):
            raise ClarificationRequiredError("The source changed. Reload forecasting options.")
        if expected_definition is not None and view.definition != expected_definition:
            raise IngestionError(
                "forecast_definition_changed",
                "The metric meaning changed. Create a new forecast before comparing.",
                409,
            )
        request = series_request(raw, table, view)
        results: list[QueryResult] = []
        query_ids = []
        for kind in ("value", "present", "samples"):
            result = await self._measure(actor, did, name, scope, table, view, raw, request, kind)
            results.append(result)
            query_ids.append(str(result.query_id))
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, view.sources)
        )
        definition = view.definition or {}
        column = next(c for c in definition["columns"] if c["name"] == raw["metric"])
        unit = "records" if raw["aggregation"] == "count" else column["currency"] or column["unit"]
        if not unit:
            raise IngestionError(
                "unit_required", "Declare a fixed unit for this forecast measure.", 422
            )
        return results, dict(
            query_ids=query_ids,
            sources=list(view.sources),
            definition=definition,
            unit=unit,
            request=raw,
            series_version="calendar-v1",
            limitations=[
                "Coverage is explicitly declared by the user; "
                "observed dates alone do not prove completeness.",
                "This saved forecast and commentary describe retained snapshots "
                "and never update silently.",
            ],
        )

    async def _measure(
        self,
        actor: User,
        did: UUID,
        name: str,
        scope: WorkspaceScope,
        table: TableData,
        view: DatasetView,
        raw: dict[str, Any],
        request: Any,
        kind: str,
    ) -> QueryResult:
        plan = series_plan(scope, did, view, request, raw["frequency"], kind)
        lineage = CalculationLineage(
            plan.query_id,
            scope.workspace_id,
            did,
            name,
            len(table.rows),
            request.metric,
            request.aggregation.value if kind == "value" else "count",
            request.group_by,
            tuple(f"{c.column} {c.operator.value} {c.value!r}" for c in request.filters),
            plan.sql,
            "deterministic:forecast-v1",
        )
        with self.uow() as repo:
            repo.membership(scope.workspace_id, actor.id)
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
        return result

    def list_forecasts(self, actor: User, wid: UUID, did: UUID) -> list[dict[str, Any]]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            dataset_access(repo, actor, wid, did)
            allowed = []
            for run in repo.forecast_runs(wid, did, actor.id):
                try:
                    authorize_sources(repo, actor, wid, run.evidence.get("sources"), did)
                except IngestionError as error:
                    if error.status != 404:
                        raise
                else:
                    allowed.append(run)
            return [
                dict(
                    id=str(r.id),
                    name=r.name,
                    created_at=r.created_at,
                    upload_id=str(r.upload_id),
                    revision_id=str(r.revision_id),
                    understanding_id=str(r.understanding_id),
                    method=r.method,
                    method_version=r.method_version,
                    request=r.request,
                )
                for r in allowed
            ]

    async def create(
        self, actor: User, wid: UUID, did: UUID, uid: UUID, raw: dict[str, Any]
    ) -> ForecastRun:
        name = checked_name(raw["name"])
        engine_version(raw)
        if len(self.list_forecasts(actor, wid, did)) >= 50:
            raise IngestionError(
                "forecast_limit",
                "At most 50 saved forecasts per dataset and person are supported.",
                409,
            )
        results, evidence = await self._series(actor, wid, did, uid, raw)
        points = tuple(
            ForecastPoint(period, value) for period, value in series_values(results, raw)
        )
        result = await read_complete(lambda: calculate_forecast(points, raw))
        result["commentary"] = commentary(result, raw["metric"], evidence["unit"])
        evidence["result_checksum"] = digest(result)
        value = ForecastRun(
            uuid4(),
            wid,
            did,
            actor.id,
            name,
            uid,
            UUID(raw["revision_id"]),
            UUID(raw["understanding_id"]),
            result["method"]["id"],
            result["version"],
            raw,
            evidence,
            result,
            datetime.now(timezone.utc),
        )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self._current(actor, wid, did, uid, raw)
            authorize_sources(repo, actor, wid, evidence["sources"], did)
            if len(repo.forecast_runs(wid, did, actor.id)) >= 50:
                raise IngestionError("forecast_limit", "The saved forecast limit was reached.", 409)
            repo.add(value)
            audit(repo, actor, wid, "forecast.created", value.id)
        return value

    async def _replay(
        self,
        actor: User,
        value: ForecastRun | ForecastComparison,
        raw: dict[str, Any],
    ) -> list[QueryResult]:
        evidence = value.evidence
        invalid = IngestionError(
            "lineage_mismatch", "The saved forecast evidence is inconsistent.", 409
        )
        try:
            keys = evidence["query_ids"]
            if not isinstance(keys, list) or len(keys) != 3:
                raise invalid
            query_ids = [UUID(key) for key in keys]
            if len(set(query_ids)) != 3 or len(evidence["sources"]) != 1:
                raise invalid
            source = evidence["sources"][0]
            if (
                source["dataset_id"] != str(value.dataset_id)
                or source["upload_id"] != str(value.upload_id)
                or source["revision_id"] != str(value.revision_id)
                or source["understanding_id"] != str(value.understanding_id)
                or raw["revision_id"] != str(value.revision_id)
                or raw["understanding_id"] != str(value.understanding_id)
                or raw != evidence["request"]
                or evidence["series_version"] != "calendar-v1"
            ):
                raise invalid
        except (KeyError, TypeError, ValueError, AttributeError):
            raise invalid from None
        _, scope, table, view = await read_complete(
            lambda: self.analytics.context_at(actor, value.workspace_id, source)
        )
        if view.definition != evidence["definition"] or list(view.sources) != evidence["sources"]:
            raise invalid
        request = series_request(raw, table, view)
        column = next(c for c in (view.definition or {})["columns"] if c["name"] == raw["metric"])
        unit = "records" if raw["aggregation"] == "count" else column["currency"] or column["unit"]
        if evidence["unit"] != unit:
            raise invalid
        results = []
        for query_id, kind in zip(query_ids, ("value", "present", "samples"), strict=True):
            plan = replace(
                series_plan(scope, value.dataset_id, view, request, raw["frequency"], kind),
                query_id=query_id,
            )
            with self.uow() as repo:
                repo.membership(value.workspace_id, actor.id)
                execution = repo.query_execution(value.workspace_id, query_id)
            saved = execution.receipt
            if (
                execution.actor_id != value.owner_id
                or execution.dataset_id != value.dataset_id
                or execution.sql != plan.sql
                or saved.get("version") != "execution-v1"
                or saved.get("outcome") != "executed"
                or saved.get("sources") != evidence["sources"]
                or saved.get("parameters") != [scalar_record(p) for p in plan.params]
            ):
                raise invalid
            result = await self.analytics.executor.execute(plan, scope, table, view)
            if result_evidence(result)["checksum"] != saved.get("result_checksum"):
                raise invalid
            results.append(result)
        with self.uow() as repo:
            repo.membership(value.workspace_id, actor.id)
            upload = repo.upload(value.workspace_id, value.dataset_id, value.upload_id)
        await read_complete(lambda: self.analytics.storage.read(upload))
        with self.uow() as repo:
            repo.membership(value.workspace_id, actor.id)
        return results

    async def open(self, actor: User, wid: UUID, did: UUID, fid: UUID) -> ForecastRun:
        value = self._owned(actor, wid, did, fid)
        try:
            version = engine_version(value.request)
        except (IngestionError, KeyError, TypeError, ValueError):
            raise IngestionError(
                "lineage_mismatch", "The saved forecast method is inconsistent.", 409
            ) from None
        if (
            value.method_version != version
            or value.result.get("version") != value.method_version
            or value.method != value.result.get("method", {}).get("id")
        ):
            raise IngestionError(
                "lineage_mismatch", "The saved forecast method is inconsistent.", 409
            )
        results = await self._replay(actor, value, value.request)
        points = tuple(
            ForecastPoint(period, actual)
            for period, actual in series_values(results, value.request)
        )
        rebuilt = await read_complete(lambda: calculate_forecast(points, value.request))
        rebuilt["commentary"] = commentary(rebuilt, value.request["metric"], value.evidence["unit"])
        if digest(rebuilt) != value.evidence["result_checksum"] or rebuilt != value.result:
            raise IngestionError(
                "lineage_mismatch", "The saved forecast failed evidence verification.", 409
            )
        self._owned(actor, wid, did, fid)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            authorize_sources(repo, actor, wid, value.evidence.get("sources"), did)
            audit(repo, actor, wid, "forecast.opened", fid)
        return value

    async def compare(
        self, actor: User, wid: UUID, did: UUID, fid: UUID, raw: dict[str, Any]
    ) -> ForecastComparison:
        original = await self.open(actor, wid, did, fid)
        uid = UUID(raw["upload_id"])
        request = {**original.request, **raw}
        results, evidence = await self._series(
            actor, wid, did, uid, request, original.evidence["definition"]
        )
        points = tuple(
            ForecastPoint(period, value)
            for period, value in series_values(results, request, allow_missing=True)
        )
        result = calculate_comparison(original.result, points)
        result["commentary"] = comparison_commentary(result, evidence["unit"])
        evidence["result_checksum"] = digest(result)
        value = ForecastComparison(
            uuid4(),
            wid,
            did,
            actor.id,
            fid,
            uid,
            UUID(raw["revision_id"]),
            UUID(raw["understanding_id"]),
            evidence,
            result,
            datetime.now(timezone.utc),
        )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self._current(actor, wid, did, uid, raw)
            self._owned(actor, wid, did, fid)
            authorize_sources(repo, actor, wid, evidence["sources"], did)
            if len(repo.forecast_comparisons(wid, fid, actor.id)) >= 50:
                raise IngestionError(
                    "forecast_limit", "At most 50 comparisons per forecast are supported.", 409
                )
            repo.add(value)
            audit(repo, actor, wid, "forecast.compared", value.id)
        return value

    def comparisons(self, actor: User, wid: UUID, did: UUID, fid: UUID) -> list[dict[str, Any]]:
        original = self._owned(actor, wid, did, fid)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            authorize_sources(repo, actor, wid, original.evidence.get("sources"), did)
            allowed = []
            for comparison in repo.forecast_comparisons(wid, fid, actor.id):
                try:
                    authorize_sources(repo, actor, wid, comparison.evidence.get("sources"), did)
                except IngestionError as error:
                    if error.status != 404:
                        raise
                else:
                    allowed.append(comparison)
            return [
                dict(
                    id=str(c.id),
                    forecast_id=str(c.forecast_id),
                    upload_id=str(c.upload_id),
                    created_at=c.created_at,
                )
                for c in allowed
            ]

    async def open_comparison(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        fid: UUID,
        cid: UUID,
    ) -> ForecastComparison:
        original = await self.open(actor, wid, did, fid)
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            value = repo.forecast_comparison(wid, cid, actor.id)
            if value.forecast_id != fid or value.dataset_id != did:
                raise AuthorizationError("Forecast comparison mismatch")
            authorize_sources(repo, actor, wid, value.evidence.get("sources"), did)
        if value.evidence["definition"] != original.evidence["definition"]:
            raise IngestionError(
                "lineage_mismatch", "The comparison meaning differs from its forecast.", 409
            )
        actual_fields = {
            "upload_id",
            "revision_id",
            "understanding_id",
            "coverage_start",
            "coverage_end",
            "coverage_confirmed",
        }
        request = value.evidence["request"]
        expected = {**original.request, **{key: request[key] for key in actual_fields}}
        if request != expected or request["upload_id"] != str(value.upload_id):
            raise IngestionError(
                "lineage_mismatch", "The actual comparison method differs from its forecast.", 409
            )
        results = await self._replay(actor, value, request)
        points = tuple(
            ForecastPoint(period, actual)
            for period, actual in series_values(
                results, value.evidence["request"], allow_missing=True
            )
        )
        rebuilt = calculate_comparison(original.result, points)
        rebuilt["commentary"] = comparison_commentary(rebuilt, value.evidence["unit"])
        if digest(rebuilt) != value.evidence["result_checksum"] or rebuilt != value.result:
            raise IngestionError(
                "lineage_mismatch", "The saved comparison failed evidence verification.", 409
            )
        self._owned(actor, wid, did, fid)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            authorize_sources(repo, actor, wid, original.evidence.get("sources"), did)
            authorize_sources(repo, actor, wid, value.evidence.get("sources"), did)
        return value
