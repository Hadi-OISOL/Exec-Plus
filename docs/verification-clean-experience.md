> **File use case:** Records evidence for the first two October 15 improvement phases.
> **What it does:** Distinguishes local checks, live verification, retained failures and remaining acceptance work.

# Verification — focused experience and reliable reading

Scope is defined in [the delivery contract](clean-experience.md) and the
[four-phase plan](clean-experience-plan.md). Public observations are recorded in
the [REA reference audit](clean-experience-reference-audit.md). The first two phases
are complete for the bounded local/test and private-demo scope.

## Local verification

The full backend/architecture run passes **1,170 cases** without failures or skips.
The final expanded selection passes **107 cases**, covering subsequent additions
and yielding **1,177 distinct passing cases** in total. New cases cover invalid
derived counts in a twenty-column file, truncated/oversized content, repeated
invalid output, saved-answer preservation, missing-unit questions, provider
failure, shared timeout, budgets, source/permission changes and cleanup. The final selection includes source/permission changes before correction,
cleanup and the category-meaning regression. Ruff and mypy (170 files) pass.

Frontend unit tests (27), TypeScript, ESLint and the final production web build
pass. All **52 distinct real-service browser journeys** pass across the full run
and focused rechecks, including the three model-dependent conversations run with
the actual configured hosted model. They exercise focused navigation, Back,
explicit partial saves, failed-save retry, exact calculations, source evidence,
private reopening, keyboard navigation and reduced motion. Independent screenshot
inspection confirms separate Home/conversation/reading views and readable
1440/390/320 reading layouts; forecast and scenario charts fit narrow screens.
Forecast accuracy and method details remain available in native disclosures.

The retained full browser run had 43 passes, eight failures and one live-model
skip. An eleven-case offline recheck had nine passes and two failures. The first
five-case live selection had two passes and three failures, including an
accidentally selected model-disabled guided-review fixture that already passed
offline. The last two intended live cases both passed. Together these runs cover
all 52 cases; this is not a claim that one uninterrupted full run passed. Three
genuinely model-dependent cases now explicitly skip unless live-model testing is
enabled, and all three were exercised successfully for this release.

Initial failures are retained in ignored logs: the first backend attempt had
unstarted local test infrastructure; a draft test used the nonexistent state
`draft` instead of `needs_review`; another assertion read the wrong response
nesting. A helper closure error was corrected before integration. Browser work
initially overlapped a build with the development cache and used an overly exact
textbox label. Later failures were stale navigation/copy assumptions after
separating views, a provider-dependent calculation attempted with the model
disabled, and a reload helper that did not reopen an intentionally unfinished
review. Assertions still check exact values and evidence. A development router
page error occurred during edits; it did not recur in frozen-code reload rechecks
with explicit page-error assertions. These are not reported as successful first
attempts or proof that all possible browser errors are absent.

## Private release

Pre-release backup `20261015T182108Z` passes database/object archive checksums
and restarts the existing services successfully. This is archive integrity,
not a restore rehearsal. Candidate API/web builds pass, along with existing
non-root, network-disabled exact/statistical/analysis compute checks. The same
restricted image also passes bounded reading recovery and missing-unit preservation
with fictional data. Application **412bf4e** is activated on unchanged **0017**.
All **47 table fingerprint entries** and the environment-file checksum match
before/after activation. Source/image checkpoint: `pre-412bf4e-20261015`.

Deployed API checks pass on a fictional twenty-field source. The configured hosted
model returns an accepted reading with `source=model` and `repaired=true`, directly
exercising correction rather than counting profile fallback as model success.
The contextual reading uses saved definitions, private notes and the private goal;
only the one deliberately missing unit is requested. A private note's alias leads
to an exact **20.5** average and matching replay. Three same-workspace private-thread
requests are denied while the shared source remains available; private notes and
goals stay hidden from the peer. The source, definitions and revisions remain intact.

A pre-release ordinary receipt, pattern answer/receipt, forecast and compound
scenario reopen with their original evidence. The actual farm file's bytes,
profile, definitions and revision history remain unchanged. Initial live harness
failures are retained: the local tunnel was absent, the demo1 session had expired,
and an older fixture index contained no numerical receipt. The tunnel and one
session were renewed without revoking teammates; a real retained pre-release
receipt was selected. Successful model calls were reused when resuming checks.
Two deployed browser journeys pass in **48.3 seconds**: the fictional context
journey takes 22.1 seconds and the read-only farm journey 25.3 seconds. Both cover
1440/390/320 widths with no page errors. Home hides the conversation, navigation
retains the saved reading and exact answer, and reduced motion leaves no running
animations in the checked view. The farm's weak comparisons and no-date options
remain available. These are functional examples, not sustained-load acceptance.
The original farm snapshot still matches after browser verification.

Checked post-release backup **20261015T185057Z** preserves the new saved work;
database and object archive checksums pass. After restart, all five containers run
with zero recorded restarts; readiness and workspace return HTTP 200. Migration
remains 0017, all six listeners remain loopback, and the model/refresh/backup units
are active. The checked thirty-minute application log window contains no
error/traceback lines. Preserve all new saved work when rolling back code; no
database restore or destructive migration was performed.

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
