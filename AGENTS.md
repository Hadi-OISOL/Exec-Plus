> **File use case:** Persistent handoff and operating guide for humans and coding agents working on ExecPlus.
> **What it does:** Records current state, non-negotiable rules, commands, boundaries, and the next approved slice of work.

# ExecPlus Engineering Handoff

Read this file, `ROADMAP.md`, and `docs/decisions/architecture.md` before changing the project.

## User preferences and local working tools

- Explain work in simple English with short, friendly bullets. Lead with what works,
  what changed, what remains and the next step. Explain technical terms when needed;
  report test failures, skipped checks and limitations honestly. Suggest concrete
  improvements without claiming unobserved behavior or full competitor parity.
- Start future sessions by reading `data/agent-memory/context.json` when present,
  then run `python3 data/agent-tools/project.py status`. These ignored local files
  hold compact context and reusable commands; this tracked handoff remains the fallback.
- On October 16 the user explicitly confirmed that this project will remain
  noncommercial. Actual attributed Lieflat template reuse is authorized; preserve
  its license and notices. Earlier reference-only Lieflat and commercial roadmap
  assumptions are historical. Keep original feature IDs/statuses for traceability.
- The user authorizes routine personal-repo pull/push needed for requested project
  work. Use `phase2` and the repo-local Hadi-OISOL SSH identity. Preserve company
  settings, unrelated changes and existing work; never force-push or publish private
  tools, data, credentials, browser profiles or generated reports.
- ThoughtSpot (`https://www.thoughtspot.com/`) is the named product reference.
  Preparation is authorized now; wait for the user's implementation target/start
  instruction before rebuilding a referenced experience. Map each requested feature
  to observed UI/behavior, inferred design, unknown backend details, ExecPlus's
  reusable components, achievable scope and external dependencies.
- REA is installed locally under `data/agent-tools/rea/`; use
  `data/agent-tools/bin/rea`, not a global install or unpinned npx download.
  The project-only MCP registration is `.codex/config.toml`; matching instructions
  are `.agents/skills/reverse-engineer-anything/SKILL.md`. Read that skill before use.
  The CLI works without restarting this chat; MCP discovery depends on the client
  reloading project configuration. Use a separate browser profile for captures.
- Keep memory current after meaningful work. During implementation run relevant
  tests, fix failures, compare supported behavior, and update the evidence/handoff.
  Tool setup does not authorize exposing the private demo publicly, changing model
  providers, clearing production gates or assuming private competitor source access.

## Current state

### October 22 — phase5 merged, cookie sessions and new-user onboarding live

- Merged origin/phase5 (317dc94): control-plane database refused as a connector source;
  Google enabled in local/test keeps LocalSessionIdentity. Commit 14ba1db adds an
  HttpOnly SameSite=Lax `execplus_session` cookie (login/password/Google exchange);
  cookie requests need `X-ExecPlus-Request: 1`; Bearer still works and wins. Web keeps
  no token in storage, restores on load, auto-signs-in after registration and opens
  the first-upload guide. Release **a5d380f2541ef5bd** active on unchanged 0029;
  checked backups 20261022T100453Z (pre) / 20261022T100541Z (post).
- Evidence: backend 264 + 188 + 45 targeted (not full suite); web 93/93, types/lint;
  browser full run 101/17 fail/4 skip, both causes fixed, affected 7 files 41/41.
  Live curl and real-browser journey (sign-up, refresh, disable, sign-in screen) pass;
  both fictional accounts disabled. All tunnel users share the per-IP sign-up limit.
  VC audit/DOCX not updated for this slice.

### October 21 — Claude redesign, analyst overview and zero-config analysis live

- Claude Code took over from Codex. Commits 8cf8f2e..0cde101 (+ follow-up) add: one
  token-based design system (Inter, light/dark), new shell and tabbed Liveboard overview,
  ECharts chart kit, six deterministic cross-checked analysts (`/analyst-overview`,
  `docs/insights-engine.md`), zero-config unusual values, forecast quick start, unit
  suggestions from column names, ranked/offline-capable chat with chart + follow-ups.
- Live fixes found on VPS: top-N by AVG ranked by hidden SUM (executor) and overview
  narrator missing usage scope. Releases 6430e1d89fa1f6ad, 955612bb1c42d2bc, then
  **0849c0684bcb26ed** (commit 33726ed, active) on unchanged 0029; checked backups
  20261020T161935Z, 20261021T042449Z/042618Z, 20261021T092547Z/092614Z.
  Live DeepSeek check: 11 verified cards, 7/7 chat incl. Roman Urdu, correct rankings.
- Owner direction (Oct 20): demo has no users; work directly on the VPS to save tokens,
  still with checked backups. Release kit: `data/verification/2026-10-20-claude-release/`.
- Evidence limits: no single clean full backend run (67% reached, 0 failures) and browser
  full 122-test run: 116 pass/2 fail/4 model skips; both failures pass on rerun (one stale
  selector fixed, one transient fetch). VC audit rows 9/20/34/47/58
  annotated; counts unchanged 41/17/6; DOCX ExecPlus_Latest_Changes_2026-10-21.docx.

### October 19 — Proactive overview and contextual what-if verified live

- Private release **074a5821f55d2aff /0029**, runtime **c5b0b4a**, is active.
  Read `docs/proactive-data-overview.md` and `docs/verification-proactive-data-overview.md`.
  Overview leads with scoped summaries/charts, an automatic bounded structural map and
  eligible explicit what-if shortcuts. Optional reading no longer hides overview/chat.
  Internal details start closed; assumptions and limitations stay visible.
- 217 distinct affected backend cases,72 frontend,5 distinct browser cases, static checks,
  both VPS builds/restricted checks pass. Live4 hosted tasks and overview/scenario/chat
  browser journey pass across3 widths/both themes. Initial failures remain recorded.
- Checked backups **20261019T142919Z /20261019T143504Z**;77 table projections, objects,
  configuration and real sessions preserved. Five services/six loopback listeners,
  readiness/web/model/timers/exact images pass. All5 fictional check accounts revoked.
- No schema/provider/dependency change, push or restore. Maps are structural; what-if
  changes an explicit aggregate, not a causal prediction. Broader production gates remain.


### October 19 — Natural social routing and responsive activity verified live

- Private release **9ce1f703b13b957f /0029**, runtime **07c7b47**, is active.
  Read `docs/verification-conversation-experience.md`. Model-enabled casual talk uses
  a model-selected conversational focus and generated reply, not a how-are-you lookup.
  Mixed data questions retain governed tools. Social prose is not verified analysis;
  heuristic claim filters have documented limits and social report exports are refused.
- Animated activity reflects actual server stages, supports cancellation/reduced motion,
  and keeps recorded actions inspectable. Dark borders/forecast colors and reply hierarchy
  are improved; mobile chat flows with the page while exact tables remain scrollable.
- Local110 broader/31 final social tests overlap;72frontend, types/lint/Ruff/mypy269,
  fresh VPS builds and restricted image checks pass. Browser13pass/1explicit model skip;
  live4 legacy+11 social/mixed cases and3 widths/both themes pass. Initial assertion
  failures retained. Five owned live fictional accounts disabled/revoked; real sessions
  unchanged. No full-repository, universal-language or all-device guarantee.
- Activation preserves77tables/221files/config. Checked backups **20261018T193228Z** /
  **20261018T193504Z** UTC; five services, six loopback listeners, readiness/web,
  model/timers/images/schema/config pass. No restore, push, provider/schema change.
  Preserve unrelated WIP and all later saved work. Older entries are historical.


### October 19 — Reported conversation loop repaired and verified live

- Private release **0d6af5f7b68d02d3 /0029**, runtime **ff1f27e**, is active.
  Read `docs/verification-conversation-goal-repair.md`. Greetings are brief;
  capability/next-step readings use authorized context; ideal conditions ask for
  the desired outcome; “in order to” no longer falsely blocks a harvest comparison.
- Local34/156/78-case runs overlap; Ruff/mypy269 pass. Exact candidate builds and
  restricted image checks pass. Live four legacy hosted tasks and seven reported-style
  turns pass; fresh browser checks cover three widths in both themes. All six owned
  live synthetic accounts are disabled/revoked. Old saved replies remain immutable.
