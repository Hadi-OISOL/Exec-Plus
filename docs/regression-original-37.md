> **File use case:** Regression traceability for the 37 requirements completed in the historical October 13 report.
> **What it does:** Separates fresh pre-change evidence from post-change acceptance and preserves observed failures.

# Original 37 requirement regression report

The original source baseline is **d4db038**. Fresh verification uses an immutable Git archive, disposable local PostgreSQL schemas and object buckets, fictional data, and disabled model/email/vector providers. No VPS, production data, secrets, deployment or push participated.

Backend baseline: **2,380 passed / 0 failures / 0 skips**, one deprecation warning, pytest **1,481.91 seconds** (runner 1,512.898 seconds). Frontend: **59 passed**, with TypeScript, ESLint, Ruff, mypy (262 files), and the production web build passing.

The full browser baseline has **68 passes / four existing failures / three explicit model-only skips**, over 75 journeys in 801.278 seconds (runner 805.905 seconds). The four failures are in `decisions.spec.ts:7` and `forecasts.spec.ts:20`, `:154`, `:351`: those journeys still use native select/option actions after the earlier Radix replacement. They stop at that interaction; their later behavior is not counted as verified. Their original logs and error contexts remain retained. Post-change browser and feature gates are recorded in the two phase verification ledgers.

Phase 1 local acceptance is recorded in `data/verification/2026-10-17/two-phase/phase1-gate-reconciliation-final.json`: **2,580 collected cases / 2,580 latest passing executions**, with matching per-file collection counts and no unresolved nodes. The original full run retains **2,571 passes / nine failures** in 2,308.27 seconds; focused test-harness repairs supply the later passing executions. This is combined coverage, not one clean full run. All 885 frozen source files still match their manifest. The vanished wrapper has no recoverable exit status; final JUnit and pytest output provide the result.

All **37 original requirements** have their mapped baseline nodes covered by passing Phase 1 executions. Five generated-XLSX parameter IDs changed only because their ZIP metadata timestamps changed; reviewed aliases require identical uncompressed fixture bytes and the same test/parameter identity. The alias evidence is `phase1-xlsx-node-aliases.json`. No missing test was silently counted as passed. This Phase 1 local 0027 acceptance does not deploy the candidate or change live 0020.

Phase 2 backend acceptance is recorded in `data/verification/2026-10-17/two-phase/phase2-gate-reconciliation-final.json`. The immutable full run passes **2,932 tests / 0 failures / 0 errors / 0 skips**, with one retained warning, in pytest **2,333.55 seconds** (JUnit 2,333.522 seconds; producer runner 2,365.979 seconds). The producer completed with exit code **0** and wrote `phase2-backend/backend-run.json`. All **974 frozen files** match their source manifest.

The final current-source reconciliation accounts for **2,937 distinct cases with latest passing executions**, matching exact frozen/current collected nodes and per-file counts. Two services were repaired after the immutable snapshot: query-receipt export and scoped customer study/dashboard delivery now recheck sharing inside their final transaction. Their two test files add five cases. These are the only four approved backend source/test deltas; the final 56-case export and 61-case integration runs supply explicit supplemental evidence. This is full-plus-focused coverage, **not one clean 2,937-case run**. All four original failing security reproductions remain in the reconciliation history; none remains unresolved.

All **37 original requirements** have every mapped baseline node covered by a passing Phase 2 execution. Five baseline XLSX parameter aliases are proven in `phase2-gate-tools/phase2-xlsx-node-aliases.json`. Exact collection comparison additionally proves eight known generated-XLSX aliases for each collected snapshot: those five parser parameters and three validated-table parameters. Test source hashes, ZIP integrity and all uncompressed member bytes agree, apart from the explicitly recorded creation/modification timestamps. No test status or arbitrary parameter name is normalized. There are no missing/unexpected executed nodes or skipped tests. The strict verifier's twenty checks use temporary evidence copies and add zero application passes.

