> **File use case:** Records the October 24 re-assessment of every Partial and Not yet row in the 64-item feature audit.
> **What it does:** Splits each row's acceptance criteria into private-demo code scope and external/production scope, cites passing evidence and states the verdict.

# Partial-feature re-assessment — October 24, 2026

Baseline: `docs/product-feature-audit.json` at `d614432`, **42 Done / 20 Partial / 2 Not yet**.
Result: **50 Done / 12 Partial / 2 Not yet** (all 64 original IDs kept).

## Rule used

Policy: "Done means the stated tested local or private-demo scope, never production
certification" (AGENTS.md rule 14, audit `update_policy`). Precedent: #1 became Done
once every in-scope behaviour had passing tests and only verified-email/SMTP/domain
items remained.

Criteria sources per row: the row's own feature text and note, the acceptance column
of `docs/partial-feature-closure-plan.md`, `docs/remaining-work-execution.md`,
`docs/advanced-analytics-research-plan.md` (57/58/59/63) and the Phase 6 scope in
`ROADMAP.md`.

A row is promoted only when **all** of these hold:

1. Every code-buildable criterion that is in scope for the private demo has passing
   automated evidence (re-run on October 24 where cheap; see below).
2. The feature's core outcome has run end to end against real components (the real
   API/database/browser, a real local HTTP server or host page) locally or live on the
   private VPS — not only against a mock of a third-party product or a hand-written
   protocol stub.
3. What remains is purely external or production-only: third-party accounts/keys,
   SMTP, public HTTPS/domain, independent security review, real customer data or
   labels, production-scale load, owner-approved prices/policies, payments.

A row whose own note or plan still lists an unbuilt code item stays Partial even if its
other gaps are external. A wrong Done is worse than an honest Partial.

## Tests re-run on October 24

- Backend (isolated PostgreSQL/MinIO test containers): **671 passed, 0 failed, 0 skipped** across 37 files covering rows 14, 24, 40, 42, 45, 47, 57, 58, 59, 62, 63 and 64 (plans, usage view/metering, report email, security, accounts, reset codes, recovery, backup coordination, compute broker, chat history, anomaly calibration/detectors, decisions, scheduling, simulation, integration access, webhooks, customer API, access policies, contributions, consolidation, workspaces).
- Browser (real API + web + Chrome, `scripts/check_browser.py`): **10 passed** in 6.0 min: `local-plans`, `usage-view`, `model-usage`, `local-accounts` (4), `chat-history`, `integrations` (keys + embed, passed first try), `dataset-access`.
- Local recovery rehearsal (`scripts/rehearse_local_recovery.py`, disposable containers):
  passed on schema **0031**, 78 tables equal, 3 exact replays, 6.5 s.

Live evidence cited from AGENTS.md: October 22 (release f590a4a813287580: register/cookie/
me/disable, security headers, no token box, 7 connector states) and October 24 (release
4028b7309e58531f on 0031: register/login/chats/usage live; checked backups
20261024T105921Z/20261024T110011Z; 81-question run 4 62/19/0 in
`docs/verification-live-datasets-20261024.md`). October 17 private-release API journeys
(`docs/verification-codex-private-release.md`) cover Demo allowances, scoped keys, embed
sessions and quota accounting live.

## Assessment

