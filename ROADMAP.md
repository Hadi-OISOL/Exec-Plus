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
Phase 2 is the next delivery phase and has not started.

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

**Status:** Planned

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

## Phase 3 — Proactive insights and hybrid knowledge

**Status:** Planned

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
- Selected vector provider passes isolation, filtering, backup, latency, and cost tests.
- Citations resolve to accessible source passages.
- Retrieval evaluation meets an agreed relevance threshold.
- No retrieval path can expose a passage before authorization filtering.

## Phase 4 — Growth-plan analytics, collaboration, and export

**Status:** Planned

Scope:

- Role-based access, multiple workspaces per organization, and department dashboards.
- Persistent dashboards with a maximum of six pinned results and permission-aware sharing.
- KPI alerts with thresholds, cooldowns, delivery state, and audit history.
- Variance and root-cause analysis that separates computed drivers from unverified hypotheses.
- Basic time-series forecasting with uncertainty ranges and data-sufficiency checks.
- Forecast accuracy measurement and actual-versus-forecast comparison.
- Explainable forecast lineage, method, training window, backtest window, and limitations.
- Scheduled data refresh for supported workspace files and connectors, with validation before replacement.
- Management commentary grounded in authorized actual, variance, and forecast outputs.
- PDF dashboard and report export, Excel result export, PNG chart export, and CSV result export.
- User-visible audit history for uploads, cleaning, questions, dashboards, sharing, alerts, refreshes, forecasts, and exports.

Exit criteria:

- Role and workspace matrices prove tenant and department boundaries for every growth feature.
- Alert thresholds, duplicate suppression, refresh failures, and delivery outcomes have automated coverage.
- Variance and root-cause outputs can be reconstructed from executed results and do not state unsupported causality.
- Forecast backtests, accuracy calculations, actual comparisons, sufficiency checks, and failure messages are validated on representative fixtures.
- Pin limits are enforced on the server.
- PDF, Excel, PNG, and CSV exports match authorized executed results and preserve calculation lineage.
- Public product language describes forecasting as basic and limited rather than full predictive analytics.

## Phase 5 — Commercial readiness, billing, and alpha

**Status:** Planned

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

- Recovery objectives are documented and tested.
- Security and tenant-isolation review has no open critical findings.
- Service-level indicators and alerts cover the critical user journey.
- AI-response evaluations meet defined groundedness, numerical fidelity, refusal, and tenant-safety thresholds.
- Billing, payment, upgrade, downgrade, cancellation, and limit-enforcement test environments reconcile correctly.
- Admin and support access is least-privilege, audited, and unable to bypass workspace isolation silently.
- Performance budgets pass at representative alpha workloads.
- Automated and manual alpha onboarding and rollback runbooks have been rehearsed.

## Phase 6 — Integrations and advanced decision support

**Status:** Frozen

Scope:

- QuickBooks or Xero integration.
- Zoho Books or Odoo integration.
- Google Sheets integration.
- Database and BigQuery connectors, including PostgreSQL.
- Advanced forecasts and scenario planning.
- Anomaly detection with explainable evidence and calibrated thresholds.
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
- Human approval is mandatory before any prescriptive recommendation can trigger an external action.
- Product and sales material continues to avoid claims of full predictive or prescriptive analytics until separately approved acceptance evidence exists.
