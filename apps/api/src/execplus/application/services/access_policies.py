"""Use case: Lets a workspace owner explicitly manage dataset access grants.

What it does: Validates source fields and members, appends optimistic policy revisions
and records identifier-only audit events without granting implicit data access.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.analytics import UnitOfWork
from execplus.domain.dataset_access import DatasetAccessPolicy, validate_grants
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.semantics import DatasetView, dataset_view


class AccessPolicyService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def catalog(self, actor: User, wid: UUID) -> list[dict[str, str]]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            if repo.membership(wid, actor.id).role != "owner":
                raise IngestionError(
                    "forbidden", "Only the workspace owner can manage dataset access.", 403
                )
            return [dict(id=str(item.id), name=item.name) for item in repo.datasets(wid)]

    def _owner(self, repo: WorkspaceRepository, actor: User, wid: UUID, did: UUID) -> None:
        if repo.membership(wid, actor.id).role != "owner":
            raise IngestionError(
                "forbidden", "Only the workspace owner can manage dataset access.", 403
            )
        repo.dataset(wid, did)

    def _view(self, repo: WorkspaceRepository, wid: UUID, did: UUID) -> DatasetView:
        uploads = repo.uploads(wid, did)
        if not uploads:
            return dataset_view({"columns": []})
        upload = max(uploads, key=lambda value: value.created_at)
        feeds = repo.refresh_feeds(wid, did)
        if feeds:
            upload = repo.upload(wid, did, UUID(feeds[0].source["upload_id"]))
        revision = repo.active_revision(wid, did, upload.id)
        if revision is None:
            raise IngestionError("access_source", "Profile a source before setting access.", 409)
        return dataset_view(revision.profile)

    def overview(self, actor: User, wid: UUID, did: UUID) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self._owner(repo, actor, wid, did)
            policy = repo.dataset_access_policy(wid, did)
            view = self._view(repo, wid, did)
            return {
                "version": policy.version if policy else 0,
                "enabled": policy.enabled if policy else False,
                "grants": [
                    dict(
                        user_id=grant["user_id"],
                        columns=grant["columns"],
                        conditions=[
                            {key: item[key] for key in ("column", "operator", "value")}
                            for item in grant["conditions"]
                        ],
                    )
                    for grant in policy.grants
                ]
                if policy
                else [],
                "columns": [dict(name=column.name, type=column.type) for column in view.columns],
                "members": [
                    dict(
                        user_id=str(member.user_id),
                        role=member.role,
                        display_name=repo.user(member.user_id).display_name
                        or repo.user(member.user_id).email,
                    )
                    for member in repo.members(wid)
                ],
            }

    def save(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        expected_version: int,
        enabled: bool,
        grants: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self._owner(repo, actor, wid, did)
            current = repo.dataset_access_policy(wid, did)
            if type(expected_version) is not int or expected_version != (
                current.version if current else 0
            ):
                raise IngestionError(
                    "access_conflict", "Access changed. Reload before saving.", 409
                )
            if type(enabled) is not bool:
                raise IngestionError("access_invalid", "Choose whether the policy is enabled.", 422)
            view = self._view(repo, wid, did)
            members = {str(member.user_id): member for member in repo.members(wid)}
            checked = validate_grants(grants, view, set(members))
            for grant in checked:
                grant["membership_created_at"] = members[grant["user_id"]].created_at.isoformat()
            now = datetime.now(timezone.utc)
            policy = DatasetAccessPolicy(
                uuid4(), wid, did, expected_version + 1, enabled, checked, actor.id, now
            )
            repo.add_dataset_access_policy(policy)
            repo.add(
                AuditEvent(uuid4(), wid, actor.id, "dataset_access.changed", "dataset", did, now)
            )
        return self.overview(actor, wid, did)
