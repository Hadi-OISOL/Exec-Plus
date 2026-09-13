"""Use case: Manages saved questions, prompts, and dashboard configurations.

What it does: Scopes each saved item to its owner by default; a saved item is
visible to the rest of the workspace only once its owner explicitly shares it.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.workspaces import checked_name
from execplus.domain.errors import AuthorizationError
from execplus.domain.ingestion import AuditEvent, IngestionError, Membership, User
from execplus.domain.saved_items import SavedItem

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


class SavedItemService:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self.uow = unit_of_work

    def _authorize(self, repo: WorkspaceRepository, actor: User, workspace_id: UUID) -> Membership:
        return repo.membership(workspace_id, actor.id)

    async def create(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        kind: str,
        name: str,
        description: str,
        payload: dict[str, Any],
        shared: bool,
    ) -> SavedItem:
        now = datetime.now(timezone.utc)
        item = SavedItem(
            uuid4(),
            workspace_id,
            dataset_id,
            upload_id,
            actor.id,
            kind,
            checked_name(name),
            description,
            payload,
            shared,
            now,
            now,
        )
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            repo.upload(workspace_id, dataset_id, upload_id)
            repo.add(item)
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    "saved_item.created",
                    "saved_item",
                    item.id,
                    now,
                )
            )
        return item

    async def list_items(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[SavedItem, ...]:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            items = repo.saved_items(workspace_id, dataset_id, upload_id)
        return tuple(item for item in items if item.shared or item.owner_id == actor.id)

    async def get_item(self, actor: User, workspace_id: UUID, item_id: UUID) -> SavedItem:
        with self.uow() as repo:
            self._authorize(repo, actor, workspace_id)
            item = repo.saved_item(workspace_id, item_id)
        if not item.shared and item.owner_id != actor.id:
            raise AuthorizationError("This saved item is not shared with you")
        return item

    async def delete_item(self, actor: User, workspace_id: UUID, item_id: UUID) -> None:
        with self.uow() as repo:
            member = self._authorize(repo, actor, workspace_id)
            item = repo.saved_item(workspace_id, item_id)
            if item.owner_id != actor.id and member.role not in {"owner", "admin"}:
                raise IngestionError(
                    "forbidden", "Only the owner or a manager can delete this saved item.", 403
                )
            repo.delete_saved_item(workspace_id, item_id)
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    "saved_item.deleted",
                    "saved_item",
                    item_id,
                    datetime.now(timezone.utc),
                )
            )