- Activation preserves77 tables/185 files/configuration. Checked backups
  **20261018T191344Z**/**20261018T191744Z** (UTC); readiness/web, five services,
  six loopback listeners, models/timers and unchanged schema/images pass. No restore.
- This focused gate does not establish universal language accuracy, short-answer
  continuation coverage or causal crop advice. No schema/dependency/provider change,
  push or public exposure. All64 requirement statuses/eight external gates retained.
  Previous release entries below are historical. Preserve unrelated working files.


### October 18 — Proactive findings, private recall and dark mode verified live

- Private release **57f425ce74e83c35** is active on unchanged **0029**, runtime **66ba6b1**.
  API/jobs **04331cd56ad4**, web **2cefaf5169d2**. Read
  `docs/intelligence-experience-upgrade.md` and `docs/verification-intelligence-experience.md`.
- Eligible confirmed sources receive bounded automatic pattern evidence. Overview leads
  with findings and keeps charts open; System/Light/Dark works across charts and panels.
  Eligible anomaly checks have a one-click default. Narrative v2 adds readable values and
  exact grouped highlights; common-unit guards prevent mixed-currency rankings. Old v1 replays.
- Explicit earlier-answer recall uses authorized receipts and a narrow MIT Trellis tokenizer;
  negative/ambiguous references clarify. No autonomous private-memory writes or causal advice.
- Focused checks: overlapping backend177/133/24/51 groups,71frontend,23distinct latest browser
  passes, static/build/restricted checks. Four live hosted tasks pass53.279s; browser3widths
  inboth themes passes35.406s. Initial lock/checker/preflight failures remain in the ledger.
- Checked backups **20261018T185019Z**/**20261018T185309Z**; activation preserves77tables,
  198files/3997759bytes andconfiguration. Five services/sixloopbacklisteners/modeltimers
  andreadyweb pass after backup. Allfour live fictional accounts disabled/revoked.
- Scoped Replica reconnaissance and REA public ThoughtSpot evidence are used; Agent Reach
  is installed as an isolated public-reader assistant tool. Cognee1.6.5 is reviewed/pinned
  only, deferred pending retrieval/permission/forget benchmarks. Read their adoption docs.
- No schema/provider/runtime-dependency change, push, public exposure or data restore.
  Existing sessions and unrelated WIP preserved. All64IDs/counts/eightproduction gates unchanged.
  Private access and current release are in `data/agent-memory/private-vps-handoff.md`.

### October 18 — Bounded conversational harness verified live

- Private release **831c6e06a8b55bdb** is active on unchanged **0029**. Runtime source
  **5247867**, accepted test checkpoint **577d183**. Read `docs/agent-harness.md`,
  `docs/agent-harness-implementation.md` and `docs/verification-agent-harness.md`.
- Two independent governed queries can answer a compound question with both receipts.
  Bounded private follow-ups and verified factual wording selection preserve exact math,
  historical units, access checks and exports. No arbitrary tool loops or causal advice.
- Local latest coverage: **3,168 backend nodes**, all37 original mappings, **69 frontend**,
  **111 browser passes /3 explicit model skips**, static/build/restricted-image checks.
  This combines a full3153-pass/1-failure run with passing supplements; failures retained.
- Hosted before/after: **2/4 in51.268s →4/4 in52.567s**, allfour narratives selected.
  Three live layouts pass35.114s, with keyboard evidence, no overflow/actual network errors.
  Expected background signal cancellations are separately evidenced; synthetic accounts revoked.
- Checked backups: **20261018T175026Z** before/**20261018T175717Z** after. Activation
  preserves77tables,218files/4016809bytes andconfiguration; final services, loopback listeners,
  model/timers and schema pass. No restore, schema change, dependency addition or push.
- New context-enabled planning bypasses local Qwen; hosted DeepSeek handles interpretation
  and factual wording selection. Dashboard summary selection still uses local Qwen, and
  server tools calculate numbers. Main model names remain unchanged. Allfour private flags
  are enabled; general defaults remain off. All8production gates andfeaturecounts unchanged.
- Preserve newer saved work. Rollback means compatible flag disable/forward repair, never
  an old reader that drops the second calculation. Latest private access/handoff is in
  `data/agent-memory/private-vps-handoff.md`; never print sessions or provider credentials.

### October 17 — Natural record questions and selected-group comparison

- Private release **c34536b8540f7c6d** is active on unchanged **0029**; source
  checkpoint **4ec1b00**. Read `docs/harvest-language-repair.md` and
  `docs/verification-harvest-language-repair.md`. This is the current runtime;
  earlier phase/release entries remain historical.
- Record counts include matching rows with missing unrelated cells. Named-field
  counts remain nonnull counts. Highest/lowest-record requests retain ties.
  A registered group-comparison tool reuses governed projections, source-bound
  private context, exact receipts and protected PDF/Excel/CSV outputs. Unsupported
  extra scopes clarify; missing units and causal effects are never invented.
- 442 distinct affected backend/architecture cases,63 frontend tests,9 targeted browser
  journeys, Ruff/mypy 320 and both VPS image builds/restricted checks pass. Retained
  initial failures have passing rechecks. This is not a fresh full-repository gate.
  Four hosted natural-language live jobs pass in 83.551s; live UI nine layouts pass in 48.220s.
  All three fictional live accounts are disabled/revoked afterward.
- Activation preserves 77 tables and179 stored files/configuration. Checked backups:
  pre **20261017T170043Z**, post **20261017T170737Z**. Final readiness/web, five
  services, six loopback listeners, model/timers and unchanged runtime identities
  pass. A Python 3.10/JavaScript-timestamp verifier issue is fixed with retained
  failure evidence; no app/schema/data rollback occurs.
- Local qwen3:4b is advisory selection; hosted deepseek-v4-pro remains configured
  for interpretation/readings/summaries. Server tools calculate the results.
  No specialized-provider switch, new dependency, feature-count change or push.
  Preserve current saved work and all unrelated root files. Private memory carries
  the supplied farm-file analysis; do not turn its associations into crop advice.


### October 17 — Both phases delivered and private0029 release verified

- Both development phases are accepted within documented local bounds at
  **00be9da**. Connector merge **142a7dd** and incoming **2188a2e** ancestry remain.
  Private release **4fff22633f0c5f44 /0029** is active: API/jobs **ab3d84bf**,
  web **4d348afd**. No push or live connector/provider calls occurred.
- Local evidence: **2,937 latest passing backend cases**, all37 original mapped
  requirements, **107 browser passes /3 named model skips**, **59 frontend tests**,
  static/build checks,112 offline evaluation checks and isolated0029 recovery.
  Combined coverage and initial failures remain explicit, not one clean full run.
- Separate live fictional checks pass five Phase1 API groups (64.479s), twelve
  Phase2 groups (140.485s) and five native UI groups/nine desktop/mobile layouts
  (40.652s). Generated accounts are disabled and sessions revoked. The initial
  tunnel/verifier failures and exact synthetic-account cleanup remain recorded.
- Activation preserves **50 original table projections**, **167 stored files**
  and configuration. Checked backups: **20261017T161322Z** before and
  **20261017T162930Z** after. All five services, six loopback listeners, readiness,
  website and model/timers pass. Preserve newly saved work; never restore an old
  database over later work. Existing real sessions/secrets were not changed.
- Read [private release evidence](docs/verification-codex-private-release.md),
  [final report](docs/codex-two-phase-final-report.md) and
  [local walkthrough](docs/two-phase-local-walkthrough.md). Counts remain
  **41 Done /17 Partial /6 Not yet** across64 IDs; all8 production gates stay open.
  Broader limits and external acceptance remain explicit. Earlier entries below
  are historical. No automatic next task is scheduled.


### October 17 — Both phases accepted locally; private release prepared

- Both phases pass the combined local gate: **2,937 latest passing backend cases**,
  all37 original mapped requirements, **107 browser passes /3 explicit model skips**,
  **59 frontend tests**, types/lint/Ruff/mypy319 and production builds. The frozen
  full run is2,932 passes in2,333.55seconds; five later security cases and two
  service repairs have explicit supplements. Initial failures remain retained.
- Release candidate **4fff22633f0c5f44** is built and restricted-image checked on
  schema0029; it is not active at this checkpoint. Root alone owns the separately
  authorized private activation, checked backup, original50table/object/config
  preservation and fictional live verification. No push or provider calls.
- Ledger: **41 Done /17 Partial /6 Not yet**; all64 IDs and8 blocked production
  gates remain. See the two-phase final report, original37 regression ledger and
  local walkthrough. Connector142a7dd preserves accepted2ee7d9c/incoming2188a2e.
- Preserve unrelated next-env, originalPDF, independent-tools doc and UI coordination
  file. Do not alter session secrets, customer definitions or external settings.

### October 17 — Connector integrated; CSS live; Phase 2 gate running

- Root phase2 contains true merge **142a7dd**, parents accepted Phase1 **2ee7d9c**
  and incoming connector **2188a2e**. All17 existing WIP hashes were preserved.
  Connector peer task is complete; no push or connector/provider calls occurred.
- CSS-only web image **ui-20261017-live5c48d3c /29a4f8f** is live. API/jobs remain
  **867c5a0**, schema **0020**. Twenty deployed synthetic layouts pass; root
  inspected desktop/mobile captures. Read `docs/verification-oct17-styling-release.md`.
  Checked backups **20261017T153602Z**/**20261017T153628Z** retain unchanged bytes
  after a separately documented backup-name compatibility repair. No data restore.
