> **File use case:** Canonical delivery plan and phase-completion ledger.
> **What it does:** Defines scope, exit criteria, dependencies, and verified status for each professional delivery phase.

# ExecPlus Delivery Roadmap

Statuses are limited to `Complete`, `In progress`, `Planned`, and `Frozen`. A phase becomes complete only when its exit criteria are demonstrated by automated checks or an explicitly recorded operational review.

## Planning and product-positioning guardrails

- The September 2026 delivery window prioritizes the core product and activation capabilities allocated to Phases 1 through 3, plus enabling work for the export, metering, and billing capabilities in Phases 4 and 5. Full growth, commercial-hardening, and integration capabilities remain sequenced behind their required security and data foundations.
- A capability listed in this roadmap is planned scope, not evidence that it is implemented, production-ready, or included in a customer plan.
- Conversational analytics cannot begin until workspace isolation, upload validation, and deterministic profiling pass the Phase 1 acceptance criteria.
- ExecPlus may describe verified descriptive analytics and, after Phase 4 acceptance, limited basic time-series forecasting. It must not advertise full predictive or prescriptive analytics.
- Advanced forecasting, scenario planning, anomaly detection, and prescriptive recommendations remain frozen until the core product, evaluation, security, and approval-workflow gates pass.
- The product direction is a persistent data partner with editable business definitions, reproducible answers, source freshness, and permission-aware memory. "Understands all data" and "connects to anything" are goals, not supported-capability claims.
- Encoding serves separate purposes: typed analytical snapshots for exact queries, embeddings plus keyword indexes for evidence discovery, and versioned statistical features for approved analyses. Preserve original data; embeddings never replace records, calculations, permissions, or privacy controls.

## Revised remaining delivery sequence — 2026-09-30

The user requested that the data-partner improvements be incorporated into the
remaining phases before implementation continues. The subsequent instruction to
start Phase 3 delivered slice 3A on September 30, with evidence linked below.
Phases 0–2 keep their verified acceptance scope. Slices 3A–3C are verified and
deployed; 3D's reviewed evaluation is complete with a do-not-adopt decision.
Phase 3 is Complete for the approved private-demo scope; all deferred production
requirements remain mandatory in Phase 5. See [closure evidence](docs/verification-phase3d.md).

| Phase | Status | Remaining outcome |
| --- | --- | --- |
| 0–2 | Complete | Preserve foundation, ingestion and verified analytics contracts |
| 3 — Data understanding, conversation and knowledge | Complete | Private-demo understanding, unified conversation, catalog and candidate assessments verified; production reviews remain in Phase 5 |
| 4 — Connected analysis, studies, collaboration and export | In progress | 4A studies/dashboards and 4B refresh/alerts verified and deployed; 4C–4E basic forecasts, exports and two controlled connectors remain |
| 5 — Commercial readiness, billing and alpha | Planned | Validate representative quality, production security, recovery, operations, billing and customer onboarding |
| 6 — Broader integrations and advanced decision support | Frozen | Expand connectors/formats and introduce separately validated advanced analysis |

Two initial read-only connector deliveries, Google Sheets and PostgreSQL, move
from Phase 6 into Phase 4E. They depend on confirmed dataset meaning and tested
refresh/permission contracts. The remaining integrations and advanced capabilities
stay in Phase 6. A source connector does not grant access to the ExecPlus
control-plane database or permission to expose the private demo publicly.

The target is to make as much verified progress as possible on September 30, not
to declare every phase finished that day. Delivery order is **3A → 3B → 3C → 3D →
4A → 4B → 4C → 4D → 4E**, with Phase 5 evidence collection alongside eligible work.
Phase 4 may proceed after the new Phase 3 feature slices are verified while the
explicitly deferred production gates remain open; Phase 5 must close those gates
before external customer deployment. Phase 6 requires its activation criteria.

The first implementation slice, **3A: upload → inferred meaning → focused user
confirmation → versioned understanding**, is verified and deployed to the private
demo. Slices 3B–3C have local and deployed acceptance evidence; 3D is now complete
with a reviewed rejection of the optional judge. Phase 4A is now verified and
deployed, followed by verified 4B refresh/monitoring. The next implementation slice is 4C. At each delivery checkpoint,
record files, checks, live-demo evidence and unresolved dependencies; retain the
last known working VPS release until replacement checks pass.

