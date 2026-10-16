"""Use case: Activates validated, explicitly staged file refreshes without losing usable data.

What it does: Enforces tenant policy, idempotency, schema review and atomic monitoring enqueue.
"""

import hashlib
import logging
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from typing import Any, cast
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.analytics import AnalyticsService, UnitOfWork
from execplus.application.services.dataset_access import authorize_sources, require_full_access
from execplus.application.services.workspaces import WorkspaceService
from execplus.domain.dataset_access import denied
from execplus.domain.ingestion import IngestionError, Membership, Upload, User
from execplus.domain.profiling import Revision, TableData, reconstruct
from execplus.domain.refresh import (
    Observation,
    RefreshCandidate,
    RefreshFeed,
    combine,
    csv_bytes,
    fail,
    fingerprint,
    source_dates,
    stale,
)
from execplus.domain.understanding import Understanding, infer_definition, validate_definition

logger = logging.getLogger(__name__)


def editor(repo: WorkspaceRepository, actor: User, wid: UUID, did: UUID) -> None:
    member = repo.membership(wid, actor.id)
    require_full_access(repo, actor, wid, did)
    dataset = repo.dataset(wid, did)
    if member.role not in {"owner", "admin"} and dataset.created_by != actor.id:
        fail("forbidden", "The dataset creator or an owner/admin manages refreshes.", 403)


def authority(
    repo: WorkspaceRepository, actor: User, wid: UUID, did: UUID
) -> tuple[Membership, dict[str, str]]:
    editor(repo, actor, wid, did)
    return repo.membership(wid, actor.id), require_full_access(repo, actor, wid, did).reference()


def recheck_authority(
    repo: WorkspaceRepository,
    actor: User,
    wid: UUID,
    did: UUID,
    captured: tuple[Membership, dict[str, str]],
) -> None:
    if authority(repo, actor, wid, did) != captured:
        raise denied()


def conflict() -> None:
    fail("refresh_conflict", "The source or refresh changed; reload before continuing.", 409)


def same_source(
    repo: WorkspaceRepository,
    feed: RefreshFeed,
    upload: Upload,
    revision: Revision,
    meaning: Understanding,
) -> None:
    wid, did = feed.workspace_id, feed.dataset_id
    if (
        repo.refresh_feed(wid, feed.id) != feed
        or repo.upload(wid, did, upload.id) != upload
        or repo.active_revision(wid, did, upload.id) != revision
        or repo.latest_understanding(wid, did) != meaning
        or not current(repo, feed)
    ):
        conflict()


def current(repo: WorkspaceRepository, feed: RefreshFeed) -> bool:
    source = feed.source
    revision = repo.active_revision(feed.workspace_id, feed.dataset_id, UUID(source["upload_id"]))
    meaning = repo.latest_understanding(feed.workspace_id, feed.dataset_id)
    return bool(
        revision
        and str(revision.id) == source["revision_id"]
        and meaning
        and str(meaning.id) == source["understanding_id"]
        and meaning.state == "confirmed"
    )


def enqueue(repo: WorkspaceRepository, feed: RefreshFeed, now: datetime) -> None:
    for monitor in repo.monitors(feed.workspace_id, feed.id):
        if monitor.enabled:
            repo.add(
                Observation(
                    uuid4(),
                    feed.workspace_id,
                    monitor.id,
                    feed.version,
                    feed.source,
                    "pending",
                    0,
                    None,
                    None,
                    {},
                    now,
                )
            )


