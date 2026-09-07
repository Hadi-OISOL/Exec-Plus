> **File use case:** Documents supported Phase 1 data preparation and its contracts.
> **What it does:** Explains profiles, quality, cleaning, sample versions, usage and local operation.

# Data preparation

Run `make migrate` and `make init-storage`, then `make api` and `make web` in
separate terminals. Sign in at `/workspace` using an operator-provisioned local
session. Existing workspace, invitation and upload instructions remain in
[week1-api.md](week1-api.md), including LAN configuration and alternate database ports.

1. Create or select a workspace. Owners and admins can invite teammates in Team.
2. Try a finance, sales or inventory sample, or create a dataset for your own file.
3. Upload a supported CSV or single-sheet XLSX. Its profile opens automatically.
   Select an older upload under **Profile upload** to inspect it.
4. Review the score, column suggestions, date ranges and quality explanations.
5. Choose cleaning options or map column names. **Preview changes** shows full-file
   counts and at most ten output rows. Editing options clears the previous preview.
6. **Apply reviewed changes** creates a revision. **Revision history and lineage**
   allows restoring the original or any earlier revision without deleting history.

This is a data preparation interface. KPI dashboards, business questions and
conversational analytics remain Phase 2 scope. Authentication currently supports
local/test opaque sessions only; production identity is a later deployment decision.

## Deterministic contract: profile-v1

The validated reader produces ordered strings, preserving CSV whitespace, leading
zero identifiers, header order and row order. XLSX empty cells become empty strings;
native dates become ISO dates, and non-midnight datetimes retain their ISO time.
Original bytes are never replaced. No model is called.

Types are inferred from trimmed values: empty, boolean (`true`/`false`), ISO calendar
date (`YYYY-MM-DD`), integer, decimal or text. Leading-zero numbers remain text;
non-finite numbers remain text. Numeric or boolean types need a strict majority
of nonempty values. A date/day header word or a majority of ISO date-shaped values
selects date. Ties and other heterogeneous text remain text; these conservative
suggestions do not authorize analytical queries. Ambiguous local date formats and
datetime values in date columns require correction in the source; the application
does not guess a locale or discard a time during cleaning.

Numeric columns are suggested metrics unless their names contain an identifier
word (`id`, `code`, `sku`, `zip`, `postal`); other columns are dimensions. Tags use
an explicit name vocabulary: revenue, sales, cost, amount, quantity, stock, price,
identifier and date. These are suggestions, not governed KPI definitions.

Profile metadata contains row/column counts, column names, suggested types/roles/tags,
nonempty distinct counts, missing/conflict/invalid-date counts and valid date ranges.
It does not persist example row values in PostgreSQL. Authorized previews return
row values only to the requesting workspace member with `Cache-Control: no-store`.

## Quality score

Let R be data rows, C be columns, and N = R × C. Five equally weighted checks give:

`score = 100 - 20 × (missing/N + duplicates/R + conflicts/N + invalid_dates/N + unsupported)`

The score is returned as a decimal string rounded half-up to two places.
Missing means whitespace-only or empty. Duplicates are exact full-row repetitions
beyond the first occurrence, in the current revision. Conflicts are nonempty values
that disagree with an inferred numeric/boolean type. Date columns count nonempty
values that are not valid ISO calendar dates as invalid dates; malformed ISO-shaped
values in other columns also count. A value can affect more than one check.
Unsupported structures are rejected by the parser before storage, so this component
is zero for a retained upload; rejected files do not get a misleading profile.
Each check returns its count, denominator and an actionable explanation.

Golden fixture: four rows, three columns, one missing cell, one duplicate row,
one numeric conflict and one invalid date score **90.00**. A score of 100 describes
these consistency checks and does not guarantee correct business data.

## Reversible recipes and storage

Migration `0002` adds `revisions`, `revision_heads`, `usage_events`, a composite
upload tenant key and optional `uploads.sample_id`. Original objects remain under
Week 1 workspace/dataset/upload keys. Existing uploads receive a root profile on
first profile access, once, under the workspace transaction lock.