Real connector account access, representative-data approval, production identity,
domain/HTTPS, SMTP, payment-provider setup and independent reviews remain external
inputs where required. Fixtures can verify adapter behavior but cannot substitute
for live integration or release acceptance. No delivery date clears these requirements.

## September 2026 delivery focus

The monthly focus is organized as dependency-ordered vertical slices. Unfinished scope carries forward without weakening an acceptance gate.

1. Secure activation foundation: organization and user workspaces, team invitations, isolated CSV and Excel upload, a guided upload wizard, sample datasets, column identification, data-quality validation and scoring, and traceable cleaning and mapping.
2. Descriptive analytics activation: recommended dashboards, KPI cards, trends, filters, drill-down, natural-language questions, management summaries, saved analyses, saved questions, prompts, and finance, sales, inventory, and HR KPI libraries.
3. Retention and commercial foundation: sharing, scheduled email reports, usage metering, customer usage analytics, feedback capture, in-app onboarding, exports, subscription management, payments, billing, and plan upgrades.

The phase definitions below remain authoritative for implementation order and completion evidence.

## Phase 0 — Engineering foundation

**Status:** Complete  
**Completed:** 2026-09-02

Delivered:

- Product invariants and system boundaries documented.
- Modular monorepo created for the API and web application.
- Domain-first backend dependency rules established.
- Replaceable language-model and embedding-store ports established.
- Local and hosted model routing expressed through validated configuration.
- PostgreSQL and S3-compatible local infrastructure defined.
- Health/readiness API and project-status UI implemented.
- Backend unit and architecture test foundations added.
- CI, linting, type checking, environment template, and developer commands added.
- Architecture decision records created for modularity, exact computation, and provider neutrality.

Exit evidence:

- Python modules compile.
- Baseline tests pass in an installed development environment.
- Frontend type and lint checks pass in an installed development environment.
- No runtime dependency points directly at a vector database vendor.
- Reverified 2026-09-07: compilation, backend tests, frontend tests/lint/types/build, and expanded architecture checks pass. Detailed evidence and the local infrastructure limitation are in [the verification record](docs/verification-week1.md).

## Phase 1 — Secure ingestion and profiling

**Status:** Complete

**Completed:** 2026-09-08

Week 1 secure workspace/ingestion foundation and the remaining Phase 1 preparation
and activation scope are implemented for the supported local/test identity flow.
Evidence: 134 backend tests against PostgreSQL 16.10 and MinIO, 2 frontend tests,
4 real-service browser tests, lint/types/compilation and production web build.
Profiles, stable quality scores, reversible cleaning/mapping, versioned synthetic
samples, guided onboarding and privacy-safe usage events are covered. See
[Phase 1 verification](docs/verification-phase1.md) and
[data preparation contracts](docs/phase1-data-preparation.md).

Production identity/deployment remains outside this local/test acceptance scope.
Phase 2 has since been implemented and audited; see its verification record below.

Scope:

- Authentication, organization and user workspaces, workspace membership, and team invitations.
- Configurable seat limits from 3 to 50.
- Workspace-isolated dataset metadata, upload records, object storage, and audit events.
- Guided upload wizard for single-table CSV and single-sheet Excel files up to 20 MB.
- Versioned finance, sales, and inventory sample datasets that contain no customer or secret data.
- Clear rejection of multi-sheet files, merged cells, unsafe formats, and size violations.
- Automated column identification and deterministic profiling for row count, column count, inferred types, date ranges, dimensions, metrics, and semantic tags.
- Data-quality validation and a reproducible quality score covering missing values, duplicates, type conflicts, invalid dates, and unsupported structures.
- Previewable, reversible basic data cleaning and column mapping with source-to-output lineage.
- In-app onboarding for workspace creation, invitation, sample-data exploration, and first upload.
- Usage-event foundations for uploads, storage, seats, and profiling activity without recording uploaded row values.

Exit criteria:

- Cross-workspace access tests prove isolation.
- Parser fixtures cover valid, malformed, oversized, multi-sheet, and merged-cell inputs.
- Profiling results are reproducible for fixed fixtures.
- Cleaning and mapping tests prove the original upload is retained and every transformation is reconstructable.
- Quality-score fixtures produce stable results with actionable explanations.
- A non-technical user can create a workspace, invite a teammate, upload a supported file, and understand its profile.

