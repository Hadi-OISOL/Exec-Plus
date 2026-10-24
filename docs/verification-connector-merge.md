> **File use case:** Records integration of the teammate's connector branch with current Syntelio.
> **What it does:** Preserves source ancestry, migration decisions, verification and remaining limits.

# Connector branch integration — October 17, 2026

## Source and coordination

The user requested pulling and merging `phase4-abm`, coordinating with the ongoing
`EXECT_PLUS_WHOLE` session. Fetched tip:
`2188a2e81ecf698fb76b2f568f162bde313897d5`. It contains one connector commit based on
`2a930807d67e0f4ea6fe25a209503c82bdae4bd2`, 47 commits behind the committed `phase2`
baseline `d4db038aa43e16715e171b7ca8b0b8ca171bc95d`.

Preparation and testing used a separate worktree to preserve unfinished Phase 1 work.
A read-only snapshot recorded hashes of 121 Phase 1 files, followed by five verified
test supplements. WHOLE accepted Phase 1 checkpoint
`2ee7d9c551ebef9e0a3004825fc7da945e2a70e1`; the true merge retains that checkpoint and
the incoming connector tip as parents. Private evidence and coordination stay ignored
under `data/`. Shared work and separately owned UI/Phase 2 changes are preserved.

The sessions agreed to preserve migrations 0025–0027 and append the incoming Google
and connector tables as **0028 and 0029**, with the chain
`0024 → 0025 → 0026 → 0027 → 0028 → 0029`. The teammate's colliding 0018/0019
identifiers are not introduced into existing migration history. Empty downgrades
preserve earlier rows; nonempty connection tables refuse destructive downgrade.

## Integration repairs

- Retain current exports, private memory, dataset policies, controlled PostgreSQL
  imports, integration APIs, plans, metrics and account/onboarding services while
  adding the connector routes and optional runtime services.
- Preserve disabled-account session checks and password-account provisioning
  refusal in the shared session issuer. Google sign-in cannot implicitly link or
  bypass an existing native password account; the browser explains the refusal.
- Reuse the current session loader for Google returns and native/password login.
  Remove two obsolete dashboard-toggle calls, preserving the open Overview UI.
- Preserve workspace upload quotas and permission checks through `WorkspaceService`.
  Connector/Sheets imports are categorized as ingestion in operational metrics.
- Probe one additional provider row and refuse oversized imports rather than
  silently publishing truncated sources. Parse incoming JSON decimal numbers
  without a binary-float conversion before CSV serialization.
- Correct incoming connector protocol annotations and retain dependency licenses.
  The verified local dependency is cryptography 47.0.0; no credentials are included.

## Verification

All external platforms use deterministic stand-ins or HTTP mock transports. Database
and storage integration uses disposable schemas/buckets on synthetic local services.
Browser verification uses separate ports from the other session's acceptance run.

Before adding the Phase 1 overlay:

- 121 connector/API/architecture cases pass in 90.50 seconds.
- 100 migration, workspace, private-memory and dataset-policy cases pass in 137.46 seconds.
- 83 overlapping final connector/Google logic and service checks pass in 45.02 seconds,
  including decimal preservation and row-limit refusal.
- 59 frontend tests, TypeScript, ESLint, Ruff, mypy (284 files) and a production web
  build pass. Overlapping test executions are not additional distinct cases.

On the combined Phase 1 and connector source, TypeScript and mypy (307 files) pass.
The production web build, 59 frontend tests, ESLint and Ruff also pass on combined
source. All eleven connector/Google browser journeys pass in 1.4 minutes. Four
focused account/plan/metrics compatibility cases pass in 13.12 seconds. These
overlap the earlier two account checks and are not added as distinct tests.
All four native-account/onboarding/password/invitation/plan browser journeys also
pass in 1.2 minutes, and eight migration supplement checks pass in 24.68 seconds.
The combined targeted backend regression run passes 297 cases in 417.96 seconds.
These are pre-hardening results, not final merge acceptance.

Initial failures remain in the private evidence: transient GitHub DNS resolution,
missing cryptography in the existing environment, obsolete UI state setters,
connector protocol typing, and an isolated Next.js build resolving dependencies
outside its workspace. Dependencies were installed/copied inside task-owned ignored
directories; the shared Python environment and other acceptance processes were preserved.

## Security review and hardening

