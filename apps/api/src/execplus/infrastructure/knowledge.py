"""Use case: Supplies a bounded, deterministic retrieval reference for evaluation.

What it does: Fuses lexical and hashed-vector rankings, then reranks authorized passages.
"""

import hashlib
import math
import re
from collections import Counter
from uuid import UUID

from execplus.application.contracts import KnowledgeChunk, RetrievalHit


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
    def rank(
        self, query: str, chunks: tuple[KnowledgeChunk, ...], limit: int
    ) -> tuple[RetrievalHit, ...]:
        terms = set(tokens(query))
        query_vector = vector(query)
        lexical = {}
        semantic = {}
        for chunk in chunks:
            counts = Counter(tokens(chunk.text))
            lexical[chunk.chunk_id] = sum(counts[term] / (1 + counts[term]) for term in terms)
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
