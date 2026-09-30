> **File use case:** Records measured Phase 3 optimization and advisory-review decisions.
> **What it does:** Separates offline candidate evidence from runtime and production adoption.

# ADR 0007: Keep current execution/search; do not adopt the judge

Date: 2026-09-30. Scope: fictional private demo, not production approval.
Benchmark rules were written before evaluation in
[the representation protocol](../phase3-representation-benchmark.md) and
[the judge review sheet](../phase3-judge-review.md).

## Typed Parquet

DuckDB 1.5.5 ran the real current executor against a temporary typed Parquet candidate.
Each sample is a three-query batch: grouped decimal sum, a filtered large-integer
maximum, and a non-missing count. Each query opens a fresh connection; the baseline
reconstructs its typed table each time. Three batches were measured per size.

| Rows | CSV bytes | Added Parquet bytes | Common parse/profile ms, baseline / candidate | Candidate preparation ms | Median query batch ms, baseline / candidate | Peak process KiB, baseline / candidate |
| --- | --- | --- | --- | --- | --- | --- |
| 1,000 | 30,826 | 6,331 | 5.71 / 5.59 | 197.64 | 88.23 / 19.09 | 156,284 / 153,472 |
| 10,000 | 307,927 | 52,031 | 62.26 / 57.60 | 318.09 | 487.77 / 20.93 | 160,804 / 157,452 |
| 50,000 | 1,539,561 | 252,069 | 304.17 / 311.69 | 825.77 | 2,180.36 / 21.80 | 182,016 / 180,512 |

Exact output parity passed at all three sizes, including negative/missing decimals
and identifiers beyond JavaScript's safe range. The source bytes remain retained;
Parquet is additional storage, not a reduction in total retained bytes. Maximum
query-batch times were 253.47 / 26.73, 618.06 / 21.52 and 2681.33 / 21.92 ms.
Peak memory is process-wide Linux RSS, not attributable solely to one query.
OS file caching was not flushed; results are a local microbenchmark, not eight-user
VPS load evidence or ingestion throughput at customer scale.

**Decision:** promising repeated-query improvement, but no runtime adoption yet.
The experiment does not implement a concurrent artifact publication, invalidation,
restoration and access lifecycle. The frozen adoption rule requires that evidence.
Keep current receipts/original reconstruction and no persistent result cache.
An immutable Parquet serving adapter is a later measured optimization, not a
condition silently treated as satisfied by these timings.

## Learned retrieval

CPU trial: all-MiniLM-L6-v2 dense encoding, lexical reciprocal-rank fusion, then
ms-marco-MiniLM-L-6-v2 reranking with a fixed raw-logit cutoff of zero. The candidate
implements the existing passage-ranker shape only in an offline script; bootstrap
still composes the reference ranker. Both see the same fixed authorized fixtures.

Reference scored **20/21**. Learned retrieval scored **18/21**, failing one original
question about damaged-delivery evidence and both added synonym questions. Reference
missed the money-back synonym. Both passed the exact-identifier and two unrelated
negative cases. Both retain the original source IDs rather than generating answers.
The learned candidate failed the predeclared 21/21 threshold and is **rejected**.
Do not lower the cutoff after seeing these results and present that as this trial.

The first run's median retrieval was 0.31 ms reference / 237.13 ms learned; final
reproduction uses stable fixture UUIDs and is recorded in the verification ledger.
Weights were already cached locally; no external inference or new vendor was used.
Packages: sentence-transformers 5.1.2, transformers 4.57.1, torch 2.13.0+cpu.

| Candidate | Snapshot | Weight SHA-256 |
| --- | --- | --- |
| all-MiniLM-L6-v2 | c9745ed1d9f207416be6d2e6f8de32d1f16199bf | 53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db |
| ms-marco-MiniLM-L-6-v2 | c5ee24cb16019beea0893ab7796b1df96625c6b8 | 821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae |

## Optional judge: initial preliminary trial

A single bounded DeepSeek call per canonical fictional case reviewed the proposed
behavior, independently from application planning. It received no customer documents
or runtime history. Outputs were restricted to issue codes and evidence IDs.
There is no runtime endpoint, no answer rewriting and no permission authority.

Against the **agent-proposed, not yet human-reviewed labels**, six defects triggered
alerts, but paid-revenue meaning was labeled `missing_filter` rather than the expected
`wrong_meaning`. Thus there were zero completely missed defects, one misclassified
defect, and zero false alerts on completed acceptable cases. Three acceptable cases
timed out at 10 seconds; these are failures, not correct passes. Strict matching
passed eight of twelve. Added p95 latency was **10,013.47 ms**, above the 5-second
adoption threshold. The no-judge baseline has no calls/false alerts and misses six
defects. This is a passive zero-alert baseline over deliberately proposed behaviors,
not evidence that the real application would accept those invalid plans. Existing
deterministic guards already enforce many of these conditions. This toy trial does
not measure incremental benefit over those guards or establish real-world quality.

Reported usage from completed calls was 1,417 input and 130 output tokens. Timed-out
calls may also incur usage; total billing is unknown, and no judge spending budget
has been approved. No per-token rate or monetary saving is invented.

The preliminary decision was not to adopt. Its then-pending human review was
completed before the fresh reviewed trial below. The earlier observations remain
retained, including failures, and are not retroactively relabeled as reviewed.

## Reviewed judge decision (2026-09-30)

The repository user explicitly approved all twelve unchanged labels. A new live
DeepSeek V4 Pro run completed at 12:30:16 UTC, with one bounded call per case and
no retries. Strict matching passed **5/12**. Six requests were unavailable at the
ten-second deadline; three of those were defective cases, so three defects produced
no alert. Paid-revenue meaning again received `missing_filter` instead of the
approved `wrong_meaning` label. Completed acceptable cases had zero false alarms;
unavailable acceptable cases were retained as failures.

Added p95 latency was **10,012.89 ms**, above the frozen 5,000 ms threshold. Completed
calls reported **959 input / 82 output tokens**. Timed-out usage and total billing
remain unknown. The trial gives no basis for a reliable low-latency review pass
or an approved operating budget.

**Final decision: do not adopt. Phase 3D is Complete as an assessment.** Human label
review is satisfied; reliability, exact-label recall and latency failed. The judge
stays disabled, and no runtime answers changed. Budget approval is unnecessary for
rejection and remains a prerequisite for any future adoption. The assessed negative
result satisfies the roadmap's explicit option to reject an optional candidate.

The [final verification](../verification-phase3d.md) records every outcome, model,
case/rubric/evaluator/report hashes and the approval provenance. There is no change
to the frozen scoring criteria or the mandatory Phase 5 production reviews.

## Retention and production gates

Generated JSON reports live in ignored `data/phase3-evaluation/` and can be
recreated with the documented commands. No source data, weights, private context,
credentials, derived Parquet files or persistent search index enter Git.
The catalog uses current metadata and retrieval rereads/checksums source bytes.
Access, source change, missing/corrupt storage and restored citation tests remain
mandatory. All eight production evidence gates remain blocked.
