> **File use case:** Evidence ledger for the personal agent, useful examples and studio repair.
> **What it does:** Records checks, retained failures, source preservation and private-release limits.

# Verification — personal agent and studio

Scope is defined in [the contract](personal-agent-studio.md) and
[plan](personal-agent-studio-plan.md). The bounded local/test and private-demo
slice is complete on application **327ba7d**, schema **0018**. No production gate
or broad feature status is promoted.

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
planning and advisory selection. A final read-only spot review of committed
`327ba7d` finds no material blocker in those boundaries or unit-write/reload
handling; it is not an exhaustive audit.

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
production build pass. Deployment and live evidence follow below.

## Activated private release

Application **327ba7d** is activated on **0018**. Both VPS images build and the
non-root, read-only, network-disabled image passes eight prior compute/forecast
checks, three earlier extensions, eight pattern/daily checks and 48 group/rule
computations across eight workers. Activation holds the maintenance lock and keeps
checkpoint `pre-327ba7d-20261016`. All **46 prior business-table fingerprints** and
the environment checksum match; the expected differences are the Alembic version
and an empty new `agent_memories` table. Rollback refuses to discard memory rows
or tombstones and never restores an old database over new saved work.

Activated runtime has five running containers, zero restarts, healthy database/
storage readiness, workspace HTTP 200, six loopback listeners and active model,
refresh and backup units. No application-error lines were found in the inspected
thirty-minute window. The reported four-column file's five retained artifacts
match their pre-release copies. The original farm bytes, profile, definitions and
revision history also match the pre-release snapshot.

## Live application checks

The first API rehearsal passes its assertions in **261.701 seconds**, using three
fictional actors and two new workspaces. It checks 24 private denials, two stale
memory-edit conflicts, explicit save/edit/forget, immutable saved reading,
two exact retail totals, two pattern jobs, all three planted support spikes,
seven forecast dates, exact scenario/allocation results and seven legacy reopens.
Source snapshots remain unchanged. A fresh natural-language calculation uses the
configured local selector and hosted planner and returns exactly 8,235,156.60 USD.

The first qualitative retail reading **falls back** to saved dataset information.
The recorded route is `deterministic:dataset-guidance-v1`; the retained response
does not expose enough detail to attribute the cause. It is not counted as a
successful hosted reading. A separate probe on the smaller action file, with
plain saved preferences, succeeds through
`hosted:deepseek-v4-pro:dataset-reading-v1`. It uses the current private memory,
explains the declared costs/assumed benefits/staff hours and suggests eligible
comparisons without inventing a dated forecast. Its receipt records the memory
version without copying the raw memory text. Forget advances the private revision,
the saved answer still reopens, a second member is denied its private thread and
source preservation passes. This different probe does not establish that the
initial retail fallback is resolved.

Private live evidence is retained under
`data/verification/2026-10-16/workspace-upgrade/live-20261016T062136Z/`.
These synthetic functional checks do not establish representative model quality,
calibrated decision benefits or sustained-load acceptance.

The live browser run passes **three journeys** in **193.285 seconds**, with
**eighteen layouts** at 1440/390/320 pixels, zero page errors and no horizontal
overflow. It opens the retail Home and saved forecast, reopens the accepted hosted
action-file explanation, repairs a separate fictional confirmed-v3 definition
through partial v4 to complete v5, and saves/reopens/forgets a member's own memory.
Both units persist as explicitly entered, descriptions remain unchanged and the
fictional fixture has zero remaining questions. The real reported file is not
edited. The first two attempts remain recorded: an overly exact history selector,
then an omitted **Load saved answer** step in the new helper. Only the helper was
corrected; no product change was needed. A separate read-only Home capture waits
for saved context to finish loading rather than retaining a transient screenshot.
That recapture passes three layouts with no page errors/overflow in 32.404 seconds;
it repeats the Home view and is not counted as another distinct journey.

## Checked post-release state

Post-release backup **20261016T063610Z** retains the new fictional verification
work and private memory revisions. Both archive checksums pass and the script
restarts writers/storage successfully. Final checks again show five running
containers, zero restarts, schema 0018, ready database/storage, workspace HTTP 200,
six loopback listeners and active model/refresh/backup units. The inspected
thirty-minute application-log window contains no error lines. The reported real
source's five original artifacts still match after backup. This is archive and
functional evidence, not a restore drill or off-server disaster recovery.

The maintained feature report and refreshed October 16 Desktop DOCX retain all
64 original ordered rows and counts 37/16/11. The DOCX archive and new evidence
text were checked; its previous version is preserved in Desktop report-backups.
The user's original October 13 PDF remains untouched and untracked. Private
sessions, local skills, tools, samples, captures and reports remain ignored.

## Development-tool review

All seven requested repositories are downloaded at the pins recorded in
[the adoption record](project-skill-adoption.md). Four selected skills are local
coding guidance; Lieflat is an inactive reference outside discovery. No downloaded
skill is a deployed product tool. UI guidance informed the studio; documd guidance
informed the attributed local walkthrough; the SQL/EDA references informed its
question progression and explicit limitations. oneDAL was neither built nor
benchmarked, and no learned model was trained.

Five no-LLM SkillSpector scans finish with valid reports and no timeout. Their
125 findings receive source judgments. UI/documd/Lieflat retain raw CRITICAL
scores and partial parser coverage; EDA retains a MEDIUM result with unresolved
example references; inspector instructions receive LOW/zero findings. This is
not a clean scan or safety certification. Scoped UI/documd/EDA guidance remains
CAUTION, Lieflat retention remains CAUTION/inactive, and the inspector procedure
is APPROVE within its reviewed scope. Optional exporters/templates/analyzers
were not executed. Reports, dependencies and source checksums stay ignored.

A fresh production-preflight check still blocks all eight required gates. No
feature count or production status changes: **37 Done / 16 Partial / 11 Not yet**.
