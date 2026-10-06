> **File use case:** Persistent handoff and operating guide for humans and coding agents working on ExecPlus.
> **What it does:** Records current state, non-negotiable rules, commands, boundaries, and the next approved slice of work.

# ExecPlus Engineering Handoff

Read this file, `ROADMAP.md`, and `docs/decisions/architecture.md` before changing the project.

## Current state

- October 6 internal operations slice is Complete for local/test and the private
  demo: separate operator-managed staff grants, metadata-only admin console, private
  support lifecycle and aggregate product usage/cohorts. Phase 5 remains In progress;
  this delivery does not complete commercial readiness or broader performance work.
  Read `docs/operations-gap-audit.md`, `docs/operations-console-support.md`,
  `docs/verification-operations.md` and ADR 0009 before extending.
- Current readiness is **0015**. Staff grants never imply workspace membership or
  source/analysis access. Support tickets belong to their requester and active staff;
  ordinary workspace owners cannot read another member's private requests. Status,
  replies and assignment use bounded immutable events and optimistic versions.
  No external support message/email is sent. CLI grant/revoke and staff operations
  retain identifier/outcome audit; support text stays out of general logs/audit.
- Usage-v1 reports use one PostgreSQL statement snapshot, explicit deliberate-action
  definitions, UTC weeks, historical cohort denominators and current-member cards.
  Incomplete weeks stay null; inactivity is a rule, not predicted churn. Large
  integers remain exact strings at HTTP boundaries. Old usage/onboarding response
  shapes remain compatible; the legacy usage-event list is still unbounded.
- Operations checks pass **869 backend/architecture cases** (53 new), nine frontend
  tests, 24 real-service browser journeys, Ruff/mypy (148 files), types/lint/build,
  clean-image computations and six old receipt/forecast compatibility checks.
  All eight deployed users passed support history and reports, 36 protected-access
  denials with 36 authorized controls, and desktop/mobile checks in 114.171 seconds.
  This is a functional rehearsal, not sustained-load or production acceptance.
- Measured local 100k-event overview median improves 1,934.907 to 241.882 ms with
  independent result parity; resource-total queries fall from 26 to one. The new
  report remains one snapshot under eight concurrent calls. Initial compressed
  browser JavaScript is 7.64% smaller. Timings exclude HTTP/network/browser overhead;
  representative alpha performance remains open. No unproven index/cache was added.
- Migration 0015 preserved all forty existing data tables' hashes/counts. Source and
  image checkpoint is `pre-operations-20261006`; checked pre-release backup is
  `20261006T080234Z`. Checked post-release backup `20261006T082942Z` stopped API/jobs
  before storage, then restarted with healthy readiness. Preserve all new staff,
  ticket, event and audit data plus forecasts/jobs/profile versions before rollback;
  old images expect 0014. Only the first existing demo account received admin staff
  access. Models, network exposure and all eight production gates are unchanged.
- October 6 forecast/audit and operations work remain uncommitted on `phase2` at
  baseline `9c2445d`; this delivery did not push or merge. Phase 4D/4E remain unfinished,
  and Phase 6 remains Frozen. Refresh and backup timers remain active.
- The user requested ongoing DOCX upkeep after verified deliveries. Maintain the
  original 64 feature IDs in `docs/product-feature-audit.json` and use
  `scripts/build_feature_report.py` to regenerate the Desktop report with backups.
  Current report includes Phase 4C and operations: **36 Done / 13 Partial / 15 Not yet**.
  Performance remains Partial pending representative alpha acceptance. Both Desktop
  DOCX filenames and the October 6 PDF are updated; all 64 original feature IDs,
  ten-page layout and October 5 competitor review are retained. Previous reports
  are backed up under ignored `data/reports/2026-10-06/`. Optional `python-docx`
  tooling lives in `data/report-tools`; it is not an application dependency.
- October 6 VC priorities 34–39 implement basic forecasting, error measurement,
  actual comparisons, grounded commentary and searchable audit history, reusing
  existing scheduled staged-file refresh. Phase 4C is Complete for local/test and
  the private demo; all eight deployed browsers pass. Read `docs/phase4c-gap-audit.md`,
  `docs/phase4-forecasting.md`, `docs/audit-history.md` and
  `docs/verification-phase4c.md` before extending.