- Phase2 code exists for contribution/PVM, constrained scenarios, capacity
  sensitivities, rolling/multivariate anomalies, owner-governed consolidation and
  expanded scoped API/embed paths. Full frozen backend2932 and current browser110
  gates are running; five appended sharing-race regressions are separate supplements.
  Preserve original failures and source hashes. Final backend acceptance is pending.
- Focused browser/core tests pass,59frontend/types/lint/Ruff/mypy319 pass;
  offline evaluation112checks/40cases and disposable0029 recovery77tables/3replays
  pass. These do not deploy the backend or clear production gates. Root alone
  prepares the separately authorized exact0029 private release after final evidence.
- Continue `docs/codex-two-phase-implementation.md`, both phase verification ledgers
  and `docs/codex-two-phase-final-report.md`. The report explicitly remains pending
  until full reconciliation. Operator steps are in `docs/two-phase-local-walkthrough.md`.
  Do not overwrite unrelated files or private evidence; no push is authorized in
  this two-phase slice. All64IDs/original37features and8blocked production gates remain.


### October 17 — Two-phase Phase 1 accepted locally; Phase 2 continues

- Phase 1 native accounts/private guide, internal price-free tiers, exact exports,
  monitoring, recovery, evaluation and performance increments are locally accepted
  on **0027**. Read `docs/codex-two-phase-implementation.md`,
  `docs/verification-codex-phase1.md` and `docs/regression-original-37.md`.
  All **2,580 backend cases** have passing latest executions across a full run
  and focused harness repairs; nine initial failures remain recorded. All 37
  historical requirement mappings pass. This is not one clean full-suite run.
- Frontend 59 tests/types/lint/build and 76 distinct offline browser journeys pass,
  with three explicit model skips. Successful guide Finish/reopen, nine new API
  timing checks, exact exports, offline evaluation and disposable 0027 recovery
  have separate evidence. Mixed performance results and external limits remain.
- The live private demo remains web **5c48d3c**, API/jobs **867c5a0**, schema **0020**.
  The user later authorized tested incremental private-VPS releases; root alone
  owns activation, checked backups and preservation. No push, provider change,
  public exposure or customer-data analysis is part of this work. The latest
  credential-free local handoff is `data/agent-memory/private-vps-handoff.md`.
- Connector work is isolated in `data/agent-tools/worktrees/connector-merge`.
  Preserve 0025–0027; connector 0028 follows 0027 and 0029 follows 0028. R1–R8
  security/import repairs are contributed and combined checks are running. Read
  `data/agent-memory/connector-merge-coordination.json` before touching shared
  files/index/branches. No root merge or connector deployment is implied.
- Phase 2 contribution/scenario/anomaly/decision/consolidation/API/embed work and
  the final full regression remain unfinished. Preserve unrelated next-env,
  original PDF, independent-tools verification document and separate UI work.
  Feature counts are **40 Done / 16 Partial / 8 Not yet** across all 64 IDs; only
  #46 advances for tested local internal allowances, never billing. All eight
  production gates remain blocked.

### October 16 — Open Overview and accessible controls

- Web **5c48d3c** is live; API/jobs remain **867c5a0** on unchanged **0020**.
  Read [the UI contract and evidence](docs/overview-controls.md). Charts/dashboard
  controls and first findings stay open in both modes. The Simple/Expert switch
  keeps native keyboard controls and reduced-motion support; Analysis focus uses
  actual pinned **Radix Select 2.3.8**, with its licenses and dependency notices.
- All **59 frontend tests**, types/lint and local/VPS builds pass. All twelve
  distinct focused browser journeys pass across an eleven-pass run and one
  corrected recheck; the initial asynchronous-focus test failure remains recorded.
  Live checks pass six actual-data layouts and three menu layouts in **20.987
  seconds**, with no page errors or overflow. Five source artifacts and private
  memory remain unchanged. This is a web-only repair, not new backend acceptance.
- Checkpoint: `pre-overview-5c48d3c-20261016`; checked pre-release backup:
  `20261016T134653Z`; checked post-release backup: `20261016T135121Z`. Both archive
  checksums pass; services, model/timers and six loopback listeners are healthy.
  Preserve all saved work.
- Larger backend candidate **b817068 / 0024 is not deployed**. Its fresh full
  backend run passes **2,380 tests**; candidate browser evidence passes **71
  journeys**, with three explicit model skips. Those results are separate from
  this UI release. Keep this UI change in the candidate's future web build.
  Counts remain **39 Done / 16 Partial / 9 Not yet**, with all eight production
  gates blocked. Continue the authorized unfinished-work task from its ledger.

### October 16 — Portable results, dataset policies and operational checks

- Application **867c5a0** is live on additive schema **0020**. Read
  `docs/verification-remaining-work-release.md` and its linked contracts. Portable
  PDF/Excel/CSV-evidence/PNG downloads cover supported saved answers, dashboards
  and analyses. Advanced forecasts use explicit method selection; dataset policies
  enforce row/field scope, and internal staff can review collected incidents.
- All 1,856 final backend cases have passing executions across retained runs;
  this is combined coverage, not one clean full suite. Static/build/restricted-image
  checks, 55 frontend tests and 63 offline browser journeys pass, with three model
  skips. Live API checks cover actual exports, hosted record planning, diagrams,
  forecast/comparison replay, staged refresh, privacy and source/memory preservation.
  Live browser passes nine layouts and four downloads in 24.499 seconds.
- All 47 prior business-table fingerprints/config match. Checkpoint:
  `pre-integration-867c5a0-20261016`; checked backups: `20261016T121340Z` and
  `20261016T123757Z`. Schema changes 0018 to 0020; saved work is preserved.
  Models, timers and loopback-only access remain unchanged. A slow local SSH
  connection was replaced without restarting the application; retained diagnostics
  do not distinguish compression from the changed network path.
- Operator helper **ee3a058** keeps isolated restored PostgreSQL read-only while
  checking current receipt permissions. The 0020 restore passes in 24 seconds:
  93 uploads, 95 revisions, 27 documents/passages, twenty exact replays and one
  revoked-access denial. Initial locking/command failures remain in the recovery
  ledger. Production custody, retention and recovery objectives remain open.
- Feature ledger: **39 Done / 16 Partial / 9 Not yet**, preserving 64 original IDs.
  IDs 13/43 close within the tested private-demo scope; advanced forecasting 56
  becomes Partial. All eight production gates remain blocked.
- Continue the authorized unfinished-work task. The next local batch contains
  metering, scoped keys/webhooks/embedding, approved PostgreSQL import,
  source-derived scenarios, calendar anomalies/drift, consolidation and larger
  allocations. It is **not deployed** yet. External credentials, prices and
  representative customer acceptance must not be invented.


### October 16 — Conversational task repair

- Application **b3a1fb1** is deployed on unchanged **0018**. Read
  `docs/conversation-harness-repair.md` and `docs/verification-conversation-harness.md`.
  The router's rejection of valid whole-file overview plans caused the two
  reported generic menus. Both exact questions now receive accepted hosted
  explanations; simpler follow-ups reuse current private context safely.
- New tasks end old calculation context; genuine short numerical continuations
  retain it. Reading context is rechecked before correction/publication and old
  prose cannot restore forgotten memory. Model budgets/providers remain unchanged.
  Full isolated backend/architecture: **1,545 passed**; overlapping focused suite:
  168 passed; Ruff/mypy192, candidate builds/restricted images pass. Live exact
  calculation/replay, follow-up grouping, twelve private denials and three browser
  layouts pass. Initial checker/fixture failures remain in the ledger.
- All 48 activation fingerprints/config match. Checkpoint:
  `pre-integration-b3a1fb1-20261016`; checked backups `20261016T104413Z` and
  `20261016T105008Z`. Sources, meanings, memory and old turns are preserved.
  API/jobs/web remain loopback-only with unchanged models/timers.
- Recovery helpers `64240dd` verify the post-release backup in an isolated
  environment in 22 seconds: 86 uploads, 88 revisions, 27 documents/passages and 20
  exact receipt replays. A 4,133,086-byte encrypted copy outside the VPS passes
  in-memory decryption and manifest checks. Read `docs/recovery-rehearsal.md`;
  initial hostname/transfer failures are retained. Feature 42 remains Partial for
  approved retention, independent custody/destination and production objectives.
