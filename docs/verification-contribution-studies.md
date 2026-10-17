> **File use case:** Local verification ledger for requirement 33 contribution studies.
> **What it does:** Records real commands, evidence, limitations and remaining checks.

# Contribution study verification

Subsequent combined local acceptance is recorded in [Phase 2 verification](verification-codex-phase2.md).
The separately authorized [private release](verification-codex-private-release.md)
does not change the local-only scope of the focused executions below.

Status: backend and browser implementation with focused verification complete on top of accepted
Phase 1 and connector checkpoint `142a7dd`. Local synthetic data only; no provider,
customer data, VPS, deployment, schema or dependency change. The full Phase 2
regression gate is owned by the coordinated release workflow.

## Delivered behavior

- Explicit same-file nonoverlapping date windows and mapped two-file comparisons.
- Exact signed category changes, missing/absent distinction, immutable source
  receipts, matched-cohort volume/mix/unit-revenue decomposition and entries/exits.
- Existing private studies, deliberate sharing, version history, six-pin boards,
  PDF/Excel/CSV-evidence/PNG exports and source-based processing admissions.
- Server-side row/column policies before computation, both-source authorization
  for list/open/replay/artifacts/boards/downloads, final publication/source checks
  and unavailable provisional query receipts.
- A real Radix form, visible totals/chart, exact component and coverage tables,
  filtered supporting records and ordinary dashboard/sharing controls.
- Successful saves survive a subsequent list-read error; recovery repeats only
  the read and blocks another creation until the list has reloaded.

## Evidence and initial failures

Ignored run evidence is under
`data/verification/2026-10-17/two-phase/contributions/`.

- `domain-initial.xml`: 18 numerical/request cases passed in 0.12 seconds.
  Independent examples cover net115 with volume75, mix−75, unit-revenue65,
  entry80 and exit−30; nonterminating components4/3,1/6,3/2 sum exactly to3.
- `integration-initial.xml`: one test-harness failure: query ID is inside the
  response's lineage, not a top-level result field. No application defect claimed.
- `integration-recheck.xml`:8 passes,2 harness failures: wrong lineage URL and
  nested HTTP client in the async executor callback. Corrected to the actual
  route and a direct understanding-service mutation.
- `integration-recheck2.xml`:9 passes,1 harness failure: a comparison projection
  artifact belongs to the comparison dataset, not the baseline dataset.
- `sharing-recheck.xml`: existing artifact full-access guard returns403 for a
  row-restricted actor; the assertion expected404. Final assertion accepts either
  access denial and requires absence of result rows. This did not weaken a guard.
- `security-initial.xml`:14 passes,1 intentionally deselected pending that
  assertion correction,54.61 seconds. The cases cover real four-format exports,
  exact replay, restricted records, unpublished receipts, tampered calculations,
  current-source changes, unshare-during-replay, secondary-policy change during
  rendering, cross-workspace input and immutable dataset reruns.
- `backend-regression.xml`:125 passes,1 retained assertion failure in224.11
  seconds. This includes existing descriptive studies, artifacts, restricted
  analysis and portable export regression tests. `sharing-final.xml` passes the
  corrected denial assertion in4.95 seconds, giving126 latest passing cases
  across those runs; this is combined coverage, not one clean full run.
- `backend-final.xml`:35 passes (17 API/integration cases and18 numerical/request
  cases),44.94 seconds, no failures/skips. This adds an explicit empty filtered
  population case, giving127 distinct latest passing cases with the broader
  regression run. The working test file SHA256 is
  `a4dda40a2a1cc781a7a8c95abb49f976cc6b25cf168f497383d2f6141d967cdb`.
- `frozen-source-comparison.json`:all owned application files and the numerical
  test are byte-identical to the full Phase 2 gate snapshot. Only the appended
  empty-population integration test is a supplemental case absent from that
  snapshot. Its final focused pass is retained separately.
- Actual browser evidence is recorded below. No unexecuted check is a pass.
- Ruff on10 owned Python files, mypy on8 source files, frontend types and ESLint
  pass. No new migration or runtime dependency was added.

