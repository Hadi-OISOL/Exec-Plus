"""Use case: Ingests documents and retrieves only passages authorized before ranking.

What it does: Keeps source bytes in object storage and resolves immutable, scoped citations.
"""

import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID, uuid4

from execplus.application.contracts import KnowledgeChunk
from execplus.application.ports import DocumentStorage, PassageRanker, WorkspaceRepository
from execplus.application.services.analytics import UnitOfWork
from execplus.application.services.dataset_access import dataset_access, require_full_access
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.knowledge import Document, chunks, document_text


class KnowledgeService:
    def __init__(self, uow: UnitOfWork, storage: DocumentStorage, ranker: PassageRanker) -> None:
        self.uow = uow
        self.storage = storage
        self.ranker = ranker

    def _authorized(
        self, repo: WorkspaceRepository, actor: User, wid: UUID, docid: UUID
    ) -> Document:
        repo.membership(wid, actor.id)
        document = repo.document(wid, docid)
        if not document.shared and document.owner_id != actor.id:
            raise IngestionError("not_found", "The document is unavailable.", 404)
        if dataset_access(repo, actor, wid, document.dataset_id).restricted:
            raise IngestionError("not_found", "The document is unavailable.", 404)
        repo.dataset(wid, document.dataset_id)
        return document

    async def ingest(
        self, actor: User, wid: UUID, did: UUID, name: str, content: bytes, shared: bool
    ) -> Document:
        text = document_text(name, content)
        now = datetime.now(timezone.utc)
        document = Document(
            uuid4(),
            wid,
            did,
            actor.id,
            name,
            hashlib.sha256(content).hexdigest(),
            len(content),
            shared,
            now,
        )
        written = False
        try:
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                repo.membership(wid, actor.id)
                repo.dataset(wid, did)
                require_full_access(repo, actor, wid, did)
                if len(repo.documents(wid, did, actor.id)) >= 20:
                    raise IngestionError(
                        "document_limit",
                        "Reference retrieval supports twenty accessible documents per dataset.",
                        422,
                    )
                self.storage.put_document(document, content)
                written = True
                repo.add(document)
                for chunk in chunks(document, text):
                    repo.add(chunk)
                repo.add(
                    AuditEvent(
                        uuid4(), wid, actor.id, "document.ingested", "document", document.id, now
                    )
                )
        except Exception:
            if written:
                self.storage.delete_document(document)
            raise
        return document

    async def list_documents(self, actor: User, wid: UUID, did: UUID) -> list[dict[str, object]]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            repo.dataset(wid, did)
            if dataset_access(repo, actor, wid, did).restricted:
                return []
            return [asdict(document) for document in repo.documents(wid, did, actor.id)]

    async def citation(
        self, actor: User, wid: UUID, docid: UUID, chunkid: UUID
    ) -> dict[str, object]:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            document = self._authorized(repo, actor, wid, docid)
            chunk = next(
                (item for item in repo.document_chunks(wid, docid) if item.id == chunkid), None
            )
            if chunk is None:
                raise IngestionError("not_found", "The passage is unavailable.", 404)
            text = self.storage.read_document(document).decode("utf-8")[chunk.start : chunk.end]
            if hashlib.sha256(text.encode()).hexdigest() != chunk.checksum:
                raise IngestionError(
                    "source_integrity", "The passage failed its integrity check.", 409
                )
            return {
                "document_id": docid,
                "chunk_id": chunkid,
                "name": document.name,
                "text": text,
                "start": chunk.start,
                "end": chunk.end,
                "checksum": chunk.checksum,
                "source_created_at": document.created_at.isoformat(),
            }

    async def reading_context(
        self, actor: User, wid: UUID, did: UUID, uid: UUID
    ) -> list[dict[str, object]]:
        name = f"data-reading-{str(uid)[:8]}.md"
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.upload(wid, did, uid)
            if dataset_access(repo, actor, wid, did).restricted:
                return []
            documents = sorted(
                (item for item in repo.documents(wid, did, actor.id) if item.name == name),
                key=lambda item: item.created_at,
                reverse=True,
            )[:3]
            refs = [
                (document.id, chunk.id)
                for document in documents
                for chunk in repo.document_chunks(wid, document.id)
            ][:3]
        return [await self.citation(actor, wid, docid, chunkid) for docid, chunkid in refs]

    async def search(
        self, actor: User, wid: UUID, did: UUID, query: str, limit: int = 5
    ) -> list[dict[str, object]]:
        if not query.strip() or len(query) > 500 or not 1 <= limit <= 10:
            raise IngestionError(
                "invalid_search",
                "Use a question up to 500 characters and a limit from 1 to 10.",
                422,
            )
        candidates = []
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            repo.dataset(wid, did)
            access_reference = require_full_access(repo, actor, wid, did).reference()
            documents = repo.documents(wid, did, actor.id)
            if len(documents) > 20:
                raise IngestionError(
                    "document_limit",
                    "Select a smaller document collection for reference retrieval.",
                    422,
                )
            for document in documents:
                text = self.storage.read_document(document).decode("utf-8")
                for chunk in repo.document_chunks(wid, document.id):
                    passage = text[chunk.start : chunk.end]
                    if hashlib.sha256(passage.encode()).hexdigest() != chunk.checksum:
                        raise IngestionError(
                            "source_integrity", "A passage failed its integrity check.", 409
                        )
                    candidates.append(
                        KnowledgeChunk(
                            chunk.id, wid, did, passage, {"document_id": str(document.id)}
                        )
                    )
            hits = self.ranker.rank(query, tuple(candidates), limit)
            allowed = {chunk.chunk_id: chunk for chunk in candidates}
            if any(
                hit.chunk.chunk_id not in allowed or allowed[hit.chunk.chunk_id] != hit.chunk
                for hit in hits
            ):
                raise IngestionError(
                    "retrieval_scope", "The retrieval result could not be verified.", 503
                )
            repo.add(
                AuditEvent(
                    uuid4(),
                    wid,
                    actor.id,
                    "knowledge.searched",
                    "dataset",
                    did,
                    datetime.now(timezone.utc),
                )
            )
        results = []
        for hit in hits:
            docid = UUID(hit.chunk.metadata["document_id"])
            citation = await self.citation(actor, wid, docid, hit.chunk.chunk_id)
            results.append(
                dict(
                    citation,
                    citation_url=f"/workspaces/{wid}/documents/{docid}/chunks/{hit.chunk.chunk_id}",
                    score=hit.score,
                )
            )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            if require_full_access(repo, actor, wid, did).reference() != access_reference:
                raise IngestionError("not_found", "The requested documents are unavailable.", 404)
        return results

    async def delete(self, actor: User, wid: UUID, docid: UUID) -> None:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            document = self._authorized(repo, actor, wid, docid)
            if document.owner_id != actor.id:
                raise IngestionError("forbidden", "Only the document owner can delete it.", 403)
            repo.delete_document(wid, docid)
            repo.add(
                AuditEvent(
                    uuid4(),
                    wid,
                    actor.id,
                    "document.deleted",
                    "document",
                    docid,
                    datetime.now(timezone.utc),
                )
            )
        self.storage.delete_document(document)