- The latest user instruction authorizes finishing independent Partial/Not yet
  implementations; read `docs/remaining-work-execution.md`. This supersedes older
  implementation deferrals, not external setup requirements or production gates.
  Export, advanced forecast, access-policy and operations work remains **in progress**
  in the working tree. Do not deploy its migration 0019 until the full permission
  surface and compatibility checks pass. Counts remain **37 / 17 / 10** across
  64 original IDs; all eight production gates remain blocked.

### October 16 — Domain tools, protected PDFs and saved-role repair

- Application **`919dd0a`** is deployed on unchanged **0018**. The bounded release
  is complete for local/test and the private demo, with final browser and checked
  post-release backup evidence. Read `docs/domain-agent-tools.md`,
  `docs/pdf-export.md` and `docs/verification-domain-agent-tools.md` before extending.
  The earlier checkpoints below are historical and do not override this entry.
- Structural requests now run a registered diagram tool. Version 2 preserves
  confirmed identifier, ordinal, ignored and ordinary field roles; version 1
  answers reopen unchanged with an earlier-role notice. Unknown fields and row
  restrictions clarify. Numerical chart requests retain governed calculations.
  Maps show file membership, not causes or inferred joins. Optional upfront
  preferences use explicit private memory saves; upload context saves before reading.
- Protected PDF downloads work for completed saved calculations, tables and
  source-backed explanations, including an explicit chat request. Reopening a
  report never downloads it automatically. Export rechecks ownership and source
  evidence, records private audit activity and uses bounded serialized rendering.
  Excel, chart/diagram images, broader analysis reports and whole-conversation
  exports remain unfinished. No arbitrary skill executor or provider change was added.
- Evidence: the full baseline passes 1,448 backend/architecture tests and 59 offline
  browser journeys with three explicit model-dependent skips. Final fixes pass
  104 diagram/report/conversation cases and 84 reading/private-memory cases; the
  37 final correction rechecks overlap those tests. All 54 frontend tests, static
  checks, local/VPS builds and restricted image computations pass. Do not add
  overlapping focused counts to the full baseline as distinct tests.
- The live API verifies all thirteen v2 fields, complete immutable v1 reopening,
  three protected PDFs, twenty private denials and a first-request hosted named
  chart with all three exact rows. A separate hosted retail reading now succeeds
  in twenty seconds with two valid suggestions; exact total/replay, six private
  denials and old evidence pass. This is observed functional success, not a model
  quality guarantee. The earlier role defect and rejected readings remain recorded.
- Chart compatibility passes three journeys and 36 layouts in 45.884 seconds with
  zero errors or retries. Its earlier saved-answer GET `ECONNRESET` is retained;
  no application restart or OOM was observed. The final domain browser passes five journeys /
  21 layouts in 61.707 seconds, including no-op clarification-button removal and
  two explicit PDFs, with zero page errors or automatic downloads. Its backend
  source is unchanged from the successful 5372e95 hosted checks. Sources, private
  memory, all 48 activation fingerprints and
  configuration are preserved; existing real user definitions were not rewritten.
- Checkpoint: `pre-integration-919dd0a-20261016`. Checked pre-release backup:
  `20261016T095238Z`; checked post-release backup: `20261016T095854Z`.
  Both database/object archive checksums pass and services restart normally. Preserve all newly
  saved work on rollback. ID 13 is now Partial for bounded PDF delivery: counts
  are **37 Done / 17 Partial / 10 Not yet**, preserving all 64 original IDs.
  All eight production gates remain blocked. Broader export/connectors, advanced
  methods and representative acceptance remain open.

### October 16 — Actual chart-template reuse and ongoing domain-agent work (earlier checkpoint)

- API/jobs/web `7b46db2` is deployed on unchanged **0018**. The owner explicitly
  confirmed noncommercial use. Actual attributed Lieflat G10 bars and separate
  documd line options run through bundled ECharts 6.1.0, themed for ExecPlus.
  Every returned row remains reachable through zoom, keyboard and exact inspection;
  the live retail check reaches all 365 periods. Read `docs/repository-integration.md`,
  `docs/chart-experience.md` and `docs/verification-repository-integration.md`.
- Curated MIT EDA/SQL recipes guide qualitative readings through existing supported
  operations. Truncated replies get one bounded fresh correction; no provider or
  numerical-method change occurs. UIUX and SkillSpector are actual development
  tools; oneDAL remains reviewed-only. Full licenses/notices ship with the app.
- Checks: 1,351 backend cases, 49 frontend cases, Ruff/mypy (180 files), types/lint,
  local/VPS builds and restricted image computations pass. All 56 distinct offline
  browser journeys have passing executions across full/focused runs; three model
  cases remain skipped. Initial formatting/selector/renderer warnings are retained.
  Three live browser journeys pass 36 layouts in 46.336 seconds, without page
  errors or overflow. Root inspects live desktop/mobile captures.
- The fresh hosted retail reading still falls back with `invalid_response`; exact
  total/replay, six private denials, source state and memory pass. Do not claim it
  resolved or blindly retry. A later in-progress slice adds fixed validation issue
  codes and targeted correction hints without private prompt/reply logging.
- All 48 activation fingerprints/config match. Checkpoint
  `pre-integration-7b46db2-20261016`; checked backups `20261016T084552Z` before and
  `20261016T085923Z` after. The reported file acquired v4 definitions and both units
  before activation; retain that legitimate update. Its five latest artifacts match
  after release/backup. Five containers, readiness/web, model/timers and six loopback
  listeners pass. Preserve all live saved work on rollback.
- New user instruction: implement domain-agent tools for structural diagrams,
  appropriate chart/query routing, authenticated PDF reports and optional upfront
  preference choices. This work is **in progress**, not deployed. Read
  `docs/domain-agent-tools.md` and `docs/verification-domain-agent-tools.md`.
  It must preserve typed evidence, private ownership, source freshness and explicit
  memory saves. Do not stop at the preceding chart release. All 64 feature IDs,
  37/16/11 counts and eight blocked production gates remain unchanged for now.

### October 16 — Prepare data repair after delivery feedback

- Web `aded714` is deployed on unchanged **0018**; API/jobs remain `327ba7d`.
  Read `docs/prepare-data-experience-repair.md`. The previous images had already
  been rebuilt, but Prepare still exposed the old technical layout. It now leads
  with active data, actual checks and a review action; columns, cleaning and
  history expand on request. Exact values, preview/apply and restore remain intact.
- A successful cleaning/restore write consumes its preview and invalidates
  dependent views before reloading. Failed reads lock further edits until a full
  reload, preventing reuse of an old preview. Manual reload still refreshes other
  panels. The apply failure branch has browser coverage; the shared restore
  failure branch is source-reviewed rather than separately injected.
- Fresh checks: 29 frontend tests, four distinct focused browser journeys, five
  architecture checks, types/lint and local/VPS builds pass. A corrected selector
  failure is retained. One read-only deployed journey passes nine layouts in
  15.701 seconds without page/HTTP errors or overflow. The reported source's five
  metadata/content/profile/history/meaning artifacts remain unchanged. The full
  backend suite below is prior evidence, not a fresh rerun for this web repair.
- Checkpoint `pre-prepare-aded714-20261016`; checked backups
  `20261016T072438Z` before and `20261016T073434Z` after. Web activation preserves
  backend containers and environment checksum. Backups restart writers/storage
  normally. Schema, model settings, six loopback listeners and timers are retained;
  all 64 IDs, 37/16/11 counts and eight blocked production gates stay unchanged.
- The user says their open `http://localhost:18400/workspace` tab lacks My memory
  and the new Overview heading. Fresh browser checks show both. Hard refresh and
  a screenshot if unchanged were requested; their actual tab remains unverified.
  Do not claim caching as the established cause, or the broader experience as
  accepted. The prior UI completion message overstated its completeness.

### October 16 — Personal agent, studio UI and saved-unit repair

- This bounded slice is complete for local/test and the private demo. Application
  `327ba7d` is deployed on **0018**.
  Read `docs/personal-agent-studio.md`, `docs/verification-personal-agent-studio.md`,
  `docs/demo-data-guide.md`, `docs/personal-agent-reference-audit.md` and
  `docs/project-skill-adoption.md`.
- Migration **0018** adds explicit actor/workspace-private memory. It guides new
  qualitative readings and suggestions, never numeric planning/filters. Forget
  clears future active use; historical replies/backups remain. Membership removal
  cascades memory. Version conflicts, source/context freshness and private audit
  boundaries remain enforced. Downgrade refuses retained memory/tombstones.
- Fictional `retail-v1` and `actions-v1` use normal import and meaning confirmation.
  Local CSVs/visual guide live in ignored `data/demo-kit/`; the generator and
  walkthrough are tracked. Five old samples retain their bytes. The retail file
  covers 365 days and three regions; action benefits are explicit assumptions.
