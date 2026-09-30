> **File use case:** Public Phase 3 contracts and operational boundaries.
> **What it does:** Explains observations, reports, feedback, retrieval and outstanding evaluation gates.

# Phase 3 implementation and boundaries

The September 30 data-understanding extension is documented separately in
[Phase 3A contracts](phase3-data-understanding.md). Apply migration 0009 before
running this version. Confirmed definitions govern new calculations and keep
historical replay bound to the original definition version.

Phase 3 is **In progress**. Local/test application behavior is implemented; provider
selection and representative-corpus acceptance are not complete. No production
vector vendor has been selected. See [the evaluation decision](decisions/0006-retrieval-evaluation.md).

## Activation and evidence

GET `.../uploads/{uid}/insights` returns exactly three ranked observations from the
immutable active profile: quality issues first, then coverage/quality/provenance
facts. `observations-v1` has stable ordering and revision/field references. These
are descriptive facts, not predictions or inferred business causes.

POST `/workspaces/{wid}/comparisons` takes `current_query_id` and `previous_query_id`.
Both executions are replayed. They must have the same dataset, metric and aggregation,
with scalar results and no grouping. The response includes exact difference, percentage
change (relative to the absolute baseline), evidence IDs, and an explicit statement
that the calculation does not establish a cause. Zero baseline percentages are null.

GET `/workspaces/{wid}/onboarding` derives a checklist and next steps from actual
workspace events. Existing dashboard/question recommendations remain schema-based.
GET `/workspaces/{wid}/usage-analytics` requires owner/admin role and returns event
counts, seat capacity, usage quantities, weekly active counts, returning-user counts,
and support signals. Returning means activity in two distinct ISO weeks; this is
not a predictive churn score or a commercial entitlement system.

POST `/workspaces/{wid}/feedback` accepts only `feature`, `rating` (1–5), and `category`.
Features: upload, profile, dashboard, question, knowledge, report, onboarding.
Categories: helpful, confusing, incorrect, slow, missing_feature. Workspace, actor,
release and time are server supplied. Free text, source passages, arbitrary context
and client-supplied releases are rejected. No prompts or row values enter usage/feedback.

## Scheduled email

POST `/workspaces/{wid}/report-schedules` takes an accessible saved-analysis `item_id`
and `interval_hours` (1–8760). Recipients subscribe themselves; the destination is
their current identity email. At most twenty schedules per workspace member.
GET lists the caller's schedules; DELETE `/{schedule_id}` unsubscribes idempotently.
The Saved work panel provides daily subscription and unsubscribe controls.

Run `python3 -m execplus.manage deliver-reports` from an operator-managed scheduler.
It processes up to 100 due schedules per invocation. The API does not create a
background scheduling thread. Reports replay **the saved original revision**, not a
new live-data query. Membership, saved-item visibility and subscription state are
checked again immediately before sending while holding the workspace lock.

Email defaults to disabled. Set `EXECPLUS_EMAIL_MODE=smtp` with SMTP host, port
(default 465), username, password and sender to enable authenticated implicit TLS.
Never put real credentials in source control. Tests use a capture adapter; no real
email was sent in verification. The email links to the authenticated workspace UI
for unsubscribe; it is not an unauthenticated one-click mailing-list endpoint.

Each due slot is claimed durably before replay. Concurrent workers cannot claim it
twice. Sent/failed/unauthorized/cancelled outcomes are audited without message bodies
or provider error text. Unauthorized schedules are disabled. Failures wait until
the next scheduled slot; they do not immediately resend. A crash after claim can
leave `claimed`, and SMTP delivery can be uncertain after a network failure. There
is **no exactly-once SMTP guarantee**. Operators must inspect uncertain claims;
automatic resending of uncertain mail is intentionally absent.

## Documents and citations

Under `/workspaces/{wid}/datasets/{did}`:

- POST `/documents?name=policy.txt&shared=false` takes raw UTF-8 text, TXT/MD only,
  at most 1 MiB; private by default. PDF, Office, OCR and HTML rendering are unsupported.
- GET `/documents` returns only owner-private or workspace-shared document metadata.
- POST `/knowledge/search` takes `query` (up to 500 characters) and optional `limit`
  (1–10). It returns source passages with scores and authenticated citation URLs.
- GET `/workspaces/{wid}/documents/{docid}/chunks/{chunkid}` resolves one accessible
  source passage. DELETE `/workspaces/{wid}/documents/{docid}` is owner-only.

Original bytes are checksum-bound objects under workspace/document keys. PostgreSQL
stores only document and chunk metadata, character offsets and passage checksums.
`chunks-v1` uses 1,000-character windows with 100-character overlap, including a
short final window. Documents are immutable; replacement means a new document ID.

Authorization filters documents **before** loading text or ranking. Search again
verifies returned chunks and resolves citations with current authorization. The
reference adapter combines token overlap and normalized hashed token vectors, fuses
rankings, and reranks by token overlap. It is deterministic and not a trained semantic
embedding model. It supports at most twenty accessible documents per dataset and
rebuilds the in-memory search state from the retained documents on each request.
No document passages are sent to a hosted provider. Search returns passages, not
model-generated answers; embedded instructions are source text, never executable.

## Evaluation commands

`python3 scripts/evaluate_phase3.py` runs three synthetic relevance questions and
prints hit rate, reciprocal rank and latency. These tiny fixtures test the harness;
they are not customer relevance or production latency evidence.

For locally approved documents, run:

```bash
python3 scripts/evaluate_phase3.py --manifest /absolute/path/evaluation.json
```

The manifest contains `documents: [{"id":"policy","path":"policy.txt"}]` and
`questions: [{"query":"refund requirements","relevant_ids":["policy"]}]`.
Paths resolve beside the manifest; do not commit customer documents or the manifest.
The command runs locally and does not send source text externally.

Still required: agreed relevance threshold, representative approved corpora,
learned embedding candidate evaluations, vector-provider isolation/filtering/
backup-restore/latency/cost benchmarks, and local-versus-hosted model quality,
privacy, latency and cost measurements. No endpoints, model choices or approved
customer corpus have been supplied for those tests. These remain release gates.

## Approved demo deferral — 2026-09-17

The user subsequently approved generated fictional documents and known answers,
selected hosted DeepSeek V4 Pro for the current iteration, and moved representative
customer/provider validation to mandatory pre-production work in Phase 5. See
[the demo guide and enforced release gates](phase3-demo-and-production-gates.md).
This supersedes the earlier request for customer files/local hardware now; it does
not change the limitations of the reference ranker or certify production acceptance.