- Phase 4C introduced migration **0014**, with private immutable forecast and
  comparison records. Daily/monthly series require confirmed meaning, explicit units
  and declared complete periods. Three exact source receipts reconstruct each series;
  reopening verifies source bytes, method, parameters, result and current permissions.
  Preserved actuals remain Decimal strings; forecasts are labelled estimates.
- Runtime methods are bounded standard-library last value, recent mean, linear trend
  and explicitly eligible seasonal naive. Selection uses validation MAE before the
  untouched test window. Errors, naive benchmark and heuristic ranges are disclosed;
  ranges are not calibrated confidence intervals. ARIMA/Prophet were researched in
  isolation and are not runtime dependencies. Forecasts/commentary never ask an LLM
  to calculate. Missing later actuals remain pending; refresh does not auto-retrain.
- The upload flow offers descriptive, basic predictive and all-supported analysis;
  prescriptive remains planned. Forecasts and Audit history have dedicated views;
  a fifth fictional sample is `forecast-v1`. Existing sample bytes remain frozen.
  Audit visibility runs before bounded pagination and retains others' private events
  as private, including for workspace managers. New actions default to actor-only.
- October 6 checks: **816 backend/architecture cases** (118 new), nine frontend tests,
  20 real-service browser journeys, Ruff/mypy (136 files), web lint/types/build pass.
  The clean non-root image passes eight concurrent exact/calendar/forecast journeys
  without optional scientific libraries or network access. Four old profile-v1/v2
  live receipts pass independent typed-checksum replay. Production gates stay blocked.
- Eight deployed browsers created eight forecasts and eight actual comparisons,
  preserved all originals, reopened sixteen saved results and replayed 48 exact
  source receipts. Sixteen cross-user denials, sixteen private-audit probes, eight
  audit searches and 1440/390/320-pixel layouts pass. Total rehearsal was 55.048s;
  this is functional evidence, not sustained load or customer accuracy acceptance.
  The first run's form-selector timeout submitted no forecasts and is retained;
  corrected combobox-role selectors required no runtime change. Sessions remain
  private in ignored `data/vps-private/sessions.json`; model/network settings stayed
  unchanged.
- The 0014 migration preserved hashes/counts of all 38 existing data tables, including
  2,909 query executions. Checkpoint source/images use `pre-phase4c-20261006` and
  pre-release checked backup is `20261006T063824Z`. Preserve new forecast/comparison
  metadata as well as 0013 jobs and profile-v2 compatibility during rollback.
- Post-release backup `20261006T065810Z` stopped API/jobs before storage, verified
  database/object checksums and restarted services successfully. Refresh and backup
  timers remain active. New forecast metadata must survive any rollback.
- Baseline `phase2` commit `9c2445d` now contains the September 30/October 2 repairs
  and Foundation A. October 6 forecasting/audit changes remain uncommitted; this work
  has not pushed or merged. Phase 4D exports and 4E connectors remain Planned,
  Phase 6 Frozen and all eight production gates remain blocked.
- October 4 Foundation A is Complete for local/test and the private demo: additive
  artifact/capability and quality projections, compatible bounded compute, durable
  private conversation jobs and real action activity with resume/cancellation.
  The audited proposal is sequenced in `docs/platform-foundation-plan.md` and
  ADR 0008; read `docs/verification-platform-foundation.md` before extending.
- Migration 0013 adds jobs/attempts/events and fenced turn linkage. The VPS has a
  separate bounded `jobs` container using the API image, four slots and a default
  two active jobs per workspace. Local development now needs `make jobs`. Stop
  API/jobs before object storage during backups; refresh retains the maintenance
  lock. Preserve 0013 metadata and profile-v2 compatibility during rollback.
- Foundation evidence: 689 full backend/architecture cases plus nine later reader
  cleanup/CLI cases (698 distinct, 97 new), seven frontend tests, 18 real-service
  browser journeys, Ruff/mypy (128 files), types/lint and production builds pass.
  Eight deployed browsers passed 56 exact receipt replays, 18 jobs, 204 recorded
  events, 32 private-access denials and desktop/mobile checks. Eight concurrent
  clean-image computations and original profile-v1/v2 receipt replay also pass.
