> **File use case:** Evidence ledger for the October 2 upload-first usability release.
> **What it does:** Records actual checks, real-data failures, corrective work and deployed acceptance.

# Data partner verification — 2026-10-02

Scope: private-demo/local-test usability, not completion of Phase 4C–4E or production.
See [the gap audit and contracts](data-partner-reset.md).

## Delivered behavior

- Upload-first workspace with automatic personal workspace/file-named dataset and
  deliberate addition to an existing dataset; optional context remains optional.
- Immediate calculated ranges/averages and category counts, source evidence,
  practical questions and progressive disclosure of advanced forms/dashboards.
- Topic-specific metadata guidance, private clarification continuation, retained
  context through gratitude and tested Urdu/Roman Urdu planning.
- Stored CSV dialects and profile-v2 for new identifiers/calendar components,
  with historical profile-v1 and synthetic samples preserved.

## Local verification

The backend run before the concurrency repair passed **577 tests**, with one existing
warning and no skips, in 235.79 seconds. Sixty-five new regressions were added across:
`test_delimited_intake.py` (15), `test_discovery.py` (16),
`test_partner_conversation.py` (15), `test_profile_refresh_version.py` (2) and
`test_profile_v2.py` (17). Earlier September 30 precision/guidance regressions are
preserved in that total. The first concurrency repair adds eight cases in
`test_discovery_snapshot.py`: one snapshot per request, worker-thread I/O, deletion,
tampering, revision/definition changes and membership revocation before delivery.
That intermediate backend rerun passed 585 tests. Final release verification passed
**601 tests**, no skips, one existing warning, in 232.62 seconds. Added cancellation
audit (2), ASGI disconnect cleanup (6) and exact/bounded column transport (8) cases
bring this release to **89 new backend regressions**. Final log:
`data/vps-private/partner/backend-release-final.log`.

Ruff and strict mypy passed (113 files). TypeScript, ESLint, two frontend tests and
production builds passed. Fourteen real-service Chromium journeys passed, including
live mixed chat and superseded-request cancellation, followed by four final checks
after removing the
redundant suggestions request. Earlier chat-layout/category-label checks remain retained.
Screenshots were visually inspected at desktop/mobile sizes. Existing preparations,
meanings, studies, boards, refreshes, alerts and saved-answer flows remain covered.

## Public real data

Final live report: `data/realdata-evaluation/evaluation-20261002T043712Z.json`,
**24/24 checks passed** in 90.09 seconds, requiring every expected finding and
nonempty record pages. This counts evaluation cases, not model calls. Sources,
licenses, SHA-256 hashes, original archives and every failed report are retained in
ignored `data/realdata-evaluation/`.

- UCI Bank Marketing: original publisher-provided 4,521-row semicolon CSV.
- UCI Online Retail: first 10,000 original transaction rows in an XLSX subset,
  preserving negative quantities, whitespace and missing values. The full workbook
  exceeds current intake limits; this subset is not a representative scale benchmark.

Checks cover independent Decimal totals/averages/groups/filters, all automatic
finding receipts, missing/duplicate counts, column help, absent-field clarification,
filtered records → total → thanks → breakdown, and Urdu/Roman Urdu guidance topics.

Failures were investigated rather than removed: the first live run passed 18/24.
The banking day-of-month field and mixed retail invoice codes blocked record browsing;
versioned profiling fixed them. A later 23/24 result exposed reference-harness labels
that did not apply established executor whitespace normalization. The reference was
corrected explicitly, and both targeted and fresh full runs passed. Originals remain
unchanged; no source rows were omitted to make arithmetic checks pass.

## Deployment rehearsal and corrections

Source/image checkpoint: `releases/pre-partner-20261002/source`, image tags
`pre-partner-20261002`. Fresh checksummed database/object backup:
`backups/20261002T035155Z`. Readiness remains migration 0012. Initial activated
source matched 35/35 staged files and 17/17 installed API modules.

The first eight-user rehearsal stopped at a test selector requiring an exact label
where the established upload selector uses a partial accessible label. After correcting
that harness error, the real concurrent run passed only 2/8: repeated synchronous
source parsing delayed discovery and produced query timeouts. These failed reports
are retained. The release is not declared complete from those results.

The correction reuses one parsed snapshot per briefing and moves initial parsing
and final source verification off the async event loop. The final checksum read is
bracketed by permission/revision/definition checks. Queries retain ordinary receipts,
timeouts and authorization. Independent review found no regression; per-query database
authorization/persistence still uses synchronous calls and is not represented as fully
asynchronous. Final installed API hashes matched all 17 changed/new runtime modules.

The stricter next browser run still failed 0/8; direct eight-request isolation
showed only 4/8 complete bank briefings, with 37–85 second elapsed times and query
timeouts. This ruled out a browser-only cause. The retained evidence is
`eight-browsers-optimized.json` and `eight-api-diagnostic.log`. The browser now
debounces visible settled selections and cancels superseded requests;
the API stops abandoned work and retains failed query receipts. The chat panel no
longer calls the synchronous legacy suggestions endpoint on every intermediate file.
Fourteen browser journeys plus four final targeted checks passed after these repairs.

