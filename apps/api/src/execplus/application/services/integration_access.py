"""Use case: Issues scoped read-only integration credentials and private embed sessions.

What it does: Rechecks current membership, resource sharing and dataset policy on
both sides of external work, while keeping bootstrap and API credentials separate.
"""

import hmac
from collections.abc import Awaitable, Callable
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import UUID, uuid4

from execplus.application.integration_ports import IntegrationRepository, IntegrationStore
from execplus.application.services.dataset_access import authorize_sources, dataset_access
from execplus.application.services.studies import StudyService, visible_pin
from execplus.application.services.workspaces import checked_name
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.integration_access import (
    BOOTSTRAP_MAX_SECONDS,
    KEY_MAX_SECONDS,
    EmbedGrant,
    IntegrationKey,
    issue_secret,
    lifetime,
    origin,
    secret_hash,
    unavailable,
    validate_scope,
)
from execplus.domain.studies import StudyBoard

T = TypeVar("T")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def audit(repo: IntegrationRepository, actor: User, wid: UUID, action: str, target: UUID) -> None:
    repo.add(AuditEvent(uuid4(), wid, actor.id, action, "integration", target, now_utc()))


def public_key(value: IntegrationKey) -> dict[str, Any]:
    body = asdict(value)
    body.pop("token_hash")
    return body


def public_grant(value: EmbedGrant) -> dict[str, Any]:
    body = asdict(value)
    for key in ("bootstrap_hash", "session_hash"):
        body.pop(key)
    return body


def scoped_sources(
    repo: IntegrationRepository,
    actor: User,
    wid: UUID,
    datasets: tuple[UUID, ...],
    primary: UUID,
    sources: Any,
) -> None:
    if not isinstance(sources, (list, tuple)) or not sources:
        raise unavailable()
    try:
        identifiers = {UUID(source["dataset_id"]) for source in sources}
    except (KeyError, TypeError, ValueError, AttributeError):
        raise unavailable() from None
    if primary not in identifiers or not identifiers <= set(datasets):
        raise unavailable()
    authorize_sources(repo, actor, wid, sources, primary)