- Existing 35 control-plane tables, including 2,497 receipts and 85 turns, retained
  their aggregate hashes/counts through migration. Checkpoint source/images use
  `pre-foundation-20261004`; pre-release backup is `20261004T111433Z`. The corrected
  API image makes packaged files readable by its non-root runtime; retain that
  clean-image check. Worker-aware backup `20261004T113138Z` stopped both writers
  before storage, verified checksums and restarted services successfully.
- Activity events contain server-owned actions, never model chain-of-thought,
  prompts or source values. Only supported server-derived plans are recorded;
  no arbitrary DAG/code executes. Simple/Expert changes presentation. Artifact
  metadata is not byte-integrity proof; labelled quality heuristics are not confirmed
  errors. Legacy `/ask`, exact numerical wire formats and replay remain supported.
- Cancellation is cooperative and waits for reader/query cleanup. Safe pre-start
  claims can retry, while lost started work fails conservatively; do not claim
  exactly-once execution. Worker fatal logs use fixed codes, and SIGTERM awaits
  cleanup. Model attempts count actual HTTP retries; three logical calls/seven
  provider attempts and a default 100-second execution/publication deadline apply.
- The initial eight-browser attempt stopped at sign-in because its local SSH tunnel
  stalled; it created no jobs. The reconnect and fresh eight-user pass are retained
  separately. Measured total jobs took 12.072–27.777 seconds including queue time;
  this is a short functional rehearsal, not a sustained-load or speed improvement
  claim. Sessions were renewed privately. Models, environment files, network
  exposure and production gates did not change.
- At the October 4 checkpoint, September 30/October 2 changes and Foundation A
  were uncommitted; baseline `9c2445d` now preserves them. Preparation, broader
  statistics, sandbox, ML and connector extensions remain mapped future work.
