> **File use case:** Records evidence for the first two October 15 improvement phases.
> **What it does:** Distinguishes local checks, live verification, retained failures and remaining acceptance work.

# Verification — focused experience and reliable reading

Scope is defined in [the delivery contract](clean-experience.md) and the
[four-phase plan](clean-experience-plan.md). Public observations are recorded in
the [REA reference audit](clean-experience-reference-audit.md). This ledger is
being completed during verification; deployment results are not yet claimed.

## Local verification

The focused reading/context selection passes 74 cases. New cases cover invalid
derived counts in a twenty-column file, truncated/oversized content, repeated
invalid output, saved-answer preservation, missing-unit questions, provider
failure, shared timeout, budgets, source/permission changes and cleanup. A final
expanded selection and the complete backend/architecture run are in progress.

Frontend unit tests (27), TypeScript, ESLint and a production web build pass.
Real-service browser journeys are in progress. They exercise focused navigation,
Back, explicit partial saves, failed-save retry, actual calculations and replay.
Independent screenshot inspection confirms a separate Home and conversation;
remaining narrow-layout and keyboard checks are recorded after completion.

Initial failures are retained in ignored logs: the first backend attempt had
unstarted local test infrastructure; a draft test used the nonexistent state
`draft` instead of `needs_review`; another assertion read the wrong response
nesting. A helper closure error was corrected before integration. Browser work
initially overlapped a build with the development cache and used an overly exact
textbox label. These are not reported as successful first attempts.

## Private release

Pre-release backup `20261015T182108Z` passes database/object archive checksums
and restarts the existing services successfully. This is archive integrity,
not a restore rehearsal. Candidate build, activation fingerprints and deployed
journeys remain pending in this working ledger.

## Limits and continuation

Qualitative readings remain fallible. Provider-level incomplete-response errors
may still use honest fallback; the bounded correction handles invalid content
actually returned to the application. A forty-second model deadline includes
both attempts, but cleanup can extend elapsed time. Historical saved responses
remain unchanged; a new question uses the improved reading.

No representative model-quality, causal, predictive or sustained-performance
acceptance is claimed. Phases three/four remain planned for the next session.
All 64 feature IDs, 37 Done / 16 Partial / 11 Not yet counts and all eight blocked
production gates remain unchanged. Private artifacts stay under ignored
`data/verification/2026-10-15/clean-experience/` and neighboring focused-browser logs.
