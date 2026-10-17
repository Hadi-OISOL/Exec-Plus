> **File use case:** Evidence for the two-phase synthetic workflow, recovery and evaluation changes.
> **What it does:** Records actual focused executions, corrected failures and the boundaries of local measurements.

# Local workflow verification

This slice is local only. No VPS, prior backup, real user file, provider call, external connector, production database, deployment or push was used. Existing Python/runtime dependencies were reused; no new dependency or license obligation was introduced.

## Delivered behavior

- `create_synthetic_workflow_kit.py` explicitly generates finance, sales, inventory, HR, company, dirty-data and precision/null fixtures, with independent decimal oracles and hashes. No automatic import or correction occurs.
- `rehearse_local_recovery.py` creates its own cached-image disposable services, seeds fictional authorized API workflows, validates bounded backup checksums, and restores new empty targets. Existing targets/evidence and unsafe object archive entries are refused.
- The existing recovery verifier now runs account and compute-admission authorization through transaction-local read-only snapshot repositories. It keeps account-disable and source-permission checks, removes only row locking inappropriate to the immutable isolated snapshot, and replays immutable executions without new usage charges. Application locking remains unchanged.
- `StructuredFileParser.parse_table` returns validated cells in the same request-local CSV/XLSX traversal. Analytics source reconstruction and replay use this optional capability; older parser ports retain the validated fallback. XLSX archive/security inspection remains mandatory. There is no shared data cache.
- A confirmed numeric measure named `unit` or `units`, with a declared fixed unit, no longer masquerades as a per-row unit-label column. Unconfirmed/unitless fields, actual currency labels and explicit unit-column mappings retain their existing safeguards.
- `two-phase-evaluation-cases.json` preserves all 32 prior cases and adds eight, for **40 cases / 112 exact checks**. The evaluator reports unique fixed checks by measurement dimension; it does not infer representative model accuracy.
- `benchmark_data_workflow.py` measures thirteen synthetic parser, export and API operations with retained fixture bytes, first/warm timing samples, serial throughput, source identity and qualified process-memory measurements.

## Focused executions

All evidence below is in ignored `data/verification/2026-10-17/two-phase/`. Counts overlap and must not be added as a distinct full-suite total.

| Evidence | Actual result | Scope |
| --- | --- | --- |
| `parser-focused.xml` | 65 passed, 2.78 seconds | New parser path, original parser validation, architecture |
| `fixture-kit.xml` | 5 passed | Explicit fictional generator, independent totals, edited-file preservation |
| `recovery-safety.xml` | 26 passed, 3.34 seconds | Recovery archive/target safety plus fixture generator |
| `benchmark-evaluation-unit.xml` | 11 passed, 0.50 seconds | Repeated bytes/timing arithmetic, evaluation failure/skip/missing/duplicate accounting |
| `roundtrip-recovery-final.xml` | 11 passed, 19.17 seconds | Four business-domain output journeys, unit semantics and read-only receipt replay |
| `recovery-readonly-final.xml` | 2 passed, 5.66 seconds | Real read-only PostgreSQL replay and disabled-native-account denial |
| `confirmed-units-final.xml` | 7 passed, 0.08 seconds | Confirmed quantities, unconfirmed/unitless guard, mixed/missing currency, explicit unit mapping, numeric currency-code guard |
| `recovery-attempt4/report.json` | Passed, 6.766 seconds | Actual fresh source → dump/object archive → fresh restore → read-only verification on schema 0027 |
| `recovery-native-attempt1/report.json` | Passed, 6.962 seconds | Expanded native-account source with nonempty new account/plan/operational tables, same fresh restore and read-only receipt checks |
| `offline-evaluation-phase1/summary.json` | 112/112 passed, 40 cases, zero skips; pytest 123.47 seconds | Fixed offline suite including all 89 earlier checks; runner 129.936 seconds |
| `standalone-benchmark-smoke.json` | Passed, 20.499 seconds | All thirteen operator-command operations in disposable services; concurrent smoke timings excluded from controlled comparisons |
| `finance-cleaning-roundtrip.xml` | 1 passed, 4.61 seconds | Strengthened 120-day dirty finance case through preview/apply, analysis/dashboard, saved evidence and all three exports |
| `recovery-denial-final.xml` | 2 passed, 3.79 seconds | Disabled native-account receipt and revoked-dataset receipt denial; read-only snapshot permissions remain enforced |

The actual restore checked **73 table fingerprints**, **three uploads**, **three revisions** and **three exact sum receipts**. Finance revenue 12,714, sales revenue 2,340 and HR salary 30,900 agree with independent expected totals. Source fingerprints remain unchanged and the restored database stays read-only. The three-object rehearsal contains no document/passages and no revoked-source receipt; those behaviors remain covered separately by existing focused recovery tests, including revoked-access denials. The new disabled-native-account test proves the snapshot adapter retains that boundary.

The expanded rehearsal uses a newly registered native account with the real local Demo assignment and saved private onboarding progress. Its checksums cover nonempty `local_accounts` (1), `onboarding_progress` (1), `workspace_plans` (1), `plan_admissions` (6), `incident_alert_policies` (1), `request_metrics` (3) and `request_metric_batches` (1). An independently provisioned fictional operator saves the alert policy. Observations come from actual synthetic HTTP calls, not invented failures. No password, hash, token or uploaded content appears in the report.

The four domain journeys compare query and dashboard results with saved studies, independently opened PDF/Excel/CSV evidence and private-export denials. Inventory deliberately filters to the last snapshot date. HR declares a total explicitly rather than assuming its default dashboard average should equal a sum. Reopening saved results and shared meanings must remain unchanged after export.