- Phase 0: Engineering Foundation remains complete; its four exit criteria were reverified on 2026-09-07.
- The repository is a Python and TypeScript modular monorepo.
- The API has liveness and dependency-aware readiness endpoints for migrated PostgreSQL and the configured object bucket.
- Language models and vector databases are represented by provider-neutral protocols.
- No vector database vendor has been selected.
- The local-model path expects an OpenAI-compatible endpoint so Ollama, vLLM, or another server can be evaluated later.
- Runtime model selection is composed in `execplus/bootstrap.py`; routes and use cases must not branch on vendors.
- Metadata profiling uses deterministic standard-library computation; DuckDB now executes validated Phase 2 snapshot queries.
- PostgreSQL is reserved for control-plane metadata, permissions, conversations, lineage, and audit records.
- MinIO provides an S3-compatible local object-store target.
- Week 1 implements local/test opaque-session identity behind an identity port; production identity remains a separate decision.
- Workspaces, roles, invitations, seat limits, retained CSV/XLSX uploads, and audit events have real PostgreSQL/MinIO integration coverage.
- Phase 1 is complete for supported local/test operation as of 2026-09-08.
- Profiles, quality scores, immutable cleaning/mapping recipes, synthetic samples, onboarding and usage foundations are implemented.
- Phase 2 was audited from teammate commit `7d70cd7`; verified local/test analytics now include exact decimals, isolated SQL, replayable receipts, private threads and workspace sharing.
- Current Phase 4B evidence: 458 backend tests on isolated PostgreSQL/MinIO plus 46 final targeted hardening/foundation checks, 2 frontend tests, 10 real-service browser journeys including live mixed chat, plus a final refresh journey after declaring the upload parser. Ruff/mypy (109 files), TypeScript, lint and production builds pass. All 8/8 concurrent deployed refresh browsers passed exact activation, alerts, original evidence replay and mobile layout. See `docs/verification-phase4b.md`; this is not a sustained-load benchmark.
- Phase 3 is Complete for the approved local/test and private-demo scope as of 2026-09-30; its approved fictional demo is verified: six documents, twenty known answers, 16/16 top-three retrieval and 20/20 live DeepSeek cases. Production evaluation work is deferred with mandatory gates.
- Document passages live in object storage; metadata and immutable citation offsets live in PostgreSQL. The reference hybrid ranker is not a selected production vector provider.
- Migration 0006 adds execution receipts; 0007 adds activation/document/report metadata; 0008 adds record/overview conversation kinds and model routes; 0009 adds immutable business meanings and private goals. Migration 0011 adds organizations/departments, study versions, six-pin boards and private view dismissals; migration 0012 adds staged refresh heads/candidates, monitoring jobs and private alerts. Foundation A deployed 0013; October 6 advances readiness to 0014 as described above. Legacy executions without receipts cannot be replayed reliably.
- Reports default to disabled email. `python3 -m execplus.manage deliver-reports` processes due slots; SMTP delivery needs explicit operator configuration. No real email was sent during verification.
- Decimal results and integers outside JavaScript's safe range are JSON strings. Preserve this wire contract and frozen profile-v1 reconstruction.
- Runtime model summaries select server-rendered evidence statements; never restore free-form prose guarded only by a number regex.
- Migration 0002 preserves uploads; existing uploads receive their initial profile on first access.
- Preserve profile-v1 reconstruction semantics and synthetic sample versions; introduce new versions for incompatible changes.
- On 2026-09-17 the user approved fictional demo documents/answers and hosted DeepSeek V4 Pro for current development. Generated material lives in ignored `data/phase3-demo-v1/`; recreate with `make demo-corpus`.
- The existing provider-neutral adapter uses `https://api.deepseek.com`, model `deepseek-v4-pro`, reasoning disabled, explicit JSON mode and a 1024-token response limit. Credentials stay in ignored `.env`.
- On 2026-09-17 the user identified `Qwen/Qwen3-4B` as the intended model candidate; the VPS trial below supersedes the then-pending hosting request. It is not selected for production. See `docs/ceo-request-qwen-hosting.md` for the original request and remaining pre-production needs.
- On 2026-09-28 the user authorized a private VPS demo for about eight users and deferred domain/public access. The VPS runs an isolated Qwen3-4B Q4_K_M service, API, web, PostgreSQL and MinIO. The subsequent explorer request selected hosted DeepSeek V4 Pro as primary, with Qwen for advisory route/column selection and summary evidence selection. Bootstrap composes separate provider-neutral adapters; routes must not branch on vendors. Local development `.env` remains unchanged. Historical Q4/Q8 document scores (19/20 and 16/20) do not clear production quality gates.
- The private workspace now includes a column/flow diagram, chart interactions, reduced-motion support, paired chat turns, bounded record queries and the fictional `cities-v1` sample. Record responses add `matched_records` while preserving `records_analyzed` and historical checksum semantics. Invalid/unavailable helper hints fall back to primary planning; the primary retains the full schema. See `docs/conversational-explorer.md`.
- Model files live under `/sdb-disk/AIML-Models/OISOL_ExecPLUS`; app/data/secrets/backups live under `/sdb-disk/OISOL_ExecPLUS`. Other VPS applications and their ports remain separate. Eight short-lived app sessions and individual restricted SSH keys support private access on ports 18400/18401. Never publish credentials, private keys or generated demo data.
- Daily private-demo backups run at 03:00 UTC and briefly pause ExecPlus writes. A separate restore verified migration 0007 and all nine seed objects. Off-server disaster recovery and production validation remain open. Read `docs/vps-demo-runbook.md` before operating the VPS.
- Representative-customer, learned embedding/vector-provider, local/hosted comparison and operational production reviews were explicitly deferred to Phase 5, before any external customer deployment. Track them in `docs/production-readiness.json`.
- `make production-preflight` and production runtime construction require reviewed evidence with intact artifact checksums. Demo completion must never clear those production gates.
- No product feature should be represented as implemented unless tests prove it.
- On 2026-09-30 the user requested a roadmap revision for a persistent data partner and then authorized starting Phase 3. Slice 3A is Complete for the private demo; 3B–3C are verified locally and deployed, 3D is complete as a reviewed rejection of the optional judge, and Phase 4A (adaptive dashboards/studies) and 4B (refresh/alerts) are Complete for the private demo. The October 6 entry governs subsequent 4C forecasting; exports and first connectors remain Planned.
- Google Sheets and a read-only PostgreSQL source are now planned in Phase 4E after semantic and refresh foundations. Broader connectors, new file formats and advanced research/decision methods remain Frozen in Phase 6. No new connector, production learned search provider, runtime judge or Parquet serving optimization is selected. Unified document/data chat is now implemented in 3B.
- Phase 3A implements optional domain/goal prompts, inferred row/column meaning, focused confirmation, versioned workspace definitions, reviewed declared relationships and inspectable history. Only the dataset creator or owner/admin edits shared meaning; goals remain private. Saved unconfirmed/stale definitions block new calculations. Sources without saved meaning retain their legacy inferred behavior. Read `docs/phase3-data-understanding.md` before extending.
- Confirmed roles, metric aggregation/required filters and unit rules apply to planners, dashboards and joins. Receipts retain understanding IDs; replay uses original definitions. Changed definitions during planning clarify before execution. Joined right-side measures require unique left keys as well as the existing right-key guard. No automatic conversion, join discovery or scheduled refresh is implied. Phase 4A now adds goal-aware recommendations in the separate Studies & dashboards view.
- Slices 3B–3C are verified locally and deployed: bounded mixed document/data chat, private history, retry idempotency, current authorized catalog and measured offline representations. Migration 0010 adds durable turn claims/evidence references. See `docs/phase3-unified-conversation.md` and `docs/verification-phase3b-c.md`. VPS deployment verification is recorded in that ledger.
- The learned search candidate failed (18/21 versus reference 20/21); typed Parquet preserved exact results and improved repeat-query timings but is not adopted without lifecycle integration. No persistent cache was added. `docs/decisions/0007-representation-and-judge-trials.md` records the decision.
- Phase 3D is Complete: the user explicitly approved all twelve labels on September 30, followed by a fresh DeepSeek V4 Pro trial with 5/12 exact matches, six timeouts, one misclassified defect and p95 10012.89 ms. The judge is rejected and remains disabled. See `docs/verification-phase3d.md`; this closes the assessment, not production acceptance.
- The September 30 final judge evaluator now binds reviews to case/rubric hashes, refuses changed or incomplete observations and preserves prior reports. 34 targeted evaluation/architecture tests plus Ruff/mypy pass. See `docs/phase3-judge-evaluation.md`. A reviewed run requires explicit `--review`; unreviewed runs require `--preliminary` and a fresh output path. Human approval and the reviewed run are now recorded; no repeat label approval is needed for these unchanged cases.
- The preceding 0010 release passed 5/5 live combined-conversation/catalog checks. Backup `20260930T095357Z`, `pre-phase3bc` image tags and `releases/pre-phase3bc-source` preserve 3A. The user authorized starting Phase 4 on September 30; 4A is now verified and deployed on 0011. The September 30 target does not waive live-source rehearsals, external setup, or any of the eight production gates. Private-demo backup `20260930T053553Z`, rollback images tagged `pre-phase3a`, and `releases/pre-phase3a-source` preserve the preceding release. Eight sessions were renewed into ignored `data/vps-private/sessions.json`; never publish their tokens.