## Phase 2 — Verified conversational analytics

**Status:** Complete

**Verified:** 2026-09-17 for supported local/test operation.

The teammate's `phase2` commit (`7d70cd7`) was audited against implementation and
acceptance tests. Decimal accuracy, SQL isolation, replayable receipts, competing
mapping guards, thread privacy, summary grounding and saved/share UI gaps were fixed.
Golden/injection/tenant tests and the real-service browser journey pass. Live model
quality comparisons remain the separate Phase 3 evaluation gate.
See [Phase 2 verification](docs/verification-phase2.md) and
[analytics contracts](docs/phase2-analytics.md).

Scope:

- Curated semantic definitions and join-path representation.
- Finance, sales, inventory, and HR KPI libraries with versioned definitions, required fields, units, and validation fixtures.
- Finance, sales, and inventory dashboard templates backed by those governed KPI definitions.
- Intent router for numerical, textual, unsupported, and ambiguous questions.
- Read-only SQL planning, parsing, validation, cost limits, timeout limits, and DuckDB execution.
- Clarification guard for competing metric or dimension mappings.
- Multi-turn thread state using structured references rather than raw prompt history alone.
- Natural-language questions, suggested questions, and reusable prompt starters derived from the authorized profiled schema.
- Answer assembly and AI-generated management summaries from executed rows and authorized evidence only.
- Descriptive dashboards with KPI cards, trend analysis, filters, and permission-aware drill-down.
- Automated dashboard recommendations derived deterministically from profile and KPI compatibility.
- Saved questions, prompts, dashboard configurations, and analyses scoped to a workspace and owner.
- Permission-aware links for saving and sharing analysis within a workspace.
- Calculation lineage and complete audit trail.

Exit criteria:

- Golden question suites return exact expected values.
- Prompt-injection tests cannot bypass read-only or tenant constraints.
- Ambiguous and unsupported questions never execute a query.
- Each numerical answer can be reconstructed from stored lineage.
- Dashboard cards, trends, filters, and drill-down values match the underlying executed results.
- Management summaries cannot introduce a number absent from executed evidence.
- KPI-library and dashboard-recommendation fixtures are deterministic and explain why each recommendation applies.
- Shared analyses cannot be opened outside their authorized workspace or role.

## Phase 3 — Data understanding, conversation and hybrid knowledge

**Status:** Complete for approved local/test and private-demo scope, September 30.
Deferred production acceptance remains mandatory in Phase 5.

Implemented and tested for local/test operation: ranked profile observations,
executed comparison commentary, self-subscribed scheduled reports with delivery-time
authorization, bounded feedback, usage summaries, server-managed onboarding,
TXT/Markdown ingestion, scoped chunks/citations and a reference hybrid ranker.
The web workspace exposes insights, feedback, documents, saved work and subscriptions.
Slice 3A is **Complete** for the supported private-demo scope. Slices 3B–3C
are verified locally and deployed with combined chat, resumable history, catalog discovery and
candidate measurements. Slice 3D is **Complete** after human label approval and
a fresh twelve-case evaluation. The judge failed adoption criteria and stays
disabled. See [the reviewed results](docs/verification-phase3d.md).

**Approved demo scope (2026-09-17):** use reproducible fictional documents and known
answers, with hosted DeepSeek V4 Pro for current model testing. The user deferred
representative-customer and comparative provider evaluation to pre-production work.
Demo evidence: six documents, twenty expected answers, 16/16 top-three retrieval,
20/20 live DeepSeek cases and 292 backend tests passing. This verifies the demo
historical milestone. The later 3A–3D work closes the private-demo scope; deferred
production validation remains open in Phase 5.
At that milestone the API/data services ran on the development machine; no local GPU
was required for hosted inference. Demo evidence must not be represented as customer validation.

**Private VPS demo (2026-09-28):** the user authorized a separately deployed demo
for about eight users, with domain/public access deferred. Dedicated API/web,
PostgreSQL, MinIO and Qwen3-4B services run on the inspected P100 VPS. Evidence:
298 backend tests, 24/24 concurrent API journeys and 8/8 deployed browser sessions.
An isolated backup restore verified all nine seeded objects. Qwen Q4 passed 19/20
fictional document cases; Q8 passed 16/20 and was not selected. Ambiguity handling
and representative quality remain open; these scores do not satisfy production
model acceptance. See [VPS operations](docs/vps-demo-runbook.md) and
[verification](docs/verification-vps-demo.md). The later private-demo closure is
recorded in [Phase 3D verification](docs/verification-phase3d.md).