class RefreshService:
    def __init__(
        self, uow: UnitOfWork, uploads: WorkspaceService, analytics: AnalyticsService
    ) -> None:
        self.uow, self.uploads, self.analytics = uow, uploads, analytics

    def audit(
        self, repo: WorkspaceRepository, actor: User, wid: UUID, action: str, rid: UUID
    ) -> None:
        self.uploads._audit(repo, actor, wid, action, "refresh", rid)

    def configure(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        uid: UUID,
        revision_id: UUID,
        understanding_id: UUID,
        expected_version: int,
        interval_hours: int,
        freshness_hours: int,
        enabled: bool,
        as_of: datetime,
        coverage_start: date | None = None,
        coverage_end: date | None = None,
    ) -> RefreshFeed:
        now = datetime.now(timezone.utc)
        dates = source_dates(as_of, coverage_start, coverage_end, now)
        if not 1 <= interval_hours <= 8760 or not 1 <= freshness_hours <= 8760:
            fail("invalid_interval", "Use intervals between 1 and 8,760 hours.")
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            captured = authority(repo, actor, wid, did)
            upload = repo.upload(wid, did, uid)
            revision = repo.active_revision(wid, did, uid)
            meaning = repo.latest_understanding(wid, did)
            if (
                not revision
                or revision.id != revision_id
                or not meaning
                or meaning.id != understanding_id
                or meaning.revision_id != revision_id
                or meaning.state != "confirmed"
            ):
                fail(
                    "definition_conflict",
                    "Confirm the selected current source meaning before configuring refresh.",
                    409,
                )
            feeds = repo.refresh_feeds(wid, did)
            prior = feeds[0] if feeds else None
            if expected_version != (prior.version if prior else 0):
                fail(
                    "refresh_conflict", "Refresh configuration changed; reload before saving.", 409
                )
        reconstruct(self.uploads._table(upload), revision)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            recheck_authority(repo, actor, wid, did, captured)
            if (
                repo.upload(wid, did, uid) != upload
                or repo.active_revision(wid, did, uid) != revision
                or repo.latest_understanding(wid, did) != meaning
                or repo.refresh_feeds(wid, did) != feeds
            ):
                conflict()
            source = dict(
                dataset_id=str(did),
                upload_id=str(uid),
                revision_id=str(revision_id),
                understanding_id=str(understanding_id),
                source_checksum=upload.checksum,
                output_checksum=revision.output_checksum,
                definition_hash=fingerprint(meaning.definition),
                **dates,
                **require_full_access(repo, actor, wid, did).reference(),
            )
            feed = RefreshFeed(
                prior.id if prior else uuid4(),
                wid,
                did,
                actor.id,
                expected_version + 1,
                source,
                interval_hours,
                freshness_hours,
                enabled,
                now + timedelta(hours=interval_hours),
                None,
                "ready",
                prior.created_at if prior else now,
            )
            if prior:
                repo.set_refresh_feed(feed)
            else:
                repo.add(feed)
            enqueue(repo, feed, now)
            self.audit(repo, actor, wid, "refresh.configured", feed.id)
            return feed

    def overview(self, actor: User, wid: UUID, did: UUID) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            require_full_access(repo, actor, wid, did)
            dataset = repo.dataset(wid, did)
            feeds = repo.refresh_feeds(wid, did)
            member = repo.membership(wid, actor.id)
            can_edit = member.role in {"owner", "admin"} or dataset.created_by == actor.id
            if not feeds:
                return dict(feed=None, candidates=[], can_edit=can_edit)
            feed = feeds[0]
            authorize_sources(repo, actor, wid, [feed.source])
            return dict(
                feed=asdict(feed),
                candidates=[
                    asdict(c)
                    for c in sorted(
                        repo.refresh_candidates(wid, feed.id),
                        key=lambda c: c.created_at,
                        reverse=True,
                    )[:50]
                ],
                stale=stale(feed.source, feed.freshness_hours, now),
                definition_state="confirmed" if current(repo, feed) else "needs_review",
                can_edit=can_edit,
                schedule_contract="Staged files only; no desktop polling.",
            )

    def _prepare_upload(
        self,
        actor: User,
        feed: RefreshFeed,
        source_revision: Revision,
        filename: str,
        content_type: str,
        content: bytes,
        stored: list[Upload],
    ) -> tuple[Upload, Revision, TableData]:
        if len(content) > self.uploads.max_upload_bytes:
            fail("file_too_large", "Files and derived snapshots must be at most 20 MiB.", 413)
        stream = BytesIO(content)
        structure = self.uploads.parser.parse(stream, filename, content_type)
        table = self.uploads.parser.read_table(stream, structure.format)
        uid = uuid4()
        upload = Upload(
            uid,
            feed.workspace_id,
            feed.dataset_id,
            filename,
            content_type,
            len(content),
            f"workspaces/{feed.workspace_id}/datasets/{feed.dataset_id}/uploads/{uid}/original",
            hashlib.sha256(content).hexdigest(),
            "stored",
            structure.format,
            structure.row_count,
            structure.column_count,
            actor.id,
            datetime.now(timezone.utc),
            None,
        )
        revision = self.uploads._make_revision(
            actor, upload, table, [], None, algorithm=source_revision.algorithm
        )
        stored.append(upload)
        self.uploads.storage.put(upload, BytesIO(content))
        return upload, revision, table

    def _cleanup(self, stored: list[Upload]) -> None:
        for upload in stored:
            try:
                retained = True
                with self.uow() as repo:
                    repo.workspace(upload.workspace_id, lock=True)
                    try:
                        repo.upload(upload.workspace_id, upload.dataset_id, upload.id)
                    except IngestionError as exc:
                        if exc.status != 404:
                            raise
                        retained = False
                if not retained:
                    self.uploads.storage.delete(upload)
            except Exception:
                logger.error(
                    "refresh_cleanup_failed workspace_id=%s upload_id=%s",
                    upload.workspace_id,
                    upload.id,
                )

    def _stage_state(
        self,
        repo: WorkspaceRepository,
        actor: User,
        wid: UUID,
        did: UUID,
        request_id: UUID,
        signature: str,
        expected_version: int,
        as_of: datetime,
    ) -> tuple[RefreshFeed, RefreshCandidate | None]:
        editor(repo, actor, wid, did)
        feeds = repo.refresh_feeds(wid, did)
        if not feeds:
            fail("refresh_not_configured", "Configure the active source first.", 409)
        feed = feeds[0]
        authorize_sources(repo, actor, wid, [feed.source])
        candidates = repo.refresh_candidates(wid, feed.id)
        existing = next((c for c in candidates if c.request_id == request_id), None)
        if existing:
            if existing.signature != signature:
                fail(
                    "idempotency_conflict",
                    "This request ID already refers to different content.",
                    409,
                )
            return feed, existing
        if feed.version != expected_version or not current(repo, feed):
            conflict()
        if sum(c.status in {"queued", "needs_review"} for c in candidates) >= 20:
            fail("refresh_limit", "Resolve the existing staged files first.", 409)
        if as_of < datetime.fromisoformat(feed.source["as_of"]):
            fail("older_source", "A refresh cannot move source freshness backwards.")
        return feed, None

    def stage(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        request_id: UUID,
        expected_version: int,
        filename: str,
        content_type: str,
        content: bytes,
        mode: str,
        keys: list[str],
        duplicates: str,
        as_of: datetime,
        coverage_start: date | None,
        coverage_end: date | None,
    ) -> RefreshCandidate:
        now = datetime.now(timezone.utc)
        dates = source_dates(as_of, coverage_start, coverage_end, now)
        signature = fingerprint(
            [
                expected_version,
                filename,
                content_type,
                hashlib.sha256(content).hexdigest(),
                mode,
                keys,
                duplicates,
                dates,
            ]
        )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            captured = authority(repo, actor, wid, did)
            feed, existing = self._stage_state(
                repo, actor, wid, did, request_id, signature, expected_version, as_of
            )
            if existing:
                return existing
            base = repo.upload(wid, did, UUID(feed.source["upload_id"]))
            revision = repo.revision(wid, did, base.id, UUID(feed.source["revision_id"]))
            meaning = repo.understanding(wid, did, UUID(feed.source["understanding_id"]))
        stored: list[Upload] = []
        prepared: list[tuple[Upload, Revision, TableData]] = []
        published = False
        details: dict[str, Any] = dict(
            mode=mode,
            keys=keys,
            duplicates=duplicates,
            dates=dates,
            base_source=feed.source,
        )
        status = "queued"
        try:
            try:
                incoming_snapshot = self._prepare_upload(
                    actor, feed, revision, filename, content_type, content, stored
                )
                prepared.append(incoming_snapshot)
                original, input_revision, incoming = incoming_snapshot
                details.update(input_upload_id=str(original.id))
                previous = reconstruct(self.uploads._table(base), revision)
                table, stats = combine(previous, incoming, mode, keys, duplicates)
                output, output_revision = original, input_revision
                if mode != "replace":
                    output_snapshot = self._prepare_upload(
                        actor,
                        feed,
                        revision,
                        "refresh-snapshot.csv",
                        "text/csv",
                        csv_bytes(table),
                        stored,
                    )
                    prepared.append(output_snapshot)
                    output, output_revision, table = output_snapshot
                details.update(
                    output_upload_id=str(output.id),
                    revision_id=str(output_revision.id),
                    stats=stats,
                )
                columns = cast(list[dict[str, Any]], output_revision.profile["columns"])
                if not table.rows or any(
                    c["type_conflicts"] or c["invalid_dates"] for c in columns
                ):
                    fail(
                        "invalid_candidate",
                        "The candidate is empty or has invalid/mixed values. Correct it first.",
                    )
                old_schema = [
                    (c["name"], c["type"])
                    for c in cast(list[dict[str, Any]], revision.profile["columns"])
                ]
                new_schema = [(c["name"], c["type"]) for c in columns]
                proposed = meaning.definition
                if old_schema != new_schema:
                    proposed = infer_definition(
                        output_revision.profile, meaning.definition["domain"]
                    )
                    proposed["grain"] = meaning.definition["grain"]
                    status = "needs_review"
                if meaning.definition["relationships"]:
                    proposed = {**proposed, "relationships": []}
                    status = "needs_review"
                details.update(
                    schema_changed=old_schema != new_schema,
                    old_schema=old_schema,
                    new_schema=new_schema,
                    relationships_invalidated=bool(meaning.definition["relationships"]),
                    definition=proposed,
                )
                try:
                    validate_definition(proposed, table, output_revision.profile, "confirmed")
                except IngestionError:
                    status = "needs_review"
            except IngestionError as exc:
                if exc.code == "storage_unavailable":
                    raise
                status = "failed"
                details["failure_code"] = exc.code
        except Exception:
            self._cleanup(stored)
            stored.clear()
            prepared.clear()
            status = "failed"
            details = dict(
                mode=mode,
                keys=keys,
                duplicates=duplicates,
                dates=dates,
                failure_code="storage_or_transaction_failed",
            )
        retained_ids = {upload.id for upload, _, _ in prepared}
        self._cleanup([upload for upload in stored if upload.id not in retained_ids])
        stored[:] = [upload for upload in stored if upload.id in retained_ids]
        try:
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                recheck_authority(repo, actor, wid, did, captured)
                _, existing = self._stage_state(
                    repo, actor, wid, did, request_id, signature, expected_version, as_of
                )
                if existing:
                    return existing
                same_source(repo, feed, base, revision, meaning)
                for upload, root, _ in prepared:
                    repo.add(upload)
                    repo.add(root)
                    repo.set_active_revision(root)
                    self.uploads._usage(repo, actor, wid, "storage_bytes", upload.size, upload.id)
                    self.audit(repo, actor, wid, "refresh.file_retained", upload.id)
                candidate = RefreshCandidate(
                    uuid4(),
                    wid,
                    feed.id,
                    request_id,
                    signature,
                    feed.version,
                    actor.id,
                    status,
                    details,
                    now,
                )
                repo.add(candidate)
                self.audit(repo, actor, wid, f"refresh.{status}", candidate.id)
            published = True
            return candidate
        finally:
            if not published:
                self._cleanup(stored)

    def review(
        self, actor: User, wid: UUID, cid: UUID, definition: dict[str, Any] | None, reject: bool
    ) -> RefreshCandidate:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            candidate = repo.refresh_candidate(wid, cid)
            feed = repo.refresh_feed(wid, candidate.feed_id)
            did = feed.dataset_id
            captured = authority(repo, actor, wid, did)
            authorize_sources(repo, actor, wid, [feed.source])
            if candidate.status not in {"queued", "needs_review"}:
                fail("refresh_conflict", "Only a pending candidate can be reviewed.", 409)
            if reject:
                changed = replace(candidate, status="rejected")
                repo.set_refresh_candidate(changed)
                self.audit(repo, actor, wid, "refresh.rejected", cid)
                return changed
            if candidate.base_version != feed.version or not current(repo, feed):
                conflict()
            upload = repo.upload(wid, did, UUID(candidate.details["output_upload_id"]))
            revision = repo.revision(wid, did, upload.id, UUID(candidate.details["revision_id"]))
            if repo.active_revision(wid, did, upload.id) != revision:
                conflict()
            base = repo.upload(wid, did, UUID(feed.source["upload_id"]))
            base_revision = repo.revision(wid, did, base.id, UUID(feed.source["revision_id"]))
            meaning = repo.understanding(wid, did, UUID(feed.source["understanding_id"]))
        table = reconstruct(self.uploads._table(upload), revision)
        validated = validate_definition(definition or {}, table, revision.profile, "confirmed")
        if validated["relationships"]:
            fail(
                "relationship_review_required",
                "Clear relationships; reconfirm them after activation in Data meaning.",
            )
        changed = replace(
            candidate,
            status="queued",
            details={
                **candidate.details,
                "definition": validated,
                "reviewed_by": str(actor.id),
            },
        )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            recheck_authority(repo, actor, wid, did, captured)
            same_source(repo, feed, base, base_revision, meaning)
            if (
                repo.refresh_candidate(wid, cid) != candidate
                or repo.upload(wid, did, upload.id) != upload
                or repo.active_revision(wid, did, upload.id) != revision
            ):
                conflict()
            repo.set_refresh_candidate(changed)
            self.audit(repo, actor, wid, "refresh.reviewed", cid)
            return changed

    def activate(
        self, actor: User, wid: UUID, cid: UUID, *, now: datetime | None = None
    ) -> RefreshCandidate:
        now = now or datetime.now(timezone.utc)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            candidate = repo.refresh_candidate(wid, cid)
            feed = repo.refresh_feed(wid, candidate.feed_id)
            captured = authority(repo, actor, wid, feed.dataset_id)
            creator = repo.user(candidate.created_by)
            creator_authority = authority(repo, creator, wid, feed.dataset_id)
            authorize_sources(repo, actor, wid, [feed.source])
            if candidate.status == "activated":
                return candidate
            if candidate.status != "queued":
                fail(
                    "review_required", "Only a validated and reviewed candidate can activate.", 409
                )
            if feed.version != candidate.base_version or not current(repo, feed):
                changed = replace(candidate, status="conflict")
                repo.set_refresh_candidate(changed)
                self.audit(repo, actor, wid, "refresh.conflict", cid)
                return changed
            upload = repo.upload(wid, feed.dataset_id, UUID(candidate.details["output_upload_id"]))
            revision = repo.revision(
                wid, feed.dataset_id, upload.id, UUID(candidate.details["revision_id"])
            )
            active = repo.active_revision(wid, feed.dataset_id, upload.id)
            if active is None or active.id != revision.id:
                fail("refresh_conflict", "The staged snapshot changed; stage a new candidate.", 409)
            latest = repo.latest_understanding(wid, feed.dataset_id)
            assert latest is not None
            base = repo.upload(wid, feed.dataset_id, UUID(feed.source["upload_id"]))
            base_revision = repo.revision(
                wid, feed.dataset_id, base.id, UUID(feed.source["revision_id"])
            )
        table = reconstruct(self.uploads._table(upload), revision)
        definition = validate_definition(
            candidate.details["definition"], table, revision.profile, "confirmed"
        )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            recheck_authority(repo, actor, wid, feed.dataset_id, captured)
            recheck_authority(repo, creator, wid, feed.dataset_id, creator_authority)
            actual = repo.refresh_candidate(wid, cid)
            actual_feed = repo.refresh_feed(wid, feed.id)
            authorize_sources(repo, actor, wid, [actual_feed.source])
            if (
                repo.upload(wid, feed.dataset_id, upload.id) != upload
                or repo.active_revision(wid, feed.dataset_id, upload.id) != revision
            ):
                conflict()
            if actual == replace(candidate, status="activated"):
                return actual
            if actual != candidate:
                conflict()
            same_source(repo, feed, base, base_revision, latest)
            meaning = Understanding(
                uuid4(),
                wid,
                feed.dataset_id,
                upload.id,
                revision.id,
                latest.version + 1,
                "confirmed",
                definition,
                actor.id,
                now,
            )
            repo.add(meaning)
            source = dict(
                dataset_id=str(feed.dataset_id),
                upload_id=str(upload.id),
                revision_id=str(revision.id),
                understanding_id=str(meaning.id),
                source_checksum=upload.checksum,
                output_checksum=revision.output_checksum,
                definition_hash=fingerprint(definition),
                **candidate.details["dates"],
                **require_full_access(repo, actor, wid, feed.dataset_id).reference(),
            )
            feed = replace(
                feed,
                version=feed.version + 1,
                source=source,
                state="ready",
                last_checked_at=now,
                next_due=now + timedelta(hours=feed.interval_hours),
            )
            repo.set_refresh_feed(feed)
            changed = replace(candidate, status="activated")
            repo.set_refresh_candidate(changed)
            enqueue(repo, feed, now)
            self.audit(repo, actor, wid, "refresh.activated", cid)
            return changed

    def process_due(self, now: datetime | None = None) -> dict[str, int]:
        now = now or datetime.now(timezone.utc)
        counts = dict(activated=0, waiting=0, failed=0)
        with self.uow() as repo:
            due = repo.due_refreshes(now)
        for wid, fid in due:
            cid = None
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                feed = repo.refresh_feed(wid, fid)
                if not feed.enabled or feed.next_due > now:
                    continue
                actor = repo.user(feed.owner_id)
                try:
                    editor(repo, actor, wid, feed.dataset_id)
                    authorize_sources(repo, actor, wid, [feed.source])
                except IngestionError:
                    repo.set_refresh_feed(
                        replace(feed, enabled=False, state="unauthorized", last_checked_at=now)
                    )
                    counts["failed"] += 1
                    continue
                candidates = sorted(
                    repo.refresh_candidates(wid, fid), key=lambda item: item.created_at
                )
                queued = [item for item in candidates if item.status == "queued"]
                cid = queued[0].id if queued else None
                state = "processing" if cid else "waiting_for_file"
                repo.set_refresh_feed(
                    replace(
                        feed,
                        state=state,
                        last_checked_at=now,
                        next_due=now
                        + (timedelta(minutes=5) if cid else timedelta(hours=feed.interval_hours)),
                    )
                )
                if not cid:
                    counts["waiting"] += 1
            if cid:
                try:
                    result = self.activate(actor, wid, cid, now=now)
                    counts["activated" if result.status == "activated" else "failed"] += 1
                except Exception:
                    with self.uow() as repo:
                        repo.workspace(wid, lock=True)
                        feed = repo.refresh_feed(wid, fid)
                        repo.set_refresh_feed(replace(feed, state="activation_failed"))
                        self.audit(repo, actor, wid, "refresh.activation_failed", cid)
                    counts["failed"] += 1
        return counts