The WHOLE session reviewed the connector-only diff and reproduced defects despite
those passing tests. The isolated candidate now refuses flattened-name collisions,
preserves exact secret whitespace, bounds HTTP/page/database/CSV ingestion and
propagates failed imports to their panels. Failed authorization/metadata reads clear
private browsing; retryable import failures retain the selected source/tab.

Eighty focused hardening checks passed initially. Ruff and mypy (250 application
source files) pass after a SQL expression annotation repair. Two new browser
journeys pass in 18.8 seconds: allowance rejection and retry for Sheets/connectors,
then revoked reads clearing private titles, accounts and selection. The broader
backend recheck passes 135 cases in 88.81 seconds; five architecture checks also pass.
After covering single-tab retry too, all three browser cases pass in 31.1 seconds. The initial recheck used nonexistent test filenames
and collected no cases; its failed log is retained before the corrected invocation.

WHOLE's tested backend and browser contributions are now reconciled with the import
repairs. Browser-bound one-use attempts and exchange replace bearer fragments/storage.
Google subjects identify self-service accounts with Demo allowances and exact-account
approval. Disabled-account/session and connection-version checks cover concurrent
refresh, validation, disconnect, reads and upload publication. Provider audits commit
inside that publication transaction. See [identity boundaries](connector-identity-security.md).
The only merge conflict was an equivalent secret-field variable name; `secret_fields`
preserves exact values without shadowing the newly imported `secrets` module.

A follow-up review found that a successful import POST followed by a failed list
GET looked like a failed import, allowing an accidental duplicate write. The
candidate now consumes the selection after the successful POST, clears stale upload
views on a failed GET, and offers an actor/workspace/dataset-bound read-only reload.
Fresh source/picker read failures clear account metadata for all HTTP failures.
Expanded browser verification passes six import-retry/read-failure journeys. The
four saved-import/read-retry cases pass in a fresh 36.0-second run after selector
corrections; these ten distinct cases are combined coverage across retained runs.
The R2 OAuth frontend patch is now applied, and combined TypeScript passes. The initial follow-up test wrongly
expected the empty upload selector to disappear; the UI intentionally keeps it
visible and disabled, so the corrected assertion checks its empty value and only
placeholder option. A second correction scopes the successful-reload message because
analytics mounts additional status regions. Both failed test runs remain retained.

## Final combined verification

On unchanged combined application/test source (tree
`45906dd08c9d49f427df90190ef08be2b54c4872`), two disjoint backend groups pass:

- 179 connector/security/resource/migration/architecture cases in 158.81 seconds.
- 219 native-account/plan/scoped-access/memory/policy/historical-schema/metrics cases
  in 272.25 seconds. Total: **398 distinct backend/architecture cases**.
- **29 browser journeys** pass in 2.8 minutes, including one-use OAuth returns,
  rejection of bearer URLs/storage, Google account classification, import failure/retry,
  saved-write/failed-read recovery, native onboarding Finish/reopen, password rotation,
  invitation identity approval and plan enforcement.
- **59 frontend tests**, ESLint, TypeScript, Ruff, mypy (311 files) and a production
  web build pass. The web build includes the final external-account profile repair.

The accepted Phase 1 checkpoint is reconciled separately against the captured baseline;
changes from its final docs and test evidence are retained. Reconciliation changes
only handoff/ledger documents and three accepted Phase 1 tests; application, migration,
dependency and other tested source bytes remain identical to the combined gate. Upstream license files keep
their original whitespace; authored diffs pass whitespace checks. No shared environment
or running acceptance process was replaced. Overlapping earlier executions are not
added to these final counts.

Main Codex supplied the existing VPS handoff. A metadata-only check through its current
control socket reports readiness `ready`, PostgreSQL available and object storage
available. Main's handoff records live schema 0020, API/jobs 867c5a0 and web 5c48d3c;
that is the previous release, not this connector candidate. No customer records,
provider calls, restart, migration, session renewal or deployment occurred here.

## Acceptance boundary

This is local branch integration, not deployment or real-provider acceptance.
Google/Sheets, QuickBooks, Xero, Zoho Books, Odoo and BigQuery have not been verified
with real accounts in this task. PostgreSQL tests use a disposable local database.
Connectors remain disabled without explicit configuration. No provider setup, live
connector calls, VPS change, public exposure or feature-ledger promotion is implied.

Imports are snapshots, not scheduled refreshes. The upstream first-organisation,
nested-record flattening and network-policy limits remain documented in
[connectors](connectors.md) and [Google integration](google-integration.md).
All eight production gates remain blocked.
