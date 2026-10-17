> **File use case:** Tracks the October 17 two-phase implementation and separately authorized private release.
> **What it does:** Connects the original requirements to inspected code, implementation, tests and honest acceptance boundaries.

# Two-phase implementation

## Authority and starting state

The October 17 instruction authorizes repository code, migrations, tests and local
demonstrations. It forbids pushes, deployments, production/customer data, secret
changes, external credentials, live email/webhooks and external connectors. Those
restrictions supersede earlier permission to operate the private VPS. Existing
external adapters are outside this work; deterministic local fakes and disposable
synthetic fixtures may exercise their internal contracts without contacting a service.

**Later October 17 authorization:** after an accidental IDE shutdown, the user
explicitly requested incremental deployment of tested VPS updates. The root agent
may stage and activate verified private-demo releases with checked backups,
compatibility/preservation checks and health verification. The earlier no-deploy
instruction applies to the work before this authorization. No push, external
connector, provider change, public exposure or customer-data analysis is authorized
by this change. Local test evidence remains separate from deployment evidence.

Starting commit: `d4db038`, personal branch `phase2`. Pre-existing changes are the
generated `apps/web/next-env.d.ts`, the untracked original October 13 PDF and the
untracked `docs/verification-independent-tools-release.md`. Preserve all three.
The starting local schema is **0024**. Later authorized private-release preparation
confirms the live application still uses **0020**; it has not yet been activated
to the Phase 1 candidate.

The October 13 report is historical: 37 Done / 16 Partial / 11 Not implemented.
The checked-in October 16 ledger is 39 Done / 16 Partial / 9 Not yet: exports and
incident monitoring have already advanced. Several additional local implementations
exist without final ledger promotion. Inspect those before adding anything.

Baseline execution uses an immutable copy of the starting commit and isolated local
PostgreSQL/object storage. All model routes are disabled. Retain logs, JUnit and
browser reports, including failures and skipped provider cases, under ignored
`data/verification/2026-10-17/two-phase/`. A previous passing run is historical
evidence, not a substitute for the requested baseline.

## Phase 1 implementation matrix

| Slice / IDs | Prior ledger | Inspected local foundation and required increment | Expected checks / dependencies | State |
| --- | --- | --- | --- | --- |
| P1.1 / 13 | Done | Reuse `result_exports`, PDF/portable renderers and protected downloads. Verify supported study/dashboard/KPI/forecast/comparison round trips, metadata, precision, nulls, dates, units, pagination and bounds; repair actual gaps. | Synthetic report fixtures; PDF text/pages, XLSX explicit cells/evidence, injection, forged IDs, current grants and oversized results. Existing ReportLab/Pillow/openpyxl only. | Locally accepted; deployment separate |
| P1.2 / 1 | Partial | Extend existing opaque sessions with local password registration/login/change/disable and documented operator recovery. Reuse users, workspace/organization provisioning and current authorization. Registration must never claim an existing operator identity or treat an unverified email as invitation proof. | Password hashing, generic errors, throttling/concurrency, expiry/revocation, CSRF/origin, reset/disable, cross-user denial, real UI registration/login. No SMTP/OAuth. | Locally accepted; deployment separate |
| P1.3 / 47 | Partial | Reuse upload-first onboarding, samples, definitions/cleaning, studies and invitations; persist actor-private step/resume/skip state. Add contextual progression without auto-confirming shared meanings. | Registration → synthetic upload/sample → review → first study/board → decisions/team; resume/skip/version conflicts/private isolation. | Locally accepted; deployment separate |
| P1.4 / 14,46 | Partial / Missing | Extend current model allowance and product usage foundations with explicit local plan catalog/assignment and atomic resource/operation entitlements. Preserve global safety bounds and distinguish configured allowances from subscriptions. | Seats, datasets, file size, processing, saved work, exports and forecast/model operations; concurrent admission, retries, period boundaries, administrator assignment, visible remaining amounts. No billing. | Locally accepted; deployment separate |
| P1.5 / 40 | Partial | Audit every changed route/service and preserve existing tenant, dataset and private-owner guards. Cover new authentication and output surfaces, safe logging, filenames and job admission. | Horizontal/vertical escalation, cross-workspace resources, malformed/injection inputs, forged exports/jobs, account lifecycle and permissions races. Independent production review stays open. | Locally accepted; deployment separate |
| P1.6 / 42 | Partial | Reuse integrity/replay verification in a disposable synthetic local backup/restore rehearsal. Record schema/application metadata and reject nonempty restore targets. Never use a production backup. | Checksums, corrupted/missing archive rejection, isolated migration/restore and representative exact replay, cleanup and preserved original fixture. No custody/RTO claim. | Locally accepted; deployment separate |
| P1.7 / 43 | Done | Extend fixed-code incidents with request/job correlation, redacted failure categories, bounded metrics and configurable in-app thresholds. Reuse staff-only console and incident lifecycle. | Ingestion/export/queue/job failures, denominator-aware rates, alert transitions, staff revocation, content/token-free logs, storage failure. No vendor or SMTP. | Locally accepted; deployment separate |
| P1.8 / 44 | Partial | Extend existing fixed-case evaluation with declared synthetic finance/sales/inventory/HR fixtures and source/citation/claim/privacy/replay checks. Deterministic fakes keep it offline. | Exact node manifest, no missing cases, numeric/citation/unsupported-claim negatives, access denials and immutable reopening. Provider quality remains unmeasured. | Locally accepted; deployment separate |
| P1.9 / 45 | Partial | Reuse versioned prices, provider counters, atomic reservations and unknown-cost states. Add reliable upper-bound admission only where locally configured caps and actual counters support it; separate estimates from invoices. | Concurrent budgets, retries, failures/missing counters, exact prices and unknown exposure; offline fake provider only. | Locally accepted; deployment separate |
| P1.10 / 50 | Partial | Reuse declared workload tooling; measure ingestion/profile/dashboard/query/forecast/export and modified APIs cold/warm, memory, throughput and bundle size on one fixture/environment. Optimize an observed bottleneck with parity tests. | Before/after measurements and source hashes, exactness/permission parity, resource bounds. Local measurements are not production acceptance. | Locally accepted; deployment separate |

