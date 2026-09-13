"""Use case: Declares replaceable infrastructure capabilities.

What it does: Defines contracts for queries, models, retrieval, and readiness.
"""

from typing import BinaryIO, Protocol
from uuid import UUID

from execplus.application.contracts import (
    ComponentStatus,
    KnowledgeChunk,
    ModelRequest,
    ModelResponse,
    RetrievalHit,
)
from execplus.domain.ingestion import (
    AuditEvent,
    Dataset,
    FileStructure,
    Invitation,
    Membership,
    ObjectMetadata,
    Upload,
    User,
    Workspace,
)
from execplus.domain.join_paths import JoinPath
from execplus.domain.models import QueryExecution, QueryPlan, QueryResult, WorkspaceScope
from execplus.domain.profiling import Revision, TableData, UsageEvent
from execplus.domain.saved_items import SavedItem
from execplus.domain.semantics import DatasetView
from execplus.domain.threads import Thread, ThreadTurn


class QueryExecutor(Protocol):
    async def execute(
        self, plan: QueryPlan, scope: WorkspaceScope, table: TableData, view: DatasetView
    ) -> QueryResult: ...

    async def execute_join(
        self,
        plan: QueryPlan,
        scope: WorkspaceScope,
        join_path: JoinPath,
        left_table: TableData,
        left_view: DatasetView,
        right_table: TableData,
        right_view: DatasetView,
    ) -> QueryResult: ...


class LanguageModel(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...


class EmbeddingStore(Protocol):
    async def upsert(self, chunks: tuple[KnowledgeChunk, ...]) -> None: ...

    async def search(
        self,
        query: str,
        scope: WorkspaceScope,
        dataset_ids: frozenset[UUID],
        limit: int,
    ) -> tuple[RetrievalHit, ...]: ...

    async def delete_dataset(self, workspace_id: UUID, dataset_id: UUID) -> None: ...


class ReadinessProbe(Protocol):
    @property
    def name(self) -> str: ...

    async def check(self) -> ComponentStatus: ...


class IdentityProvider(Protocol):
    def authenticate(self, token: str) -> "User": ...

    def revoke(self, token: str) -> None: ...


class ObjectStorage(Protocol):
    def put(self, upload: "Upload", content: "BinaryIO") -> None: ...

    def metadata(self, upload: "Upload") -> "ObjectMetadata": ...

    def read(self, upload: "Upload") -> bytes: ...

    def delete(self, upload: "Upload") -> None: ...

    def ready(self) -> bool: ...


class FileParser(Protocol):
    def read_table(self, content: BinaryIO, format: str) -> TableData: ...

    def parse(self, content: "BinaryIO", filename: str, content_type: str) -> "FileStructure": ...


class WorkspaceRepository(Protocol):
    def user(self, user_id: UUID) -> "User": ...

    def workspaces(self, user_id: UUID) -> tuple["Workspace", ...]: ...

    def workspace(self, workspace_id: UUID, *, lock: bool = False) -> "Workspace": ...

    def membership(self, workspace_id: UUID, user_id: UUID) -> "Membership": ...

    def members(self, workspace_id: UUID) -> tuple["Membership", ...]: ...

    def invitations(self, workspace_id: UUID) -> tuple["Invitation", ...]: ...

    def invitation(self, workspace_id: UUID, invitation_id: UUID) -> "Invitation": ...

    def set_invitation_status(
        self, workspace_id: UUID, invitation_id: UUID, status: str
    ) -> None: ...

    def remove_member(self, workspace_id: UUID, user_id: UUID) -> None: ...

    def set_seat_limit(self, workspace_id: UUID, limit: int) -> None: ...

    def datasets(self, workspace_id: UUID) -> tuple["Dataset", ...]: ...

    def dataset(self, workspace_id: UUID, dataset_id: UUID) -> "Dataset": ...

    def rename_dataset(self, workspace_id: UUID, dataset_id: UUID, name: str) -> "Dataset": ...

    def uploads(self, workspace_id: UUID, dataset_id: UUID) -> tuple["Upload", ...]: ...

    def upload(self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID) -> "Upload": ...

    def audit_events(self, workspace_id: UUID) -> tuple["AuditEvent", ...]: ...

    def revisions(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[Revision, ...]: ...

    def revision(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID, revision_id: UUID
    ) -> Revision: ...

    def active_revision(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> Revision | None: ...

    def set_active_revision(self, revision: Revision) -> None: ...

    def usage_events(self, workspace_id: UUID) -> tuple[UsageEvent, ...]: ...

    def query_execution(self, workspace_id: UUID, query_id: UUID) -> QueryExecution: ...

    def saved_items(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[SavedItem, ...]: ...

    def saved_item(self, workspace_id: UUID, item_id: UUID) -> SavedItem: ...

    def delete_saved_item(self, workspace_id: UUID, item_id: UUID) -> None: ...

    def thread(self, workspace_id: UUID, thread_id: UUID) -> Thread: ...

    def thread_turns(self, thread_id: UUID) -> tuple[ThreadTurn, ...]: ...

    def join_paths(self, workspace_id: UUID) -> tuple[JoinPath, ...]: ...

    def join_path(self, workspace_id: UUID, join_path_id: UUID) -> JoinPath: ...

    def add(
        self,
        record: Workspace
        | Membership
        | Invitation
        | Dataset
        | Upload
        | AuditEvent
        | Revision
        | UsageEvent
        | QueryExecution
        | SavedItem
        | Thread
        | ThreadTurn
        | JoinPath,
    ) -> None: ...