- The reported confirmed-v3 source had two genuinely empty units in every saved
  version. Review now targets the unit directly, preserves the description and
  shows actual unfinished questions. Successful saves survive reopening/remount
  avoidance; a failed follow-up read retries reading without resubmitting a write.
  No real user definition has been inferred or overwritten.
- Selected UI UX Pro Max, documd visuals, exploratory-data-analysis and Skill
  Inspector instructions are installed only in ignored project skill directories.
  Requested repositories are pinned under `data/agent-tools/references/`.
  Lieflat is reference-only outside automatic discovery because its template-copy
  workflow is noncommercial; product chart code remains original. oneDAL/SQL
  references are research, not new runtime dependencies. Review adoption documents
  before executing tools or changing this boundary. No global settings changed.
- All 1,335 full-suite backend cases plus two later regressions have passing
  executions (1,337 distinct); the two original fixture failures remain recorded.
  All 29 frontend tests, Ruff/mypy (179 files), types/lint and local/VPS builds pass.
  All 54 distinct offline browser journeys have passing executions across full/
  focused runs; three model-dependent cases remain explicitly skipped. Restricted
  non-root image checks pass prior and new calculations without network access.
- Live API checks use three fictional actors/two workspaces and pass 24 private
  denials, two memory conflicts, seven legacy reopens and all sample calculations.
  The first retail reading fell back; a separate action-file reading successfully
  uses saved memory through the configured hosted model. Forget preserves that
  historical answer. This does not establish that the first fallback is resolved.
  Three live browser journeys pass eighteen 1440/390/320 layouts with zero page
  errors/overflow in 193.285 seconds; a settled Home recapture also passes.
  Two initial helper failures remain in the ledger. The fictional v3→v4→v5 unit
  repair persists both entered units; real user definitions remain unchanged.
- Activation preserves all 46 prior business-table fingerprints and configuration.
  Checkpoint: `pre-327ba7d-20261016`; checked backups: `20261016T061031Z` before and
  `20261016T063610Z` after release. Post-backup readiness/web, five containers,
  zero restarts, six loopback listeners and model/timers pass. The reported source's
  five artifacts still match. Preserve all new saved work and memory on rollback.
- Five no-LLM skill scans completed and all 125 findings were source-reviewed;
  raw scores and partial coverage remain recorded. This is not a clean scan or
  safety certification. Selected guidance remains scoped; downloaded templates,
  optional exporters and scientific analyzers do not run in the product.
- The October 16 Desktop DOCX and maintained ledger preserve all 64 IDs and counts
  37 Done / 16 Partial / 11 Not yet. All eight production gates stay blocked.
  Broader methods, exports/connectors and representative model/load acceptance
  remain open. Future work should use the current contracts and actual failures;
  no broader model-quality or competitor-parity claim is supported.


### October 16 — Group comparisons, selection rules and fixed evaluation

- The user authorized continuing the remaining clean-experience phases. All four
  bounded phases are now complete for local/test and the private demo. Application
  `dfddb8c` runs on unchanged **0017**. Read `docs/internal-analytics-depth.md`,
  `docs/verification-internal-analytics-depth.md` and the completed
  `docs/clean-experience-plan.md` before extending this work.
- Compare groups takes two confirmed fixed-unit measures and one category. Pooled
  and within-group Pearson/Spearman scores use identical covered rows; missing,
  sparse, constant and unstable groups are explicit. Bounds: 10,000 matching rows,
  twelve groups, twenty complete varying pairs per group and two eligible groups.
  The 0.5 direction threshold is a display rule, not significance or causality.
  A canonical chooser request fits the existing 500-character question limit;
  ambiguous/filtered phrasing clarifies. Old pattern evidence remains unchanged.
- Allocation adds explicit prerequisites and exclusions for up to twenty actions,
  both existing resource limits and at most 100,000 quantity combinations. Cycles
  are refused. Exact enumeration supplies the bounded optimum; a separate checker
  verifies selected quantities, totals and rules, not a second optimality proof.
  Old request/result methods, private ownership, source guards and reviews remain.
- Evidence: **1,300** full backend/architecture passes, **29** frontend tests,
  Ruff/mypy (174 files), types/lint and local/VPS builds. Full offline browser run:
  **51 passes / three explicit model-dependent skips / zero failures**. Fixed
  evaluation: eighteen named cases / forty-two checks, all passing. Independent
  rational/numerical fixtures and 48 new restricted-image computations pass.
  Initial fixture/selector/static issues and the saved method-route repair are
  retained in the ledger; three skipped journeys are not counted as passes.
- The declared eight-user local workload passes 144 before / 208 after requests,
  with exact answers and no errors. Common elapsed time is 6.068 / 5.241 seconds,
  but a single short pair with mixed step timings proves no general speedup.
  The fixed evaluation and workload remain fictional internal evidence.
- Deployed checks: eight actors, eight group jobs, eight rule allocations, sixteen
  exact replays, 224 private denials and sixteen authorized controls pass. A fresh
  hosted reading uses saved private context and reopens; old ordinary/pattern/
  forecast/scenario/October15-reading evidence remains compatible. Two browser
  journeys pass six 1440/390/320 layouts in 49.8 seconds with zero page errors.
  Actual farm bytes, meanings and metadata remain unchanged.
- All 47 activation table fingerprints and configuration checksum match.
  Checkpoint: `pre-dfddb8c-20261016`; checked pre-release backup:
  `20261016T044108Z`; checked post-release backup: `20261016T050051Z`.
  Preserve every new saved result/review on rollback. The independent demo tunnel
  is restored and only expired demo1 was renewed; teammates were not revoked.
- No provider, dependency, schema or network-exposure change. All 64 original IDs,
  **37 Done / 16 Partial / 11 Not yet** and eight blocked production gates remain.
  Broader scenario/anomaly/decision methods, exports/connectors and representative
  acceptance remain open. No additional work is scheduled automatically. Small
  follow-up: the existing “Generate AI summary” action summarizes dataset insights,
  not the selected grouped result; its label could state that scope more clearly.

### October 15 — Focused experience and reliable reading

- The user requested four improvement phases: deliver the first two now, retain
  two for the next session. The first two are complete for local/test and the
  private demo. Application `412bf4e` runs on unchanged **0017**. Read `docs/clean-experience-plan.md`,
  `docs/clean-experience.md`, `docs/verification-clean-experience.md` and
  `docs/clean-experience-reference-audit.md` before extending this work.
- Home, conversation and review have separate primary views. Reading asks one
  question at a time; Back keeps drafts, partial saves stay drafts and failed saves
  retry only the unfinished part. Forecast/scenario charts fit mobile screens;
  accuracy and method details expand on demand. Essential uncertainty remains
  visible. Finite motion respects reduced motion and never invents progress.
- Upload/chat reading reuses saved meanings and actual missing details. One bounded
  correction can repair invalid returned model content within a shared forty-second
  deadline and existing budgets. Server merging preserves saved answers; source,
  definitions, private context and permissions are rechecked. Provider failures or
  repeated invalid replies use explicit fallback. Cleanup may extend wall time;
  provider-level incomplete responses may still fall back. Old replies remain
  immutable; ask again to receive the enhanced reading. No model arithmetic,
  automatic shared confirmation, provider change or schema change was added.
- Local evidence: 1,170 full backend/architecture passes plus 107 final targeted
  checks yield **1,177 distinct**. All 27 frontend tests, Ruff/mypy (170 files),
  types/lint and final local/VPS builds pass. All **52 distinct browser journeys**
  have passing executions across full/focused/live runs, including all three
  model-dependent conversations. Initial failures and the earlier development
  router error remain in the ledger; no single clean full browser run is claimed.
  Non-root network-disabled images pass old/new compute and reading-recovery checks.
- REA inspected five public ThoughtSpot/Metabase documentation illustrations.
  Radix/Motion licenses and compatibility were reviewed; native disclosures/CSS
  meet this slice's needs, so no new runtime dependency was installed. No private
  competitor backend or code was accessed. This is not full product parity.
- Eight deployed API checks pass, including a twenty-field hosted reading that
  successfully uses correction, saved private notes/goal, the actual missing-unit
  question, exact 20.5 alias calculation/replay and three private-thread denials.
  Old ordinary/pattern/forecast/scenario evidence reopens. Two live browser journeys
  pass six 1440/390/320 layouts with zero page errors in 48.3 seconds; source metadata
  and bytes remain unchanged. This is functional evidence, not representative
  model-quality or sustained-load acceptance. The absent local tunnel, expired
  demo session and stale verification receipt index were corrected and retained
  as initial harness failures. Only one demo session was renewed; teammates remain.