Phase 1 gate: unit/integration/migration/backend/frontend/security/build checks and
actual local UI registration/onboarding/plan enforcement plus the complete synthetic
upload → cleaning → analysis → evidence → dashboard → export journey. Record outcomes
in `docs/verification-codex-phase1.md` before implementing Phase 2 increments.

Implementation ownership reserves migration 0025 for native accounts/onboarding,
0026 for plan entitlements and 0027 for operational observations. Shared changes
must preserve the lock order **workspace(s), then account, then staff grant**.
Password hashing, parsing, rendering and network I/O must not hold those locks.
The existing operator path must refuse to provision a password-account session;
native recovery requires the separate explicit identity-check procedure.

The cost audit found no reliable provider input-token or total-invoice upper
bound. Preserve the existing exact ledger, configured exposure reservations and
unknown-cost states. Add bounded serialized model request/response sizes and
reliable local operation quotas; do not manufacture token counts from text bytes.

## Phase 2 implementation matrix

| Slice / IDs | Prior ledger | Inspected local foundation and required increment | Expected checks / dependencies | State |
| --- | --- | --- | --- | --- |
| P2.1 / 33 | Partial | Extend existing exact change/group comparisons with a standalone saved period/dataset contribution workflow and eligible price/volume/mix formulas. Preserve source receipts and explicit observed-contribution wording. | Independent exact decomposition, missing groups/units/periods, source/version changes, drilldown permissions and export parity. | Locally accepted; deployment separate |
| P2.2 / 56 | Partial | Existing naive/seasonal-naive/SES/Holt/damped/Holt-Winters selection uses chronological validation/holdout. Verify sufficiency, train-only preparation, metrics, empirical interval labels and immutable vintages; repair gaps. | Leakage adversaries, seasonal/missing periods, benchmark comparison, exact actual comparisons, save/replay/export. Existing local numerical stack. | Locally accepted; deployment separate |
| P2.3 / 57 | Partial | Existing private source scenarios accept up to four explicit drivers with immutable successors. Extend declared constraints and meaningful sensitivity/variant presentation without learned causal claims. | Unit/formula consistency, simultaneous change/no double count, conservative/baseline/optimistic assumptions, source lineage and private revisions. | Locally accepted; deployment separate |
| P2.4 / 58 | Partial | Reuse MAD/IQR, seasonal residual and distribution-drift engines. Add justified bounded rolling and multivariate methods where synthetic evidence supports them; retain exact flagged records and feedback. | Seasonal alignment, insufficient/dirty observations, thresholds, exact replay, labeled-fixture alert precision/recall, permission scopes. | Locally accepted; deployment separate |
| P2.5 / 59 | Partial | Reuse exact enumeration and bounded CP-SAT, multi-resource constraints and approval histories. Add transparent alternative/sensitivity comparisons and infeasibility explanations where missing. | Independent objective/utilization checks, infeasible/unknown outcomes, explicit assumptions, source changes invalidate new approval, preserved history. Existing vetted solver. | Locally accepted; deployment separate |
| P2.6 / 61 | Missing | Local company worksheets already implement mappings, explicit FX, balanced user eliminations and protected exports. Add/verify explicit consolidation grant and current access to every source. | Synthetic companies, missing periods/FX/nonadditive metrics, exact layers, revoked grant/result/export denial, no private automatic merge. | Locally accepted; deployment separate |
| P2.7 / 62 | Partial | Reuse issuer-scoped hashed keys, outbox/signature/retry engine. Extend allowed saved analysis/forecast/job status surfaces through existing services and local loopback receiver tests. | Scope/expiry/revocation/quotas, row/column privacy, deterministic payloads, retry/idempotency and SSRF defenses. Real delivery disabled. | Locally accepted; deployment separate |
| P2.8 / 63 | Missing | Reuse existing one-use host-bound embed grants and dashboard-only sessions; verify local host, short expiry/revocation and protected exports. | Valid/forged/expired/wrong-host/wrong-tenant/session escalation, response/frame policy and local browser embedding. No external hosting. | Locally accepted; deployment separate |
| P2.9 / 64 | Partial | Extend existing server-side source policy/replay guards to every new route and artifact. Audit aggregate/profile/suggestions/cache/error paths and existing method-specific sample bounds; no aggregate-only anonymity guarantee. | Permission matrix across source, query, saved result, search, forecast, export, integration and embed; grant/revoke races and redacted audit events. | Locally accepted; deployment separate |
| P2.10 / 1–64 applicable | Mixed | Connect supported lifecycle steps through existing Simple/Expert views and contextual actions, preserving the always-open Overview repair. | Full synthetic lifecycle, keyboard/mobile/reduced-motion, evidence/units/missing-input labels, explicit recommendation review and later actuals. | Locally accepted; deployment separate |

