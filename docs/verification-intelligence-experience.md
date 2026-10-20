# Intelligence experience verification — 18 October 2026

Runtime checkpoint `66ba6b1` is based on `387d884`. Private release `57f425ce74e83c35`
is active on unchanged schema `0029`; the bounded local and private live gates are complete.
All fixtures described here are synthetic. Historical release evidence is separate.

## Local checks

| Check | Latest outcome | Retained evidence |
| --- | --- | --- |
| Combined discovery, scope, routing and threads | 177 pass | `intelligence-upgrade/backend-combined.log` |
| Context recall, narrative, diagrams and replay | 133 pass | `intelligence-upgrade/review-regression.log` |
| Focused proactive and narrative API | 24 pass | `intelligence-upgrade/combined-focused.log` |
| Protected compound exports, replay, cohorts and discovery publication | 51 pass | `intelligence-upgrade/evidence-regression.log` |
| Frontend unit tests | 71 pass | `intelligence-upgrade/frontend-combined.log` |
| Production build and lint | pass | `intelligence-upgrade/build-combined.log`, `lint-combined.log`, `ruff-combined.log` |
| Source typing | mypy 269 files, TypeScript pass | `intelligence-upgrade/mypy-combined.log`, `types-combined.log` |
| Browser initial combined run | Six pass, two failures retained | `intelligence-upgrade/browser-combined-recheck.log` |
| Browser repaired navigation, decisions and proactive evidence | Six pass in 58.9 seconds | `intelligence-upgrade/browser-ui-proactive.log` |

Paths above are relative to ignored `data/verification/2026-10-18/`. Backend sets
overlap and must not be added as unique cases. Browser coverage comprises nine distinct
journeys across the retained runs, including the three initial passes not in the recheck:
appearance, selected narrative and fallback narrative. This is a focused affected-surface
gate, not a new full-repository run or production-scale acceptance.

The proactive browser case uploads 40 fictional rows, explicitly confirms meanings,
checks automatic pattern receipts, replays all 40 rows, and checks light/dark charts at
1440, 390 and 320 pixels. Changing appearance makes no discovery/dashboard requests and
preserves exact displayed metrics and saved definitions. Screenshots remain private.
The decision case covers the new quick check, custom anomaly analysis, human review,
conditional allocation, approval, replay and reopening. No external action is executed.

## Failures and repairs

- Initial runner invocations had a wrong test filename, missing npm PATH and an incorrect
  disposable-service password. Corrected runners read only the task-owned container
  configuration; no production database was used.
- Initial new narrative assertion compared a Python dictionary representation; corrected
  to assert the actual segment text. The old currency test expected twelve-place display;
  it now checks readable v2 text while preserving immutable old-definition replay.
- Independent review found cross-currency group ranking. Ranking now requires a common
  confirmed unit or count aggregation; mixed-currency regression passes.
- Independent review found negation lost by lexical recall. Unsupported negative references
  now clarify; five exclusion variants have regression coverage.
- Saved-work browser navigation now opens the explicit tools disclosure using the keyboard,
  retaining its original exact receipt, values and selected-source assertions.
- A successful custom analysis POST followed by a history GET could reset review selection
  after interaction with the previous result. Publication now uses the POST response and
  updates local history directly. The browser waits for the named new result before review.
- Backend helper fixture corrections and their initial failures are separately retained in
  `proactive-intelligence/backend/report.json`; its 104 latest passes overlap this gate.

## Limits retained

Automatic patterns use the existing descriptive methods and eligibility bounds; they do
not establish causes, calibrated predictions or crop interventions. Memory recall is
explicit and conservative lexical matching, not a learned semantic graph. New narrative
prose selects verified statements; it does not introduce arbitrary model claims. Old v1
answers retain their original rendering contract. All eight external production gates
and the canonical 64 feature IDs remain unchanged.

Agent Reach and Replica are assistant development tools. They are not executable product
skills or mandatory services. Their separate adoption reports retain source pins, licenses,
scan findings and actual use. ThoughtSpot evidence is from a public product page, not its
private application or backend.

The current multi-result Overview can still be long with many eligible findings. All charts
remain visible as requested; general layperson usability and competitor parity are not
established by layout checks. Cognee is reviewed-only: see `docs/cognee-memory-assessment.md`.

## Additional affected-surface gate

