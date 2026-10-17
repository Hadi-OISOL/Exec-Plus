> **File use case:** Retains evidence for the October 17 local Phase 1 work.
> **What it does:** Separates baseline results, new behavior, regressions and outstanding acceptance checks.

# Phase 1 verification — local gate accepted

The Phase 1 local implementation gate is accepted within the recorded scope.
Private-VPS activation and Phase 2 remain separate unfinished work. See
[the implementation matrix](codex-two-phase-implementation.md) for authorized scope.
The acceptance runs use local synthetic data, with hosted models and external
delivery disabled. The later October 17 user instruction additionally authorizes
tested private-VPS releases by the primary session. Read-only service checks and
an isolated candidate build are now separate deployment preparation; the live
application has not been switched. No customer-data analysis, provider setup,
secret modification or push is part of these runs.

## Starting baseline

The immutable baseline is commit `d4db038`, schema **0024**. PostgreSQL and object
storage run locally with disposable synthetic schemas and buckets. The original
working-tree changes are preserved. Baseline evidence lives in ignored
`data/verification/2026-10-17/two-phase/baseline/`.

| Check | Current observation |
| --- | --- |
| Frontend unit tests | 59 pass |
| TypeScript / ESLint | Pass |
| Web production build | Pass; 29.944 seconds |
| Ruff / mypy | Pass; mypy checks 262 files |
| Full backend / architecture | **2,380 passed / 0 failed / 0 skipped / 1 warning**; pytest 1,481.91 seconds; JUnit retained |
| Offline browser | **68 passed / 4 failed / 3 explicit model-dependent skips**; 75 journeys; 801.278 seconds (805.905 including runner); no retries or flaky passes |

The completed initial browser run exposes four pre-existing failures:
`decisions.spec.ts:7` and `forecasts.spec.ts:20`, `:154`, `:351`. Three interactions call native
`selectOption` on the Radix Analysis focus button, and one expects a native
`option`. These tests were not migrated with the earlier dropdown change. The
backend baseline passes; corrected focused browser reruns will be recorded
before declaring acceptance. They are not new
Phase 1 regressions or passing checks. `browser.json`, `browser-summary.json`,
logs and error contexts retain the original results. The disposable browser
schema, object bucket and worker were cleaned up after this run.

Initial infrastructure attempts used an internal Docker network without published
ports and a shell without the project's Node executable on PATH. These harness
errors were corrected before the application runs; they are retained separately
from application failures. The complete baseline counts and durations are recorded above.

## Pre-change findings

- An additional fixed-input export probe produces different PDF, XLSX and ZIP
  bytes across identical generations. Evidence:
  `audit/export-determinism-before.json`. Existing baseline tests do not cover
  this requested reproducibility property.
- Current Excel output preserves exact data with text cells and typed evidence,
  but generic `Result N` tabs need a clearer summary and methodology structure.
- Native password accounts cannot safely inherit email-only invitation acceptance
  or operator session provisioning. Explicit account-bound invitation approval
  and a separate audited recovery path are required.
- Existing fixed-code incidents provide a useful foundation; denominator-aware
  request metrics, request correlation and configurable in-app alerts remain to
  be implemented and verified.
- Profiling confirms that the XLSX path opens and traverses the same workbook
  twice. A diagnostic 3,000-row probe retains identical CSV/XLSX values; its warm
  medians are 18.916 / 584.912 ms. These measurements ran alongside the baseline
  suites and are diagnostic only. A controlled before/after run remains required.
- The adapter has no pinned input tokenizer or verified provider invoice upper
  bound. Existing atomic reservations protect configured exposure, not an
  unknown final charge. Bounded request/response bytes will strengthen resource
  controls without misrepresenting byte counts as billable tokens.

## Implemented increments — focused verification in progress

- Export renderers now reproduce PDF/XLSX/CSV bytes for the same complete input
  and timestamp. Excel includes a summary, meaningful unique table sheets,
  methodology, exact typed evidence and a visible mapping. UTC labels match the
  actual timestamp. Existing permission checks and literal text cells remain.
- Schema 0025 adds local accounts, explicit account-bound invitation approval and
  private resumable guidance. Schema 0026 adds price-free local plan assignments
  and operation admissions. Their owned verification is being integrated.