Each immutable revision records actor/time, parent, source upload SHA-256, output
SHA-256, algorithm version, cumulative recipe and profile. The normalized output
checksum hashes UTF-8 JSON `[headers, rows]` with `ensure_ascii=False` and separators
`(',', ':')`. Recipes reconstruct output from the retained original; no customer
row data or derived row tables are stored in PostgreSQL. Derived object copies are
unnecessary for this bounded Phase 1 workflow.

One step maps selected header names, optionally trims cells, removes incomplete
rows, then removes exact duplicates while keeping first-occurrence order. Mapping
uses existing source names and unique printable output names of 1–100 characters.
The original header remains unchanged unless mapped. Removing all rows is rejected.
A recipe has at most 20 steps; restoring an earlier revision permits a new branch.
Future algorithms must retain the v1 reader/recipe contract or introduce a new
version with a compatibility path; unknown versions fail closed.

Preview and apply both reconstruct and verify the original checksum and current
output checksum. Apply writes the revision, active pointer, audit and usage in one
PostgreSQL transaction. Every apply/restore supplies `expected_revision_id`; stale
edits return 409. Restore verifies the selected revision before switching the
pointer. Cross-workspace and cross-upload revision references fail before file reads.
Upload/sample failures compensate object writes and roll back metadata. Crash-time
orphan reconciliation remains the deployment-hardening limitation documented in
ADR 0004, not a guarantee of distributed atomic commits.

Metadata profiling and recipe replay use bounded standard-library computation in
the domain. DuckDB remains the planned Phase 2 execution adapter for validated
analytical SQL; Phase 1 introduces no query planner or model-generated numbers.

## HTTP additions

All routes require a bearer session. Define
`P = /workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}`.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/samples` | Synthetic sample catalog and explicit versions |
| POST | `/workspaces/{workspace_id}/samples/{sample_id}` | Atomically create sample dataset, original, profile and events (201) |
| GET | `P/profile` | Active revision with profile; initialize older upload if needed |
| GET | `P/revisions` | Immutable scoped revision history |
| POST | `P/cleaning/preview` | Reconstructed preview, full profile, removed count, at most 10 rows |
| POST | `P/cleaning/apply` | Persist a new revision (201) |
| POST | `P/restore` | Select an existing revision without deleting history |
| GET | `/workspaces/{workspace_id}/usage` | Owner/admin current seat/upload/storage snapshot and usage events |

Cleaning JSON: `expected_revision_id` (UUID), `trim`, `drop_duplicates`,
`drop_missing` (strict booleans, default false), `mapping` (source-to-output name
object, default empty). Unknown fields and invalid mappings return 422.
Restore JSON: `expected_revision_id`, `revision_id` (UUIDs). Missing or unauthorized
resources return 404; members cannot read manager usage (403). All members can
profile and prepare their workspace's data, matching Week 1 upload permissions.

## Samples and usage

`finance-v1`, `sales-v1`, `inventory-v1` generate entirely fictional CSVs in code.
Golden SHA-256 tests freeze each version's bytes. Changing a sample requires a new
version. No customer datasets, binary fixtures, credentials or generated exports
are committed. `sample_id` distinguishes imported samples from user files.

Usage events contain only ID, workspace, actor, fixed kind, integer quantity,
resource ID and timestamp. Kinds cover uploads, stored bytes, seat additions/removals,
seat-limit changes, profile creation, cleaning, restores and sample imports.
Events start at migration deployment; historical events are not invented. Current
seat/upload/storage totals are calculated from current metadata, including uploads
created before migration. Reserved seats are pending unexpired invitations only.
These are usage foundations, not billing-grade metering or Phase 3 usage analytics.

Browser acceptance uses `.next/browser` so its temporary Next.js server does not
share the local development server's lock. No test uses customer schemas or buckets.
