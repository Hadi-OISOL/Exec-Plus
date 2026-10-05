"""Use case: Opens scoped artifact metadata and lineage over existing immutable records.

What it does: Reauthorizes each resource, preserves private sharing and projects versioned quality.
"""

from dataclasses import replace
from typing import Any
from uuid import UUID

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.analytics import UnitOfWork
from execplus.application.services.studies import visible
from execplus.domain.artifacts import (
    TABULAR_CAPABILITIES,
    ArtifactDescriptor,
    ArtifactKind,
    ArtifactRef,
    AssetKind,
    Capability,
    content_checksum,
    require_acyclic,
)
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.profiling import ALGORITHM, CURRENT_ALGORITHM, Revision
from execplus.domain.quality import QUALITY_VERSION, quality_report

MAX_GRAPH_NODES = 32
MAX_GRAPH_DEPTH = 8


class ArtifactService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def _authorize(self, repo: WorkspaceRepository, actor: User, reference: ArtifactRef) -> None:
        repo.membership(reference.workspace_id, actor.id)
        repo.dataset(reference.workspace_id, reference.dataset_id)

    def _revision(self, repo: WorkspaceRepository, reference: ArtifactRef) -> Revision:
        if reference.upload_id is None:
            raise IngestionError("upload_required", "Identify this revision's upload.", 422)
        upload = repo.upload(reference.workspace_id, reference.dataset_id, reference.upload_id)
        revision = repo.revision(
            reference.workspace_id, reference.dataset_id, reference.upload_id, reference.id
        )
        if revision.algorithm not in {ALGORITHM, CURRENT_ALGORITHM}:
            raise IngestionError(
                "unsupported_version", "This snapshot version is unavailable.", 409
            )
        if revision.source_checksum != upload.checksum:
            raise IngestionError("lineage_mismatch", "The revision source does not match.", 409)
        return revision

    def _source_refs(
        self, repo: WorkspaceRepository, actor: User, wid: UUID, sources: object
    ) -> tuple[ArtifactRef, ...]:
        if not isinstance(sources, list) or len(sources) > 4:
            raise IngestionError("lineage_mismatch", "Source references are unsupported.", 409)
        refs: list[ArtifactRef] = []
        try:
            for source in sources:
                reference = ArtifactRef(
                    wid,
                    UUID(str(source["dataset_id"])),
                    ArtifactKind.DATASET_SNAPSHOT,
                    UUID(str(source["revision_id"])),
                    UUID(str(source["upload_id"])),
                )
                self._authorize(repo, actor, reference)
                revision = self._revision(repo, reference)
                if (
                    revision.source_checksum != source["source_checksum"]
                    or revision.output_checksum != source["output_checksum"]
                ):
                    raise IngestionError(
                        "lineage_mismatch", "The retained source reference does not match.", 409
                    )
                refs.append(reference)
                if source.get("understanding_id"):
                    definition = repo.understanding(
                        wid, reference.dataset_id, UUID(str(source["understanding_id"]))
                    )
                    if definition.revision_id != revision.id:
                        raise IngestionError(
                            "lineage_mismatch", "The definition references another revision.", 409
                        )
                    refs.append(replace(reference, kind=ArtifactKind.DEFINITION, id=definition.id))
        except (KeyError, TypeError, ValueError):
            raise IngestionError(
                "lineage_mismatch", "Source references are invalid.", 409
            ) from None
        return tuple(refs)

    def _describe(
        self, repo: WorkspaceRepository, actor: User, reference: ArtifactRef
    ) -> ArtifactDescriptor:
        self._authorize(repo, actor, reference)
        wid, did = reference.workspace_id, reference.dataset_id
        kind = reference.kind
        if (
            kind in {ArtifactKind.DOCUMENT, ArtifactKind.QUERY_RESULT, ArtifactKind.STUDY_VERSION}
            and reference.upload_id is not None
        ):
            raise IngestionError(
                "invalid_artifact_reference", "This reference does not accept an upload ID.", 422
            )
        if kind == ArtifactKind.RAW_ASSET:
            upload = repo.upload(wid, did, reference.id)
            if reference.upload_id not in {None, upload.id}:
                raise IngestionError("not_found", "The artifact is unavailable.", 404)
            return ArtifactDescriptor(
                replace(reference, upload_id=upload.id),
                AssetKind.TABULAR,
                upload.filename,
                upload.checksum,
                "original_bytes",
                "retained-upload-v1",
                upload.created_by,
                upload.created_at,
                "workspace",
                (Capability.INSPECT, Capability.PROFILE),
                (),
                dict(
                    format=upload.format,
                    bytes=upload.size,
                    rows=upload.row_count,
                    columns=upload.column_count,
                ),
            )
        if kind in {
            ArtifactKind.DATASET_SNAPSHOT,
            ArtifactKind.PROFILE,
            ArtifactKind.QUALITY_REPORT,
        }:
            revision = self._revision(repo, reference)
            base = ArtifactRef(
                wid, did, ArtifactKind.DATASET_SNAPSHOT, revision.id, revision.upload_id
            )
            if kind == ArtifactKind.QUALITY_REPORT:
                report = quality_report(revision)
                return ArtifactDescriptor(
                    reference,
                    AssetKind.METADATA,
                    "Quality report",
                    report["checksum"],
                    "quality_report",
                    QUALITY_VERSION,
                    revision.created_by,
                    revision.created_at,
                    "workspace",
                    (Capability.INSPECT,),
                    (replace(base, kind=ArtifactKind.PROFILE),),
                    dict(profile_version=revision.algorithm, findings=len(report["findings"])),
                )
            if kind == ArtifactKind.PROFILE:
                return ArtifactDescriptor(
                    reference,
                    AssetKind.METADATA,
                    "Retained profile",
                    content_checksum(revision.profile),
                    "profile_metadata",
                    revision.algorithm,
                    revision.created_by,
                    revision.created_at,
                    "workspace",
                    (Capability.INSPECT,),
                    (base,),
                    dict(
                        rows=revision.profile["row_count"], columns=revision.profile["column_count"]
                    ),
                )
            sources: tuple[ArtifactRef, ...] = (
                ArtifactRef(
                    wid, did, ArtifactKind.RAW_ASSET, revision.upload_id, revision.upload_id
                ),
            )
            if revision.parent_id:
                sources += (replace(base, id=revision.parent_id),)
            return ArtifactDescriptor(
                reference,
                AssetKind.TABULAR,
                "Dataset snapshot",
                revision.output_checksum,
                "reconstructed_table",
                revision.algorithm,
                revision.created_by,
                revision.created_at,
                "workspace",
                TABULAR_CAPABILITIES,
                sources,
                dict(
                    rows=revision.profile["row_count"],
                    columns=revision.profile["column_count"],
                    preparation_steps=len(revision.recipe),
                ),
            )
        if kind == ArtifactKind.DOCUMENT:
            document = repo.document(wid, reference.id)
            if document.dataset_id != did or (
                not document.shared and document.owner_id != actor.id
            ):
                raise IngestionError("not_found", "The artifact is unavailable.", 404)
            return ArtifactDescriptor(
                reference,
                AssetKind.DOCUMENT,
                document.name,
                document.checksum,
                "original_bytes",
                "chunks-v1",
                document.owner_id,
                document.created_at,
                "workspace" if document.shared else "private",
                (Capability.INSPECT, Capability.TEXT_SEARCH),
                (),
                dict(bytes=document.size),
            )
        if kind == ArtifactKind.DEFINITION:
            definition = repo.understanding(wid, did, reference.id)
            if reference.upload_id not in {None, definition.upload_id}:
                raise IngestionError("not_found", "The artifact is unavailable.", 404)
            revision = self._revision(
                repo, replace(reference, id=definition.revision_id, upload_id=definition.upload_id)
            )
            return ArtifactDescriptor(
                replace(reference, upload_id=definition.upload_id),
                AssetKind.METADATA,
                "Business meaning",
                content_checksum(definition.definition),
                "definition_metadata",
                "understanding-v1",
                definition.created_by,
                definition.created_at,
                "workspace",
                (Capability.INSPECT,),
                (
                    ArtifactRef(
                        wid, did, ArtifactKind.DATASET_SNAPSHOT, revision.id, revision.upload_id
                    ),
                ),
                dict(state=definition.state, definition_version=definition.version),
            )
        if kind == ArtifactKind.QUERY_RESULT:
            execution = repo.query_execution(wid, reference.id)
            if execution.dataset_id != did:
                raise IngestionError("not_found", "The artifact is unavailable.", 404)
            receipt = execution.receipt
            sources = self._source_refs(repo, actor, wid, receipt.get("sources", []))
            checksum = receipt.get("result_checksum")
            replayable = (
                receipt.get("version") == "execution-v1"
                and receipt.get("outcome") == "executed"
                and bool(sources)
                and isinstance(checksum, str)
                and len(checksum) == 64
                and all(char in "0123456789abcdef" for char in checksum)
            )
            return ArtifactDescriptor(
                reference,
                AssetKind.TABULAR,
                "Query execution",
                checksum if isinstance(checksum, str) else None,
                "execution_result",
                str(receipt.get("version", "legacy-unavailable")),
                execution.actor_id,
                execution.created_at,
                "workspace",
                (Capability.INSPECT, Capability.REPLAY) if replayable else (Capability.INSPECT,),
                sources,
                dict(
                    outcome=receipt.get("outcome", "unavailable"),
                    records_analyzed=execution.records_analyzed,
                ),
            )
        if kind == ArtifactKind.STUDY_VERSION:
            version = repo.study_version(wid, reference.id)
            study = visible(repo, actor, wid, version.study_id)
            if study.dataset_id != did:
                raise IngestionError("not_found", "The artifact is unavailable.", 404)
            sources = self._source_refs(repo, actor, wid, version.evidence.get("sources", []))
            query_ids = version.evidence.get("query_ids", [])
            if not isinstance(query_ids, list) or len(query_ids) > 8:
                raise IngestionError("lineage_mismatch", "Study query references are invalid.", 409)
            replayable = bool(query_ids)
            try:
                for query_id in query_ids:
                    query_ref = ArtifactRef(
                        wid, did, ArtifactKind.QUERY_RESULT, UUID(str(query_id))
                    )
                    query = self._describe(repo, actor, query_ref)
                    replayable = replayable and Capability.REPLAY in query.capabilities
                    sources += (query_ref,)
            except (TypeError, ValueError):
                raise IngestionError(
                    "lineage_mismatch", "Study references are invalid.", 409
                ) from None
            return ArtifactDescriptor(
                reference,
                AssetKind.METADATA,
                study.name,
                content_checksum(dict(method=version.method, evidence=version.evidence)),
                "study_evidence",
                str(version.evidence.get("method_version", "unavailable")),
                version.created_by,
                version.created_at,
                "workspace" if study.shared else "private",
                (Capability.INSPECT, Capability.REPLAY, Capability.VISUALIZE)
                if replayable
                else (Capability.INSPECT,),
                sources,
                dict(
                    study_id=str(study.id),
                    number=version.number,
                    method_kind=version.method.get("kind"),
                ),
            )
        raise IngestionError("unsupported_artifact", "This artifact kind is unavailable.", 422)

    def describe(self, actor: User, reference: ArtifactRef) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(reference.workspace_id, lock=True)
            return self._describe(repo, actor, reference).record()

    def upload_artifacts(self, actor: User, wid: UUID, did: UUID, uid: UUID) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            reference = ArtifactRef(wid, did, ArtifactKind.RAW_ASSET, uid, uid)
            artifacts = [self._describe(repo, actor, reference).record()]
            revision = repo.active_revision(wid, did, uid)
            if revision:
                for kind in (
                    ArtifactKind.DATASET_SNAPSHOT,
                    ArtifactKind.PROFILE,
                    ArtifactKind.QUALITY_REPORT,
                ):
                    artifacts.append(
                        self._describe(
                            repo, actor, ArtifactRef(wid, did, kind, revision.id, uid)
                        ).record()
                    )
            return dict(version="artifact-v1", artifacts=artifacts)

    def quality(
        self, actor: User, wid: UUID, did: UUID, uid: UUID, revision_id: UUID | None = None
    ) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self._authorize(repo, actor, ArtifactRef(wid, did, ArtifactKind.RAW_ASSET, uid, uid))
            repo.upload(wid, did, uid)
            current = repo.active_revision(wid, did, uid) if revision_id is None else None
            if revision_id is None and current is None:
                raise IngestionError("not_found", "This upload has no retained profile.", 404)
            identifier = revision_id if revision_id is not None else current.id if current else uid
            revision = self._revision(
                repo, ArtifactRef(wid, did, ArtifactKind.QUALITY_REPORT, identifier, uid)
            )
            return quality_report(revision)

    def lineage(self, actor: User, reference: ArtifactRef) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(reference.workspace_id, lock=True)
            pending = [(reference, 0, frozenset[str]())]
            nodes: dict[str, dict[str, Any]] = {}
            edges: list[dict[str, str]] = []
            truncated = False
            while pending:
                current, depth, ancestors = pending.pop(0)
                if current.workspace_id != reference.workspace_id:
                    raise IngestionError("lineage_mismatch", "Lineage crossed a workspace.", 409)
                key = current.key()
                if key in ancestors:
                    raise IngestionError("lineage_mismatch", "Lineage contains a cycle.", 409)
                if key in nodes:
                    continue
                if len(nodes) >= MAX_GRAPH_NODES or depth > MAX_GRAPH_DEPTH:
                    truncated = True
                    continue
                item = self._describe(repo, actor, current)
                nodes[key] = item.record()
                for source in item.sources:
                    self._authorize(repo, actor, source)
                    self._describe(repo, actor, source)
                    edges.append(dict(source=source.key(), target=key, relationship="derived_from"))
                    pending.append((source, depth + 1, ancestors | {key}))
            kept_edges = [edge for edge in edges if edge["source"] in nodes]
            require_acyclic(tuple((edge["source"], edge["target"]) for edge in kept_edges))
            return dict(
                version="lineage-v1",
                root=reference.record(),
                nodes=list(nodes.values()),
                edges=kept_edges,
                truncated=truncated,
                limits=dict(nodes=MAX_GRAPH_NODES, depth=MAX_GRAPH_DEPTH),
                availability="metadata_only",
            )