- Schema 0027 extends the existing incident collector with fixed-category minute
  counts, duplicate-safe batches, request/job correlation and staff-only versioned
  alert settings. It exposes response-header latency, not full download duration.
  UI thresholds and known collection limitations remain visible.
- Repeated spreadsheet validation was consolidated within one authorized request;
  no shared customer-data cache was added. Controlled before/after evidence uses
  retained synthetic fixtures; measured mixed results are recorded in
  `docs/verification-local-workflow.md`.

The first root integration run passed **125 of 127** cases in **97.45 seconds**.
The two new failures were a PostgreSQL INSERT rowcount assumption (fixed using
RETURNING) and an incorrect test fixture property. The next run passed all **22
operational-metric cases** and four shared regression checks; one forecast creation
failed because an in-progress quota hook lacked an import. That import is corrected
and the regression is being rechecked. These overlapping counts are not additive.
A later selected-run command named a nonexistent sample test; collection stopped
without executing that run. Its log/XML remain separate from test failures.
Safe generic HTTP 500 responses replace raw exception propagation. Existing
rollback tests still inspect unchanged database/object state and now additionally
assert the internal exception message is absent from HTTP responses.

Artifacts: `phase1-root-focused.{log,xml}`, `phase1-root-recheck.{log,xml}`,
`phase1-root-final-focused.{log,xml}` (invalid selector), and the corrected run in
`phase1-root-corrected-focused.{log,xml}`, under the ignored evidence directory.

The corrected root selection passes **36 cases** in **31.76 seconds**, including
the actual **200,000-cell** Excel boundary, typed null/empty/date/precise-number
round-trip, the new metric paths and repaired historical rollback/migration
checks. A subsequent incident/architecture run passes **50 cases** in **23.59
seconds**, including a further actual commit-acknowledgement-loss regression for
collector overflow/recovery counters. Both initial failures remain retained.
Frontend TypeScript checks pass after owner/admin allowance wiring.

The final metrics selection passes **28 cases** in **6.38 seconds**, including
metrics-only graceful shutdown and stable retry-batch flushing. Independent review
found that lifecycle gap before the gate. Root inspected the desktop and mobile
incident captures; a narrow checkbox alignment correction is included in the
fresh browser gate.

The deterministic evaluation passes **112 exact checks across 40 declared cases**,
with no skips or failures, in **123.47 seconds**. These are synthetic offline
checks, not a model-quality percentage. The strengthened 120-day finance journey
passes upload, dirty-data profile, trim preview/apply, confirmed meaning, exact
query/dashboard, saved study, independent PDF/XLSX/CSV reading and private-export
denial while retaining original source bytes.

The disposable recovery rehearsal passes on schema **0027** in **6.962 seconds**:
73 table fingerprints agree and three native-owned saved receipts replay with
read-only verification. New account, onboarding, plan admissions and metrics rows
are present in the restored synthetic database. No live backup or target is used.

Independent export review also found that an oversized methodology paragraph could
fail after openpyxl created temporary source XML. Metadata is now validated before
workbook creation; long valid paragraphs use ordered numbered cells, and a finally
block cleans only this workbook’s temporary writers on any failure. All **27 export
checks pass in 17.21 seconds**, including failure injection, full Unicode paragraph
reassembly and the 200,000-cell boundary. No dependency was added.

Full Ruff passes. Full mypy passes **285 source files** after correcting a reused
variable with incompatible SQLAlchemy row types. The initial typing failure and
shared import/format failures remain in the pre-gate logs. Unrelated existing
format-only differences are preserved; no claim is made that the entire repository
was reformatted.

## Phase 1 gate

Focused implementation is in place. All **59 frontend unit tests** pass; final
lint, TypeScript and production build pass (build **12.752 seconds**). The earlier
guide-effect lint failure is retained. Generated JavaScript across all static
chunks is 1,917,807 raw / 596,934 gzip bytes, versus 1,884,027 / 586,746 at baseline;
this is not a per-route network transfer measurement. Controlled performance
results and their mixed outcomes are in [the workflow ledger](verification-local-workflow.md).