**Conversational explorer (2026-09-28):** the user approved a redesigned interactive
workspace with a column/flow diagram, animated charts, paired chat turns, filtered
record requests and proactive profile observations. DeepSeek V4 Pro now plans
queries, while the separate Qwen3-4B helper suggests routes/columns and selects
verified evidence. Record results expose exact matching counts and explicit limits;
the new fictional city-sales sample supports the Karachi walkthrough. Migration
0008 preserves earlier conversations and adds the new turn kinds/model route.
Evidence: 320 backend tests, 6 real-service browser journeys, 6 live explorer checks,
2 additional live conversation checks, 8/8 concurrent browsers and 24/24 API journeys.
See [the explorer contract](docs/conversational-explorer.md) and
[verification](docs/verification-conversational-explorer.md). This is a private-demo
extension; the production gates below and the broader Phase 4 scope remain open.

**Deferred, mandatory production gates:** representative corpora, agreed retrieval
thresholds, learned embeddings/vector-provider selection and benchmarks, backup/restore,
local/hosted quality/privacy/cost comparison, SMTP rehearsal and production identity.
These are tracked in [the release ledger](docs/production-readiness.json) and are
required in Phase 5 before any external customer deployment. Production startup is
blocked until reviewed evidence is supplied. See
[demo setup and production follow-up](docs/phase3-demo-and-production-gates.md) and
[Phase 3 verification](docs/verification-phase3.md).

Scope:

- Three deterministic, ranked observations after profiling.
- Evidence-linked management commentary and variance explanations without unsupported causal claims.
- Scheduled email reports with workspace authorization checked again at delivery time.
- Customer feedback capture linked to feature context, workspace, and release without storing sensitive dataset values.
- Customer usage analytics for activation, feature adoption, retention, limits, and support signals.
- Product-managed onboarding checklists and automated dashboard, question, and next-step recommendations.
- Document ingestion and chunk metadata model.
- Embedding provider evaluation using representative customer corpora.
- Vector database benchmark and architecture decision record.
- Permission-first hybrid retrieval, reranking, and citations.
- Local and hosted model quality, latency, privacy, and cost evaluation.

Exit criteria:

- Scheduled reports contain only currently authorized analyses and have tested unsubscribe, failure, and audit paths.
- Feedback and usage reporting are tenant-safe and exclude uploaded row values, prompts containing source passages, and secrets.
- Management commentary cites the executed comparison and distinguishes observation from interpretation.
- Production gate (deferred to Phase 5): selected vector provider passes isolation, filtering, backup, latency, and cost tests.
- Citations resolve to accessible source passages.
- Demo retrieval/evidence selection is evaluated against fictional known answers; production relevance thresholds and representative-corpus evaluation remain mandatory Phase 5 gates.
- No retrieval path can expose a passage before authorization filtering.

### 3A — Confirmed data understanding and workspace memory

**Status:** Complete for supported local/test and private-demo operation.

**Verified:** 2026-09-30. Optional upload context, deterministic proposals, editable
and immutable shared meanings, private goals, reviewed declared relationships,
required metric filters, revision/concurrency guards and historical replay are
implemented. Evidence: 343 backend tests, 2 frontend tests, 7 real-service browser
journeys, lint/types/build, 6/6 live definition/model checks and 8/8 concurrent
deployed browsers. Migration 0009 is deployed after a verified backup. See
[contracts and limits](docs/phase3-data-understanding.md) and
[verification](docs/verification-phase3a.md). Legacy profile-only datasets keep
their inferred flow; new automatic relationship discovery, refresh and goal-driven
dashboards are not claimed here. Production gates remain open.

Scope:

- Offer optional domain and goal prompts before ingestion: sales, finance, inventory, HR, marketing, operations, research, other, or automatic detection. The selected label never overrides parser validation or authorizes another file format.
- Infer a dataset description, column roles and row meaning; ask focused post-profile questions only where uncertainty affects results. Distinguish one order from one order item, an identifier from a quantity, and an ordered rating from a general numeric measure.
- Separate file structure, business domain, column type, sensitivity and update behavior. The current CSV/single-sheet XLSX and TXT/Markdown support boundary remains until a separately tested parser is delivered.
- Store workspace-scoped descriptions, goals, currency/units, date/time-zone meaning, identifiers, metric definitions, missing-value conventions and relationship proposals. Do not silently combine currencies or treat unknown units as interchangeable.
- Give interpretations explicit inferred, confirmed, rejected or needs-review states; record author, evidence, version and source revision. Human corrections take precedence over later suggestions until deliberately revised.
- Confirm relationship keys and row cardinality before using joins; preserve governed KPI definitions and reject ambiguous mappings or duplicate-amplifying joins.
- Let authorized users inspect, edit and revoke shared business definitions. Keep personal preferences private by default and never let remembered context bypass current access checks.

Acceptance:

- Fixtures cover unfamiliar names, wrong category hints, identifier-like numbers, order/item grain, mixed currencies, ambiguous dates, duplicate keys and missing values.
- Corrections survive a new conversation and consistently affect downstream plans; earlier answers still replay with their original source and definition versions.
- Concurrent edits, revoked access, foreign-workspace lookups and source-schema changes cannot silently reuse invalid context or leak private memory.
- A browser journey proves upload, inference, clarification, correction and an inspectable saved definition. Unresolved definitions visibly limit the supported analysis.

### 3B — Unified data and document conversation

**Status:** Complete for local/test and private-demo operation, September 30. See the
[conversation contract](docs/phase3-unified-conversation.md) and
[verification](docs/verification-phase3b-c.md).

Scope:

- One conversation supports record queries, supported metrics, document questions and bounded combined requests. Replace the current separate-only document search experience with authorized tool orchestration while keeping direct search available.
- DeepSeek remains the primary planner; Qwen remains an advisory route/column/evidence selector behind provider-neutral ports. Resolve references using the selected data, confirmed definitions and versioned execution context.
- Represent mixed requests as explicit validated steps, with bounded tool calls, timeouts and clear partial-failure handling. Ambiguous or unsupported requests clarify or stop rather than silently dropping conditions.
- Present a concise answer with executed numerical evidence, accessible citations, source freshness, applied definitions, assumptions and useful follow-up actions. Distinguish a source's quoted numerical claim from an executed dataset calculation.
- Expose private conversation history and resumable investigations; reauthorize sources and identify changed revisions when resuming. Persist approved context, not unreviewed model assertions as facts.

Acceptance:

- Golden tests cover numerical, textual, mixed, follow-up, unsupported and ambiguous requests, including malicious source instructions and conflicting sources.
- Permissions apply before every query/retrieval and citation access, including revocation between steps. Missing evidence produces an explicit limitation rather than an invented answer.
- Every calculated value retains reproducible lineage; every cited passage resolves to its retained source. A combined browser journey proves both in one conversation.
- History and partial results stay private; retries do not duplicate turns or hide a failed analysis step.

### 3C — Efficient analytical and search representations

**Status:** Complete for the catalog and offline candidate-evaluation scope, September 30.
The learned candidate is rejected; Parquet remains an unadopted experiment.
No persistent cache or production vector provider is delivered. See
[ADR 0007](docs/decisions/0007-representation-and-judge-trials.md).

Scope:

- Benchmark immutable, typed Parquet snapshots with the existing DuckDB path for representative demo sizes; adopt only with measured benefit and exact-result parity. Preserve originals, decimal/large-integer contracts, historical receipts and profile-v1 reconstruction.
- Maintain a catalog of authorized datasets, definitions, relationships and source freshness. Index descriptions and document passages for discovery; never substitute nearest-neighbor row retrieval for an exhaustive filter or total.
- Evaluate learned embeddings plus keyword retrieval and reranking behind existing ports using known-answer fixtures. Record failures and costs; production provider selection and representative thresholds remain Phase 5 gates.
- Cache only against source revision, definition version, request parameters and current access scope; reject stale or unauthorized reuse. Invalidate derived snapshots, features and indexes after applicable edits, deletion or access changes.

Acceptance:

- Baseline/optimized comparisons report ingestion time, query latency, memory, storage and exact output parity; performance improvements are measured rather than assumed.
- Version-change, deletion, restoration and access-change tests cover derived artifacts and caches. Retained, authorized historical sources remain replayable; deleted or unavailable sources produce an explicit unavailable result rather than stale cached evidence.
- Search evaluation covers exact identifiers, synonyms, negative cases and accessible citations. A documented no-adoption decision is acceptable if a candidate fails its benchmark; it is not a claim that optimization or production search was delivered.