## Regression and acceptance records

The implemented standalone contribution method compares explicit authorized
sources/windows and preserve group row counts alongside exact differences.
Absent groups and zero-valued groups must remain distinguishable. Eligible
price/volume/mix decomposition uses declared compatible quantity/currency fields,
an explicit formula order and a matched-product cohort. Entry/exit amounts are
separate contributions; unknown counterfactual prices are never filled in.
Nonterminating ratios must retain exact rational numerators/denominators with
clearly marked display rounding, so the accounting identity reconciles exactly.
Observed contributions never become a causal explanation.

Existing cell grants authorize particular source rows/fields. They are not an
aggregate-only anonymity guarantee. New outputs must never read hidden cells or
silently offer an unsupported anonymized sharing mode; all source grants and
stronger private ownership must be rechecked before replay and export.

The 37 protected October 13 requirements are **2–12, 16–23, 25–27, 29–32,
34–39, 41, 48, 49, 51 and 60**. Their existing code paths, immutable receipts,
access boundaries and tested limitations remain part of the regression matrix.
Final traceability will map every ID to named tests and actual run evidence;
overlapping focused runs must not be added as distinct full-suite passes.

Excluded external requirements remain **15, live delivery in 24, 28, 52–55** and
external acceptance portions of **40, 42, 44, 45, 62 and 63**. No payment activation,
email identity verification, provider invoice, production security, current live
restore, regulated compliance or competitor parity is inferred from local tests.

## Execution record

- Initial audit: existing 0024 foundation inspected; baseline is running before
  application changes. Native credentials, persistent onboarding, broad plan
  entitlements and several advanced-analysis/distribution increments remain real
  local work. The implementation matrices are preliminary until focused audits finish.
- Baseline frontend unit tests (59), TypeScript, ESLint, production build, Ruff and
  mypy (262 files) pass. The full backend passes 2,380 tests with no failures/skips
  and one warning in 1,481.91 seconds. The offline browser baseline is 68 passes,
  four pre-existing Radix interaction failures and three explicit model skips in
  801.278 seconds. Retain those failures and verify their correction separately.
