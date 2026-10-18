# Intelligence experience verification — 18 October 2026

Candidate `66ba6b1` is based on `387d884`; private deployment is pending at this checkpoint.
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