- Phase 4A is Complete for the approved local/test and private-demo scope. New studies
  require confirmed meaning and explicit units; deterministic domain/goal suggestions,
  ordered distributions, missingness/coverage, immutable study runs and exact comparisons
  preserve receipts. Private goals are never copied into shared study evidence.
- Six-pin dashboards enforce ownership, explicit study sharing, current access and
  optimistic edits. Departments are separate workspaces grouped under an organization;
  organization ownership/membership never grants workspace data access.
- The 4A release verified migration 0011; 4B now runs 0012 below. Backup `20260930T131523Z`, images tagged `pre-phase4a`
  and `releases/pre-phase4a-source` preserve the preceding release. Eight simultaneous
  study browsers passed on September 30; no production gate or model configuration changed.
- Phase 4B is Complete for local/test and the private demo. Scheduled refresh consumes
  staged CSV/XLSX files, validates before activation, preserves prior sources on failure,
  and requires explicit replacement/append/merge and keyed duplicate behavior. Schema
  drift and changed meaning need review. The catalog/default selection follows the feed head.
- At most six shared active monitors per dataset capture immutable sources and governed
  methods. Queries calculate metric/sample/present counts and optional SUM segments;
  comparisons and drivers replay receipts. Complete-month comparisons require declared
  coverage. No driver is a causal claim. Alerts are self-subscribed, private, in-app,
  transactional, cooldown-limited and permission/freshness/coverage checked at delivery.