- All 47 activation table fingerprints and the environment checksum match.
  Checkpoint: `pre-412bf4e-20261015`; checked pre-release backup:
  `20261015T182108Z`. Checked post-release backup `20261015T185057Z` preserves the
  live saved work and restarts services successfully.
  Preserve all new saved work on rollback. Models, timers and loopback-only access
  retain their existing configuration.
- Next session: phase 3 adds pooled-versus-within-group relationship comparisons
  and explicit allocation prerequisites/exclusions, with independent numerical,
  compatibility and privacy evidence. Phase 4 adds fixed failure-case evaluation,
  complete journeys and a declared local workload. See the plan's exact bounds.
  Broader methods and representative production acceptance remain open. All 64
  feature IDs, **37 Done / 16 Partial / 11 Not yet** and all eight blocked production
  gates remain unchanged. No automatic next-session schedule was created.

### October 14 — Measured patterns and meaningful no-date alternatives

- Application `e7e4b8c` is deployed on unchanged **0017**. Read
  `docs/measured-patterns.md`, `docs/verification-measured-patterns.md` and
  `docs/pattern-exploration-reference-audit.md`. REA inspected five public ThoughtSpot
  documentation illustrations in a separate browser; no private backend/tenant
  access or competitor code copying occurred.
- “Find patterns” now computes Pearson/Spearman relationships, governed group means
  and category associations using pinned SciPy 1.15.3/NumPy 2.2.6 behind a port.
  Stronger findings and up to two weak comparisons have separate cards, charts,
  coverage and exact evidence tables. No forced finding, p-value, causal conclusion
  or learned prediction is claimed. Explicit non-average measures cannot silently
  become group means; confirmed roles override name heuristics.
- One private projection receipt supports replay and durable jobs. Confirmed units,
  matching required filters, complete-population limits (10,000 rows; eight measures;
  four categories), source/accepted-refresh checks and owner privacy remain enforced.
  Unrecognized row restrictions clarify instead of silently broadening. Broad
  analysis can reuse a private pattern goal. Source-change/cancellation publication
  races clear unpublished evidence and preserve the appropriate failure reason.
- No-date forecasts offer patterns or an explicit daily what-if. The user supplies
  the daily change and one to 3,650 days. Exact checkpoints compute baseline + rate
  × days; negative paths warn without clipping. This is an assumption, not a
  time-series forecast. Old scenario methods and saved results remain compatible.
- Evidence: 1,140 full backend/architecture passes plus 114 final targeted checks
  yield **1,152 distinct**; 27 frontend tests, nine selected local browser journeys,
  Ruff/mypy (169 files), types/lint and production builds pass. Network-disabled
  non-root images pass eight pattern/daily computations and prior compute checks.
  Three live journeys pass source preservation, nine privacy denials, authorized
  controls, saved replay, old forecast/scenario compatibility and three layouts.
  Retained initial failures were test harness/fixture errors; see the ledger.
- The reported farm file yields **no strong pattern** and separately displays weak
  category associations. Detailed user measurements remain in ignored evidence.
  Do not guess missing units, invent a relationship or infer time
  from row order. Further prediction requires a target, suitable examples and
  representative held-out evaluation. All original user definitions remain intact.
- All 47 activation table fingerprints/config match. Checkpoint
  `pre-e7e4b8c-20261014`; checked pre-release backup `20261014T125237Z`.
  Checked post-release backup `20261014T130023Z` preserves the live saved work.
  Final runtime details are in the verification ledger. Six listeners
  stay loopback, models and timers unchanged. Report retains all 64 IDs and
  **37 Done / 16 Partial / 11 Not yet**; all eight production gates remain blocked.
  Broader Phase 6 remains Frozen outside separately authorized bounded slices.

### October 14 — Context reuse and meaning-first explanation

- Personal `phase2` application commit `e663a50` is pushed and deployed on unchanged
  0017, following `d40bc6d`. Read `docs/meaning-first-reading.md`,
  `docs/verification-meaning-first.md`, `docs/verification-context-reuse.md` and
  `docs/meaning-first-reference-audit.md` before extending. REA inspected public
  ThoughtSpot examples/docs; no authenticated tenant or private backend was accessed.
- Saved definitions, actor-private goals and checked current-upload notes feed
  interpretation and planning. Missing review resumes without overwriting answers;
  all columns are covered. A model reading is qualitative, fallible and source-bound,
  never numerical evidence or an automatic shared definition. Missing units/dates
  remain explicit. Complete missing details opens the existing review.
- Home exposes saved purpose/private goal; short explanation cards keep context
  accessible. The user's farm file now receives a soil/weather/crop/irrigation
  explanation, an eligible rainfall question and a missing soil-moisture-unit
  question. Its source metadata/answers are unchanged. Old saved replies remain
  immutable: refresh and ask again to receive the enhanced reading.
- Repair evidence: 1,060 distinct backend cases across full/final runs, 19 frontend
  and nine selected browser journeys. Follow-on: 93 selected backend/architecture
  cases plus nine final reading rechecks, 22 frontend tests, four browser journeys,
  types/lint/Ruff/mypy (163 files)/builds. Two live hosted readings pass API/UI reopening,
  1440/390/320 layouts and zero page errors in 60 seconds. These are functional checks, not
  representative model-quality or sustained-load acceptance. A separate generic
  onboarding fixture's derived-number reply is rejected and falls back safely.
- All 47 control-plane fingerprint entries/config are preserved. Checkpoint
  `pre-e663a50-20261014`; checked backups `20261014T121820Z` before and
  `20261014T122102Z` after release. Services/model/timers healthy, zero application-container
  restarts and six loopback listeners. Preserve new private turns and all saved
  work on rollback. Providers/network/schema and production gates are unchanged.
- Feature counts remain 37 Done / 16 Partial / 11 Not yet. Remaining work retains
  exports/connectors, commercial identity/billing, operational acceptance and broader
  methods. General model associations are suggestions, not measured causal effects
  or more specific row-grain confirmation. No full ThoughtSpot parity is claimed.


### October 14 — Branch merge, bounded analytics extensions and working demo access

- The user authorized starting Partial anomaly/scenario/recommendation work and
  merging last night's branch. `origin/phase3` at `2a93080` was merged into `phase2`
  in `c846835`; it adds data reading before Ask ExecPlus. Existing polish and local
  tools remain intact. The new extensions are complete for local/test and the
  private demo at `8ffdf5d`.
- Read `docs/analysis-extensions.md` and `docs/verification-analysis-extensions.md`.
  Grouped MAD/IQR uses separate baselines with explicit missing/sparse exclusions;
  compound scenarios multiply up to three named percentage assumptions; bounded
  allocation supports a second resource limit with an exact 100,000-combination
  cap. Old requests retain old results/methods. Private ownership and freshness
  guards remain in force. Schema remains **0017**; all three broad features stay Partial.
- Verification: 1,046 full backend/architecture passes plus 71 focused rechecks
  include four additional cases, giving 1,050 distinct passes. Nineteen frontend
  tests, seven selected browser journeys, Ruff/mypy (160 files), types/lint and
  production web build pass. Initial fixture and browser-selector failures are in
  the ledger. Clean non-root image checks and a 51.5-second live-model browser
  journey now pass; this is functional evidence, not model-quality or
  sustained-load acceptance.
- The user requested VPS startup. Existing containers were already running;
  Compose up and model/timer start completed under the maintenance lock. Readiness
  and workspace HTTP 200 pass. A later report of old flows triggered deployment
  of `8ffdf5d` API/jobs/web, with schema 0017 unchanged. All 47 table fingerprint
  entries and environment-file checksum were preserved. Checkpoint source/images:
  `pre-8ffdf5d-20261014`; checked backups: `20261014T110653Z` before release and
  `20261014T111211Z` afterward. Archive checksums and restarted services pass.
  Real hosted data reading, all three extensions, approval/replay/successors and
  three layouts pass with a fictional account; no browser page errors. New or
  unconfirmed data opens reading; confirmed data must be reopened from Prepare data.
  Use **http://localhost:18400/workspace**, exactly: the numeric 127.0.0.1 browser
  origin is rejected by the deployed CORS setting and causes Failed to fetch.
  Corrected real-browser sign-in passed. Preserve the configured allowed origin.
- This checkout now has ignored, mode-0600 `data/vps-private/sessions.json` for
  demo1 and `data/vps-private/tunnels/demo1`. The independent restricted tunnel
  binds 18400/18401 to loopback. Sessions expire after eight hours; issue a single
  replacement when needed without revoking teammates. Never copy tokens into notes.