Forecasting, upload reading, exports and visualization checks have 14 distinct latest
passing browser journeys across the initial 13-pass/one-failure run and three passing
supplements (35.3 seconds). The failed assertion expected the previous dashboard-first
DOM order; it now verifies findings before dashboard controls, retaining exact values,
filters, missing-value and keyboard checks. Two supplemented journeys explicitly exercise
dark forecast and reading views. Logs: `browser-affected-surfaces.log` and
`browser-affected-supplement.log`. Combined with the nine earlier journeys this is 23
distinct local browser journeys with latest passing executions, not one clean full run.
Frozen frontend rerun passes all 71 tests; lint and VPS image builds/restricted checks pass.

## Private release activation

The immutable archive contains 1,036 files; SHA-256
`74b9b48f7def0e04f81f05298be3180bcae90405de57631bb1388dc71809d381`.
Later commits `cbc1f1d` and `1077f90` add documentation/tests; runtime, migration and
dependency bytes are unchanged from `66ba6b1`. VPS image builds and restricted image
checks pass. The isolated candidate canary passes all four hosted tasks (single total,
verified follow-up, compound request and tied extrema), with selected narratives and
both fictional accounts disabled/revoked; its disposable containers are cleaned up.

An initial activation invocation incorrectly wrapped the helper's own maintenance lock
in an outer lock. The exact blocked processes were stopped before maintenance began;
all original services remained running. `activation-initial-lock.log` retains that failure.
The successful retry uses only the helper's internal lock.

Checked pre-release backup: `20261018T185019Z`. Before starting candidate writers,
all 77 existing tables, 198 stored files (3,997,759 bytes) and configuration fingerprints
match. No migration or data restore occurred. Running API/jobs image `04331cd56ad4`
and web image `2cefaf5169d2` match the checked candidate. Ready/web checks pass.
Fresh live API/browser checks and a checked post-release backup remain pending here.
Evidence: `activation.log`, `activation-evidence/`, `isolated-canary.json` and
`vps-build.log` in the same private evidence directory.

The deployed API's four hosted tasks pass in 53.279 seconds combined; all four narratives
use selected verified statements, with no fallback in this small fixture. Both created
accounts are disabled and their sessions revoked. This is functional evidence, not a broad
language-quality or latency benchmark (`live-api.json`).

The initial live browser run passed exact compound values/evidence and all three layout
widths in both themes, but retained a failure for a background data-brief cancellation.
Source inspection confirms that panel aborts its own fetch on unmount. The checker now
accepts only that exact POST during initial navigation when it independently observes the
browser AbortSignal; connection resets, missing signals, writes and job-stage failures
remain failures. Seven helper regression tests pass. The original report is retained;
a fresh browser run remains pending at this checkpoint. No application code was changed
for this checker correction.

The fresh deployed browser recheck passes in 35.406 seconds: three widths, both themes,
exact compound values, source references and keyboard evidence. There are no page errors,
HTTP failures, unexplained request failures or horizontal overflow. Its own account is
disabled, the session revoked and login refusal verified (`live-browser-recheck.json`).
Root visually inspected the deployed dark desktop capture. The initial failed report
and its cleaned-up separate account remain retained.

The first post-release verifier refused its exact-five-service preflight while the existing
refresh service ran (18:52:34–18:52:38 UTC). A subsequent read found all five application
services healthy and the refresh task stopped. A transient extra operator container is
consistent with that timing but was not captured in the failed report; the exact observed
service set is unavailable. No backup or restore was attempted by that failed preflight.
The unchanged verifier is being rerun with a new output file, preserving the failure.

## Final release result

The unchanged post-release verifier passes (`post-release-recheck.json`). Checked backup
`20261018T185309Z` has matching archive checksums and readable database/object listings.
After backup, the five services, exact candidate images, six loopback listeners, readiness,
web response, schema `0029`, configuration hashes and model/refresh/backup units pass.
The first failed preflight remains in `post-release-initial.json`; no data restore occurred.
All four live-created fictional accounts (two API and one for each browser run) are
explicitly disabled and their sessions revoked. Existing user sessions were not changed.

The dedicated REA public-capture browser is closed; its evidence/profile remain private.
All five unrelated initial working-file hashes are preserved, including the original
`next-env.d.ts`. No push, public exposure, provider switch or runtime dependency addition.
The result is a focused enhancement, not complete ThoughtSpot/Claude parity or proof of
production-scale acceptance. Automatic pattern and one-click anomaly behavior have local
real-service browser coverage; live checks target compound answers and themed presentation.
