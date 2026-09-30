> **File use case:** Documents Phase 3A business definitions and personal context.
> **What it does:** Explains the user journey, authorization, versioning, query rules and supported limits.

# Data understanding

After uploading CSV or single-sheet XLSX data, open **Overview → Data understanding**.
The upload form offers an optional business category and a private analysis goal.
These hints do not change file validation or authorize additional formats.

The deterministic profile proposes column roles, business tags and order/order-item
grain where the evidence supports it. Unknown grain, missing units and ambiguous
dates produce focused review questions. Users can correct the description, row
meaning, domain, column role, unit/currency, time-zone meaning and missing-value
policy. Numeric identifiers and ordered ratings can be excluded from business
measures. Category hints never change the inferred physical column types.

Confirming saves an immutable shared definition version. Saving for review or
revoking saves a new version and prevents new calculations until confirmed again.
The dataset creator or workspace owner/admin can change shared definitions. Any
current member can inspect them. Personal goals belong to the current user and
are not included in another user's response, audit payload or model context.

Legacy datasets with no saved definition keep the existing profile-based analysis
flow; the screen labels that context **inferred**, not confirmed. Once a definition
exists, a different upload or preparation revision requires review. Corrections
for surviving column names are carried forward for review; suggestions do not
overwrite them. Historical definitions can be inspected separately.

## Calculation rules

- Each numeric column may have one named default calculation (sum, average,
  count, minimum or maximum) and up to 20 required filters. New queries and
  dashboard calculations of that column include its required filters. A different
  aggregation requires an explicit definition change rather than silent substitution.
- Confirmed column roles and business tags reach the planner, dashboards and KPI
  compatibility checks. The average-order-value KPI requires confirmed order grain
  when a definition exists. Human descriptions are untrusted context, never executable
  instructions. Models still cannot supply calculated business values.
- Detected per-row currency/unit columns and explicitly selected unit columns
  require grouping or an equality filter when units differ or are missing. There is
  no automatic currency conversion or assumption that unknown units are equivalent.
- A missing-value policy of **Require review** blocks calculation when the metric
  contains missing cells. **Exclude** retains the existing SQL aggregate behavior;
  missing values are not replaced with zero.
- Dates/time zones, sensitivity and expected update behavior are descriptive metadata.
  This slice does not add time-zone conversion, new sharing permissions or automated
  refresh. Ambiguous dates should be corrected in the source or preparation flow.

## Relationships

The existing workspace join-path API declares the two datasets and matching keys.
Those declared paths appear as proposals in **Dataset relationships**. For a dataset
with saved understanding, the relevant relationship must be explicitly confirmed
before a new joined calculation. Review supports many-to-one and one-to-one paths
from left to right; missing keys or incompatible uniqueness cannot be confirmed.
There is no automatic join discovery or graphical join-authoring interface yet.

Execution independently validates the declared keys and right-side uniqueness.
A right-side measure also requires unique left keys, preventing duplicated totals
and reweighted averages. No implicit deduplication changes the data. Legacy declared
paths without saved understanding retain their existing declaration flow and these
execution safeguards. Relationship revocation blocks new use, while authorized
historical receipts retain their original source/definition versions.

## API and persistence

Let `root` be `/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}`.

| Endpoint | Contract |
| --- | --- |
| `GET {root}/understanding` | Current proposal/definition, questions, state/version, relationship options, own preference, history metadata and edit capability |
| `POST {root}/understanding` | `revision_id`, `expected_version`, `state`, full `definition`; creates an immutable version, returns 201 |
| `GET /workspaces/{workspace_id}/datasets/{dataset_id}/understandings/{id}` | Inspect an authorized historical version |
| `POST /workspaces/{workspace_id}/datasets/{dataset_id}/preferences` | Set the current user's `domain_hint` and `goal` |

Start an edit from the GET response rather than inventing definition fields.
The server rejects missing/extra fields, invalid columns, unsupported rules and
stale edits. Definitions store up to 24 named metrics and 24 relationship reviews.
All identity, workspace and creator fields come from authenticated server context.
Foreign or revoked membership lookups return 404; unauthorized edits return 403;
stale revision/version writes return 409. Invalid definitions or unresolved meaning
return 422. Simultaneous edits serialize on the workspace lock; one stale writer
cannot overwrite another.

Migration **0009** adds `understandings` and `data_preferences` with scoped foreign
keys and per-dataset version uniqueness. Readiness requires 0009. Apply `make migrate`
before using the new API. It does not rewrite profiles, source objects or receipts.

New receipt sources include `understanding_id` only when confirmed meaning applies.
Replay loads that immutable version; changing or revoking today's definition does
not rewrite an earlier answer. Older receipts without the field still use their
original profile semantics. A revision or definition changing during model planning
causes clarification before execution. Unsafe historical joins now fail explicitly
if current executor checks detect possible amplification.

## Delivery boundary

This is the Phase 3A foundation. Unified data/document chat (3B), representation and
search benchmarks (3C), judge evaluation (3D), adaptive studies/connectors (Phase 4)
and production evidence (Phase 5) are separate remaining work. Personal goals are
stored here; they do not yet personalize dashboards or orchestrate an investigation.
No production gate is cleared by this implementation.