- `.venv` uses Python 3.12; project-only Node 22 is available through
  `data/agent-tools/bin/with-node`. Local isolated test containers use the cached
  images in ignored `data/agent-tools/test-compose.yaml`; no other app was changed.
  SQLAlchemy is constrained to tested 2.0.x pending a separate 2.1 compatibility
  update. Browser tests can set `EXECPLUS_BROWSER_EXECUTABLE=/usr/bin/google-chrome`.
- The maintained report and October 14 Desktop DOCX retain all 64 IDs and counts
  **37 Done / 16 Partial / 11 Not yet**. All eight gates still block production.
  Next: the remaining methods and representative acceptance work
  in `docs/advanced-analytics-research-plan.md`; do not claim broad feature closure.

### October 13 — Current checkout and VPS inspection handoff

- The user requested understanding and persistent project context, not a new feature
  or deployment. This inspection made no VPS configuration/data changes or restarts.
  Local checkout: `/home/hadiabbasisdev/Desktop/OISOL`, branch `phase2`, tracking
  `origin/phase2` at `ff04c4b`. The branch name does not mean only Phase 2 is implemented.
  Repo-local Git settings use the personal `Hadi-OISOL` identity and dedicated SSH
  key; preserve the separate company Git configuration. Never record credentials here.
- The user confirmed the VPS is `administrator@173.208.151.137`; the earlier
  `172.208.151.137` was a typo. Password authentication succeeded. `/sdb-disk` is
  `/dev/sdb1`, mounted ext4, with approximately 858 GiB available at inspection.
  `/sdb-disk/OISOL_ExecPLUS/source` is a deployed source snapshot, not a Git checkout.
  Its sibling directories are `postgres`, `objects`, `secrets`, `backups`, `ops`
  and `releases`. Preserve other applications sharing this host.
- Fresh read-only checks: `/workspace` on loopback port 18400 returns HTTP 200;
  port 18401 `/health/ready` reports PostgreSQL and object storage healthy; the
  database reports migration **0017**. API/jobs/web are running with zero recorded
  container restarts. The model service and refresh/backup timers are active;
  latest systemd refresh/backup results are successful. All six project listeners
  (18400, 18401, 18432, 18490, 18491, 11450) bind only to 127.0.0.1.
- Inspected configuration retains hosted `deepseek-v4-pro` for primary planning
  and local `qwen3:4b` for advisory selection at `127.0.0.1:11450/v1`; the local
  model catalog responds. No inference request or authenticated browser journey
  was run during this inspection; readiness alone does not prove those workflows.
- Latest observed backup is `20261013T181431Z`: `database.dump` and `objects.tar.gz`
  both pass `SHA256SUMS`. This verifies archive integrity, not a latest-version
  restore or off-server disaster recovery. Daily backup time is 08:00 Pakistan time.
- Before this handoff edit, 408 of 411 tracked files matched the VPS source snapshot.
  The VPS lacks `docs/analysis-journey-gap-audit.md`; its startup guide lacks the new
  operator-restart section; `apps/web/next-env.d.ts` has generated browser-build paths.
  All 136 checked backend-source/migration files in the running API container's
  `/app` tree match this checkout. Do not infer a deployed Git commit from a snapshot.
- Reviewed the supplied `ExecPlus_Latest_Changes_2026-10-13.pdf`, startup/runbook,
  roadmap, architecture, latest verification, closure plan and feature ledger.
  PDF and JSON agree: **37 Done / 16 Partial / 11 Not yet**, covering 64 original IDs.
  Phases 0–3 and 4A–4C are complete within their recorded scope. Delivered private-demo
  work includes governed uploads/meaning, exact analytics and receipts, data/document
  chat, saved studies/dashboards, staged refresh/alerts, basic forecasts, audit,
  admin/support/usage, bounded anomalies/allocation/scenarios, guided review and polish.
  Historical 979 backend / 19 frontend / 38 browser results are recorded evidence,
  not a newly rerun suite. Older baseline and uncommitted-work notes below are historical.
- Remaining work: Phase 4D exports; 4E read-only Sheets/PostgreSQL connectors;
  Phase 5 production signup/login, commercial metering/plans/payments, real email,
  monitoring, current-version restore/off-server recovery and representative evaluation,
  security/privacy and sustained performance. Broader causal, forecast, scenario,
  anomaly and decision methods, accounting/BigQuery connectors, consolidation,
  scoped customer APIs/webhooks, embedding and row/column permissions remain unfinished.
  Read `docs/partial-feature-closure-plan.md` for all sixteen Partial items and
  `docs/product-feature-audit.json` for all eleven Not yet items and exact limitations.
- `ff04c4b` adds the **planned** intent → personal context → data review → results
  journey audit and startup instructions, not its implementation. Read
  `docs/analysis-journey-gap-audit.md` before that work. Keep its explicit forecast/
  allocation inputs, private goals, full meaning confirmation and source-change guards.
  Advanced method sequencing is in `docs/advanced-analytics-research-plan.md`;
  broader Phase 6 remains Frozen except separately authorized bounded slices.
- A fresh production-preflight check still blocks all eight gates: representative
  corpus, retrieval quality, vector provider, backup/restore, model comparison,
  provider privacy, report delivery and identity/security. No status was promoted.
- Startup: use `docs/start-project.md` with this machine's actual checkout path.
  VPS operation uses the source directory and `/run/lock/execplus-maintenance.lock`;
  do not restart a healthy deployment merely to inspect it. Access stays through
  loopback SSH forwarding. This new local checkout has no `data/vps-private/tunnels/demo1`
  or `sessions.json`; the example tunnel requires a separately supplied assigned key.
  Local development needs database/storage plus API, jobs and web, migration 0017
  and its own operator-issued session; VPS and local sessions are separate.

- October 13 dashboard/conversation refinement is Complete for local/test and the
  private demo on unchanged **0017**. Read `docs/interface-polish-gap-audit.md`,
  `docs/interface-polish.md` and `docs/verification-interface-polish.md`. Self-hosted
  Manrope, navy/teal surfaces, grouped exact-value KPI presentation, early chart tools,
  finite/reduced-motion animation and concise real-stage progress replace mixed styling
  and duplicate event logs. Exact chart/table/source strings remain intact.
- Broad goals now ask source-specific follow-ups. Persisted bounded choices continue
  the same private thread; calculation fallback asks for a real measure while retaining
  original operation/filters. Stale clarification blocks even deterministic choices.
  No arbitrary agent code, auto-confirmation, model arithmetic or provider change.
- Checks: 978 full backend cases plus final 102-case rechecks/one additional regression
  give 979 distinct (eleven new); 19 frontend tests, all 38 browser journeys, Ruff/mypy,
  types/lint and local/VPS builds pass. Eight users pass 16 exact numeric answers,
  16 typed replays, 56 private-thread denials, 224 authorized ordinary-query controls,
  24 layouts and zero browser errors in 85.161 seconds. Four old v1/v2 receipts replay.
  This is functional evidence, not sustained load or production acceptance.
- API/jobs/web changed, but all 46 prior data tables and migration metadata retain
  hashes/counts. Checkpoint `pre-polish-20261013`; checked pre-backup `20261013T121947Z`.
  Checked post-release backup `20261013T125517Z` retains new work with healthy restarts;
  refresh/backup timers remain active. Ordinary query receipts remain workspace-scoped;
  private threads and analysis
  receipts retain their respective owner-only boundaries. Preserve all new saved work
  on rollback. Current baseline is `4efb6da` on phase2; this turn made no commit/push.
  Feature counts remain 37 Done /16 Partial /11 Not yet; all eight gates stay blocked.

- October 13 teammate onboarding is integrated and verified for local/test and the
  private demo on unchanged **0017**. Read `docs/onboarding-merge-gap-audit.md`,
  `docs/onboarding-merge.md` and `docs/verification-onboarding-merge.md`. The original
  `/home/administrator/abm/Exec-Plus` checkout remains untouched; its older page was
  merged manually with current source. Separate private notes and explicit shared
  drafts replace automatic schema confirmation; full meaning review stays required.
- Onboarding checks: 67 targeted backend/architecture cases, six new browser cases,
  all 37 browser journeys, 17 frontend tests, types/lint/build and Ruff/mypy pass.
  Eight VPS users passed eight fictional uploads/notes/drafts, 112 privacy checks,
  24 layouts and zero browser errors in 78.387 seconds. Four old profile-v1/v2
  receipts replay exactly. This is functional demo evidence, not sustained load.
- Only web changed; API/jobs IDs/images, models, network and schema remain intact.
  Checkpoint `pre-onboarding-20261013`; pre-release checked backup `20261013T114537Z`.
  Checked post-release backup `20261013T115029Z` preserves the new notes/drafts and restarts
  writers/storage successfully. Preserve new notes/drafts when rolling back. Sessions were renewed privately.
  No commit/push occurred. VC report stays 37 Done /16 Partial /11 Not yet; 47 stays
  Partial and all eight gates stay blocked. `docs/partial-feature-closure-plan.md`
  lists remaining dependencies. Broader Phase 6 stays Frozen.

