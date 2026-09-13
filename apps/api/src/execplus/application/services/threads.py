"""Use case: Manages multi-turn conversation threads using structured references.

What it does: Resolves each follow-up question using the prior turn's stored,
structured lineage rather than raw prompt history, and only ever records a
reference to what was actually executed.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.intent_router import IntentRouterService, NumericalAnswer
from execplus.domain.errors import ClarificationRequiredError, UnsupportedQuestionError
from execplus.domain.ingestion import Membership, User
from execplus.domain.models import QuestionKind, VerifiedMetricAnswer
from execplus.domain.threads import Thread, ThreadTurn

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


class ThreadService:
    def __init__(self, unit_of_work: UnitOfWork, intent_router: IntentRouterService) -> None:
        self.uow = unit_of_work
        self.intent_router = intent_router

    def _authorize(self, repo: WorkspaceRepository, actor: User, workspace_id: UUID) -> Membership:
        return repo.membership(workspace_id, actor.id)

    async def start_thread(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> Thread:
        thread = Thread(
            uuid4(), workspace_id, dataset_id, upload_id, actor.id, datetime.now(timezone.utc)
        )
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            repo.upload(workspace_id, dataset_id, upload_id)
            repo.add(thread)
        return thread

    async def get_thread(
        self, actor: User, workspace_id: UUID, thread_id: UUID
    ) -> tuple[Thread, tuple[ThreadTurn, ...]]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            thread = repo.thread(workspace_id, thread_id)
            turns = repo.thread_turns(thread_id)
        return thread, turns

    async def ask(
        self, actor: User, workspace_id: UUID, thread_id: UUID, question: str
    ) -> tuple[NumericalAnswer | None, ThreadTurn]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            thread = repo.thread(workspace_id, thread_id)
            prior_turns = repo.thread_turns(thread_id)
            prior_lineage = None
            for turn in reversed(prior_turns):
                if turn.query_id is not None:
                    prior_lineage = repo.query_execution(workspace_id, turn.query_id).lineage()
                    break

        answer: NumericalAnswer | None = None
        kind = QuestionKind.UNSUPPORTED.value
        query_id: UUID | None = None
        message: str | None = None
        try:
            answer = await self.intent_router.ask(
                actor, workspace_id, thread.dataset_id, thread.upload_id, question, prior_lineage
            )
            kind = QuestionKind.NUMERICAL.value
            lineage = answer.lineage if isinstance(answer, VerifiedMetricAnswer) else answer[1]
            query_id = lineage.query_id
        except ClarificationRequiredError as error:
            kind = QuestionKind.AMBIGUOUS.value
            message = str(error)
        except UnsupportedQuestionError as error:
            kind = QuestionKind.UNSUPPORTED.value
            message = str(error)

        turn = ThreadTurn(
            uuid4(), thread_id, question, kind, query_id, message, datetime.now(timezone.utc)
        )
        with self.uow() as repo:
            repo.add(turn)
        return answer, turn
