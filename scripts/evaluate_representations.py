"""Use case: Measures exact synthetic Parquet and learned-search candidates offline.

What it does: Reports reproducible latency, storage, memory and retrieval evidence without adoption.
"""

import argparse
import asyncio
import csv
import hashlib
import importlib
import importlib.metadata
import io
import json
import resource
import statistics
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4, uuid5

import duckdb
from create_demo_corpus import DOCUMENTS, QUESTION_ROWS

from execplus.application.contracts import KnowledgeChunk, RetrievalHit
from execplus.application.ports import PassageRanker
from execplus.domain.models import QueryPlan, WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.infrastructure.knowledge import ReferenceHybridRanker, tokens
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor

QUERIES = (
    ("SELECT city, SUM(amount) FROM dataset GROUP BY city ORDER BY city LIMIT 10", ()),
    ("SELECT MAX(record_id) FROM dataset WHERE city = ? LIMIT 1", ("Karachi",)),
    ("SELECT COUNT(amount) FROM dataset LIMIT 1", ()),
)


def storage_worker(rows: int, mode: str, repeats: int) -> dict[str, Any]:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(("city", "amount", "record_id"))
    for index in range(rows):
        writer.writerow(
            (
                "Karachi" if index % 3 else "Lahore",
                "" if index % 17 == 0 else str(Decimal(index % 97 - 48) / 100),
                9007199254740993 + index,
            )
        )
    source = output.getvalue().encode()
    start = perf_counter()
    parsed = list(csv.reader(io.StringIO(source.decode())))
    table = TableData(tuple(parsed[0]), tuple(tuple(row) for row in parsed[1:]))
    view = dataset_view(profile(table))
    ingestion_ms = (perf_counter() - start) * 1000
    executor = DuckDBQueryExecutor(120, 256)
    wid, did, qid, uid = uuid4(), uuid4(), uuid4(), uuid4()
    scope = WorkspaceScope(wid, uid, frozenset({"owner"}), frozenset({did}))
    timings: list[float] = []
    result: Any = None
    with tempfile.TemporaryDirectory(prefix="execplus-parquet-") as directory:
        path = Path(directory) / "snapshot.parquet"
        preparation_ms = 0.0
        if mode == "parquet":
            start = perf_counter()
            with duckdb.connect(config={"threads": 1, "memory_limit": "256MB"}) as connection:
                executor._load(connection, table, view)
                connection.execute("COPY dataset TO ? (FORMAT PARQUET)", [str(path)])
            preparation_ms = (perf_counter() - start) * 1000
        for _ in range(repeats):
            start = perf_counter()
            result = []
            for sql, params in QUERIES:
                if mode == "baseline":
                    plan = QueryPlan(
                        qid, wid, did, "Synthetic representation comparison", sql, params
                    )
                    result.append(asyncio.run(executor.execute(plan, scope, table, view)).rows)
                else:
                    with duckdb.connect(
                        config={"threads": 1, "memory_limit": "256MB"}
                    ) as connection:
                        connection.read_parquet(str(path)).create_view("dataset")
                        result.append(tuple(connection.execute(sql, params).fetchall()))
            timings.append((perf_counter() - start) * 1000)
        retained_bytes = path.stat().st_size if path.exists() else 0
    return dict(
        mode=mode,
        rows=rows,
        source_bytes=len(source),
        derived_bytes=retained_bytes,
        ingestion_ms=ingestion_ms,
        preparation_ms=preparation_ms,
        query_median_ms=statistics.median(timings),
        query_max_ms=max(timings),
        query_samples_ms=timings,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        result=json.loads(json.dumps(result, default=str)),
    )


