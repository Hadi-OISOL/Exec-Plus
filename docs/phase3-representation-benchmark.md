> **File use case:** Defines reproducible Phase 3C candidate measurements and adoption boundaries.
> **What it does:** Freezes demo evaluation scope before running storage and learned retrieval trials.

# Representation benchmark protocol, version 1

Run `scripts/evaluate_representations.py` with isolated CPU workers. Use synthetic
1,000 / 10,000 / 50,000 row tables containing missing values, signed decimal cents,
large integer identifiers and city groups. CSV parsing/profiling is common ingestion.
Baseline queries use the actual DuckDB executor, including coercion and validation.
The experimental Parquet path pays that typed load once plus Parquet writing, then
opens a fresh connection per query. Record all three query timings, median/max,
source/derived bytes, process maximum resident memory, and exact result parity.
Memory includes the Python process and retained source table, not only DuckDB.
Temporary files are removed after each run. No existing source is rewritten.

Adoption requires exact parity, at least 20% lower median query latency at every
size, and a demonstrated safe lifecycle for source/definition edits, deletion,
restore and access revocation under concurrent application traffic. A microbenchmark
alone cannot satisfy the last condition; report a promising candidate separately
from runtime adoption. Candidate artifact loading is confined to this offline
script and is not an additional public SQL interface.

For search, compare the reference ranker against locally cached, CPU-only
`sentence-transformers/all-MiniLM-L6-v2` dense encoding, lexical reciprocal-rank
fusion and `cross-encoder/ms-marco-MiniLM-L-6-v2` reranking. Use fixed model snapshot
paths and record weight hashes, package versions, timings and memory. No downloaded
code is trusted and no model weights enter the repository. Every call receives
only its already-authorized candidate set; no global corpus or index is reused.

The fixtures include 16 original known-answer questions, one exact identifier,
two synonym questions and two unrelated negative questions. The reranker uses
raw logits with a fixed cutoff of zero. Adoption requires all 21 cases correct,
including both negative cases, and median retrieval below 500 ms on the measured
CPU. Report per-case misses and false positive evidence. Search is discovery;
relevance scores never establish a numerical answer or replace a checked citation.
Existing integration tests must still verify source availability and current access.

The production vector/provider and representative-customer gates remain open.
No persistent answer cache or derived snapshot cache is introduced in this slice;
current-source reads are retained until lifecycle and workload measurements justify
one. Cache invalidation is not claimed as an implemented optimization.
