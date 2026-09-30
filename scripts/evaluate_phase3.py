"""Use case: Produces reproducible synthetic retrieval and optional approved-corpus evidence.

What it does: Measures reference relevance and latency without uploading source documents.
"""

import argparse
import json
import statistics
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid5

from execplus.application.contracts import KnowledgeChunk
from execplus.infrastructure.knowledge import ReferenceHybridRanker

NAMESPACE = UUID("5a4a592b-71f4-4c44-ae8b-19d6f965b278")


def evaluate(corpus: dict[str, object]) -> dict[str, object]:
    documents = corpus["documents"]
    questions = corpus["questions"]
    if not isinstance(documents, list) or not isinstance(questions, list) or not questions:
        raise ValueError("A corpus requires document and question lists")
    chunks = tuple(
        KnowledgeChunk(
            uuid5(NAMESPACE, item["id"]), NAMESPACE, NAMESPACE, item["text"], {"id": item["id"]}
        )
        for item in documents
    )
    ranker = ReferenceHybridRanker()
    timings = []
    questions = [
        question
        for question in questions
        if question.get("expected_kind", "supported") == "supported"
    ]
    if not questions:
        raise ValueError("At least one answerable retrieval question is required")
    found = 0
    reciprocal = 0.0
    for question in questions:
        start = perf_counter()
        hits = ranker.rank(question["query"], chunks, 3)
        timings.append((perf_counter() - start) * 1000)
        for index, hit in enumerate(hits, start=1):
            if hit.chunk.metadata["id"] in question["relevant_ids"]:
                found += 1
                reciprocal += 1 / index
                break
    return {
        "provider": "reference-hybrid-v1",
        "questions": len(questions),
        "scope": "answerable retrieval only; ambiguity/refusal evaluated separately",
        "hit_rate_at_3": found / len(questions),
        "mean_reciprocal_rank_at_3": reciprocal / len(questions),
        "latency_median_ms": statistics.median(timings),
        "latency_max_ms": max(timings),
        "external_requests": 0,
        "production_provider_selected": False,
        "release_gate": "pending representative corpus, agreed threshold and provider benchmarks",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.manifest:
        manifest = json.loads(args.manifest.read_text())
        documents = []
        for item in manifest["documents"]:
            path = (args.manifest.parent / item["path"]).resolve()
            documents.append({"id": item["id"], "text": path.read_text(encoding="utf-8")})
        corpus = {"documents": documents, "questions": manifest["questions"]}
    else:
        corpus = {
            "documents": [
                {"id": "refund", "text": "Refund requests require a receipt and manager approval."},
                {"id": "leave", "text": "Annual leave requests go to the people operations team."},
                {
                    "id": "stock",
                    "text": "Warehouse stock is counted each month by the inventory team.",
                },
            ],
            "questions": [
                {"query": "refund receipt approval", "relevant_ids": ["refund"]},
                {"query": "annual leave requests", "relevant_ids": ["leave"]},
                {"query": "warehouse inventory stock", "relevant_ids": ["stock"]},
            ],
        }
    print(json.dumps(evaluate(corpus), indent=2))


if __name__ == "__main__":
    main()