class LearnedCandidate:
    """Implements the passage-ranker port only for authorized offline fixture candidates."""

    def __init__(self, encoder_path: str, reranker_path: str) -> None:
        module = importlib.import_module("sentence_transformers")
        self.encoder = module.SentenceTransformer(
            encoder_path, device="cpu", local_files_only=True, trust_remote_code=False
        )
        self.reranker = module.CrossEncoder(
            reranker_path, device="cpu", local_files_only=True, trust_remote_code=False
        )

    def rank(
        self, query: str, chunks: tuple[KnowledgeChunk, ...], limit: int
    ) -> tuple[RetrievalHit, ...]:
        if not chunks:
            return ()
        vectors = self.encoder.encode(
            [query, *(chunk.text for chunk in chunks)],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        dense = [float(vector @ vectors[0]) for vector in vectors[1:]]
        terms = set(tokens(query))
        lexical = [len(terms & set(tokens(chunk.text))) for chunk in chunks]
        fused = [0.0] * len(chunks)
        for scores in (dense, lexical):
            order = sorted(range(len(chunks)), key=lambda i: (-scores[i], str(chunks[i].chunk_id)))
            for rank, index in enumerate(order, 1):
                fused[index] += 1 / (60 + rank)
        selected = sorted(range(len(chunks)), key=lambda i: -fused[i])[:10]
        scores = self.reranker.predict(
            [(query, chunks[i].text) for i in selected],
            show_progress_bar=False,
            activation_fn=importlib.import_module("torch").nn.Identity(),
        )
        hits = [
            RetrievalHit(chunks[i], float(score))
            for i, score in zip(selected, scores, strict=True)
            if float(score) > 0
        ]
        return tuple(sorted(hits, key=lambda item: -item.score)[:limit])


def search_benchmark(encoder: str, reranker: str) -> dict[str, Any]:
    wid = did = UUID("d22d17eb-61c2-4dc2-aee1-07f2d859bf56")
    documents = {key: text for key, (_, text) in DOCUMENTS.items()}
    documents["identifier"] = "Reference AX-731 belongs to the amber instrument calibration guide."
    chunks = tuple(
        KnowledgeChunk(uuid5(wid, key), wid, did, text, {"id": key})
        for key, text in documents.items()
    )
    cases: list[tuple[str, str | None]] = [
        (query, relevant) for query, relevant, _ in QUESTION_ROWS
    ]
    cases += [
        ("AX-731", "identifier"),
        ("Who authorizes money back to a buyer?", "refunds"),
        ("How can a worker get repaid for a lost proof of purchase?", "expenses"),
        ("quasar spectroscopy redshift", None),
        ("volcanic magma composition", None),
    ]
    result: dict[str, Any] = {}
    rankers: list[tuple[str, PassageRanker]] = [
        ("reference", ReferenceHybridRanker()),
        ("learned", LearnedCandidate(encoder, reranker)),
    ]
    for name, ranker in rankers:
        outcomes: list[dict[str, Any]] = []
        times = []
        for query, relevant in cases:
            start = perf_counter()
            hits = ranker.rank(query, chunks, 3)
            times.append((perf_counter() - start) * 1000)
            ids = [hit.chunk.metadata["id"] for hit in hits]
            outcomes.append(
                dict(
                    case=len(outcomes) + 1,
                    expected=relevant,
                    returned=ids,
                    passed=relevant in ids if relevant else not ids,
                )
            )
        result[name] = dict(
            cases=outcomes,
            passed=sum(item["passed"] for item in outcomes),
            total=len(outcomes),
            query_median_ms=statistics.median(times),
            query_max_ms=max(times),
        )
    artifacts = {}
    for path in (encoder, reranker):
        root = Path(path).resolve()
        weights = root / "model.safetensors"
        artifacts[root.name] = dict(
            bytes=weights.stat().st_size, sha256=hashlib.sha256(weights.read_bytes()).hexdigest()
        )
    return dict(
        results=result,
        artifacts=artifacts,
        device="cpu",
        external_requests=0,
        packages={
            key: importlib.metadata.version(key)
            for key in ("sentence-transformers", "transformers", "torch")
        },
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        adopted=False,
        production_provider_selected=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=("baseline", "parquet"))
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 10000, 50000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--encoder")
    parser.add_argument("--reranker")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(storage_worker(args.rows, args.worker, args.repeats)))
        return
    report: dict[str, Any] = dict(scope="fictional offline candidates only", adopted=False)
    if args.encoder and args.reranker:
        report["search"] = search_benchmark(args.encoder, args.reranker)
    else:
        comparisons = []
        for size in args.sizes:
            modes = []
            for mode in ("baseline", "parquet"):
                process = subprocess.run(
                    [
                        sys.executable,
                        __file__,
                        "--worker",
                        mode,
                        "--rows",
                        str(size),
                        "--repeats",
                        str(args.repeats),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                modes.append(json.loads(process.stdout))
            comparisons.append(
                dict(rows=size, parity=modes[0]["result"] == modes[1]["result"], measurements=modes)
            )
        report["storage"] = comparisons
        report["duckdb"] = importlib.metadata.version("duckdb")
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