The IDE interruption stopped the initial full backend and browser runs before
their result reports. They are retained and not counted as complete passes. A
fresh immutable backend run and a fresh full browser run have now finished. The first
browser restart found orphaned synthetic servers; their identity was checked
before stopping them, and that failed startup remains in the runner evidence.

The resumed backend run exposed historical-schema snapshot tests selecting a
new column after downgrade, and two old HTTP mocks that did not intercept the new
bounded streaming adapter. The test-only repairs preserve original row comparisons,
seven-attempt retry budgets and one-attempt cancellation. All ten related migration
cases and both HTTP cases pass focused rechecks. The complete initial failure run
is retained separately from passing repaired executions; no single clean full-suite
claim is made.
Two parser-instrumentation tests also still wrapped the old double-parse entrypoint.
They now observe the shared `parse_table` entrypoint while retaining their worker-thread,
exact-result and query-count assertions. Both complete files pass **44 cases in
44.56 seconds**. Another frozen failure uses a PDF cancellation fake with no unit
of work, which now stops at the new entitlement preflight. The explicit fake unit
of work records the admission and preserves all cancellation/slot assertions;
all **nine PDF tests pass in 21.58 seconds**. The full run finished **2,571 passed / nine failed / zero errors / zero skips**
across **2,580 cases**, in **2,308.27 seconds** (JUnit: 2,308.196). All nine
failures are the four historical-schema snapshot cases, two HTTP mocks, two parser
instrumentation cases and the PDF fake described here. Every failed node has a
passing focused execution. Collected and executed per-file counts agree. All **37 original requirement mappings pass**. Five generated XLSX parameter
IDs differ only because their ZIP/core timestamps changed. The same parser test
source hash appears in baseline, frozen execution and current source; every
uncompressed workbook member agrees byte-for-byte after replacing only the two
core-property timestamp texts. A narrow independently revalidated alias manifest
records both exact node IDs and fixture hashes, without altering any test result. The vanished parent
wrapper has no observed exit code; complete pytest log/JUnit and unchanged frozen
source hashes are retained instead. No application change was needed
for these identified test-contract repairs.

The fresh complete browser run finished with **74 passed / two failed expectations /
three explicit model-dependent skips** in **1,087.573 seconds**, without retries.
The two expectations assumed sign-in completed before protected reads finished and
that exported worksheets still had the old generic names. Corrected complete
operations/export files pass **five cases in 88.411 seconds**. Together these runs
cover **76 distinct passing offline journeys**, with the three skips retained;
this is combined coverage, not one clean full run. The four original baseline
Radix interaction failures have passing executions in the fresh full run.
The backend gate and failure accounting are now complete. The accepted result
is **2,580 distinct cases with passing latest executions**, with nine original
failures retained and no additional focused-only cases. This is combined coverage,
not one clean full run. The final reconciliation checks every collected file count
and every original requirement node; eight negative verifier self-checks also pass.
Evidence: `phase1-gate-reconciliation-final.json`, `phase1-xlsx-node-aliases.json`
and `xlsx-node-alias-selfcheck.json`. Phase 2 may proceed from the reviewed checkpoint.

## Private-release preparation and connector coordination

The VPS Compose command overrides the image command. It now explicitly includes
`--no-proxy-headers`, matching the native account throttle's direct peer boundary.
A content-free local Uvicorn probe confirms a forged forwarded address changes
the unprotected control's peer but leaves the protected command at `127.0.0.1`.
SSH-tunnel users still share loopback peer limits; this is not distributed abuse
protection. This Compose-only correction has separate evidence from the immutable
backend run, which was already underway.

An isolated candidate source archive excludes Git metadata, local datasets,
credentials and generated reports. Candidate builds do not switch live image
tags, source, schema or services. Original-column migration fingerprints have
five passing synthetic checks, including changed values, missing fields and the
new nullable occurrence field. An initial SQL ordering error is retained. A
future activation must preserve the old projection, check all 23 new tables and
use an explicit `0027` target. After new records are written, repair forward;
never restore an old backup over newly saved work.

The separately requested connector merge stays in an isolated worktree. Its
reserved chain is `0027 → 0028 → 0029`; existing `0025–0027` are not reparented.
The shared core files remain frozen while the two sessions coordinate through
ignored `data/agent-memory/connector-merge-coordination.json`. Connector-session
test reports are not acceptance evidence for the combined application.

