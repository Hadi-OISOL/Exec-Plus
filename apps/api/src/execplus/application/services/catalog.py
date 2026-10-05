"""Use case: Finds currently authorized sources by their reviewable business meaning.

What it does: Builds a request-scoped metadata index without caching rows or private goals.
"""

import json
import re
from typing import Any
from uuid import UUID

from execplus.application.services.analytics import UnitOfWork
from execplus.domain.artifacts import (
    TABULAR_CAPABILITIES,
    ArtifactKind,
    ArtifactRef,
    Capability,
)
from execplus.domain.ingestion import IngestionError, User


class CatalogService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def search(self, actor: User, wid: UUID, query: str = "") -> list[dict[str, Any]]:
        if len(query) > 200 or "\x00" in query:
            raise IngestionError("invalid_search", "Use at most 200 characters.", 422)
        terms = set(re.findall(r"\w+", query.casefold()))
        result: list[dict[str, Any]] = []
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            paths = repo.join_paths(wid)
            for dataset in repo.datasets(wid):
                uploads = repo.uploads(wid, dataset.id)
                upload = max(uploads, key=lambda item: (item.created_at, item.id), default=None)
                feeds = repo.refresh_feeds(wid, dataset.id)
                if feeds:
                    upload = repo.upload(wid, dataset.id, UUID(feeds[0].source["upload_id"]))
                revision = repo.active_revision(wid, dataset.id, upload.id) if upload else None
                saved = repo.latest_understanding(wid, dataset.id)
                definition = saved.definition if saved else {}
                state = saved.state if saved else "inferred"
                if saved and (revision is None or saved.revision_id != revision.id):
                    state = "needs_review"
                documents = repo.documents(wid, dataset.id, actor.id)
                artifact_refs = []
                if upload:
                    artifact_refs.append(
                        ArtifactRef(
                            wid, dataset.id, ArtifactKind.RAW_ASSET, upload.id, upload.id
                        ).record()
                    )
                if revision:
                    artifact_refs.extend(
                        ArtifactRef(wid, dataset.id, kind, revision.id, revision.upload_id).record()
                        for kind in (
                            ArtifactKind.DATASET_SNAPSHOT,
                            ArtifactKind.PROFILE,
                            ArtifactKind.QUALITY_REPORT,
                        )
                    )
                artifact_refs.extend(
                    ArtifactRef(wid, dataset.id, ArtifactKind.DOCUMENT, doc.id).record()
                    for doc in documents
                )
                entry = dict(
                    dataset_id=str(dataset.id),
                    name=dataset.name,
                    upload_id=str(upload.id) if upload else None,
                    source_uploaded_at=upload.created_at.isoformat() if upload else None,
                    revision_id=str(revision.id) if revision else None,
                    source_revised_at=revision.created_at.isoformat() if revision else None,
                    understanding_id=str(saved.id) if saved else None,
                    definition_version=saved.version if saved else 0,
                    state=state,
                    description=definition.get("description", ""),
                    grain=definition.get("grain", "unknown"),
                    columns=definition.get("columns", []),
                    metrics=definition.get("metrics", []),
                    relationships=[
                        dict(
                            id=str(path.id),
                            left_dataset_id=str(path.left_dataset_id),
                            right_dataset_id=str(path.right_dataset_id),
                            left_column=path.left_column,
                            right_column=path.right_column,
                        )
                        for path in paths
                        if dataset.id in {path.left_dataset_id, path.right_dataset_id}
                    ],
                    reviewed_relationships=definition.get("relationships", []),
                    documents=[
                        dict(id=str(doc.id), name=doc.name, uploaded_at=doc.created_at.isoformat())
                        for doc in documents
                    ],
                    availability="metadata_only",
                    asset_kinds=(["tabular"] if upload else [])
                    + (["document"] if documents else []),
                    capabilities=sorted(
                        {item.value for item in TABULAR_CAPABILITIES} if revision else set()
                    )
                    + ([Capability.TEXT_SEARCH.value] if documents else []),
                    artifact_refs=artifact_refs,
                )
                searchable = " ".join(
                    [
                        dataset.name,
                        str(entry["description"]),
                        json.dumps(entry["columns"]),
                        json.dumps(entry["metrics"]),
                        " ".join(doc.name for doc in documents),
                    ]
                ).casefold()
                words = set(re.findall(r"\w+", searchable))
                if terms <= words:
                    result.append(entry)
        return sorted(result, key=lambda item: (item["name"].casefold(), item["dataset_id"]))
