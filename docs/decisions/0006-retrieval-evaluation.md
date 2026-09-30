> **File use case:** Records the provisional retrieval implementation and selection gates.
> **What it does:** Prevents synthetic reference results from becoming an unsupported vendor decision.

# ADR 0006: Evaluate before selecting a vector provider

Status: Provisional reference adapter; production selection deferred, 2026-09-17.

Keep document metadata in PostgreSQL and immutable source bytes in S3-compatible
storage. Apply workspace membership and owner/sharing filters before loading passages.
Preserve exact offsets/checksums so citations can be independently resolved after
ranking. Domain and application services remain independent of provider SDKs.

Use a bounded in-process lexical/hashed-vector reference for local tests. Its index
is reconstructed from retained objects; it is not a persistent production vector
database and its vectors do not establish semantic relevance quality. The original
EmbeddingStore protocol remains available; PassageRanker isolates this authorized
candidate-ranking stage. Do not set VECTOR_MODE to a selected vendor based on this work.

A production decision must compare candidate metadata filtering, tenant isolation,
revocation, passage deletion, restore from backup, latency at representative sizes,
local/managed operation, privacy, and total operating cost. Evaluate learned embedding
models against approved documents and human relevance labels, with an agreed threshold.
Evaluate local and hosted model routes on the same approved tasks, recording model
version, quality/refusal/numerical fidelity, p50/p95 latency, token use, actual pricing,
data retention policy and allowed deployment boundary.

The synthetic three-question harness establishes reproducibility only. No representative
corpus, live model measurements, provider backup drill, agreed threshold, or production
cost assessment exists yet. Phase 3 cannot be marked Complete until these pass.

## User-approved deferral, 2026-09-17

Current development uses generated fictional documents plus hosted DeepSeek V4 Pro.
Representative-customer, comparative provider and operational evaluations move to
Phase 5 and remain mandatory before external customer deployment. The production
ledger and startup evidence check enforce this deferral. This does not select a
production vector provider or claim that hashed vectors are learned embeddings.
