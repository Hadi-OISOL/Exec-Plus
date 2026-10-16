> **File use case:** Evidence ledger for the personal agent, useful examples and studio repair.
> **What it does:** Records checks, retained failures, source preservation and private-release limits.

# Verification — personal agent and studio

Scope is defined in [the contract](personal-agent-studio.md) and
[plan](personal-agent-studio-plan.md). This ledger is in progress until release
checks below are complete. No production gate or broad feature status is promoted.

## Reported definition-saving issue

Read-only inspection identified the reported four-column source at confirmed
version three. Both server questions contain text. All three saved definitions
are identical with empty revenue/cost units. Source bytes, profile, revisions,
upload metadata, current definitions and history were retained privately; no user
answer was guessed or source definition changed during diagnosis.

The frontend had directed the answer to a general meaning field while leaving the
unit optional. The corrected review asks for the missing unit directly, preserves
the prior meaning, keeps skipped fields unfinished and uses the actual saved
missing-detail list in completion feedback. The main editor no longer remounts
on a successful save. A saved-write/failed-read outcome offers a read retry.
Two backend regressions pass save/reopen, question removal and history preservation.
The browser regression reproduces confirmed version three, saves one unit to
version four while the other stays missing, then saves and reopens both correctly.

## Backend and sample evidence

The full backend/architecture run has **1,333 passes and two failures** in
521.82 seconds. Both failures were outdated test assumptions introduced by the
new additive table/sample registry: a migration fixture tried to read a later
removed table after downgrade; a provisioning test expected five samples.
The original failed run remains retained.

The corrected migration test still compares every prior table row, asserts exact
table sets and confirms the new memory table is empty. Its operations/migration/
memory/review recheck passes **59 cases**, zero skips, in 58.065 seconds.
The provisioning/sample/profile recheck passes **63 cases**, zero skips. It now
checks all seven sample IDs, bytes, dataset identities and meaning states after
provisioning twice. The two new samples remain unconfirmed. Together these runs
provide passing executions for all 1,335 full-suite cases, plus two new unit-save
regressions collected afterward: **1,337 distinct** passing cases. No clean
single full-suite run is claimed.

The memory-focused run passes 168 targeted cases, including 23 new regressions.
The sample-focused run passes 57 related cases, including eight new checks of
real execution/reopening. These overlap the full suite and are not added again.
Memory checks cover actor/workspace isolation, administrator denial, optimistic
conflict, membership removal/rejoin, forget tombstones, private audit visibility,
model-input boundaries, changes during correction/publication and immutable old
replies. The independent code review confirms memory is absent from numerical
planning and advisory selection.

The retail fixture verifies 1,095 rows, 365 dates, exact revenue 8,235,156.60 USD,
three support spikes and pooled/within-region direction reversal. The separate
six-action fixture verifies the exact constrained optimum and 64 combinations.
Forecast, scenario, anomaly, pattern and original receipt compatibility run through
real application services. The old five sample byte strings remain unchanged.
No synthetic result establishes representative real-world model accuracy.

Early targeted failures were fixture/harness problems: hidden raw turn evidence,
Decimal display scale, an invalid test directory, deprecated `/ask` use, profile-v1
name heuristics, anomaly minimum sample size and an incorrect scalar expectation.
The date-like sample category was renamed to `Week_Part` before freezing its bytes.
All retained logs distinguish failed attempts from passing rechecks.

## Frontend, tools and private release

The full offline browser run has 50 passes, four failures and three explicit
model-dependent skips. Three failures exposed a scenario dropdown's intrinsic
width at 320 pixels; one was an obsolete Home-headline assertion. The dropdown
received a scoped width fix, and the assertion now targets the current Home region.
All **15 affected journeys** then pass in 3.2 minutes, including all scenario forms,
forecasts, group comparisons, allocation, exact charts, upload, memory and saved
units. Across full/focused runs, **54 distinct offline journeys** have passing
executions. The three model-dependent skips are not counted as passes. Retained
screenshots cover 1440/390/320 and demonstrate visible missing questions and the
separate required-unit/meaning inputs.

Ruff and mypy pass over 179 configured source files. A first browser attempt
collided with a simultaneous Next.js build; that harness failure is retained and
final browser/build operations run sequentially. Five spot-checked text/background
pairs found one status-badge contrast of 4.38; the final style darkens that label to a measured 4.842:1.
This is a limited check, not a comprehensive accessibility certification.
The standalone local demo guide passes 1440/390/320 layout checks without overflow
or browser errors. Its static HTML loads no remote script/font and credits the
reviewed documd theme guidance.

The selected skills, tool limitations and licenses are documented in the reference
reviews. Their source installations remain ignored and project-local. No external
skill code is loaded by the deployed agent. Functional tests do not constitute
representative model-quality, sustained-load or production-security acceptance.

The checked pre-release backup is **20261016T061031Z**. Both database/object
archive checksums pass and services restart healthy. The first invocation omitted
`bash` for a non-executable script and made no changes; the corrected command is
retained separately. Archive integrity is not current-version restore or off-server
recovery evidence. Models and timers are active and /sdb-disk retains ample space.
All **29 frontend unit tests**, TypeScript, ESLint and the final sequential local
production build pass. Deployment/build/live results will be added once those
operations finish.