| ID | Feature | In-scope (private-demo, code) criteria and evidence | Remaining external / production items | Verdict | Reason |
| --- | --- | --- | --- | --- | --- |
| 14 | Usage limits and metering | Versioned plans, atomic stock/period admissions, idempotent retries, per-period accounting, owner remaining-capacity, 30-day daily history, near/reached notices, staff ranking, query concurrency limits: `test_local_plans.py` (16), `test_usage_view.py` (3), `test_usage_metering*.py`, `test_product_usage*.py`; browser `local-plans.spec.ts`, `usage-view.spec.ts`; live Demo allowances (Oct 17) and usage view (Oct 24) | Payment-derived plans and billing-grade metering (payments skipped by owner, #15/#28); production acceptance | **Done** | All limit/metering behaviour that does not depend on payments is built, tested and live. |
| 24 | Scheduled email reports | Scheduling, unsubscribe, access checks, retry after temporary failure, opt-in timer: `test_report_email_delivery.py`, `test_phase3_integration.py` | Approved SMTP account and sender; real deliverability | **Partial** | The only delivery evidence is a hand-written SMTP stub (`FakeSMTP`, plain socket, no TLS/AUTH). Missing in-scope item: exercise the STARTTLS/SSL + AUTH path against a real SMTP server implementation locally (e.g. a local Mailpit/aiosmtpd container). Email is disabled in the private demo, so no report has ever been delivered. |
| 33 | Variance and root-cause analysis | Period/file contribution, PVM, ranked root cause with exact drilldown, UI/exports/month picker: `test_contributions.py`, `test_contribution_studies.py`, `contribution-studies.spec.ts` | Representative validation of any causal method | **Partial** | The plan's "root cause beyond observed differences" needs at least one explicit-assumption causal/counterfactual module; none is built. Current output is accounting attribution only. |
| 40 | Security hardening | Native auth, origin/body checks, safe errors, rate limits incl. trusted-proxy keying, disable/revoke, session-fixation revoke, security headers, anti-framing, Secure cookies, token box removed from production builds, tenant guards: `test_security_hardening.py`, `test_local_accounts*.py`, `test_dataset_access.py`, `test_oauth_security.py`, `operator-signin.test.mjs`, `local-accounts.spec.ts`; live headers/no token box (Oct 22) | Public HTTPS/proxy setup; independent penetration and privacy review; production acceptance (`identity_security` gate) | **Done** | All code-side hardening listed for the feature passes tests and is live; what remains needs a domain or an independent reviewer. |
| 42 | Backup and recovery | Daily checked VPS backups pausing writers (`backup.sh`, `test_backup_worker_coordination.py`); isolated read-only restore verifier (`test_recovery_verification.py`, 9); actual VPS backup restored in isolation (0020, Oct 16, `docs/recovery-rehearsal.md`); encrypted off-server copy rehearsal (Oct 16); current-schema synthetic rehearsal re-run Oct 24 on **0031**; checked pre/post backups 20261024T105921Z/20261024T110011Z | Approved off-server destination and key custody; owner retention policy and recovery objectives (RPO/RTO); production restore drill (`backup_restore` gate) | **Done** | Backup and restore work and are rehearsed on the current schema; remaining items need an external destination or owner policy decisions. |
| 44 | AI-response evaluation | Offline 40-case/112-check evaluation, provider-free labelled routing/grounding sets, live 81-question harness with pandas cross-check (`test_demo_readiness.py`, `test_live_dataset_defects.py`, run 4: 62/19/0) | Representative customer questions/labels; provider privacy approval (`representative_corpus`, `model_comparison` gates) | **Partial** | 19 of 81 live answers are still Partial for code reasons (ratio/net computation not completed, label variants such as 'Store 1'/' store 1 ', two run-4 regressions #4 and #42, forecasts/correlation needing confirmed meanings). No agreed pass threshold exists. |
| 45 | Query cost controls | Atomic budget reservations, provider-reported counters, unknown-exposure holds, operator-only settlement, request/response byte bounds, pre-dispatch rejection, query concurrency 503 with receipt, model-attempt allowances: `test_compute_broker.py`, `test_usage_metering_integration.py` (12), `test_usage_provider.py`, `model-usage.spec.ts`; live allowances | Owner-approved provider prices and money caps (none configured; the code refuses invented prices); reconciliation against real provider invoices; production cost acceptance | **Done** | Every control is built and tested and the count/concurrency limits are live; money-denominated caps only need owner price input and provider billing access. |
| 47 | Automated onboarding | Registration + workspace, auto sign-in, first-upload guide with resume/skip/finish/reopen, unit suggestions, reset codes, chat history: `test_local_accounts_integration.py`, `test_account_reset_codes.py`, `test_chat_history_integration.py` (5), `local-accounts.spec.ts`, `chat-history.spec.ts`, `guided-review.spec.ts`; live sign-up/login/chats (Oct 22/24) | Verified-email recovery/delivery (SMTP + domain); representative customer acceptance | **Done** | Same shape as #1: the full onboarding journey works live; only email verification needs SMTP. |
| 50 | Performance optimization | Repeatable benchmarks with exact parity, 19-34% faster query loading, measured operations: `benchmark_data_workflow.py`, `test_synthetic_workflow_roundtrip.py` | Representative data/users and production-scale load | **Partial** | Missing in-scope item: a sustained-load rehearsal (even synthetic) against declared latency/error/resource thresholds. Existing eight-user runs are short functional rehearsals. |
| 52 | QuickBooks or Xero integration | Connectors with encrypted tokens, paging, limits, error mapping, isolation, staged refresh: `test_connector_safety.py`, `test_connector_refresh.py` (mock providers) | Intuit/Xero developer apps and sandbox companies; VPS configuration | **Partial** | Never run against the real APIs; mocks encode our assumptions about them. Blocker is external (sandbox keys). |
| 53 | Zoho Books or Odoo integration | Connectors incl. Odoo private-host blocking and limited RPC: `test_connector_safety.py` (mock providers) | Zoho/Odoo accounts; VPS configuration | **Partial** | Never run against real services. Blocker is external. |
| 54 | Google Sheets integration | Sign-in, Picker import, staged refresh: `test_google_access.py`, `test_connector_refresh.py`, `google-sheets.spec.ts` (mocked Google); Google configured live, consent page reached | One completed live sign-in and sheet import with a test Google user | **Partial** | Core outcome (a sheet imported from real Google) has not happened yet. Owner action with a test account. |
| 55 | Database/BigQuery connector | Read-only PostgreSQL connector end to end against a real server with a SELECT-only role, control-plane refused: `test_connectors_postgres_api.py`; BigQuery mock-tested | Google Cloud project/service account for BigQuery | **Partial** | The database half is real; BigQuery, named in the feature, is mock-only. |
| 56 | Advanced forecasts | Validation/holdout selection, Holt-Winters family, split-conformal 80% ranges, calendar-effect forecasts with 0/1 event column: `test_advanced_forecasting.py`, `test_advanced_forecast_integration.py`, `test_calibrated_forecasting.py`, `test_calendar_regression_forecasting.py` | Representative customer accuracy | **Partial** | Missing in-scope items: general numeric external regressors (only a 0/1 event column exists) and holiday calendars, both listed as open. |
| 57 | Scenario planning | Source-derived scenarios, constraints, sensitivity, low/high ranges, seeded 10,000-draw simulation: `test_scenarios_integration.py`, `test_source_scenarios_integration.py`, `test_scenario_constraints.py`, `test_scenario_simulation.py`, `scenarios.spec.ts` | Representative acceptance | **Partial** | Missing in-scope items: simulation results are not in PDF/Excel exports (`result_exports.py` has no simulation path) and correlated drivers; learned demand response is listed as open. |
| 58 | Anomaly detection | MAD/IQR, grouped, seasonal, rolling, drift, multivariate distance, zero-config scan, seeded false-alarm calibration for snapshot/grouped/seasonal/rolling: `test_detector_calibration.py`, `test_anomaly_calibration.py`, `test_advanced_anomaly_integration.py`, `advanced-anomalies.spec.ts` | Real labelled anomalies and agreed per-use-case thresholds | **Partial** | Missing in-scope item: multivariate distance and distribution drift still report `calibrated=False` (`multivariate_anomalies.py`, `distribution_drift.py`); the research plan's Isolation Forest/LOF trial is not done. |
| 59 | Prescriptive recommendations | Exact enumeration, CP-SAT up to 50 actions with resources, prerequisites/exclusions, capacity alternatives, multi-period scheduling with web form, independent verification: `test_decision_analysis_integration.py`, `test_large_allocation_integration.py`, `test_scheduled_allocation.py`, `decisions.spec.ts` | Validated real-world action effects (needs real outcome data) | **Partial** | Missing in-scope item: the research plan's first business decision module (e.g. inventory replenishment with stock/lead time/demand assumptions) is not built; the plan also keeps 59 Partial until an agreed evaluation. |
| 62 | API and webhooks | Hashed scoped expiring revocable keys, atomic rate windows, audited access, eight operations, signed metadata-only outbox with dedup/retry/backoff and revocation-before-transport, real loopback HTTP receiver verifying signatures: `test_integration_access*.py`, `test_customer_results_api.py`, `test_webhooks_integration.py` (7), `test_webhook_transport.py`, `integrations.spec.ts`; scoped keys live (Oct 17) | Approved real webhook destination and network allowlist; production capacity and security acceptance | **Done** | All code paths run against real HTTP servers; outbound delivery is off by default and only needs an approved destination. |
| 63 | Embedded dashboards | One-use host-bound bootstrap, short-lived frame session, source/sharing rechecks, frame-host restriction, forgery/expiry/revocation refusal in a real browser with the local embed host: `test_integration_access_integration.py`, `test_customer_results_api.py`, `integrations.spec.ts`; embed sessions live (Oct 17) | Public HTTPS, approved host domains, real hosting acceptance | **Done** | Embedding works end to end with a real host page and browser; only domain/HTTPS allow-listing remains. Note: `integrations.spec.ts` was flaky on this machine on Oct 23 (2/3). |
| 64 | Detailed permissions and audit logs | Versioned row/column grants enforced before calculation, reopen, export and delivery; both-source, organization, scoped-key and embed rechecks incl. sharing races; redacted audit history: `test_analysis_access_policies.py` (8), `test_dataset_access.py`, `test_contribution_studies.py`, `test_company_consolidation_integration.py`, `test_customer_results_api.py`, `test_workspace_integration.py`, `dataset-access.spec.ts` | Regulated-customer audit requirements, independent privacy/security review, compliance certification | **Done** | The permission and audit behaviour is built and tested; what remains needs a regulator/customer specification or an independent reviewer. |
| 15 | Subscription and payment management | — | Payments skipped by owner (noncommercial) | **Not yet** | Unchanged. |
| 28 | Billing and plan upgrades | — | Payments skipped by owner (noncommercial) | **Not yet** | Unchanged. |

## What would close the remaining Partial rows

- Code: 24 (real-SMTP local test), 33 (a causal module), 44 (ratio/net answers, label
  variants, two regressions), 50 (sustained-load rehearsal), 56 (numeric regressors,
  holidays), 57 (simulation exports, correlated drivers), 58 (calibrate drift and
  multivariate), 59 (one business decision module).
- Owner/external: 24 (SMTP account), 52/53 (sandbox accounts), 54 (one live Google
  import), 55 (Google Cloud project for BigQuery), 44/50/56/58/59 representative data.

No production gate changes. Promoted rows keep their external items in their notes.
