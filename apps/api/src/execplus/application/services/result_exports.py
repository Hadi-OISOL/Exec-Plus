"""Use case: Exports existing authorized results across portable file formats.

What it does: Replays immutable answers and analyses, rechecks permissions and
source state after bounded rendering, and never trusts browser-supplied values.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.dataset_access import authorize_sources
from execplus.application.services.decision_analysis import DecisionAnalysisService
from execplus.application.services.forecasts import ForecastService, read_complete
from execplus.application.services.pdf_exports import PdfExportService, UnitOfWork
from execplus.application.services.studies import StudyService, visible
from execplus.application.services.thread_export_documents import thread_tables
from execplus.domain.errors import AuthorizationError
from execplus.domain.exports import ExportContent, ExportDownload, ExportTable, validate_export
from execplus.domain.ingestion import AuditEvent, IngestionError, User


class ResultRenderer(Protocol):
    def render(self, content: ExportContent, format: str, chart_index: int = 0) -> bytes: ...


Prepared = tuple[ExportContent, tuple[dict[str, str], ...]]


class ResultExportService:
    def __init__(
        self,
        uow: UnitOfWork,
        pdf: PdfExportService,
        analytics: AnalyticsService,
        studies: StudyService,
        forecasts: ForecastService,
        decisions: DecisionAnalysisService,
        renderer: ResultRenderer,
    ) -> None:
        self.uow, self.pdf, self.analytics = uow, pdf, analytics
        self.studies, self.forecasts, self.decisions, self.renderer = (
            studies,
            forecasts,
            decisions,
            renderer,
        )
        self.slots = asyncio.Semaphore(2)

    async def thread(
        self, actor: User, wid: UUID, tid: UUID, turn_id: UUID, format: str, chart: int = 0
    ) -> ExportDownload:
        async def prepare(now: datetime) -> Prepared:
            document, sources = await self.pdf._prepare(
                actor, wid, tid, turn_id, now, validate_pdf=False
            )
            answer = await self.pdf.resolver.resolve(actor, wid, tid, turn_id)
            tables = thread_tables(answer)
            if not tables:
                tables = (
                    ExportTable(
                        "Saved explanation",
                        ("Section", "Text"),
                        tuple(
                            (section.title, paragraph)
                            for section in document.sections
                            for paragraph in section.paragraphs
                        ),
                    ),
                )
            return ExportContent(document, tables, document.charts), sources

        def guard(repo: WorkspaceRepository) -> object:
            thread = repo.thread(wid, tid)
            if thread.owner_id != actor.id:
                raise AuthorizationError("This conversation is private")
            turn = next((item for item in repo.thread_turns(wid, tid) if item.id == turn_id), None)
            if turn is None:
                raise IngestionError("not_found", "This saved answer is unavailable.", 404)
            return thread, turn

        return await self._deliver(actor, wid, turn_id, format, chart, prepare, guard)

    async def record(
        self,
        actor: User,
        wid: UUID,
        kind: str,
        record_id: UUID,
        dataset_id: UUID | None,
        format: str,
        chart: int = 0,
        forecast_id: UUID | None = None,
    ) -> ExportDownload:
        async def prepare(now: datetime) -> Prepared:
            from execplus.application.services.analysis_report_documents import (
                build_analysis_report,
            )

            if kind == "forecast" and dataset_id:
                record = asdict(await self.forecasts.open(actor, wid, dataset_id, record_id))
                sources = tuple(record["evidence"]["sources"])
            elif kind == "forecast_comparison" and dataset_id and forecast_id:
                record = asdict(
                    await self.forecasts.open_comparison(
                        actor, wid, dataset_id, forecast_id, record_id
                    )
                )
                sources = self._sources(record)
            elif kind in {"scenario", "anomaly", "allocation"} and dataset_id:
                record = await self.decisions.open(actor, wid, dataset_id, record_id)
                expected = {
                    "scenario": "scenario_comparison",
                    "anomaly": "robust_distribution",
                    "allocation": "bounded_allocation",
                }[kind]
                if record["run"]["kind"] != expected:
                    raise IngestionError("not_found", "This saved analysis is unavailable.", 404)
                sources = tuple(record["run"]["evidence"]["sources"])
            elif kind == "dashboard":
                board, values = await self.studies.open_board(actor, wid, record_id)
                record = {
                    "board": asdict(board),
                    "studies": [self._study_record(value) for value in values],
                }
                sources = self._sources(record)
            elif kind == "study":
                record = self._study_record(await self.studies.open(actor, wid, record_id))
                sources = self._sources(record)
            else:
                raise IngestionError(
                    "export_target", "Choose a saved dashboard, study, forecast or analysis.", 422
                )
            content = build_analysis_report(kind, record, now)
            return self._with_sources(actor, wid, content, sources), sources

        def guard(repo: WorkspaceRepository) -> object:
            if kind == "forecast":
                return repo.forecast_run(wid, record_id, actor.id)
            if kind == "forecast_comparison":
                return repo.forecast_comparison(wid, record_id, actor.id)
            if kind in {"scenario", "anomaly", "allocation"}:
                return repo.analysis_run(wid, record_id, actor.id), repo.analysis_reviews(
                    wid, record_id, actor.id
                )
            if kind == "study":
                version = repo.study_version(wid, record_id)
                return visible(repo, actor, wid, version.study_id), version
            board = repo.study_board(wid, record_id)
            if not board.shared and board.owner_id != actor.id:
                raise AuthorizationError("This dashboard is private")
            pins = tuple(repo.study_version(wid, UUID(pin)) for pin in board.pins)
            return board, pins, tuple(visible(repo, actor, wid, pin.study_id) for pin in pins)

        return await self._deliver(actor, wid, record_id, format, chart, prepare, guard)

    async def dashboard(
        self,
        actor: User,
        wid: UUID,
        query_ids: tuple[UUID, ...],
        name: str,
        format: str,
        chart: int = 0,
    ) -> ExportDownload:
        if not query_ids or len(query_ids) > 12 or len(set(query_ids)) != len(query_ids):
            raise IngestionError(
                "export_scope", "Choose one to twelve distinct executed dashboard results.", 422
            )

        async def prepare(now: datetime) -> Prepared:
            from execplus.application.services.analysis_report_documents import (
                build_analysis_report,
            )

            results = []
            for query_id in query_ids:
                result, lineage = await self.analytics.replay(actor, wid, query_id)
                results.append({"result": asdict(result), "lineage": asdict(lineage)})
            record = {"name": name, "results": results}
            sources = self._sources(record)
            return self._with_sources(
                actor, wid, build_analysis_report("dashboard_queries", record, now), sources
            ), sources

        return await self._deliver(actor, wid, query_ids[0], format, chart, prepare)

    def _with_sources(
        self, actor: User, wid: UUID, content: ExportContent, sources: tuple[dict[str, str], ...]
    ) -> ExportContent:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            sections = self.pdf._source_sections(repo, actor, wid, sources)
        document = replace(
            content.document, sections=content.document.sections + sections, charts=content.charts
        )
        return replace(content, document=document)

    async def _deliver(
        self,
        actor: User,
        wid: UUID,
        target_id: UUID,
        format: str,
        chart: int,
        prepare: Callable[[datetime], Awaitable[Prepared]],
        guard: Callable[[WorkspaceRepository], object] | None = None,
    ) -> ExportDownload:
        extensions = {
            "pdf": ("pdf", "application/pdf"),
            "xlsx": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            "csv": ("zip", "application/zip"),
            "png": ("png", "image/png"),
        }
        if format not in extensions:
            raise IngestionError("export_format", "Choose PDF, Excel, CSV or PNG.", 422)
        if self.slots.locked():
            raise IngestionError(
                "export_busy", "Export generation is busy. Please try again shortly.", 429
            )
        async with self.slots:
            now = datetime.now(timezone.utc)
            content, sources = await prepare(now)
            validate_export(content)
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                repo.membership(wid, actor.id)
                authority = guard(repo) if guard else None
            data = await read_complete(lambda: self.renderer.render(content, format, chart))
            current, current_sources = await prepare(now)
            if current != content or current_sources != sources:
                raise IngestionError(
                    "source_changed",
                    "This result, source or review changed during export. Reopen it and try again.",
                    409,
                )
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                repo.membership(wid, actor.id)
                authorize_sources(repo, actor, wid, sources)
                if guard and guard(repo) != authority:
                    raise IngestionError(
                        "source_changed",
                        (
                            "Sharing, review or saved content changed during export. Reopen "
                            "and try again."
                        ),
                        409,
                    )
                final = self.pdf._source_sections(repo, actor, wid, sources)
                if final and content.document.sections[-len(final) :] != final:
                    raise IngestionError(
                        "source_changed", "The recorded source changed during export.", 409
                    )
                repo.add(
                    AuditEvent(uuid4(), wid, actor.id, "result.exported", "export", target_id, now)
                )
            extension, media_type = extensions[format]
            return ExportDownload(f"execplus-result-{target_id}.{extension}", data, media_type)

    @staticmethod
    def _study_record(value: Any) -> dict[str, Any]:
        study, version, results = value
        return {
            "study": asdict(study),
            "version": asdict(version),
            "results": [
                {"result": asdict(result), "lineage": asdict(lineage)}
                for result, lineage in results
            ],
        }

    @staticmethod
    def _sources(value: Any) -> tuple[dict[str, str], ...]:
        found: list[dict[str, str]] = []

        def visit(item: Any) -> None:
            if isinstance(item, dict):
                if {
                    "dataset_id",
                    "upload_id",
                    "revision_id",
                    "source_checksum",
                    "output_checksum",
                } <= item.keys():
                    if item not in found:
                        found.append(item)
                else:
                    for child in item.values():
                        visit(child)
            elif isinstance(item, list | tuple):
                for child in item:
                    visit(child)

        visit(value)
        if not found:
            raise IngestionError(
                "export_integrity", "No complete source evidence is available.", 409
            )
        return tuple(found)
