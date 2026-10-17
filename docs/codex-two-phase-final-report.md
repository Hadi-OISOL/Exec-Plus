> **File use case:** Reports the two-phase delivery against the original requirement IDs.
> **What it does:** Separates delivered local behavior, verification, live release and external gates.

# Two-phase implementation report

**Both phases are accepted within the documented local scope.** The backend,
frontend, browser, migration and recovery evidence is reconciled. Private-VPS
activation is a separate step and remains pending at this checkpoint.
The connector merge is integrated as `142a7dd`, preserving the accepted Phase 1
parent `2ee7d9c` and incoming `2188a2e` ancestry. Existing working changes and
private data were preserved. No push was performed.

## Requirement traceability

All rows describe bounded local functionality. A broader feature remaining Partial
does not mean its requested local implementation was skipped. The feature ledger
also retains external acceptance or explicitly broader product limitations.

| ID | Final ledger status / local delivery | Delivered behavior / primary code | Test and evidence entrypoint | Remaining boundary |
| --- | --- | --- | --- | --- |
| 13 | Done; local scope delivered | `result_exports.py`, portable renderers: protected deterministic PDF/Excel/CSV/eligible PNG; exact values, metadata, methodology, evidence and pagination | `test_portable_exports.py`, `test_result_exports.py`; [Phase 1](verification-codex-phase1.md) | Bounded supported artifacts; Excel precision may require exact text cells; protected source access is checked again before download |
| 1 | Partial; local scope delivered | `accounts.py`, password adapter, native account/session routes: signup, owned workspace, login/logout, password change, disable and operator recovery | `test_local_accounts*.py`, `e2e/local-accounts.spec.ts`; [account contract](local-accounts-onboarding.md) | Email is an unverified identifier; no email reset or identity-proof bypass; production identity/security review open |
| 47 | Partial; local scope delivered | Private saved setup progress connected to upload/sample, meaning/cleaning, analysis/dashboard, recommendations and teammates | Account integration/browser checks; [setup evidence](verification-local-accounts-onboarding.md) | User explicitly confirms shared meanings and approvals; pause/skip/Finish never imply completed data review |
| 14,46 | Partial / Done; local scope delivered | `plans.py`, versioned catalog/admissions: seats, datasets, file/storage, studies, processing, export and forecast/model allowances | `test_local_plans.py`, account/plan browser journeys; [plan evidence](verification-local-plan-entitlements.md) | Internal price-free assignments, not subscriptions or payment activation; global limits remain |
| 40 | Partial; local scope delivered | Shared actor/workspace/source/publication checks, origin/body limits, throttling, disabled-account and revocation guards | Native, scoped-source, connector security, export and customer API negative tests | HTTPS/public exposure, independent penetration/privacy review and production security are not cleared |
| 42 | Partial; local scope delivered | `rehearse_local_recovery.py`: bounded checksum-verified backup and disposable empty-target restore with read-only comparison/replay | `test_recovery_verification.py`, current0029 rehearsal; [recovery contract](recovery-rehearsal.md) | Production restore, off-server custody/retention and formal recovery objectives open |
| 43 | Done; local scope delivered | Operational metrics/incident collector and staff UI: redacted correlation, counts, observed windows, thresholds and in-app alert states | `test_operational_metrics.py`, operations regressions; [Phase 1](verification-codex-phase1.md) | No raw customer content, external paging or uptime guarantee |
| 44 | Partial; local scope delivered | Fixed synthetic numerical/citation/claim/privacy/replay evaluation; disabled providers and deterministic fakes | `docs/two-phase-evaluation-cases.json`, `scripts/check_analysis_evaluation.py` | 40 fixed cases /112 checks do not establish arbitrary model quality, live speed, cost or customer accuracy |
| 45 | Partial; local scope delivered | `usage_metering.py` and plan admission: actual supplied counters, configured estimates, atomic reservations, unknown exposure and local operation caps | `test_usage_metering*.py`, `test_usage_provider.py`, plan concurrency cases | Estimated exposure is not an invoice or a guaranteed provider-token upper bound |
| 50 | Partial; local scope delivered | Repeatable fixture/API benchmarks and shared validated XLSX parse avoiding duplicate work | [measured workflow evidence](verification-local-workflow.md) | Reported improvements and slowdowns are local; no general speedup or production-scale acceptance |
| 33 | Partial; local scope delivered | `contribution_studies.py`, `contributions.py`: period/file comparisons, ranked exact differences, eligible ordered price/volume/mix, coverage, drilldown, sharing/dashboard/export | `test_contributions.py`, `test_contribution_studies.py`, `e2e/contribution-studies.spec.ts`; [evidence](verification-contribution-studies.md) | Observed contributors are not proven causes; missing populations and unmatched products stay explicit |
| 56 | Partial; local scope delivered | Existing `advanced_forecasting.py`: eligible local statistical candidates, chronological selection and untouched holdout, empirical intervals, immutable vintages and later actuals | `test_advanced_forecasting.py`, `test_forecast_hardening.py`, forecast integration/browser cases | No universal reliability, external regressors or calibrated probability claim |
| 57 | Partial; local scope delivered | `source_scenarios.py`, `scenario_constraints.py`: simultaneous declared drivers, exact formulas, variants, sensitivities, units, outcome limits and immutable successors | `test_scenario_constraints.py`, `test_scenario_capacity_integration.py`, `e2e/scenario-capacity.spec.ts`; [evidence](verification-scenario-constraints-capacity-comparisons.md) | Hypothetical assumptions, not learned demand response or probabilities |
| 58 | Partial; local scope delivered | Existing seasonal/drift plus `rolling_anomalies.py` and `multivariate_anomalies.py`: past-only references, bounded explicit cohorts, exact flags, thresholds, feedback and source records | Domain/API/SQL-boundary cases, `e2e/advanced-anomalies.spec.ts`; [contract](advanced-anomaly-review.md) | Unusual does not mean fraud/error; drift and adaptation can mask sustained changes; no customer-calibrated false-alarm rate |
| 59 | Partial; local scope delivered | `large_allocation.py`, `allocation_sensitivity.py`: declared linear objectives/resources/rules, bounded CP-SAT, capacity alternatives, exact verification and specific infeasibility evidence | Domain and scenario/capacity integration/browser cases; [contract](scenario-constraints-capacity-comparisons.md) | Conditional recommendations; unknown/feasible results retain status; variants require separate saved approval; no external action |
| 61 | Done; local scope delivered | `company_consolidation.py`: owner-authorized manual company sources, mappings, reporting periods, explicit FX and balanced declared eliminations, layered private reports | `test_company_consolidation*.py`, `e2e/consolidation.spec.ts`; [evidence](verification-governed-distribution.md) | Requires current permission to every source; no guessed FX/eliminations or statutory accounting certification |
| 62 | Partial; local scope delivered | `integration_access.py` and existing outbox: hashed scoped expiring keys, quotas, saved-result/job reads, OpenAPI, signed metadata payloads and local receiver retry tests | `test_customer_results_api.py`, existing integration/webhook tests and browser journey; [API contract](customer-results-api.md) | Real outbound delivery disabled; no arbitrary URLs, provider setup or production delivery acceptance |
| 63 | Partial; local scope delivered | Existing embed grants/session path and `examples/local-embed-host`: one-use bootstrap, short dashboard/tenant/host scope, expiry/revocation and protected output | Integration/embed negative tests and actual local host browser journey; [evidence](verification-governed-distribution.md) | No broad credential in embedded JS; public domains/HTTPS/real hosting acceptance open |
| 64 | Partial; local scope delivered | Existing dataset policies extended through all new source receipts, saved results, sharing, consolidation, API, downloads and embedding; redacted audit events | Dataset-policy tests plus negative/late-revocation cases on each new surface | Visible cells do not create aggregate-only anonymity; regulated compliance and independent privacy review remain separate |