A minimal dependency comparison exposed a second cause: local optional data libraries
made DuckDB Python binding much faster than the clean deployed image. Ten thousand
integers took about 0.404 seconds repeatedly in a local DuckDB-only environment versus
0.0061 seconds after imports in the full development environment. VPS phase timing
measured roughly 1.6 seconds loading those values, while query execution was about
0.001 seconds. Merely switching to typed list parameters did not solve the VPS
concurrency failure. The final loader serializes already validated columns as bounded
JSON parameters
cast to explicit SQL array types. Decimal values use fixed-point strings; there is
no binary-float conversion or new dependency. This is internal transport, not JSON
file intake. The existing 500-row/20,000-cell batch limits and 15-second query timeout
remain unchanged. Eight concurrent synthetic executor sequences completed 56/56
queries on the VPS in 8.864 seconds, then 5.035 seconds with independent Decimal/count
references. This measures the executor, not full browser or model latency.
`loader-performance-evidence.json` and `minimal-loader-check.json` retain the methods.

Final browser report: `data/vps-private/partner/eight-browsers-release.json`, **8/8
passed**. Every browser displayed all seven bank findings and replayed every receipt
(56 replays total), completed quality chat and passed desktop/mobile layout. One user
also completed three live DeepSeek turns: total balance, retired records, then their
balance, followed by all seven retail findings. Rendered answers and nonempty record
pages were checked. The seven shorter complete journeys took 23.8–26.6 seconds; the
journey with live chat and retail took 54.5 seconds. These are whole-workflow timings,
not individual query latency or sustained-load capacity.

The final API/web build and clean import passed. Staged source matched 39/39 files;
17/17 installed API modules matched. Readiness, model service and refresh timer were
healthy, with no API error/timeout/restart evidence during the final rehearsal.

A final visual review found long exact averages wrapping across lines. A CSS-only
adjustment gives averages their own row, preserving the entire value. A Chromium
component fixture checked `1422.657819066578` at seven widths from 320 to 1440 pixels:
one line, no
value/page overflow. Evidence: `data/vps-private/partner/average-layout-check.json`.
The subsequent web-only build and deployed layout check are recorded in
`deployed-average-layout.json`. The full-page check also caught a 320-pixel control
overflow missed by the fixture; the narrow-screen correction is verified separately.
No API behavior changed after the full suite and eight-user acceptance.

## Commands

Implementation areas changed in this slice:

- Discovery domain/service/HTTP route, query loading and cancellation evidence.
- Profiling, parser protocol/adapter and source reconstruction in workspace,
  analytics, understanding, join and refresh services.
- Guidance, intent routing and private thread clarification context.
- Workspace page, discovery/chat panels, shared CSS and browser journeys.
- Nine new backend regression modules listed above, public-data evaluator and VPS
  browser script; roadmap, engineering handoff, README, architecture and demo runbook.

The pre-existing September 30 precision/guidance work was preserved. The complete
39-file code/test release manifest is in ignored
`data/vps-private/partner/source-manifest-delivered.json`; it excludes datasets and
credentials. Repository documentation is synchronized separately.

All integration commands used these disposable services, not the user's existing
applications. Containers were `execplus-partner-postgres` and `execplus-partner-minio`.

```bash
export EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus
export EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000
python3 -m pytest --tb=short
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
npm run lint:web
npm run typecheck:web
npm run test:web
npm run build:web
EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py
EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py --grep 'first file needs no setup|superseded discoveries|column meanings|combined data'
python3 scripts/evaluate_data_partner.py --live-model
node --check scripts/check_data_partner_vps.mjs
node scripts/check_data_partner_vps.mjs data/vps-private/sessions.json data/vps-private/partner/targets.json data/vps-private/partner/eight-browsers-release.json
make production-preflight
docker stop execplus-partner-postgres execplus-partner-minio
```

The production-preflight command intentionally fails with all eight gates blocked. No gate was
cleared, no provider changed, and no public port or production identity was added.
The final report path must be fresh; previous reports are not overwritten.

Remote commands, run under the existing authorized administrator connection:

```bash
cd /sdb-disk/OISOL_ExecPLUS/source
sudo -n bash deploy/vps/backup.sh
sudo -n docker compose -f deploy/vps/compose.yaml build api web
sudo -n docker compose -f deploy/vps/compose.yaml run --rm -T operator python -c 'import execplus.main'
sudo -n flock --timeout 45 /run/lock/execplus-maintenance.lock docker compose -f deploy/vps/compose.yaml up -d --no-deps api web
curl -fsS http://127.0.0.1:18401/health/ready
```

The first concurrency correction rebuilt only `api`; the final parameter-loader and
navigation release rebuilt both `api web`. The independent minimal-runtime check used
`python3 -S data/realdata-evaluation/minimal_json_loading.py`; its retained VPS companion
was passed on stdin to `sudo -n docker exec -i oisol-execplus-api-1 python -`.
The final average-layout correction used `build web` and `up -d --no-deps web` under
the same maintenance lock; it did not restart the API.
The deployed visual check used `node data/vps-private/partner/check-delivered-layout.mjs`.
Owned disposable local services were stopped after all tests; unrelated containers
and the private browser-access tunnel were left running.

Short-lived private sessions were renewed without exposing tokens. Attributed public
files are in the separate **Public banking and retail walkthrough** workspace, shared
with the eight demo identities. Existing user data and earlier private workspaces
were retained. Do not roll back to v1-only code over newly created v2 revisions.

## Remaining scope

Automatic findings inspect selected columns, not every possible pattern. Meanings
remain inferred until deliberately confirmed. Company terminology, causal/statistical
inference, unsupported formula combinations, automatic timestamp normalization,
large/multi-sheet formats and universal connectivity are not claimed. Forecasting,
exports and first connectors remain 4C–4E; advanced methods and production reviews
keep their existing phases. No commits, pushes or merges were made by this release.