- `python3 -m execplus.manage process-refreshes` runs bounded durable jobs. The VPS
  `execplus-refresh.timer` runs every minute, sharing `/run/lock/execplus-maintenance.lock`
  with backups. Do not run an uncoordinated worker during a backup. The explicit
  `python-multipart>=0.0.32,<0.1` runtime dependency is required for staged-file intake.
- VPS 0012 is healthy; backup `20260930T141138Z`, `pre-phase4b` images and
  `releases/pre-phase4b-source` preserve 0011. Eight private sessions were renewed after
  expiry. Fictional refresh walkthrough workspaces show an exact 0.30 to 0.50 PKR update.
  All eight production gates remain blocked, and model/network settings did not change.
- The 4B release did not implement forecasts, exports or connectors. Its baseline
  was `c9560af`; the subsequent repairs are now retained in `9c2445d`.
- September 30 spreadsheet repair is verified and deployed: per-column decimal
  scale expands from twelve only when needed, within 38 digits; query projection
  includes filter/group/join dependencies and preserves column-free sample counts.
  Referenced invalid cells identify column/data-row/expected type without contents.
  Profile-v1, ordinary decimal wire formatting, full-source receipts and AVG rounding
  are unchanged. Never silently round or skip problematic source values.
- Repair evidence: 485 backend tests pass, including 24 new regressions; Ruff/mypy
  pass; all 160 numeric totals in the reported upload match independent Decimal sums.
  Live dashboard, exact reported question, five API totals/replays and an older
  monitoring replay pass. See `docs/verification-query-precision.md`. API rollback
  image is `pre-queryfix-20260930`; no migration or production gate changed.
- September 30 column-explanation repair is verified and deployed. Chat now matches
  column names (including spaces/underscores), explains actual metadata and saved
  meanings, labels inferred/common meanings, and retains column context for “??”
  and related-value follow-ups. A model may select known columns but cannot author
  these explanations. Guidance never auto-confirms shared meaning or enables a
  blocked calculation. No business unit/currency is inferred from ERP labels.
- `overview` answers add `guidance` and immutable `sources`. Private turns retain
  versioned explanation evidence; reopening checks original source bytes/definitions.
  Explanations remain available for unconfirmed meaning, with calculation guards
  intact. The UI shows paragraphs, relevant question buttons and source details;
  only executed numerical answers receive the Verified badge.
- September 30 evidence: 512 backend/architecture tests, 2 frontend tests, 11 real-service
  browser journeys (including live mixed chat), Ruff/mypy (110 files), web lint/types
  and production build all pass. The four reported ERP questions and a subsequent
  exact total passed live on the private VPS. See `docs/dataset-guidance.md` and
  `docs/verification-dataset-guidance.md`. API/web rollback images use
  `pre-guidance-20260930`; no migration, model configuration or production gate changed.

- October 2 upload-first data partner repair is verified and deployed for the private
  demo. First upload supplies a personal workspace and file-named dataset; optional
  setup and advanced forms no longer precede useful findings. Discovery executes at
  most seven governed queries, shows exact evidence and supplies relevant chat prompts.
  It never silently confirms business meanings or guesses a revenue formula/currency.
- New ordinary files use profile-v2 for label-based identifiers and valid calendar
  components. Cleaning/refresh inherit their source version. Profile-v1 functions,
  old receipts and synthetic sample versions remain frozen. Stored CSV dialects add
  UTF-8 semicolon/tab intake without redetecting historical comma files. No migration.
- Discovery reuses one parsed snapshot, moves source I/O off the event loop and
  rechecks permission/revision/meaning around a final checksum read. The browser
  debounces/aborts superseded requests; the API stops abandoned queries while retaining
  failed/completed receipts. Chat no longer duplicates parsing for starter questions.
