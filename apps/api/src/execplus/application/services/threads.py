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
    ConversationAnswer,
    DatasetGuide,
    IntentRouterService,
)
from execplus.domain.errors import (
    ClarificationRequiredError,
    ProviderUnavailableError,
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
            return DatasetGuide(turn.message or "", turn.model_route or "historical")
        return None

    async def ask(
        self,
        actor: User,
        workspace_id: UUID,
        thread_id: UUID,
        question: str,
        request_id: UUID | None = None,
    ) -> tuple[ConversationAnswer | None, ThreadTurn]:
        if not question.strip() or len(question) > 500 or "\x00" in question:
            raise IngestionError(
                "invalid_question", "Use a nonempty question up to 500 characters.", 422
            )
        request_id = request_id or uuid4()
        now = datetime.now(timezone.utc)
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            thread = self._thread(repo, actor, workspace_id, thread_id)
            prior_turns = self._expire(
                repo, workspace_id, repo.thread_turns(workspace_id, thread_id)
            )
            existing = next((item for item in prior_turns if item.request_id == request_id), None)
            if existing and existing.question != question:
                raise IngestionError(
                    "request_conflict",
                    "Use a new request identifier for a different question.",
                    409,
                )
            if existing and existing.status == "running":
                raise IngestionError(
                    "request_running",
                    "This request is still running. Reopen the conversation shortly.",
                    409,
                )
            if existing is None and any(item.status == "running" for item in prior_turns):
                raise IngestionError(
                    "thread_conflict", "Another request is running in this conversation.", 409
                )
            prior_lineage = None
            prior_document_query = ""
            if existing is None:
                if len(prior_turns) >= 100:
                    raise IngestionError(
                        "thread_limit", "Start a new conversation after one hundred turns.", 422
                    )
                for item in reversed(prior_turns):
                    if not prior_document_query and item.evidence.get("document_query"):
                        self._authorize_evidence(repo, actor, workspace_id, item.evidence)
                        prior_document_query = str(item.evidence["document_query"])
                    if prior_lineage is None and item.query_id:
                        prior_lineage = repo.query_execution(workspace_id, item.query_id).lineage()
                turn = ThreadTurn(
                    uuid4(),
                    thread_id,
                    question,
                    "unsupported",
                    None,
                    None,
                    now,
                    request_id=request_id,
                    status="running",
                )
                repo.add_thread_turn(workspace_id, turn)
        if existing is not None:
            return await self.resolve(actor, workspace_id, thread_id, existing.id), existing

        answer: ConversationAnswer | None = None
        try:
            answer = await asyncio.wait_for(
                self.intent_router.ask(
                    actor,
                    workspace_id,
                    thread.dataset_id,
                    thread.upload_id,
                    question,
                    prior_lineage,
                    prior_document_query,
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
                turn = replace(
                    turn,
                    kind="overview",
                    message=answer.message,
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
        except UnsupportedQuestionError as error:
            turn = replace(turn, kind="unsupported", message=str(error)[:1000], status="complete")
        except (ProviderUnavailableError, asyncio.TimeoutError, UnsafeQueryError):
            turn = replace(
                turn,
                status="failed",
                message=(
                    "This request could not complete safely. No complete answer is available. "
                    "Start a new turn to try again."
                ),
            )
        except IngestionError:
            with self.uow() as repo:
                repo.update_thread_turn(
                    workspace_id,
                    replace(turn, status="failed", message="A required source is unavailable."),
                )
            raise
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            self._thread(repo, actor, workspace_id, thread_id)
            self._authorize_evidence(repo, actor, workspace_id, turn.evidence)
            current = next(
                item for item in repo.thread_turns(workspace_id, thread_id) if item.id == turn.id
            )
            if current.status != "running":
                raise IngestionError(
                    "request_conflict",
                    "This request was already closed. Reopen the conversation.",
                    409,
                )
            repo.update_thread_turn(workspace_id, turn)
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    f"conversation.{turn.status}",
                    "thread_turn",
                    turn.id,
                    datetime.now(timezone.utc),
                )
            )
        return answer, turn