After the full fixed evaluation, its existing finance case was strengthened with an explicitly generated whitespace-dirty variant of the 120-day source. A read-only preview leaves the original revision intact, applying trim creates the predicted new checksum without removing rows, and the subsequent complete query/dashboard/study/export journey keeps original source bytes/checksum unchanged. That changed node passes separately; the final full gate exercises it again. The earlier 112-check execution is not silently described as having included the later cleaning assertions.

Ruff passes this slice's source/tests/scripts. Mypy passes the parser helper, parser, synthetic generator, recovery scripts, evaluator and benchmark. Full phase gates and final production-build results are owned by the main two-phase verification ledgers, not inferred from these focused checks.

## Retained failures and repairs

The first focused run retained **five failures / fourteen passes**. Fixture assertions initially assumed the PDF's heading capitalization, identical integer/decimal formatting, and HR's default aggregation. They were corrected to compare the actual declared calculation and exact numeric evidence. The sales failure also exposed the existing `units` name heuristic ignoring a confirmed numeric quantity; the narrow product fix and its positive/negative regressions are included.

The next run exposed a new plan-admission replay conflict. Reconstructed views had already been source-checked but omitted their `sources` field. The entitlement implementation restored that lineage to the replay view so exact source/parameter comparisons could succeed without waiving admission checks. Subsequent round trips and read-only receipt replay pass.

Recovery attempts 1 and 2 stopped during the fictional sales seed on the same unit clarification, before restore. Attempt 3 seeded/backed up/restored successfully, then stopped because the preliminary source authorization still requested `FOR SHARE` in read-only PostgreSQL. Both authorization and replay units of work now use the snapshot adapter; attempt 4 passes. Failed attempt directories and logs remain. None restored over an existing database, changed application production locking, or switched a restored database to writable verification.

After the expanded native rehearsal, a targeted compatibility review added the new `account_unavailable` code to the verifier's expected denial handling. A disabled-account receipt must fail with that same code on replay; other failures still fail verification. The real read-only regression and existing revoked-dataset check both pass. No actor is re-enabled and no denied result is returned.

## Controlled local performance comparison

The baseline and candidate use the **same retained bytes** for the 3,000-row CSV/XLSX fixtures, 300-row renderer input and forty-day forecast; the expected total remains **24,339.000** and the first forecast **4.1**. All thirteen operations pass their exact checks. Evidence: `baseline/before.json`, `after.json` and `performance-comparison.json`. Source hashes, fixture hashes and every timing sample remain in those artifacts.

Both measurements ran after our test/build/browser processes stopped, against the same dedicated local PostgreSQL/MinIO services. Python remains 3.12.14. Unrelated applications were left running; the one-minute host load differs (2.366 before, 1.206 after). Each entry has one first operation after imports and three warm repetitions. There is no operating-system cache flush, representative production workload or statistical acceptance claim.

| Operation | First milliseconds, before → after | Warm median milliseconds, before → after | Warm change |
| --- | ---: | ---: | ---: |
| parse_csv | 31.099 → 98.318 | 21.005 → 18.386 | -12.5% |
| parse_xlsx | 575.979 → 241.011 | 503.193 → 279.019 | -44.6% |
| export_pdf | 9.833 → 5.104 | 8.985 → 3.081 | -65.7% |
| export_xlsx | 61.930 → 55.925 | 53.718 → 66.057 | +23.0% |
| export_csv | 11.550 → 6.634 | 21.290 → 5.661 | -73.4% |
| api_ingestion_profile | 110.630 → 171.184 | 120.054 → 117.934 | -1.8% |
| api_profile_read | 16.005 → 13.815 | 17.491 → 15.990 | -8.6% |
| api_query | 319.506 → 370.720 | 89.821 → 90.743 | +1.0% |
| api_dashboard | 264.135 → 297.442 | 377.240 → 296.960 | -21.3% |
| api_forecast | 402.330 → 237.394 | 181.025 → 222.767 | +23.1% |
| api_export_pdf | 655.250 → 734.433 | 731.243 → 707.548 | -3.2% |
| api_export_xlsx | 914.890 → 648.667 | 732.032 → 727.061 | -0.7% |
| api_export_csv | 618.079 → 598.451 | 652.005 → 631.498 | -3.1% |

The XLSX bottleneck was measured as two `load_workbook`/row traversals during validation and reading. The candidate's optional combined parser returns the equivalent validated table in one traversal, preserving archive inspection and all invalid-file refusals. Its warm result falls from **503.193 to 279.019 ms** in this fixture. This comparison intentionally measures the former complete validated-read path against the new complete validated-read path, rather than timing an unvalidated read.

Results are mixed: warm forecast API and direct XLSX export are slower by approximately 23%, while dashboard and validated XLSX reading improve. The candidate also adds authorization, plan accounting, operational observations and report metadata. This short pair does not isolate every cause or establish a general speedup. Peak process high-water RSS is **310.215 → 309.926 MiB**, covering imports and prior operations, excluding container memory. The JSON derives serial operations/second from these medians; those are not concurrent capacity figures. Frontend bundle/build measurements and broader gates are recorded in the main Phase 1 ledger.

## Pending broader evidence and external gates

The full fixed evaluation reports 89/89 earlier behavioral checks, 9/9 numerical checks, 5/5 replay-consistency checks and 3/3 each for access control, source citation binding and selected unsupported outputs. These are counts on named synthetic fixtures, not general accuracy estimates. The controlled comparison is recorded above; final whole-repository regression is recorded after its actual completion. See [the local runbook](local-workflow-verification.md), [Phase 1](verification-codex-phase1.md), [Phase 2](verification-codex-phase2.md) and [the original 37 regression map](regression-original-37.md).

Off-server backup custody/retention, production restore, formal RTO/RPO, representative live-model quality and sustained production load remain unverified. No local result clears those gates.
