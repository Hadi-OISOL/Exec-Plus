"""Use case: Keeps resumable conversations private and protects retries from duplicate turns.

What it does: Claims bounded work, records evidence references and reauthorizes historical answers.
"""

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID, uuid4

from execplus.application.conversation import EvidenceAnswer, NumericalAnswer, answer_lineage
from execplus.application.ports import WorkspaceRepository
from execplus.application.services.intent_router import (
    ClarificationContext,
    ConversationAnswer,
    DatasetGuide,
    IntentRouterService,
    PlanningClarification,
)
from execplus.domain.errors import (
    ClarificationRequiredError,
    ProviderUnavailableError,
    QueryDataError,
    UnsafeQueryError,
    UnsupportedQuestionError,
)
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.models import VerifiedMetricAnswer
from execplus.domain.threads import Thread, ThreadTurn

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


class ThreadService:
    def __init__(self, unit_of_work: UnitOfWork, intent_router: IntentRouterService) -> None:
        self.uow = unit_of_work
        self.intent_router = intent_router

    def _thread(self, repo: WorkspaceRepository, actor: User, wid: UUID, tid: UUID) -> Thread:
        repo.membership(wid, actor.id)
        thread = repo.thread(wid, tid)
        if thread.owner_id != actor.id:
            raise IngestionError("not_found", "The conversation is unavailable.", 404)
        repo.upload(wid, thread.dataset_id, thread.upload_id)
        return thread

    def _expire(
        self, repo: WorkspaceRepository, wid: UUID, turns: tuple[ThreadTurn, ...]
    ) -> tuple[ThreadTurn, ...]:
        result = []
        for turn in turns:
            if (
                turn.status == "running"
                and turn.job_id is None
                and (datetime.now(timezone.utc) - turn.created_at).total_seconds() > 120
            ):
                turn = replace(
                    turn,
                    status="failed",
                    message=(
                        "This request was interrupted. Start a new turn to retry; "
                        "no completed answer is available."
                    ),
                )
                repo.update_thread_turn(wid, turn)
            result.append(turn)
        return tuple(result)

    async def start_thread(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> Thread:
        thread = Thread(
            uuid4(), workspace_id, dataset_id, upload_id, actor.id, datetime.now(timezone.utc)
        )
        with self.uow() as repo:
            repo.membership(workspace_id, actor.id)
            repo.upload(workspace_id, dataset_id, upload_id)
            repo.add(thread)
        return thread

    def list_threads(self, actor: User, wid: UUID, did: UUID, uid: UUID) -> tuple[Thread, ...]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.upload(wid, did, uid)
            return repo.threads(wid, did, uid, actor.id)

    async def get_thread(
        self, actor: User, workspace_id: UUID, thread_id: UUID
    ) -> tuple[Thread, tuple[ThreadTurn, ...]]:
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            thread = self._thread(repo, actor, workspace_id, thread_id)
            turns = self._expire(repo, workspace_id, repo.thread_turns(workspace_id, thread_id))
            return thread, turns

    def _authorize_evidence(
        self, repo: WorkspaceRepository, actor: User, wid: UUID, evidence: dict[str, Any]
    ) -> None:
        repo.membership(wid, actor.id)
        if evidence.get("guide"):
            for source in evidence.get("sources", []):
                repo.upload(wid, UUID(source["dataset_id"]), UUID(source["upload_id"]))
        for ref in evidence.get("citations", []):
            doc = repo.document(wid, UUID(ref["document_id"]))
            repo.dataset(wid, doc.dataset_id)
            if not doc.shared and doc.owner_id != actor.id:
                raise IngestionError(
                    "not_found",
                    "A conversation source is no longer accessible. Start a new conversation.",
                    404,
                )

    async def resolve(
        self, actor: User, wid: UUID, tid: UUID, turn_id: UUID
    ) -> ConversationAnswer | None:
        _, turns = await self.get_thread(actor, wid, tid)
        turn = next((item for item in turns if item.id == turn_id), None)
        if turn is None:
            raise IngestionError("not_found", "The conversation turn is unavailable.", 404)
        if turn.status in {"running", "failed"}:
            return None
        with self.uow() as repo:
            self._authorize_evidence(repo, actor, wid, turn.evidence)
        data: NumericalAnswer | None = None
        if turn.query_id:
            result, lineage = await self.intent_router.analytics.replay(actor, wid, turn.query_id)
            data = (result, lineage)
            if turn.evidence.get("data_kind") == "scalar" or (
                not turn.evidence and not lineage.grouping and lineage.aggregation != "rows"
            ):
                data = self.intent_router.analytics.assembler.assemble_metric(
                    label=str(turn.evidence.get("label", lineage.metric)),
                    column="__value",
                    result=result,
                    lineage=lineage,
                )
        if turn.kind in {"textual", "mixed"} and turn.evidence:
            citations = []
            documents = self.intent_router.documents
            if documents is None:
                raise IngestionError(
                    "evidence_unavailable", "Document evidence is not configured.", 503
                )
            for ref in cast(list[dict[str, str]], turn.evidence.get("citations", [])):
                doc_id, chunk_id = UUID(ref["document_id"]), UUID(ref["chunk_id"])
                citation = await documents.knowledge.citation(actor, wid, doc_id, chunk_id)
                if citation["checksum"] != ref["checksum"]:
                    raise IngestionError("source_integrity", "The stored citation changed.", 409)
                citations.append(
                    dict(
                        citation,
                        citation_url=f"/workspaces/{wid}/documents/{doc_id}/chunks/{chunk_id}",
                    )
                )
            with self.uow() as repo:
                self._authorize_evidence(repo, actor, wid, turn.evidence)
            return EvidenceAnswer(
                turn.kind,
                data,
                tuple(citations),
                str(turn.evidence["document_query"]),
                str(turn.evidence["coverage"]),
                tuple(cast(list[str], turn.evidence["limitations"])),
                turn.model_route or "historical",
                tuple(cast(list[dict[str, str]], turn.evidence["sources"])),
            )
        if data is not None:
            return data
        if turn.kind == "overview":
            if turn.evidence.get("guide"):
                guide = self._saved_guide(turn)
                for source in guide.sources:
                    self.intent_router.analytics.describe(
                        actor, wid, UUID(source["dataset_id"]), UUID(source["upload_id"]), source
                    )
                return guide
            return DatasetGuide(turn.message or "", turn.model_route or "historical")
        return None

    def _saved_guide(self, turn: ThreadTurn) -> DatasetGuide:
        body = cast(dict[str, Any], turn.evidence["guide"])
        return DatasetGuide(
            str(body["message"]),
            turn.model_route or "historical",
            tuple(body["columns"]),
            tuple(body["suggestions"]),
            tuple(cast(list[dict[str, str]], turn.evidence["sources"])),
            str(body["definition_state"]),
            str(body.get("focus", "orientation")),
        )

    def claim(
        self,
        repo: WorkspaceRepository,
        actor: User,
        wid: UUID,
        tid: UUID,
        question: str,
        request_id: UUID,
        *,
        accept_running: bool = False,
    ) -> tuple[Thread, ThreadTurn, bool]:
        if not question.strip() or len(question) > 500 or "\x00" in question:
            raise IngestionError(
                "invalid_question", "Use a nonempty question up to 500 characters.", 422
            )
        repo.workspace(wid, lock=True)
        thread = self._thread(repo, actor, wid, tid)
        prior = self._expire(repo, wid, repo.thread_turns(wid, tid))
        existing = next((item for item in prior if item.request_id == request_id), None)
        if existing is not None:
            if existing.question != question:
                raise IngestionError(
                    "request_conflict",
                    "Use a new request identifier for a different question.",
                    409,
                )
            if existing.status == "running" and not accept_running:
                raise IngestionError(
                    "request_running",
                    "This request is still running. Reopen the conversation shortly.",
                    409,
                )
            return thread, existing, False
        if any(item.status == "running" for item in prior):
            raise IngestionError(
                "thread_conflict", "Another request is running in this conversation.", 409
            )
        if len(prior) >= 100:
            raise IngestionError(
                "thread_limit", "Start a new conversation after one hundred turns.", 422
            )
        turn = ThreadTurn(
            uuid4(),
            tid,
            question,
            "unsupported",
            None,
            None,
            datetime.now(timezone.utc),
            request_id=request_id,
            status="running",
        )
        repo.add_thread_turn(wid, turn)
        return thread, turn, True

    def publish(self, repo: WorkspaceRepository, actor: User, wid: UUID, turn: ThreadTurn) -> None:
        repo.workspace(wid, lock=True)
        self._thread(repo, actor, wid, turn.thread_id)
        self._authorize_evidence(repo, actor, wid, turn.evidence)
        current = next(
            item for item in repo.thread_turns(wid, turn.thread_id) if item.id == turn.id
        )
        if current.status != "running":
            raise IngestionError(
                "request_conflict", "This request was already closed. Reopen the conversation.", 409
            )
        repo.update_thread_turn(wid, turn)
        repo.add(
            AuditEvent(
                uuid4(),
                wid,
                actor.id,
                f"conversation.{turn.status}",
                "thread_turn",
                turn.id,
                datetime.now(timezone.utc),
            )
        )

    async def ask(
        self,
        actor: User,
        workspace_id: UUID,
        thread_id: UUID,
        question: str,
        request_id: UUID | None = None,
    ) -> tuple[ConversationAnswer | None, ThreadTurn]:
        with self.uow() as repo:
            thread, turn, created = self.claim(
                repo, actor, workspace_id, thread_id, question, request_id or uuid4()
            )
        if not created:
            return await self.resolve(actor, workspace_id, thread_id, turn.id), turn
        try:
            answer, turn = await self.run_turn(actor, workspace_id, thread, turn)
        except (IngestionError, asyncio.CancelledError):
            with self.uow() as repo:
                repo.workspace(workspace_id, lock=True)
                current = next(
                    item
                    for item in repo.thread_turns(workspace_id, thread_id)
                    if item.id == turn.id
                )
                if current.status == "running":
                    repo.update_thread_turn(
                        workspace_id,
                        replace(
                            turn,
                            status="failed",
                            message=(
                                "This request was interrupted or a required source is unavailable."
                            ),
                        ),
                    )
            raise
        with self.uow() as repo:
            self.publish(repo, actor, workspace_id, turn)
        return answer, turn

    async def run_turn(
        self, actor: User, wid: UUID, thread: Thread, turn: ThreadTurn
    ) -> tuple[ConversationAnswer | None, ThreadTurn]:
        prior_lineage = None
        prior_document_query = ""
        prior_guide = None
        prior_clarification = None
        with self.uow() as repo:
            self._thread(repo, actor, wid, thread.id)
            all_turns = repo.thread_turns(wid, thread.id)
            position = next(i for i, item in enumerate(all_turns) if item.id == turn.id)
            prior_turns = all_turns[:position]
            for item in reversed(prior_turns):
                if not prior_document_query and item.evidence.get("document_query"):
                    self._authorize_evidence(repo, actor, wid, item.evidence)
                    prior_document_query = str(item.evidence["document_query"])
                if prior_lineage is None and item.query_id:
                    prior_lineage = repo.query_execution(wid, item.query_id).lineage()
            if prior_turns and prior_turns[-1].evidence.get("guide"):
                self._authorize_evidence(repo, actor, wid, prior_turns[-1].evidence)
                prior_guide = self._saved_guide(prior_turns[-1])
                if prior_guide.columns:
                    prior_lineage = None
                    prior_document_query = ""
            if prior_turns and prior_turns[-1].evidence.get("clarification"):
                saved = cast(dict[str, Any], prior_turns[-1].evidence["clarification"])
                prior_clarification = ClarificationContext(
                    str(saved["question"]),
                    str(saved["message"]),
                    tuple(cast(list[dict[str, str]], saved["sources"])),
                )
        answer: ConversationAnswer | None = None
        try:
            answer = await asyncio.wait_for(
                self.intent_router.ask(
                    actor,
                    wid,
                    thread.dataset_id,
                    thread.upload_id,
                    turn.question,
                    prior_lineage,
                    prior_document_query,
                    prior_guide,
                    prior_clarification,
                ),
                timeout=100,
            )
            evidence: dict[str, Any] = {}
            data = None
            if isinstance(answer, EvidenceAnswer):
                data = answer.data
                evidence = dict(
                    document_query=answer.document_query,
                    coverage=answer.coverage,
                    limitations=list(answer.limitations),
                    sources=list(answer.sources),
                    citations=[
                        {key: str(item[key]) for key in ("document_id", "chunk_id", "checksum")}
                        for item in answer.citations
                    ],
                )
                turn = replace(
                    turn,
                    kind=answer.kind,
                    model_route=answer.model_route,
                    status="partial" if answer.limitations else "complete",
                )
            elif isinstance(answer, DatasetGuide):
                evidence = dict(
                    guide=dict(
                        version="dataset-guidance-v1",
                        message=answer.message,
                        columns=list(answer.columns),
                        suggestions=list(answer.suggestions),
                        definition_state=answer.definition_state,
                        focus=answer.focus,
                    ),
                    sources=list(answer.sources),
                )
                turn = replace(
                    turn,
                    kind="overview",
                    message=None,
                    model_route=answer.model_route,
                    status="complete",
                )
            else:
                data = answer
                lineage = answer_lineage(data)
                turn = replace(
                    turn,
                    kind="rows" if lineage.aggregation == "rows" else "numerical",
                    model_route=lineage.model_route,
                    status="complete",
                )
            if data is not None:
                turn = replace(turn, query_id=answer_lineage(data).query_id)
                evidence.update(
                    data_kind="scalar" if isinstance(data, VerifiedMetricAnswer) else "table"
                )
                if isinstance(data, VerifiedMetricAnswer):
                    evidence["label"] = data.label
            turn = replace(turn, evidence=evidence)
        except ClarificationRequiredError as error:
            turn = replace(turn, kind="ambiguous", message=str(error)[:1000], status="complete")
            if isinstance(error, PlanningClarification):
                turn = replace(
                    turn,
                    evidence={
                        "clarification": {
                            "question": error.context.question,
                            "message": error.context.message[:1000],
                            "sources": list(error.context.sources),
                        }
                    },
                )
        except UnsupportedQuestionError as error:
            turn = replace(turn, kind="unsupported", message=str(error)[:1000], status="complete")
        except QueryDataError as error:
            turn = replace(turn, status="failed", message=str(error)[:1000])
        except (ProviderUnavailableError, asyncio.TimeoutError, UnsafeQueryError):
            turn = replace(
                turn,
                status="failed",
                message=(
                    "This request could not complete safely. No complete answer is available. "
                    "Start a new turn to try again."
                ),
            )
        return answer, turn
