"""Use case: Exports an actor's existing, source-checked answer as a PDF.

What it does: Reopens saved evidence, prepares exact content, bounds rendering and
reauthorizes after generation without persisting exports or invoking a model.
"""

import asyncio
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime, timezone
from typing import cast
from uuid import UUID, uuid4

from execplus.application.export_ports import PdfRenderer, SavedAnswerResolver
from execplus.application.ports import WorkspaceRepository
from execplus.application.services.data_diagrams import DiagramAnswer
from execplus.application.services.dataset_access import (
    authorize_sources,
    dataset_access,
    scoped_definition,
)
from execplus.application.services.forecasts import read_complete
from execplus.application.services.intent_router import DatasetGuide, PatternAnswer
from execplus.application.services.thread_export_documents import extended_sections, thread_charts
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.models import CalculationLineage, QueryResult, Scalar, VerifiedMetricAnswer
from execplus.domain.pdf_exports import (
    PdfDocument,
    PdfDownload,
    PdfSection,
    PdfTable,
    ReportAnswer,
    validate_document,
)
from execplus.domain.public_evidence import public_evidence

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


def _cell(value: Scalar) -> str:
    if value is None:
        return "Missing (null)"
    if isinstance(value, bool):
        return "true" if value else "false"
    return value.isoformat() if isinstance(value, date | datetime) else str(value)