### 3D — Measured advisory judge

**Status:** Complete as a reviewed assessment with a do-not-adopt decision,
September 30. The user approved all twelve labels; the fresh reviewed trial matched
5/12, with six timeouts and one issue-label disagreement. The judge stays disabled.
See [verification](docs/verification-phase3d.md) and
[ADR 0007](docs/decisions/0007-representation-and-judge-trials.md).

Scope:

- Evaluate whether an independent review pass catches missing filters, wrong periods, incorrect metric meaning, unsupported conclusions and incomplete answers.
- Start with human-labeled synthetic cases and offline evaluation; an optional shadow run must not change user-visible answers. Record disagreements, missed errors, false alarms, latency and token/cost overhead against the no-judge baseline.
- Keep arithmetic, query safety, tenant access and evidence integrity under deterministic checks. Judges cannot introduce numbers, approve access, or clear production gates.

Acceptance:

- Set the scoring rubric and adoption thresholds before evaluation, including acceptable false alarms and added latency; retain reviewed examples and model versions.
- A decision record reports measured benefit or rejects adoption. Always-on judging is not a completion requirement and cannot be enabled solely because a judge exists.
- Tests cover judge outage, malformed feedback, prompt injection and private-context handling. Live adoption needs a separately tested policy and representative Phase 5 evidence.

## Phase 4 — Connected analysis, studies, collaboration and export

**Status:** In progress

The user authorized Phase 4 on September 30. 4A and 4B are verified and deployed;
4C–4E remain Planned. See [the pre-implementation audit](docs/phase4-gap-audit.md)
and [study contracts](docs/phase4-studies.md). Phase 3 remains complete for the
private demo and all production gates remain open.

### 4A — Adaptive dashboards, studies and collaboration

**Status:** Complete for approved local/test and private-demo operation on 2026-09-30.

Evidence: 420 backend tests, 2 frontend tests, 9 real-service browser journeys,
static analysis and a production build; final permission/repair checks passed.
Migration 0011 is deployed with 8/8 concurrent study browser journeys.
See [verification](docs/verification-phase4a.md). 4B is now verified below; 4C–4E remain Planned.

- Role-based access, multiple workspaces per organization, and department dashboards.
- Persistent dashboards with a maximum of six pinned results and permission-aware sharing.
- Choose supported chart components and starter questions from confirmed data meaning and the user's goal; show why each recommendation applies and allow correction or dismissal. Preserve keyboard navigation, mobile access and reduced-motion support.
- Tailor supported views to sales, finance, inventory, operations and tabular surveys using validated metric definitions; show insufficient-data states rather than guessing missing metrics.
- Save investigations as reproducible studies with their question, source revisions, definitions, preparation steps, executed methods, findings and limitations. Support authorized reopening, comparison and rerun against a new snapshot without rewriting the original.
- Provide descriptive survey/research views for distributions, missingness and group comparisons with explicit units, ordered categories and sample counts. Specialized inferential/causal methods remain Phase 6 scope.

### 4B — Refresh, proactive observations and alerts

**Status:** Complete for approved local/test and private-demo operation on 2026-09-30.

Validated staged-file replacement/append/merge, scheduled activation, source freshness,
schema/meaning review, six bounded monitors, replayable period/segment observations
and private in-app KPI alerts are deployed on migration 0012. Evidence: 458 backend
tests, 46 final targeted hardening/foundation checks, 2 frontend tests,
10 real-service browser journeys, static analysis/build, an additional refresh browser check and 8/8 simultaneous deployed refresh
browsers. The worker shares a maintenance lock with backups. See
[contracts](docs/phase4-refresh-monitoring.md) and
[verification](docs/verification-phase4b.md). Schedules consume explicitly staged
files; live connectors remain 4E. No production gate is cleared.