The candidate images build successfully on the VPS without replacing running
services. Network-disabled, read-only, non-root image checks pass existing compute
methods plus password hashing and exact PDF/XLSX/CSV/PNG rendering. An initial image
checker incorrectly imported the development-only PDF reader; the corrected checker
uses that reader locally, without adding it to the runtime image.

A separate release checker passes against the isolated application in **18.42
seconds**. It creates two fictional native accounts, checks private Demo allowances,
onboarding version conflicts, upload/cleaning/confirmed meaning, exact query/dashboard/
study, independently parsed exports, cross-account denials and password rotation.
Both synthetic accounts are disabled afterward; their saved audit history remains.
Its two retained initial harness failures used the VPS origin against the local
origin guard and incorrectly expected separate downloads with different generation
timestamps to have identical bytes. Complete-input/timestamp reproducibility is
verified separately; repeated HTTP downloads retain exact identical table evidence.
This checker has **not run against the live application** yet.

## External limitations

Mailbox verification and emailed password recovery remain unavailable. Local plan
assignment is not billing. Estimated model cost is not invoiced spending. Local
restore, workload and offline evaluation cannot establish production recovery,
security, capacity or live-provider quality. All existing production gates remain
blocked unless independently supported by authorized evidence; this work does
not provide such external evidence.

### Final local evidence supplements

The native signup/resume browser journey now also finishes the guide through the
real UI, signs out/in, and reopens its saved finished state. Explicitly skipped
recommendations remain `observed=false`; completion does not invent activity.
The extended existing journey passes in **22.949 seconds**, with no retries or
page errors; targeted ESLint also passes. This overlaps the 76 distinct browser
journeys above, rather than adding a new independent journey. Evidence:
`phase1-onboarding-finish/browser.json`.

A separate disposable-schema benchmark measures nine newly introduced account,
onboarding, allowance and incident APIs: **36 timed requests**, one first request
and three warm requests each, with exact/version/privacy assertions. Warm medians
are 679.824 ms for registration, 581.862 ms for login, 9.460 / 24.682 ms for guide
read/write, 34.574 ms for owner allowances, 25.641 / 12.660 ms for administrator
plan assignment/read, 14.890 ms for alert settings and 13.073 ms for incident/metric
reads. The fixture passes in 11.15 seconds including setup/teardown.

Process RSS changes from 252.781 to 255.875 MiB; the final process-wide high-water
reading is 380.887 MiB. These are TestClient timings with real disposable SQL/object
services on a shared host, not network/browser/TLS latency or concurrent capacity.
First request does not mean OS-cold startup. New routes have no pre-change timings,
so no speedup is claimed. Fictional metric observations are explicitly seeded.
All application/migration hashes agree before and after. Reusable local harness:
`data/verification/2026-10-17/two-phase/benchmark_modified_apis.py`; measurements,
log, JUnit and reproduction command are in `modified-api-benchmark-attempt1.*` and
`modified-api-benchmark-summary.md`. This is supplementary performance evidence,
not an extra full-suite pass.

### Accepted boundary and release preparation

All requested independent Phase 1 increments have local implementation and
verification evidence. Existing providers, customer data and production gates were
not used to fill gaps. Verified-email reset, provider invoice accuracy, independent
security/privacy review, off-site custody and production recovery/load acceptance
remain open as documented in the feature matrix. The current private VPS remains
on schema **0020**; locally accepted schema **0027** is not yet active.

The private release checker now attempts cleanup of every synthetic account even
when one cleanup fails, retains the original journey error and writes only account
IDs/status to its private report. Its full synthetic journey plus injected cleanup
failure pass **two tests in 13.766 seconds**. The activation helper now keeps
storage stopped until database and original object-file content/path/size checks
pass. The aggregate object verifier passes **12 tests in 0.275 seconds**, including
mutation, symlink/FIFO refusal and archive/checksum round-trip. Shell syntax and
Python compilation pass. These checks validate local helpers; the full activation
script remains unexecuted. Evidence: `release-helper-repair-manifest.json`.
