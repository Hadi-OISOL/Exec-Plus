"""Use case: Separates PDF orchestration from stored-answer access and rendering.

What it does: Allows existing authorization/replay and an interchangeable bounded
PDF adapter without importing framework or graphics code into the application.
"""

from typing import Protocol
from uuid import UUID

from execplus.domain.ingestion import User
from execplus.domain.pdf_exports import PdfDocument, ReportAnswer
from execplus.domain.threads import Thread, ThreadTurn


class SavedAnswerResolver(Protocol):
    async def get_thread(
        self, actor: User, workspace_id: UUID, thread_id: UUID
    ) -> tuple[Thread, tuple[ThreadTurn, ...]]: ...

    async def resolve(self, actor: User, wid: UUID, tid: UUID, turn_id: UUID) -> object: ...


class PdfRenderer(Protocol):
    def validate(self, document: PdfDocument) -> None: ...

    def render(self, document: PdfDocument) -> bytes: ...


class PdfDescriptorProvider(Protocol):
    async def describe(self, actor: User, wid: UUID, tid: UUID, turn_id: UUID) -> ReportAnswer: ...