- Scheduled data refresh for supported workspace files; establish the refresh contract before 4E connectors consume it. Validate a candidate snapshot before activating it and preserve the previous usable revision on failure.
- Track freshness, ingestion state, source-schema changes and definition invalidation. A replacement, append or merge must be explicit, with deduplication rules where applicable.
- Recompute a bounded set of descriptive observations and period/segment comparisons after refresh; rank by declared relevance, magnitude and data quality. Persist method, filters, period, sample coverage and evidence for each observation.
- KPI alerts with thresholds, cooldowns, delivery state, and audit history.
- Variance and root-cause analysis that separates computed drivers from unverified hypotheses.
- Avoid calling a changed total an anomaly or a measured association a cause. Calibrated anomaly detection remains Phase 6.

### 4C — Basic forecasting and grounded commentary

- Basic time-series forecasting with uncertainty ranges and data-sufficiency checks.
- Forecast accuracy measurement and actual-versus-forecast comparison.
- Explainable forecast lineage, method, training window, backtest window, and limitations.
- Management commentary grounded in authorized actual, variance, and forecast outputs.

### 4D — Exports and user-visible evidence

- PDF dashboard and report export, Excel result export, PNG chart export, and CSV result export.
- User-visible audit history for uploads, cleaning, questions, dashboards, sharing, alerts, refreshes, forecasts, and exports.
- Carry the source revision, definition/method versions, freshness and assumptions into applicable study/report exports. Reauthorize generation and download, and handle spreadsheet formula injection in tabular exports.

### 4E — Connector framework and first read-only sources

- Define provider-neutral connection discovery, authentication, schema inspection, initial snapshot, refresh, cancellation and disconnect contracts. Declare source capabilities rather than implying every adapter supports identical sync modes.
- Deliver Google Sheets and an operator-approved PostgreSQL source as the first integrations. Limit reads to explicitly selected spreadsheets/tables and preserve source metadata and stable identities.
- Reuse 4B snapshot validation and freshness states; implement retry/checkpoint behavior, idempotency, credential expiry/revocation, schema-change review and declared deletion semantics. Permit full refresh when safe incremental tracking is unavailable.
- Use least-privilege source credentials, protected secrets, destination/network validation and connection-specific access checks. Never accept model-supplied connection strings, arbitrary network targets or data-changing queries.
- Inspect or approve key/cardinality relationships before analyses combine sources. Surface different source update times and prevent duplicate-amplifying joins.
- Keep disconnect, credential revocation and deletion of retained imported data separate, explicit operations. Update authorized search/cache/derived artifacts when retained data is deleted.

### Phase 4 exit criteria

- Role and workspace matrices prove tenant and department boundaries for every growth feature.
- Upload/domain corrections change the selected views and questions predictably; the adaptive UI never bypasses data sufficiency or renders untrusted generated code.
- A study can be reproduced from its saved versions; a refreshed rerun creates new evidence. Fixtures cover ordered survey responses, missingness, small groups and privacy of shared results.
- Alert thresholds, duplicate suppression, refresh failures, and delivery outcomes have automated coverage.
- Incomplete periods, stale sources and schema drift produce explicit limitations; observations and alerts recheck access and retain replayable evidence.
- Variance and root-cause outputs can be reconstructed from executed results and do not state unsupported causality.
- Forecast backtests, accuracy calculations, actual comparisons, sufficiency checks, and failure messages are validated on representative fixtures.
- Pin limits are enforced on the server.
- PDF, Excel, PNG, and CSV exports match authorized executed results and preserve calculation lineage.
- Both connector adapters pass real-source rehearsals with approved test accounts, alongside fixtures for pagination where applicable, retries, duplicates, deletion, revocation, schema drift, network restrictions and cross-workspace access. Mocks alone do not establish live connector completion.
- Public product language describes forecasting as basic and limited rather than full predictive analytics.

## Phase 5 — Commercial readiness, billing, and alpha

**Status:** Planned

Includes all deferred Phase 3 production validation in
[the production-readiness ledger](docs/production-readiness.json).
`make production-preflight` and production runtime startup must pass reviewed,
checksum-bound evidence checks before any external customer deployment. Synthetic
corpus results and a working DeepSeek connection cannot clear these gates.

Scope:

- Cloud deployment with isolated staging and production environments.
- Security hardening and verified customer-data isolation across application, query, retrieval, storage, export, and reporting paths.
- Managed database, object storage, secrets, encryption, backup and recovery automation, and restoration drills.
- Error monitoring, model and query tracing, AI-response evaluation, query cost controls, rate limits, budgets, and incident runbooks.
- Plan-specific usage limits and metering for seats, workspaces, uploads, storage, queries, model use, refreshes, schedules, forecasts, and exports.
- Subscription and payment management, billing history, plan upgrades, entitlements, grace periods, cancellation, and webhook reconciliation.
- Automated onboarding and provisioning backed by entitlement and workspace-isolation checks.
- Admin console for customer, workspace, plan, usage, job, support, and incident visibility without exposing customer row data.
- Customer-support workflow for feedback triage, account-safe diagnostics, escalation, and resolution tracking.
- Performance optimization supported by load, query, upload, dashboard, and export measurements.
- Product usage, activation, cohort-retention, and churn-risk reporting.
- Load, security, privacy, accessibility, and browser testing.
- Manual provisioning for five to six alpha companies.

Exit criteria:

- All deferred Phase 3 production gates have reviewed evidence and production preflight passes.
- Recovery objectives are documented and tested.
- Security and tenant-isolation review has no open critical findings.
- Service-level indicators and alerts cover the critical user journey.
- AI-response evaluations meet defined groundedness, numerical fidelity, refusal, and tenant-safety thresholds.
- Representative evaluations cover the new understanding, mixed-question, research-view, connector and optional judge paths. Report quality, failure/clarification rates, latency and cost for the actual configured DeepSeek/Qwen composition; do not reuse fictional-demo scores as production acceptance.
- All eight existing evidence gates remain mandatory: representative corpus, retrieval quality, vector provider, backup/restore, model comparison, provider privacy, report delivery and identity/security. Additional feature acceptance does not remove or satisfy a gate automatically.
- Production security and recovery include confirmed business memory, connector credentials, derived analytical/search artifacts, studies and exported files; deletion/revocation and restore are tested across those representations.
- Billing, payment, upgrade, downgrade, cancellation, and limit-enforcement test environments reconcile correctly.
- Admin and support access is least-privilege, audited, and unable to bypass workspace isolation silently.
- Performance budgets pass at representative alpha workloads.
- Automated and manual alpha onboarding and rollback runbooks have been rehearsed.

## Phase 6 — Broader integrations and advanced decision support

**Status:** Frozen

Phase 4E now owns the first Google Sheets and PostgreSQL source deliveries. This
phase expands the connector catalog and analysis methods after Phase 5 acceptance;
the revision does not unfreeze advanced features or promise universal connectivity.

Scope:

- QuickBooks or Xero integration.
- Zoho Books or Odoo integration.
- Additional Google Sheets and PostgreSQL capabilities beyond the tested Phase 4E contracts, driven by measured customer needs.
- Additional database and BigQuery connectors.
- New-format ingestion for approved JSON/API structures, PDF/document extraction and, separately, images/audio/video where needed. Every parser gets quality, provenance, resource-limit and permission tests before support is advertised.
- Advanced forecasts and scenario planning.
- Anomaly detection with explainable evidence and calibrated thresholds.
- Evaluated statistical feature pipelines, segmentation and relationship exploration. Exploratory discoveries retain method, coverage and uncertainty; repeated searches must not be presented as independently confirmed findings.
- Specialized study workflows for experimental or observational analysis, with reviewed assumptions, missing-data policies, uncertainty, multiple-comparison controls and clear limits on causal claims.
- Prescriptive recommendations with explicit limitations and source evidence.
- Recommendation approval workflow with human decision, rejection, and audit states.
- Multi-company consolidation with entity, currency, period, and elimination controls.
- Public API and outbound webhooks with scoped credentials, signing, retries, and rate limits.
- Embedded dashboards with tenant-bound tokens and host-origin controls.
- Detailed permissions and audit logs suitable for regulated customer review.
- Live Shopify connector, advanced email alerts, and native mobile applications.

Activation criteria:

- Phase 5 commercial-readiness criteria pass for representative customers.
- Connector authorization, refresh isolation, revocation, reconciliation, and deletion contracts are approved.
- Advanced forecast, scenario, anomaly, and recommendation evaluations have agreed accuracy, safety, and explanation thresholds.
- Research/statistical methods and new extraction formats have method-specific reviewed fixtures, failure criteria, source attribution and reproducibility evidence.
- Human approval is mandatory before any prescriptive recommendation can trigger an external action.
- Product and sales material continues to avoid claims of full predictive or prescriptive analytics until separately approved acceptance evidence exists.