- October 13 scenario slice is Complete for local/test and the private demo on
  **0017**. Read `docs/scenario-planning-gap-audit.md`, `docs/scenario-planning.md`
  and `docs/verification-scenario-planning.md`. VC 57 is now Partial: one confirmed
  aggregate, five explicit alternatives, immutable private successors and three
  exact source receipts. No demand response, causal effects or external action.
  Compatible successors also preserve grain, meaning and governed population.
- Scenario evidence: 963 full backend/architecture cases plus five later hardening
  cases (968 distinct; 41 new), 17 frontend tests, all 31 distinct browser journeys,
  Ruff/mypy (156 files), types/lint and local/VPS builds pass. Full live browser run
  had 30 passes/one fixture load-timing failure; the corrected focused case passed.
  Initial query-validator and browser/build/selector failures remain in the ledger.
- Eight deployed users pass 16 comparisons/reopens, 48 exact typed receipt replays,
  784 cross-user denials and 24 layouts in 96.779 seconds with no browser errors or
  source-metadata changes. Clean non-root image passes eight users/48 scenario
  query executions without network/scientific packages; old methods also pass.
  This is functional rehearsal, not sustained-load or customer acceptance.
- Migration 0017 preserves all 46 prior tables. Checkpoint source/images use
  `pre-scenarios-20261013`; checked backups are `20261013T042923Z` before release
  and `20261013T043834Z` afterward. Downgrade refuses while scenarios exist;
  preserve all saved work. Local services also run 0017. Models, ports and eight
  production gates are unchanged; refresh/backup timers stay active.
- Scenario work is uncommitted on `phase2` at `639e28c`; no push/merge occurred.
  Maintained report now has 37 Done / 16 Partial / 11 Not yet, preserving all 64
  original IDs and October 5 competitor review. Broader Phase 6 remains Frozen;
  the next evaluated slice is anomaly-method expansion from the research plan.

- October 13: requested research/planning for VC 57/58/59/63 is saved in
  `docs/advanced-analytics-research-plan.md`, including method trials, evidence
  contracts, acceptance and private release steps. The supplied DOCX has 64 IDs;
  requested 69 remains unidentified. This request authorizes planning only; all
  feature statuses and production gates are unchanged. Read this plan before a
  separately authorized extension; preserve the teammate's unverified `abm`
  guided-review checkout. The observed local baseline is now `639e28c` on `phase2`.

- October 10: the user explicitly authorized the private-demo anomaly/recommendation
  extension (VC 58–59 plus review dependency 60). The bounded slice is Complete for
  local/test and the private demo on **0016**. Read `docs/decision-analysis-plan.md`,
  `docs/decision-analysis.md`, `docs/verification-decision-analysis.md` and ADR 0010.
  Broad VC 58/59 remain Partial; basic private recommendation review 60 is Done.
- Weighted snapshot MAD/IQR findings preserve frequencies, materiality and explicit
  degenerate-baseline handling. Scores are not probabilities or calibrated errors.
  Allocation is an exact bounded single-budget integer model under declared fixed
  costs/additive benefits, with infeasibility and do-nothing baseline. No causal
  effect is inferred and no external action executes. Seasonal/multivariate/drift,
  nonlinear/causal decision modules, conversational orchestration and automatic
  refresh/analysis jobs remain future work.
- Runs and optimistic append-only reviews are creator-private, including from
  workspace/staff admins. Underlying `aggregation="analysis"` query receipts are
  owner-private and excluded from ordinary saved-answer sharing and narrative
  mutation. Opening reproduces full typed query evidence and method output; current
  approval also requires the latest revision/meaning/accepted refresh source.
- October 10 evidence: 922 full backend/architecture cases plus five subsequent
  hardening cases (927 distinct; 58 new), 17 frontend tests, all 30 distinct browser
  journeys, Ruff/mypy (154 files), types/lint and local/VPS builds pass. The initial
  offline browser run had 28 passes, one model-dependent failure and one skipped
  case; both passed with live DeepSeek. Two earlier new-case selector/fixture failures
  are retained. Clean non-root image passes eight concurrent users/32 exact queries
  without network or optional scientific libraries.
- Eight deployed users created 16 runs and 16 reviews, reopened 16 immutable results,
  replayed 16 exact source receipts, passed 448 cross-user denials and 24 layouts in
  64.245 seconds with zero browser errors and unchanged source metadata. This is
  functional rehearsal, not sustained load or customer calibration. Four old
  profile-v1/v2 receipts and a retained forecast/comparison remain compatible.
- Migration 0016 preserved all 44 prior data tables. Source/images checkpoint is
  `pre-decisions-20261010`; checked pre-release backup is `20261010T175603Z`.
  Preserve new analysis/review data and existing forecasts/jobs/profile versions
  before rollback; old images require 0015. Sessions were renewed privately; no
  model setting or network exposure changed. No commit/push/merge occurred here.
  Phase 4D/4E remain unfinished, broader Phase 6 Frozen and all eight gates blocked.
- Checked post-release backup `20261010T180215Z` retains the new analyses/reviews
  and restarted API/jobs/storage with healthy readiness. Refresh/backup timers remain
  active. The maintained 64-item report is now **37 Done / 15 Partial / 12 Not yet**;
  the latest Desktop DOCX/PDF is dated October 10 and earlier report names are kept
  synchronized with backups. Competitor review still refers to October 5 sources.

- October 6 analytics interface redesign is Complete for local/test and the private
  demo. The public ThoughtSpot reference audit led to grouped navigation, question-led
  Home, dedicated chat, authorized data search/dashboard, reusable chart/table/expand
  controls and searchable saved-answer/study/board libraries. This is not complete
  ThoughtSpot feature or visual parity. Read `docs/interface-redesign-audit.md`,
  `docs/analytics-interface.md` and `docs/verification-interface-redesign.md`.
- Numerical labels/tables preserve returned strings, signs, zero and nulls; plot
  coordinates are approximate. Study date views remain observed points. Applied
  dashboard configuration is saved only after successful execution; all filters and
  record drills use existing authorized queries. Saved guidance/documents receive
  no calculation badge. A second question during active work stays an explicit draft.
- Interface evidence: 76 targeted backend/architecture cases, 17 frontend tests
  (eight new), all 29 distinct browser journeys, Ruff/mypy (148 files), types/lint
  and local/VPS production builds pass. The full browser attempt had 26 passes and
  three outdated-selector/navigation failures; all three corrected tests passed.
  Earlier focused/mobile failures and fixes remain recorded in the ledger.
- Eight deployed users passed eight real guidance jobs, eight exact saved replays,
  56 cross-user private-item denials with eight authorized controls and 72 layouts
  in 43.935 seconds, with zero browser errors and unchanged source metadata. This
  is a functional rehearsal, not sustained load. Two earlier checker-selector
  failures are retained; only test selectors changed between deployed attempts.
- A subsequent display-only caption cleanup passed the visualization browser case,
  fresh local/VPS builds and a deployed chart-header/exact-replay check. The eight-user
  rehearsal predates this caption cleanup; its report is retained separately.
- The interface release changes only web on migration 0015. API/jobs containers,
  database, models and network exposure are unchanged. Previous source lives at
  `releases/pre-interface-20261006/source`; web rollback tag is
  `pre-interface-20261006`. The verified `20261006T082942Z` backup remains available.
  Only this interface/report work is uncommitted on `phase2`; baseline `769acea`
  now retains forecasting and operations. No commit, push or merge occurred here.
  Phase 4D/4E remain unfinished, Phase 6 Frozen and all eight production gates blocked.
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
- October 6 forecast/audit and operations work are retained in baseline `769acea`
  on `phase2`. The subsequent interface work remains uncommitted. Phase 4D/4E remain
  unfinished and Phase 6 remains Frozen. Refresh and backup timers remain active.
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
Work is on local branch `phase2`, with baseline `769acea` preserving earlier work,
including the teammate's original `7d70cd7` and the later query/guidance repairs.
October 6 interface changes are uncommitted; this task did not push or merge into main.
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

The latest October 6 request prioritizes the ThoughtSpot-referenced analytics
interface. Its approved private-demo presentation slice is now verified and
running; full competitor parity and the marketing website were not established by
this work. Read its audit, interface contract and verification before extending.
Retain exact values, source-bound selections, observed-only study points, current
permissions and the distinction between guidance and executed calculations.
Do not promote exports, connectors or commercial readiness from a visual redesign.
