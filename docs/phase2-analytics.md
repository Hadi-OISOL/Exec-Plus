> **File use case:** Public contract and operating guide for verified analytics.
> **What it does:** Describes supported Phase 2 queries, evidence, sharing and numerical limits.

# Verified analytics

The teammate's Phase 2 commit is `7d70cd7`. The audit and corrections are recorded in
[verification-phase2.md](verification-phase2.md). All routes require the local/test
session bearer token and current workspace membership. Threads additionally belong
to their creator; saved items are private unless explicitly shared.

For an uploaded file, use `/workspaces/{wid}/datasets/{did}/uploads/{uid}` as `root`:

| Method and suffix | Contract |
| --- | --- |
| GET `/schema` | Authorized column names, types, roles and semantic tags |
| GET `/kpis`, `/dashboard-templates`, `/suggested-questions` | Deterministic recommendations |
| POST `/query` | `metric`, `aggregation`, optional `group_by`, `filters` |
| POST `/dashboard` | Optional filters and compatible `template_id` |
| POST `/rows` | Optional filters and limit, at most 1,000 rows |
| POST `/ask` | Natural-language `question`; requires a configured model |
| POST `/dashboard/summary` | Model selects executed statements; returns text and evidence IDs |
| POST `/threads` | Starts an owner-private conversation |
| GET/POST `/saved-items` | List or create question, prompt, dashboard or analysis |

A filter has `column`, `operator` (`eq`, `ieq`, `ne`, `lt`, `lte`, `gt`, `gte`) and `value`.
`ieq` compares text case-insensitively. Natural-language requests also support
bounded record results and server-rendered dataset guidance; see
[the conversational explorer](conversational-explorer.md). Row responses add
`matched_records`; `records_analyzed` continues to count source rows examined.
Decimal and large integer filters should use decimal strings to avoid JavaScript
rounding. Unknown columns, competing mappings, unsupported SQL and non-finite
numbers are refused. Aggregate operations are SUM, AVG, COUNT, MIN and MAX.

Additional workspace routes:

- GET `/queries/{query_id}` reads lineage; POST `/queries/{query_id}/replay`
  reconstructs the recorded upload revision and verifies the result checksum.
- POST `/threads/{thread_id}/ask` resolves follow-ups from structured prior lineage.
  A changed source revision requires a new conversation.
- GET/DELETE `/saved-items/{item_id}` enforces visibility and deletion permissions.
  POST `/saved-items/{item_id}/run` executes its configuration or replays its analysis.
- Join-path routes support a declared inner equality join between two authorized
  datasets. The right key must be unique after type conversion to prevent fan-out.

Saved questions use either `{ "question": "…" }` or a structured query payload;
prompts use a question; dashboards use dashboard parameters; analyses use
`{ "query_id": "…" }`. The saved item has `name`, `kind`, `payload`, optional
`description`, and `shared` (default false). `/workspace?workspace={wid}&saved={id}`
requires sign-in and membership. Questions/dashboard configurations use the current
revision; analyses replay the original revision. Sharing never makes a public link.

## Numerical and audit contract

- Decimal inputs use DECIMAL(38,12); values outside that range/scale are rejected.
  AVG is reconstructed from exact SUM and COUNT, rounded half-even to 12 decimal
  places. No business result passes through binary floating-point arithmetic.
- Decimal results and integers outside JavaScript's safe integer range are JSON
  strings. Chart coordinates may be approximate; displayed values retain the
  returned strings. Integers inside the safe range remain JSON numbers.
- Each new execution records source/upload/revision IDs and checksums, typed bound
  parameters, SQL, route, outcome and result checksum. Aggregate result evidence
  is retained; raw drill-down rows are reconstructed rather than copied into receipts.
- Summary text, evidence IDs and model route are attached to the source execution.
  General audit events contain identifiers/actions, not source values or prompts.
- Migration 0006 is additive. Historical executions without receipts cannot be
  replayed reliably and return a clear conflict; the system does not invent them.
  Downgrade below 0006 refuses while saved analyses exist.
- Profile-v1 reconstruction remains unchanged. HR hints are derived by the semantic
  view without mutating historical profiles. The library has eight simple governed
  aggregations across finance, sales, inventory and HR, not composite ratios.

The query adapter parses an allowlisted AST, disables external access/extension
loading, enforces tenant scope and bounded results, and interrupts timed-out work.
Timeout cleanup drains the worker before releasing the connection. In-memory
loading is included in this cooperative timeout; it is not a hard OS process kill.

After pulling: run `make install`, start infrastructure, run `make migrate`, then
restart `make api` and `make web`. Model-independent dashboards and structured queries
work with `EXECPLUS_LLM_MODE=disabled`; natural-language planning and AI selection
summaries return a configuration error until an operator configures a model.