## Reproduce

Use the repository's documented disposable local PostgreSQL/object-storage
fixtures and disabled model/email modes. The local runner never sources `.env`:

```bash
python3 data/verification/2026-10-17/two-phase/local_verify.py pytest \
  apps/api/tests/test_contributions.py \
  apps/api/tests/test_contribution_studies.py \
  apps/api/tests/test_studies.py apps/api/tests/test_artifacts.py \
  apps/api/tests/test_analysis_access_policies.py apps/api/tests/test_result_exports.py \
  -o addopts='--strict-config --strict-markers --disable-warnings'
```

Browser specification: `apps/web/e2e/contribution-studies.spec.ts`; run through
`scripts/check_browser.py` using isolated schema/bucket and the standard8001/3001
ports, after coordinating exclusive browser ownership. It creates synthetic
sources, confirms meanings, submits actual forms and checks exact saved output,
sharing, dashboard pinning, reopening, Excel download and1440/390/320 layouts.

## Explicit limits

No causal identification, calibrated uncertainty, inferred foreign exchange,
missing-value imputation or complex statistical model is provided. Exact
fractions reconcile the declared accounting convention. Production load,
representative customer acceptance and deployment remain unverified. Existing
Excel exact-text preservation and export bounds apply. The companion contract
explains row/group/filter limits and rerun semantics.


## Final query-export permission repair

Read-only final review identified a genuine publication race after the full
Phase 2 snapshot was frozen. A shared contribution projection could be exported
through the existing query-ID dashboard endpoint. If the study was made private
after the second replay/prepare but before the final download transaction, that
transaction checked sources but did not check the study's sharing state.

`export-final-guard-repro.xml` reproduces the defect: an export returned200 when
404 was expected, in3.61 seconds. The test changes sharing through the real
StudyService after the second preparation and checks that no download audit is
written. `ResultExportService.dashboard` now supplies the existing delivery
workflow with a guard that resolves every query receipt and its exact study
binding in both guarded transactions. This reuses `authorize_analysis_receipt`
and preserves ordinary query/private-analysis access. No new route or schema is
introduced. The original failing run remains retained.

This application change and its appended regression test are a **post-snapshot
supplement**, not covered by the already-running immutable full gate.
`export-final-guard-fixed.xml` passes56 cases (18 contribution integration and38
existing portable-export cases) in149.30 seconds, no failures/skips. Ruff and
mypy for the repaired service pass. `frozen-export-guard-supplement.patch` and
adjacent JSON record the exact source delta; patch SHA256:
`f12df0b0d876c1f32a53175284f6a91286c8ce784cf0011c45777867ceed42ac`.

`focused-reconciliation.json` maps128 distinct latest passing test cases across
the broader regression,35-case focused and56-case final repair runs. The earlier
failed denial assertion and the genuine export race reproduction remain visible.
This is combined scoped coverage, not a claim of a clean full application run.

## Actual browser completion

`browser-initial/` retains both initial failures. A successful save followed by
a list-read failure incorrectly kept the creation button in its calculating
state; a separate blocked state now permits the intended read-only recovery.
The other failed assertion expected a decimal-padded string, while the actual
source value is the exact integer `240`; the assertion now checks that value.
The initial run also exposed duplicate React keys for sibling chart/detail
sections. Their keys now have distinct prefixes, and both journeys fail if that
warning returns. These were fixed without changing backend calculations.

`browser-recheck/` passes **2 of 2 actual API/browser journeys in 44.0 seconds**,
with no page errors or duplicate-key warnings. Same-file period comparison and
two-file comparison each exercise confirmed definitions, the real form, exact
saved totals, contribution charts, supporting-record selection, sharing,
dashboard pinning, reopening and an Excel download. Six desktop/mobile layouts
at 1440, 390 and 320 pixels pass overflow checks; desktop and narrow captures
were also inspected visually. Reduced-motion behavior is included.

Final frontend TypeScript and ESLint checks pass after these repairs. The full
Phase 2 backend and browser release gates remain separately owned and are not
inferred from these two journeys. No deployment is claimed by this ledger.