## Verification and retained failures

- Phase 1: 2,580 backend cases have latest passing executions across the retained
  full run and focused repairs, all37 original mappings pass, 76 distinct offline
  browser journeys pass and three model-only journeys remain explicitly skipped.
  This is combined coverage, not one clean full-run claim.
- Phase 2 full frozen backend collection contains2,932 cases. Five later regression
  cases bring the current collection to2,937. The only backend source deltas after
  freezing repair two final sharing/revocation windows; the original reproductions
  and focused56/61-case passing rechecks remain retained. Strict collection/run
  reconciliation accepts all2,937 latest passing cases, with no missing, skipped or
  unresolved backend cases. The frozen run passes2,932 in2,333.55 seconds; the
  repaired-source supplements cover the five added cases and final source changes.
- Current focused UI checks include six anomaly/calendar/scenario journeys,
  two contribution journeys and two governed-distribution journeys. The full110
  browser run finishes with106 passes, three model-only skips and one retained
  expired-session test timing failure. All four related operations journeys pass
  after a controlled-request test repair: **107 distinct passing executions and
  three explicit skips**, not one clean full run.
  All59 frontend tests, types/lint, Ruff and mypy319 pass.
- Current offline evaluation passes112/112 checks in40 fixed cases. Disposable0029
  recovery checks77 table fingerprints and three exact replays. A separate local
  migration checks50 original table projections and27 new empty tables through0029.
- Initial domain/test assertions, historical fixture failures, actual narrow-screen
  overflow, busy-state/duplicate-key defects and final sharing races are retained
  in their linked ledgers. Corrected runs do not erase failed evidence.

The [original37 regression report](regression-original-37.md),
[Phase 1 ledger](verification-codex-phase1.md), [Phase 2 ledger](verification-codex-phase2.md)
and [implementation matrix](codex-two-phase-implementation.md) are the detailed
acceptance records. Counts from overlapping focused runs must not be added.

The final ledger retains **41 Done /17 Partial /6 Not yet**, all64 original IDs
and all8 open production gates. All20 targeted requirements have delivered local
behavior. Partial rows explicitly retain broader/external acceptance; none is
claimed complete merely because its local implementation passed.

## Running and release boundaries

Use [Start ExecPlus](start-project.md) and the
[two-phase local walkthrough](two-phase-local-walkthrough.md). They include
fictional finance, sales, inventory, HR and company fixtures, dirty data, exact
expected calculations and a reproducible held-back forecast/actual comparison.
Native signup works without external credentials. Model/email/vector services and
outgoing delivery can remain disabled for the local demonstration.

The private VPS currently has only the separately verified
[CSS update](verification-oct17-styling-release.md), on schema0020. Its checked
backups and actual image/container/source preservation are recorded separately.
The full0029 release requires its own completed gate, immutable build, checked
backup, old-data/object preservation, fictional live checks and post-release backup.
No localhost result establishes production readiness.

External exclusions remain: payment/billing activation, SMTP/verified-email reset,
real external connectors/identities, live webhooks, public embedding/HTTPS,
independent security/privacy certification, production recovery custody/objectives,
representative live-provider evaluation and sustained customer-scale performance.
No new credentials are required to run the delivered local scope. All eight
production gates remain blocked until their own evidence exists.