class PdfExportService:
    def __init__(
        self, unit_of_work: UnitOfWork, resolver: SavedAnswerResolver, renderer: PdfRenderer
    ) -> None:
        self.uow = unit_of_work
        self.resolver = resolver
        self.renderer = renderer
        self._render_slots = asyncio.Semaphore(2)

    async def describe(self, actor: User, wid: UUID, tid: UUID, turn_id: UUID) -> ReportAnswer:
        document, _ = await self._prepare(actor, wid, tid, turn_id)
        self.renderer.validate(document)
        return ReportAnswer(
            tid,
            turn_id,
            "Download this saved answer as PDF",
            f"/workspaces/{wid}/threads/{tid}/turns/{turn_id}/export.pdf",
        )

    async def download(self, actor: User, wid: UUID, tid: UUID, turn_id: UUID) -> PdfDownload:
        if self._render_slots.locked():
            raise IngestionError(
                "pdf_export_busy", "PDF generation is busy. Please try again shortly.", 429
            )
        async with self._render_slots:
            generated_at = datetime.now(timezone.utc)
            document, sources = await self._prepare(actor, wid, tid, turn_id, generated_at)
            content = await read_complete(lambda: self.renderer.render(document))
            checked, checked_sources = await self._prepare(actor, wid, tid, turn_id, generated_at)
            if checked != document or checked_sources != sources:
                raise IngestionError(
                    "source_changed",
                    "The answer or its source changed while the PDF was being prepared. "
                    "Open the saved answer and try again.",
                    409,
                )
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                repo.membership(wid, actor.id)
                authorize_sources(repo, actor, wid, sources)
                thread = repo.thread(wid, tid)
                if thread.owner_id != actor.id:
                    raise IngestionError("not_found", "The conversation is unavailable.", 404)
                repo.upload(wid, thread.dataset_id, thread.upload_id)
                final_sources = self._source_sections(repo, actor, wid, sources)
                if final_sources != document.sections[-len(final_sources) :]:
                    raise IngestionError(
                        "source_changed", "The source changed. Please prepare the PDF again.", 409
                    )
                repo.add(
                    AuditEvent(
                        uuid4(), wid, actor.id, "pdf.exported", "thread_turn", turn_id, generated_at
                    )
                )
            return PdfDownload(f"execplus-answer-{turn_id}.pdf", content)

    async def _prepare(
        self,
        actor: User,
        wid: UUID,
        tid: UUID,
        turn_id: UUID,
        generated_at: datetime | None = None,
        *,
        validate_pdf: bool = True,
    ) -> tuple[PdfDocument, tuple[dict[str, str], ...]]:
        _, turns = await self.resolver.get_thread(actor, wid, tid)
        turn = next((item for item in turns if item.id == turn_id), None)
        if turn is None:
            raise IngestionError("not_found", "The saved answer is unavailable.", 404)
        if turn.status != "complete":
            raise IngestionError(
                "pdf_export_unavailable", "Choose a completed saved answer to make a PDF.", 409
            )
        answer = await self.resolver.resolve(actor, wid, tid, turn_id)
        sections = [
            PdfSection(
                "Saved answer",
                (
                    turn.question,
                    f"Saved: {turn.created_at.isoformat()}",
                    f"Conversation: {tid}; answer: {turn_id}",
                    "Private export of an existing answer. This is not a fresh analysis. "
                    "A downloaded copy cannot be recalled after sharing.",
                ),
            )
        ]
        lineage: CalculationLineage | None = None
        if isinstance(answer, VerifiedMetricAnswer):
            lineage = answer.lineage
            sections.append(
                PdfSection(
                    "Calculated result", table=PdfTable((answer.label,), ((_cell(answer.value),),))
                )
            )
        elif (
            isinstance(answer, tuple)
            and len(answer) == 2
            and isinstance(answer[0], QueryResult)
            and isinstance(answer[1], CalculationLineage)
        ):
            result, lineage = answer
            sections.append(
                PdfSection(
                    "Exact returned values",
                    (
                        f"Returned rows: {len(result.rows)}. Records analyzed: "
                        f"{result.records_analyzed}.",
                        "Missing cells are written as Missing (null). A zero is a real value. "
                        "This table includes every returned row, not necessarily every source row.",
                    )
                    + (
                        (f"Matching source records: {result.matched_records}.",)
                        if result.matched_records is not None
                        else ()
                    ),
                    PdfTable(result.columns, tuple(tuple(map(_cell, row)) for row in result.rows)),
                )
            )
        elif isinstance(answer, DatasetGuide) and answer.sources:
            sections.append(
                PdfSection(
                    "Saved explanation",
                    (
                        "This is a saved qualitative explanation, not a new calculation. "
                        "Interpretations may be fallible; saved definitions and source evidence "
                        "remain authoritative.",
                        answer.message,
                        f"Definition status at the saved answer: {answer.definition_state}.",
                    ),
                )
            )
            if answer.suggestions:
                sections.append(PdfSection("Suggested questions, not results", answer.suggestions))
            sources = answer.sources
        elif isinstance(answer, DiagramAnswer | PatternAnswer):
            sections.extend(extended_sections(answer))
            sources = (
                answer.sources
                if isinstance(answer, DiagramAnswer)
                else tuple(answer.evidence["sources"])
            )
        else:
            raise IngestionError(
                "pdf_export_unsupported",
                (
                    "Open an executed calculation, diagram, measured pattern or source-backed "
                    "explanation."
                ),
                422,
            )
        if lineage is not None:
            receipt = lineage.receipt
            raw_sources = receipt.get("sources")
            if (
                receipt.get("version") != "execution-v1"
                or receipt.get("outcome") != "executed"
                or not isinstance(raw_sources, list)
                or not raw_sources
            ):
                raise IngestionError(
                    "pdf_export_unavailable", "This answer has no complete execution receipt.", 409
                )
            sources = tuple(cast(list[dict[str, str]], raw_sources))
            sections.extend(
                (
                    PdfSection(
                        "Calculation and scope",
                        (
                            f"Dataset: {lineage.dataset_name}",
                            f"Measure: {lineage.metric}; operation: {lineage.aggregation}",
                            f"Records analyzed: {lineage.records_analyzed}",
                            "Groups: " + (", ".join(lineage.grouping) or "None"),
                            "Filters: " + ("; ".join(lineage.filters) or "None"),
                            f"Query: {lineage.query_id}",
                            f"Execution method: {receipt['version']}",
                            "No new forecast, assumption or causal conclusion is added by export.",
                        ),
                    ),
                    PdfSection("Executed query", (lineage.sql,)),
                    PdfSection(
                        "Execution receipt",
                        (
                            json.dumps(
                                public_evidence(receipt),
                                ensure_ascii=False,
                                sort_keys=True,
                                indent=2,
                            ),
                        ),
                    ),
                )
            )
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            sections.extend(self._source_sections(repo, actor, wid, sources))
        document = PdfDocument(
            "ExecPlus - saved answer",
            generated_at or datetime.now(timezone.utc),
            tuple(sections),
            thread_charts(answer),
        )
        if validate_pdf:
            validate_document(document)
        return document, sources

    def _source_sections(
        self, repo: WorkspaceRepository, actor: User, wid: UUID, sources: tuple[dict[str, str], ...]
    ) -> tuple[PdfSection, ...]:
        authorize_sources(repo, actor, wid, sources)
        sections = []
        for index, source in enumerate(sources, 1):
            did, uid, rid = (
                UUID(source["dataset_id"]),
                UUID(source["upload_id"]),
                UUID(source["revision_id"]),
            )
            upload = repo.upload(wid, did, uid)
            revision = repo.revision(wid, did, uid, rid)
            if (
                upload.checksum != source["source_checksum"]
                or revision.output_checksum != source["output_checksum"]
            ):
                raise IngestionError("source_integrity", "The saved source changed.", 409)
            active = repo.active_revision(wid, did, uid)
            latest = repo.latest_understanding(wid, did)
            meaning_id = source.get("understanding_id")
            meaning = repo.understanding(wid, did, UUID(meaning_id)) if meaning_id else None
            feeds = repo.refresh_feeds(wid, did)
            current = (
                active is not None
                and active.id == rid
                and (str(latest.id) if latest else None) == meaning_id
                and all(str(feed.source.get("upload_id")) == str(uid) for feed in feeds)
            )
            state = (
                "Current recorded source at generation" if current else "Historical source snapshot"
            )
            access = dataset_access(repo, actor, wid, did)
            definition = meaning.definition if meaning else None
            if definition and access.restricted:
                headers = access.columns or tuple(item["name"] for item in definition["columns"])
                definition = scoped_definition(definition, access, headers)[0]
            paragraphs = (
                f"File: {upload.filename}",
                f"Freshness: {state}. No claim about data outside the imported file is made.",
                f"Definition version: {meaning.version if meaning else 'not recorded'}; "
                f"state: {meaning.state if meaning else 'inferred'}",
                json.dumps(public_evidence(source), ensure_ascii=False, sort_keys=True, indent=2),
            ) + (
                (
                    "Saved business definitions and units:",
                    json.dumps(definition, ensure_ascii=False, sort_keys=True, indent=2),
                )
                if meaning
                else ("No saved business definitions are recorded for this answer.",)
            )
            sections.append(PdfSection(f"Source evidence {index}", paragraphs))
        return tuple(sections)