class IntegrationAccessService:
    def __init__(
        self, store: IntegrationStore, studies: StudyService, *, allow_local_origins: bool = False
    ) -> None:
        self.store, self.studies = store, studies
        self.allow_local_origins = allow_local_origins

    def create_key(
        self,
        actor: User,
        wid: UUID,
        name: str,
        datasets: tuple[UUID, ...],
        operations: tuple[str, ...],
        expires_seconds: int,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        validate_scope(datasets, operations)
        now = now_utc()
        expires = lifetime(now, expires_seconds, KEY_MAX_SECONDS)
        token, digest = issue_secret("epk")
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            if repo.membership(wid, actor.id).role != "owner":
                raise IngestionError(
                    "integration_owner", "Only the workspace owner can issue keys.", 403
                )
            if user_id is not None and user_id != actor.id:
                raise IngestionError(
                    "integration_identity", "A key can use only your own current access.", 403
                )
            membership = repo.membership(wid, actor.id)
            for did in datasets:
                dataset_access(repo, actor, wid, did)
            active = [
                key
                for key in repo.integration_keys(wid, actor.id)
                if key.revoked_at is None and key.expires_at > now
            ]
            if len(active) >= 20:
                raise IngestionError(
                    "integration_limit", "Revoke an unused key before adding another.", 422
                )
            value = IntegrationKey(
                uuid4(),
                wid,
                actor.id,
                membership.created_at,
                checked_name(name),
                digest,
                datasets,
                operations,
                now,
                expires,
            )
            repo.add_integration_key(value)
            audit(repo, actor, wid, "integration.key_created", value.id)
        return {
            "key": public_key(value),
            "secret": token,
            "notice": (
                "Save this key now. It is shown once and grants only your current dataset access."
            ),
        }

    def keys(self, actor: User, wid: UUID) -> list[dict[str, Any]]:
        with self.store.transaction() as repo:
            membership = repo.membership(wid, actor.id)
            if membership.role != "owner":
                raise IngestionError(
                    "integration_owner", "Only the workspace owner can manage keys.", 403
                )
            values = repo.integration_keys(wid, None)
            return [public_key(value) for value in values]

    def revoke_key(self, actor: User, wid: UUID, key_id: UUID) -> None:
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            membership = repo.membership(wid, actor.id)
            key = repo.integration_key(wid, key_id)
            if membership.role != "owner":
                raise unavailable()
            if key.revoked_at is None:
                repo.update_integration_key(replace(key, revoked_at=now_utc()))
                audit(repo, actor, wid, "integration.key_revoked", key.id)

    def _key_context(
        self,
        repo: IntegrationRepository,
        digest: str,
        wid: UUID,
        did: UUID | None,
        operation: str,
        *,
        consume: bool,
    ) -> tuple[IntegrationKey, User, tuple[dict[str, str], ...]]:
        key = repo.integration_key_by_hash(digest)
        if key is None:
            raise unavailable()
        now = now_utc()
        key.authorize(now, wid, did, operation)
        actor = repo.user(key.user_id)
        membership = repo.membership(wid, actor.id)
        if membership.created_at != key.membership_created_at:
            raise unavailable()
        references = tuple(
            dataset_access(repo, actor, wid, identifier).reference()
            for identifier in ((did,) if did else key.dataset_ids)
        )
        if consume:
            if not repo.consume_integration_request(key.id, now, key.rate_limit):
                raise IngestionError(
                    "integration_rate_limit",
                    "This key has reached its request limit. Retry next minute.",
                    429,
                )
            repo.update_integration_key(replace(key, last_used_at=now))
        return key, actor, references

    async def perform(
        self,
        token: str,
        wid: UUID,
        did: UUID | None,
        operation: str,
        action: Callable[[User, IntegrationKey], Awaitable[T]],
        *,
        final_check: Callable[[IntegrationRepository, User, IntegrationKey, T], None] | None = None,
    ) -> T:
        digest = secret_hash(token, "epk")
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            key, actor, references = self._key_context(
                repo, digest, wid, did, operation, consume=True
            )
        value = await action(actor, key)
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            current, _, current_references = self._key_context(
                repo, digest, wid, did, operation, consume=False
            )
            if current.id != key.id or current_references != references:
                raise unavailable()
            if final_check is not None:
                final_check(repo, actor, current, value)
            audit(repo, actor, wid, "integration.read", key.id)
        return value

    def _shared_board(
        self,
        repo: IntegrationRepository,
        actor: User,
        wid: UUID,
        board_id: UUID,
        allowed_datasets: tuple[UUID, ...] | None = None,
    ) -> StudyBoard:
        repo.membership(wid, actor.id)
        board = repo.study_board(wid, board_id)
        if not board.shared or not board.pins:
            raise IngestionError(
                "embed_unshared", "Choose a shared dashboard with shared saved studies.", 422
            )
        for pin in board.pins:
            study = visible_pin(repo, actor, wid, UUID(pin))
            if not study.shared:
                raise unavailable()
            if allowed_datasets is not None:
                version = repo.study_version(wid, UUID(pin))
                scoped_sources(
                    repo,
                    actor,
                    wid,
                    allowed_datasets,
                    study.dataset_id,
                    version.evidence.get("sources"),
                )
        return board

    async def study_for_key(self, token: str, wid: UUID, version_id: UUID) -> Any:
        def check(
            repo: IntegrationRepository, actor: User, key: IntegrationKey, value: Any
        ) -> None:
            study = visible_pin(repo, actor, wid, version_id)
            version = repo.study_version(wid, version_id)
            scoped_sources(
                repo,
                actor,
                wid,
                key.dataset_ids,
                study.dataset_id,
                version.evidence.get("sources"),
            )

        async def action(actor: User, key: IntegrationKey) -> Any:
            with self.store.transaction() as repo:
                check(repo, actor, key, None)
            return await self.studies.open(actor, wid, version_id)

        return await self.perform(token, wid, None, "studies:read", action, final_check=check)

    def authorize_result_for_key(
        self,
        actor: User,
        key: IntegrationKey,
        wid: UUID,
        did: UUID,
        result_id: UUID,
        *,
        forecast: bool,
    ) -> None:
        with self.store.transaction() as repo:
            value = (
                repo.forecast_run(wid, result_id, actor.id)
                if forecast
                else repo.analysis_run(wid, result_id, actor.id)
            )
            if value.dataset_id != did:
                raise unavailable()
            scoped_sources(repo, actor, wid, key.dataset_ids, did, value.evidence.get("sources"))

    def authorize_job_for_key(
        self,
        actor: User,
        key: IntegrationKey,
        wid: UUID,
        job_id: UUID,
    ) -> None:
        with self.store.transaction() as repo:
            job = repo.job(wid, job_id)
            if job.owner_id != actor.id:
                raise unavailable()
            thread = repo.thread(wid, job.thread_id)
            scoped_sources(repo, actor, wid, key.dataset_ids, thread.dataset_id, job.sources)

    async def board_for_key(
        self, token: str, wid: UUID, board_id: UUID
    ) -> tuple[StudyBoard, list[Any]]:
        async def action(actor: User, key: IntegrationKey) -> tuple[StudyBoard, list[Any]]:
            with self.store.transaction() as repo:
                before = self._shared_board(repo, actor, wid, board_id, key.dataset_ids)
            value = await self.studies.open_board(actor, wid, board_id)
            if value[0] != before:
                raise unavailable()
            return value

        def check(
            repo: IntegrationRepository,
            actor: User,
            key: IntegrationKey,
            value: tuple[StudyBoard, list[Any]],
        ) -> None:
            if self._shared_board(repo, actor, wid, board_id, key.dataset_ids) != value[0]:
                raise unavailable()

        return await self.perform(token, wid, None, "boards:read", action, final_check=check)

    def create_embed(
        self,
        actor: User,
        wid: UUID,
        board_id: UUID,
        host_origin: str,
        expires_seconds: int = BOOTSTRAP_MAX_SECONDS,
    ) -> dict[str, Any]:
        host = origin(host_origin, allow_local=self.allow_local_origins)
        now = now_utc()
        expires = lifetime(now, expires_seconds, BOOTSTRAP_MAX_SECONDS)
        token, digest = issue_secret("epb")
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            membership = repo.membership(wid, actor.id)
            if membership.role != "owner":
                raise IngestionError(
                    "integration_owner", "Only the workspace owner can create embedded views.", 403
                )
            board = self._shared_board(repo, actor, wid, board_id)
            active = [
                item
                for item in repo.embed_grants(wid, actor.id)
                if item.revoked_at is None and (item.session_expires_at or item.expires_at) > now
            ]
            if len(active) >= 50:
                raise IngestionError("embed_limit", "Revoke an unused embedded view first.", 422)
            grant = EmbedGrant(
                uuid4(),
                wid,
                actor.id,
                membership.created_at,
                board.id,
                board.version,
                host,
                digest,
                now,
                expires,
            )
            repo.add_embed_grant(grant)
            audit(repo, actor, wid, "integration.embed_created", grant.id)
        return {
            "grant": public_grant(grant),
            "bootstrap_secret": token,
            "notice": (
                "Transfer this one-use secret only to the approved host frame. "
                "Never place it in a URL."
            ),
        }

    def _embed_context(
        self, repo: IntegrationRepository, grant: EmbedGrant
    ) -> tuple[User, StudyBoard]:
        actor = repo.user(grant.user_id)
        membership = repo.membership(grant.workspace_id, actor.id)
        if membership.created_at != grant.membership_created_at or grant.revoked_at is not None:
            raise unavailable()
        board = self._shared_board(repo, actor, grant.workspace_id, grant.board_id)
        if board.version != grant.board_version:
            raise unavailable()
        return actor, board

    def embed_descriptor(self, grant_id: UUID) -> dict[str, str]:
        with self.store.transaction() as repo:
            grant = repo.embed_grant(grant_id)
            self._embed_context(repo, grant)
            if (grant.session_expires_at or grant.expires_at) <= now_utc():
                raise unavailable()
            return {"host_origin": grant.host_origin}

    def exchange_embed(self, grant_id: UUID, bootstrap: str, host_origin: str) -> dict[str, Any]:
        digest = secret_hash(bootstrap, "epb")
        token, session_digest = issue_secret("eps")
        with self.store.transaction() as repo:
            first = repo.embed_grant(grant_id)
            repo.workspace(first.workspace_id, lock=True)
            grant = repo.embed_grant(grant_id)
            actor, _ = self._embed_context(repo, grant)
            if not hmac.compare_digest(grant.bootstrap_hash, digest):
                raise unavailable()
            updated = grant.exchange(now_utc(), host_origin, session_digest)
            repo.update_embed_grant(updated)
            audit(repo, actor, grant.workspace_id, "integration.embed_exchanged", grant.id)
        return {"session_secret": token, "expires_at": updated.session_expires_at}

    async def read_embed(self, session: str, host_origin: str) -> tuple[StudyBoard, list[Any]]:
        digest = secret_hash(session, "eps")
        with self.store.transaction() as repo:
            grant = repo.embed_grant_by_session(digest)
            if grant is None:
                raise unavailable()
            actor, board = self._embed_context(repo, grant)
            grant.authorize(now_utc(), host_origin, board.version)
        result = await self.studies.open_board(actor, grant.workspace_id, grant.board_id)
        with self.store.transaction() as repo:
            repo.workspace(grant.workspace_id, lock=True)
            current = repo.embed_grant(grant.id)
            _, board = self._embed_context(repo, current)
            current.authorize(now_utc(), host_origin, board.version)
            if current.session_hash != digest:
                raise unavailable()
            for _, version, _ in result[1]:
                authorize_sources(repo, actor, grant.workspace_id, version.evidence.get("sources"))
            audit(repo, actor, grant.workspace_id, "integration.embed_read", grant.id)
        return result

    def revoke_embed(self, actor: User, wid: UUID, grant_id: UUID) -> None:
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            membership = repo.membership(wid, actor.id)
            grant = repo.embed_grant(grant_id)
            if grant.workspace_id != wid or membership.role != "owner":
                raise unavailable()
            if grant.revoked_at is None:
                repo.update_embed_grant(replace(grant, revoked_at=now_utc()))
                audit(repo, actor, wid, "integration.embed_revoked", grant.id)

    def embeds(self, actor: User, wid: UUID) -> list[dict[str, Any]]:
        with self.store.transaction() as repo:
            if repo.membership(wid, actor.id).role != "owner":
                raise IngestionError(
                    "integration_owner", "Only the owner can manage embedded views.", 403
                )
            return [public_grant(value) for value in repo.embed_grants(wid, actor.id)]