Reconciliation SHA256: `415198a11a4d6cf350001ebd1f77de51092f4786b00796906ec05c46804e59ef`. Primary JUnit SHA256: `2b822854ad1113fe09e4345cfddeb4f3fb06bd7b893a7078360159d51737f7b9`. This proves the stated local backend regression scope; frontend/build/browser acceptance, deployment and production gates remain separately recorded in the two phase and release ledgers.

The table maps passing backend nodes only. Counts overlap between requirements and must never be added. The exact node IDs, not merely file names, are retained in `data/verification/2026-10-17/two-phase/baseline/original-37-regression-map.json`. Existing functional limits, private ownership, synthetic-provider scope and production gates remain in force.

| Original ID | Requirement | Baseline backend nodes | Phase 1 mapped nodes | Phase 2 final |
| --- | --- | ---: | --- | --- |
| 2 | Organization and user workspace | 25 passed | All mapped nodes pass | 25 mapped nodes pass |
| 3 | Excel and CSV upload | 57 passed | All mapped nodes pass | 57 mapped nodes pass |
| 4 | Automated column identification | 48 passed | All mapped nodes pass | 48 mapped nodes pass |
| 5 | Data-quality validation | 47 passed | All mapped nodes pass | 47 mapped nodes pass |
| 6 | Basic data cleaning and mapping | 18 passed | All mapped nodes pass | 18 mapped nodes pass |
| 7 | Descriptive dashboards | 19 passed | All mapped nodes pass | 19 mapped nodes pass |
| 8 | KPI cards and trend analysis | 19 passed | All mapped nodes pass | 19 mapped nodes pass |
| 9 | Natural-language questions | 124 passed | All mapped nodes pass | 124 mapped nodes pass |
| 10 | AI-generated management summaries | 23 passed | All mapped nodes pass | 23 mapped nodes pass |
| 11 | Filters and drill-down | 19 passed | All mapped nodes pass | 19 mapped nodes pass |
| 12 | Save and share analysis | 4 passed | All mapped nodes pass | 4 mapped nodes pass |
| 16 | Customer feedback mechanism | 17 passed | All mapped nodes pass | 17 mapped nodes pass |
| 17 | Finance, sales and inventory templates | 24 passed | All mapped nodes pass | 24 mapped nodes pass |
| 18 | Guided data-upload wizard | 39 passed | All mapped nodes pass | 39 mapped nodes pass |
| 19 | Sample datasets | 49 passed | All mapped nodes pass | 49 mapped nodes pass |
| 20 | Automated dashboard recommendations | 44 passed | All mapped nodes pass | 44 mapped nodes pass |
| 21 | Finance, sales, inventory and HR KPI libraries | 26 passed | All mapped nodes pass | 26 mapped nodes pass |
| 22 | Data-quality score | 49 passed | All mapped nodes pass | 49 mapped nodes pass |
| 23 | Saved questions and prompts | 4 passed | All mapped nodes pass | 4 mapped nodes pass |
| 25 | Team invitations | 21 passed | All mapped nodes pass | 21 mapped nodes pass |
| 26 | Customer usage analytics | 21 passed | All mapped nodes pass | 21 mapped nodes pass |
| 27 | In-app onboarding | 17 passed | All mapped nodes pass | 17 mapped nodes pass |
| 29 | Role-based access | 46 passed | All mapped nodes pass | 46 mapped nodes pass |
| 30 | Multiple workspaces | 46 passed | All mapped nodes pass | 46 mapped nodes pass |
| 31 | Department dashboards | 25 passed | All mapped nodes pass | 25 mapped nodes pass |
| 32 | KPI alerts | 41 passed | All mapped nodes pass | 41 mapped nodes pass |
| 34 | Basic time-series forecasting | 56 passed | All mapped nodes pass | 56 mapped nodes pass |
| 35 | Forecast accuracy measurement | 56 passed | All mapped nodes pass | 56 mapped nodes pass |
| 36 | Comparison between actual and forecast | 56 passed | All mapped nodes pass | 56 mapped nodes pass |
| 37 | Scheduled data refresh | 41 passed | All mapped nodes pass | 41 mapped nodes pass |
| 38 | Management commentary | 56 passed | All mapped nodes pass | 56 mapped nodes pass |
| 39 | Audit history | 25 passed | All mapped nodes pass | 25 mapped nodes pass |
| 41 | Customer-data isolation | 172 passed | All mapped nodes pass | 172 mapped nodes pass |
| 48 | Admin console | 26 passed | All mapped nodes pass | 26 mapped nodes pass |
| 49 | Customer-support workflow | 32 passed | All mapped nodes pass | 32 mapped nodes pass |
| 51 | Product usage and retention reporting | 30 passed | All mapped nodes pass | 30 mapped nodes pass |
| 60 | Recommendation approval workflow | 24 passed | All mapped nodes pass | 24 mapped nodes pass |