- DuckDB now binds bounded JSON column parameters after strict source conversion,
  with fixed-point decimal strings and explicit SQL types. This fixes repeated missing
  optional-library imports measured in the clean VPS image. It adds no dependency,
  JSON file intake, persistent cache or Parquet adoption. Query limits and precision
  contracts are unchanged; keep minimal-runtime checks in future verification.
- Latest evidence: 601 backend/architecture tests (89 new regressions), 2 frontend
  tests, 14 real-service browser journeys plus 4 final targeted checks, Ruff/mypy
  (113 files), web lint/types and production builds pass. Live public-data evaluation
  passes 24/24. All 8/8 deployed users saw seven findings and replayed seven receipts;
  live filtered follow-ups and mobile layouts passed. This is a short functional
  rehearsal, not sustained-load or production acceptance. Failed runs remain retained.
- The **Public banking and retail walkthrough** workspace contains the attributed UCI
  4,521-row bank CSV and a disclosed first-10,000-row retail XLSX subset, shared with
  the eight demo accounts. Original archives, provenance, tests and reports live in
  ignored `data/realdata-evaluation/`; credentials remain in ignored `data/vps-private/`.
  See `docs/data-partner-reset.md` and `docs/verification-data-partner.md`.
- October 2 checkpoint: `releases/pre-partner-20261002/source`, images tagged
  `pre-partner-20261002`, backup `20261002T035155Z`. Readiness stays on 0012. Older
  v1-only images cannot read new v2 revisions: preserve new metadata and account for
  compatibility before rollback. Models, network exposure and all eight production
  gates were unchanged. At that checkpoint Phase 4C–4E remained planned;
  the October 6 entry records subsequent work. Phase 6 remains frozen.

## Non-negotiable engineering rules

1. Never ask an LLM to calculate or supply a business number.
2. Execute validated, read-only queries and build answers from returned results.
3. Scope every resource lookup and mutation by `workspace_id`.
4. Apply permissions before query execution and before hybrid retrieval.
5. Return clarification for ambiguous requests and a supported-scope explanation for impossible requests.
6. Record model route, generated query, execution outcome, lineage, and returned answer in the audit trail.
7. Keep domain and application modules independent from web frameworks and infrastructure SDKs.
8. Add or update tests with each behavior change.
9. Update `ROADMAP.md` and this current-state section only when evidence supports the status change.
10. Do not commit datasets, secrets, model weights, generated exports, or local database volumes.
11. Put a file-level use-case and responsibility header at the top of every new file.
12. Do not add inline explanatory comments; prefer clear names, small functions, tests, and architecture documents.
13. Next.js can regenerate `next-env.d.ts`; restore its required file-purpose header before committing.
14. After each verified feature delivery, update the maintained 64-item VC audit and
    DOCX report together. Preserve prior report copies, evidence and the competitor
    review date; do not promote statuses from intent or clear production gates.

## Dependency direction

```text
presentation -> application -> domain
infrastructure -> application ports and domain
domain -> standard library only
```

Framework imports are forbidden in `execplus/domain`. Application services depend on protocols in `execplus/application/ports.py`, not concrete providers.

## Commands

```bash
make install
make check
make test
make api
make web
make dev-infra
make down
```


## Definition of done

- Acceptance criteria have automated coverage.
- Unit tests and architecture tests pass.
- Static analysis passes.
- Tenant isolation and numerical lineage are considered explicitly.
- Public contracts and configuration are documented.
- Logs contain identifiers and outcomes, not uploaded row values or secrets.
- Roadmap and handoff state reflect the tested implementation.

## Next approved slice

The user authorized auditing the teammate's Phase 2 branch and proceeding into
Phase 3, followed by the private explorer and the September 30 roadmap revision.
Work is on local branch `phase2`, with baseline `9c2445d` preserving earlier work,
including the teammate's original `7d70cd7` and the later query/guidance repairs.
October 6 changes are uncommitted; this task did not push or merge into main.
Keep `.env` and customer documents out of version control.