- An additional pre-change synthetic probe finds that identical fixed-timestamp
  report input produces different PDF, XLSX and CSV-bundle bytes when generated
  two seconds apart. Retained evidence: `audit/export-determinism-before.json`.
  This is a newly observed gap in the requested deterministic-generation contract,
  not a failing existing baseline test. Excel also uses generic `Result N` sheet
  names and needs a clearer summary/methodology structure.
- Native-account audit identifies email-only invitation acceptance as unsafe for
  self-asserted signup addresses. Preserve operator identities; require explicit
  account-bound approval for native invitees. Consolidation similarly needs
  explicit organization-owner authority in addition to access to every source.
- Final verification documents, per-ID outcomes and local operator instructions
  will be completed from observed results, not from this plan alone.

- Phase 1 focused implementation: deterministic exact exports and meaningful
  worksheets pass their 200,000-cell boundary; request metrics/alerts extend the
  existing incident collector on additive 0027. Local accounts/onboarding use
  0025; local price-free quotas use 0026. All have focused checks in progress.
  Fifty final incident/architecture checks pass in 23.59 seconds; thirty-six
  overlapping export/metric/legacy regression checks pass in 31.76 seconds.
  Initial SQL rowcount, fixture-property and missing forecast import failures
  remain recorded. Full Phase 1 acceptance and browser gate are still pending.

- Independent review caught a metrics-only shutdown gap. Graceful shutdown now
  makes one bounded flush for pending observations/retry batches and collector
  counters as well as incidents. All 28 metric tests pass in 6.38 seconds, including
  both shutdown states. Local request logging explicitly enables only the
  fixed-metadata logger. Desktop/mobile captures were inspected; a checkbox
  alignment repair will be covered by the fresh browser gate.

- Export source review also identified worksheet temporary-file retention after
  invalid methodology metadata. Prevalidation, lossless numbered long-text cells
  and owned-writer cleanup now pass 27 focused checks in 17.21 seconds. Full Ruff
  and mypy (285 files) pass; initial import/style/type failures remain retained.

## October 17 — Phase 1 acceptance checkpoint

The local Phase 1 gate is accepted. All **2,580 backend/architecture cases** have
passing latest executions across the retained full run and focused test-harness
repairs. Nine original failures remain recorded; every collected per-file count
matches execution, and all 37 original requirement mappings pass. Five generated
XLSX node aliases are independently proven to contain unchanged worksheet/member
bytes with only core timestamp differences. This is combined evidence, not a clean
single full-suite claim.

Frontend unit tests (59), types/lint/build and 76 distinct offline browser journeys
pass; three model-dependent browser cases are explicitly skipped. The onboarding
journey additionally verifies successful Finish and reopened state without claiming
skipped work. Exact exports, 40-case/112-check offline evaluation, disposable 0027
recovery and same-fixture performance comparisons pass within their stated bounds.
A separate nine-API first/warm measurement covers the new account/guide/plan/incident
paths with 36 timed requests and privacy/version checks. See the Phase 1 ledger for
commands, mixed timings and retained failure evidence.

Root checkpointed reviewed Phase 1 files as `2ee7d9c`. The connector candidate
subsequently passed its combined checks and was integrated as the true two-parent
merge `142a7dd`, with 0028→0027 and 0029→0028 and all 17 existing working-file hashes
preserved. Its isolated worktree/evidence remain retained; no push was made.

Phase 2 is locally accepted: 2,932 frozen backend tests pass in2,333.55 seconds;
explicit repaired-source supplements reconcile the current2,937 cases with no
missing, skipped or unresolved backend nodes. All37 original requirement mappings
pass. Browser evidence reconciles107 latest passes and3 named model-only skips. The
separately authorized private-VPS candidate now targets **0029**, not the earlier
0027 preparation. Its immutable image checks pass; activation still requires the
full gate, checked backup and original database/object/configuration preservation.
The separately accepted CSS release leaves the current live backend on0020.

## Final local acceptance

Both phases are complete within their documented local scope. All20 targeted IDs
have delivered independently testable behavior; wider feature status and external
gates remain explicit in the [final report](codex-two-phase-final-report.md).
The ledger is41 Done /17 Partial /6 Not yet, preserving all64 IDs and8 open
production gates. Private release4fff22633f0c5f44 is independently gated below
local acceptance; its prepared images have not yet been activated at this checkpoint.
