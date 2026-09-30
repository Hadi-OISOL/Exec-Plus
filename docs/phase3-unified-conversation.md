> **File use case:** Defines the unified conversation and discovery contracts.
> **What it does:** Documents bounded execution, resumable evidence, retry behavior and private access.

# Unified conversation and source discovery

A selected dataset's conversation accepts one supported calculation or record query,
a document question, or a combined data/document question. DeepSeek plans through
the provider-neutral model port; Qwen remains an optional advisory selector. The
combined grammar allows one validated data step and one document search, not an
arbitrary tool loop or cross-dataset investigation. Direct Documents search remains.

Calculations use the existing validated DuckDB path and immutable execution receipts.
For documents the model selects up to three authorized passage IDs and a coverage
state; the server reopens retained bytes and supplies exact quotations. Model prose
and invented numbers are never accepted as evidence. Quoted document numbers are
labeled separately from calculations. Contradictory sources, missing evidence and
provider/storage failure produce visible limitations; revocation refuses access.

The planner receives the schema, confirmed business meaning, accessible document
names and prior structured query context. Evidence selection sends up to five
permission-filtered passages to the configured primary model. In the private demo
that is hosted DeepSeek, including for this new evidence-selection step. Uploading
real documents still requires the separately deferred provider/privacy review.

Primary planning and document selection each have a 40-second timeout. A thread
request has a 100-second workflow deadline; a durable running claim older than
120 seconds becomes explicitly failed. It is not automatically rerun after a crash.
There is at most one running turn per thread, 100 turns per thread, and 50 recent
threads per selected upload in the history list.

## API and persistence

Migration **0010** adds request IDs, status and evidence references to thread turns;
readiness requires 0010. Existing historical turns and receipt contracts remain valid.

- `POST /workspaces/{wid}/datasets/{did}/uploads/{uid}/threads` starts a private thread.
- `GET` on that same collection lists the caller's threads for the selected upload.
- `POST /workspaces/{wid}/threads/{tid}/ask` accepts `question` and an optional UUID
  `request_id`. Repeating the same ID/question reopens its recorded outcome without
  another model call or query. A changed question with the same ID returns 409.
- `GET /workspaces/{wid}/threads/{tid}` returns private turn metadata and status.
- `GET /workspaces/{wid}/threads/{tid}/turns/{turn_id}/answer` reauthorizes and replays
  the original receipt and citations. Missing/corrupt/deleted sources refuse reopening.

Mixed/textual answer bodies add `data`, `citations`, `coverage`, `limitations`,
`model_route` and `sources`. A numerical `data` body retains the existing wire format:
exact decimals and integers beyond JavaScript's safe range remain strings.
Statuses are `running`, `complete`, `partial` or `failed`. A complete turn may also
be a clarification or supported-scope refusal, rather than an executed answer.

History stores source IDs/checksums, document search text, limitations and receipt
references; it does not cache quoted passages or result rows. Reopening a retained
historical receipt preserves its old source/definition versions. Starting a follow-up
against changed business definitions requires a new conversation. Private goals and
unreviewed model prose are not promoted into shared facts.

## Browser behavior

Ask ExecPlus presents executed data alongside document evidence, upload timestamps,
source revisions and definition IDs. Open conversation citation rechecks the source.
Private conversation history restores questions and loads each saved answer on demand.
Retries after transport failure reuse the request ID. Sign-in remains memory-only:
a page refresh requires signing in again, after which the same user's history returns.

Data library → Find data by meaning searches current dataset names, saved descriptions,
column meanings, metric names and accessible document titles. It shows source upload
and revision times, definition state/version, and opens the selected dataset.
`GET /workspaces/{wid}/catalog?q=...` provides the corresponding metadata contract;
queries are limited to 200 characters. Matching requires all supplied words.
Relationships are declared paths with separate saved review metadata, not automatically
inferred joins. A changed source marks its previous meaning `needs_review`.

The catalog is rebuilt from authorized metadata on each request and never indexes
private user goals. Its `availability: metadata_only` explicitly does not promise
that source object bytes are currently online. Source access/replay checks the bytes.
No persistent cache, production vector provider or Parquet serving path is enabled.