The fresh baseline retained two verification setup failures before any applicable tests ran: Docker internal-network port publishing was unavailable, and npm was absent from the default PATH. Only empty task-owned containers and the isolated runner PATH were corrected. These are separate from the four existing browser failures.

An elapsed-time observation changed from about sixteen minutes to over one hour during the backend run. The original process ID, kernel start tick, command and immutable working directory were confirmed unchanged; no cause is asserted. The measured pytest and runner monotonic timings above are retained as emitted.

A controlled first-operation/warm benchmark ran after the baseline test/build/browser processes stopped. It passes ingestion/profile/query/dashboard/forecast and PDF/XLSX/CSV checks with independent exact totals and saved synthetic bytes. `baseline/before.json` records timings, fixture hashes, code hashes and limitations. Other host applications were left untouched; this is not production-scale acceptance.

Post-change evidence: [Phase 1](verification-codex-phase1.md), [Phase 2](verification-codex-phase2.md). Both backend columns reflect their accepted exact-node reconciliations. Counts overlap by requirement and do not establish customer-model quality, UI acceptance or deployment. Absence of a result is not a pass.

The first frozen Phase 1 backend run was interrupted when the editor closed.
Its partial log and source manifest remain in `phase1-backend/`; there is no final
JUnit report, so its progress is not counted as a completed pass. On resuming,
all retained backend, test, migration and script hashes matched both the frozen
snapshot and the working tree. A fresh complete run started in
`phase1-backend-resumed/` against a separate immutable snapshot and the same
task-owned synthetic services. Its final JUnit and all 37 mappings are now reconciled
as described above. The interrupted run remains excluded from completed coverage.

The resumed frozen run exposed stale test-harness assumptions. The shared
historical migration snapshot helper selected the new nullable
`incident_occurrences.code` column after downgrading below the migration that
adds it. The repaired helper inspects the historical columns, requires absent
current-schema columns to be nullable, and compares all retained rows with those
absent values represented as null. All **10 affected migration tests pass** in
37.07 seconds (`phase1-migration-snapshot-recheck.xml`).

Two conversation-job tests intercepted `AsyncClient.post`, while the bounded
provider transport now uses streaming. Their fake reserved test hostname was
therefore no longer intercepted. Both now use in-memory `httpx.MockTransport`
and retain the exact seven-attempt budget and one-attempt cancellation checks.
Both pass in **6.83 seconds** (`phase1-job-transport-recheck.xml`). A redundant
reproduction was interrupted after identifying the obsolete mock; its log is
retained and is not counted as a completed test execution. These are test-only
repairs; the original frozen run remains unchanged and its failures will remain
in the final verification record.

The resumed frozen gate also exposed two obsolete parser instrumentation hooks and one
isolated PDF render-slot harness. The production parser now uses `parse_table`; the
updated tests still require one parse and no event-loop I/O. The render-slot test now
supplies an explicit fake metering transaction while preserving cancellation, busy
rejection and slot-release assertions. Rechecks: 44 parser/forecast cases and all nine
PDF export cases pass. Initial failures remain in the resumed gate and retained
reproduction logs. These are test-only repairs; the application candidate is unchanged.
