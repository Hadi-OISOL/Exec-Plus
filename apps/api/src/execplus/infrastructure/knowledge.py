"""Use case: Supplies a bounded, deterministic retrieval reference for evaluation.

What it does: Fuses lexical and hashed-vector rankings, then reranks authorized passages.
"""

import hashlib
import math
import re
from collections import Counter
from uuid import UUID

from execplus.application.contracts import KnowledgeChunk, RetrievalHit

# Retrieval candidates only: these terms never rename fields or establish meaning.
_DISCOVERY_GROUPS = (
    frozenset({"employee", "employees", "staff", "personnel"}),
    frozenset({"refund", "refunds", "reimbursement", "reimbursements"}),
    frozenset({"purchase", "purchases", "procurement"}),
    frozenset({"vendor", "vendors", "supplier", "suppliers"}),
    frozenset({"vacation", "holiday", "holidays", "leave"}),
    frozenset({"delivery", "deliveries", "shipment", "shipments", "shipping"}),
)


def discovery_terms(terms: set[str]) -> set[str]:
    """Return bounded English recall hints, not equivalence assertions."""
    return set().union(*(group for group in _DISCOVERY_GROUPS if group & terms)) - terms


def tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


def vector(text: str) -> tuple[float, ...]:
    values = [0.0] * 128
    for token in tokens(text):
        index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % 128
        values[index] += 1
    norm = math.sqrt(sum(value * value for value in values)) or 1
    return tuple(value / norm for value in values)


class ReferenceHybridRanker:
    def __init__(self, *, expand_terms: bool = False) -> None:
        self.expand_terms = expand_terms

    def rank(
        self, query: str, chunks: tuple[KnowledgeChunk, ...], limit: int
    ) -> tuple[RetrievalHit, ...]:
        terms = set(tokens(query))
        expanded = discovery_terms(terms) if self.expand_terms else set()
        query_vector = vector(query)
        lexical = {}
        semantic = {}
        for chunk in chunks:
            counts = Counter(tokens(chunk.text))
            lexical[chunk.chunk_id] = sum(counts[term] / (1 + counts[term]) for term in terms)
            lexical[chunk.chunk_id] += 0.25 * sum(
                counts[term] / (1 + counts[term]) for term in expanded
            )
            semantic[chunk.chunk_id] = sum(
                a * b for a, b in zip(query_vector, vector(chunk.text), strict=True)
            )

        def order(scores: dict[UUID, float]) -> list[UUID]:
            return sorted(scores, key=lambda key: (-scores[key], str(key)))

        fused: dict[object, float] = {}
        for scores in (lexical, semantic):
            for rank, key in enumerate(order(scores), start=1):
                fused[key] = fused.get(key, 0) + 1 / (60 + rank)
        hits = [
            RetrievalHit(chunk, fused[chunk.chunk_id] + lexical[chunk.chunk_id])
            for chunk in chunks
            if lexical[chunk.chunk_id] > 0
        ]
        return tuple(sorted(hits, key=lambda hit: (-hit.score, str(hit.chunk.chunk_id)))[:limit])