Phase 2 acceptance is verified for local/test operation. Current Phase 3 work uses
the user-approved fictional corpus and private VPS explorer, with DeepSeek primary planning
and Qwen3-4B advisory routing/evidence selection. The requested interactive explorer is
verified and deployed. The user has now authorized Phase 4; 4A is verified and deployed.
The user instructed completion of Phase 3 and then explicitly approved the twelve
judge labels. Phase 3A–3C are verified and deployed; Phase 3D's reviewed assessment
is complete with a do-not-adopt decision. Phase 3 is Complete for the private-demo
scope. Phase 4 was subsequently authorized; 4A is verified and deployed while the
explicitly deferred production reviews remain open. Do not
interpret the requested same-day deadline as acceptance evidence or silently
start Phase 6. Keep experimental optimization/judge adoption separate from claims
that those components improve quality or performance.
The user approved the private eight-user/investor demo slice; public customer access
and a domain are deferred. Do not expose the local/test identity deployment publicly.
Use `make evaluate-demo`
and `make evaluate-demo-model`; report any failures honestly. No customer corpus is
needed for this demo milestone. Representative-customer, model/provider, privacy,
restore and operational validation remains mandatory before production under Phase 5.
Do not mark these deferred gates passed from demo results. Phase 3A updated the
private VPS runtime without changing its network exposure. Read
`ROADMAP.md`, `docs/phase3-demo-and-production-gates.md`,
`docs/phase3-activation-knowledge.md`, `docs/phase3-data-understanding.md` and the
verification records before extending. Phase 4 is now authorized; Phase 6 remains frozen.

Phase 4 was authorized by “start phase4” on September 30. Read
`docs/phase4-gap-audit.md` and `docs/phase4-studies.md` for the audited gaps and
4A contracts. Preserve the previous source/image/database checkpoint before
any VPS migration. Phase 4 completion requires its own exit evidence.


The user's “start 4b?” instruction authorized the completed 4B slice. Read
`docs/phase4b-gap-audit.md`, `docs/phase4-refresh-monitoring.md` and
`docs/verification-phase4b.md` before extending. Local checks and eight deployed
browser journeys verify its private-demo scope. The first clean API startup found
an undeclared multipart package; it was corrected, clean-import checked and all
release checks passed. Do not repeat that partial release as the final state.
The October 6 instruction authorized 4C; 4B itself did not implement forecasts,
exports or connectors.
Preserve the 0011 source/image/database checkpoint and all new 0012 user metadata.

The October 2 user request reprioritized an upload-first, useful private data partner
and authorized public real-data validation. That usability repair is now deployed;
it does not implement the remaining forecasts, exports, connectors or advanced
methods. Read its audit/verification before extending. The September 30 repairs and
October 2 release are now retained in baseline `9c2445d`. Preserve both sets of
changes and exclude private/generated artifacts.

The October 4 request authorized incorporating the supplied platform proposal
without replacing verified primitives. The published A–H audit led to the now
verified Foundation A slice; it did not implement the entire advanced platform.
Read `docs/conversation-jobs.md`, `docs/platform-artifacts-quality.md`,
`docs/compute-broker.md` and ADR 0008 for its contracts. Keep Preparation B through
Integration F aligned with the existing Phase 4/5/6 gates. Baseline `9c2445d` now
retains this release; never stage private sessions, logs or data.

The October 6 request prioritizes VC items 34–36, then existing refresh (37),
management commentary (38) and audit history (39). This authorizes bounded basic
forecasting, its evaluations/comparisons and the private-demo deployment. It does
not unfreeze prescriptive analysis or clear production gates. Read the 4C contract
and verification ledger before continuing. The remaining Phase 4 work is exports
and first controlled connectors; each retains its own acceptance requirements.

The subsequent October 6 instruction explicitly prioritizes admin/support,
performance and usage/retention reporting before continuing exports/connectors.
Deliver this private-demo operations slice with a distinct staff permission boundary,
measured improvements, verified support lifecycle and updated DOCX. It does not
authorize public deployment, source-data impersonation or Phase 6 activation.

The October 6 follow-up explicitly prioritized internal administration, support,
measured performance and product usage/retention from Phase 5. That private-demo
slice is now verified and deployed on 0015; read its operations audit/contracts and
verification before extending. Keep the VC report current after verified deliveries.
Do not infer commercial readiness from the admin/support screens: billing, external
support delivery, representative performance and all eight production gates remain
open. No instruction to start frozen Phase 6 or push these changes was given.
