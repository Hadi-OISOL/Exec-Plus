> **Use case:** Retain objective local evidence for requirements 14/46 and the bounded requirement-45 increment.
> **What it does:** Records implementation paths, successful focused checks, initial defects and remaining gates without asserting production readiness.

# Local plan and model transport verification — October 17, 2026

The implementation contract is [local-plan-entitlements.md](local-plan-entitlements.md). All checks below use disposable PostgreSQL schemas and synthetic MinIO buckets through `data/verification/2026-10-17/two-phase/local_verify.py`. Provider tests use `httpx.MockTransport`; no hosted provider, production data, credentials, VPS, billing or deployment was used.

## Delivered code

- `domain/plans.py`: catalog presets, exact complete limit validation and bounded explicit periods.
- `application/services/plans.py`, persistence `plans.py`, routes `plans.py`, migration `0026_local_plans.py`: immutable assignment/catalog versions, workspace-serialized stock checks and idempotent admissions.
- Native registration and workspace creation use `initialize_native_workspace_plan` in their existing transaction. Every native workspace receives its explicit current Demo assignment; unassigned legacy workspaces retain prior behavior.
- `workspaces.py`, `studies.py`: seat/dataset/file/storage/study enforcement at actual creation/publication boundaries.
- `plan_executor.py`: shared governed query admission; exact original receipt replay remains available without new processing usage. `analytics.py` preserves checked source references in replay views.
- `forecasts.py`: precompute admission and a stable actor/workspace-scoped vintage for explicit retries.
- `result_exports.py`, `pdf_exports.py`, `consolidation_exports.py`: authorization before rendering admission; multi-company admission is atomic under ordered workspace locks.
- `usage_metering.py`: plan model-attempt admission shares the existing financial reservation transaction. Reconciliation, policy assignment, pending review and recovery now lock workspace before the active account/staff guard.
- `openai_compatible.py`: actual serialized request and streamed response byte bounds; compression refusal; no automatic retry of an oversized response; dispatched unknown exposure remains held.
- `plan-entitlements-panel.tsx`: owner remaining-capacity panel and administrator assignment form, integrated into existing Usage/Admin screens. Existing Radix selection component and design tokens are reused.

## Focused passing evidence

| Evidence | Command scope | Result |
| --- | --- | --- |
| `plan-initial-usage.xml` | Existing `test_usage_metering_integration.py` + `test_usage_provider.py` | 31 passed |
| `plans-recheck.xml` | Initial plan suite, new transport-bound tests and exact forecast replay regression | 17 passed |
| `plans-provider-recheck2.xml` | Complete plan suite at that checkpoint + transport bounds + existing usage-provider/provider-contract tests | 50 passed |
| `plans-surfaces.xml` | Three subsequently added customer-key/embed, atomic consolidation-export and malformed-header CORS tests | 3 passed |
| `plans-ruff-recheck.log` | Modified plan/usage/provider services, domain, routes, migration and focused tests | Passed |
| `plans-mypy-recheck.log` | Eight plan, usage-persistence and provider modules | No issues |

These runs overlap; do not add their totals as distinct test coverage. The later full phase gate is recorded in `verification-codex-phase1.md`. Browser evidence is owned by the coordinated phase gate; `apps/web/e2e/local-plans.spec.ts` is the real owner/admin/upload journey, not a mockup test.

Important assertions include simultaneous dataset creation admitting only one remaining slot; simultaneous identical operation IDs producing one admission; changed inputs conflicting; same-period reassignment retaining usage; an expired assignment refusing new work; seat/file/storage/study backend limits; parser never running after a rejected processing allowance; forecasts retaining one vintage on retry; PDF/Excel/CSV/PNG counting unchanged retries once; unrelated users unable to view/configure allowances; customer keys unable to bypass compute caps; authorized embed receipts reopening at the cap; and all-company export admissions rolling back if any company is blocked.

The account-disable regression holds a real workspace lock while a native administrator's model-ledger request starts. It verifies the account guard is not acquired ahead of the workspace and both operations finish without a deadlock, with disabled staff denied afterward.

Transport fixtures verify multibyte UTF-8 request size, oversized declared length, an incrementally oversized stream and compression refusal. Rejected requests create no provider attempt. Rejected responses close their streams, stop after one dispatch and retain unknown rather than zero costs. Successful bounded responses preserve actual reported token counts.

## Retained initial failures and corrections

- `plans-initial.xml`: nine passes and one replay conflict. The executor's new provenance check correctly noticed replay views had omitted source references. The replay builder now retains the already-verified sources; exact replay and read-only recovery rechecks pass.
- `plans-provider-final.xml`: eleven passes and one test-fixture failure. Native staff grants now require exact account-ID confirmation; the synthetic fixture and browser fixture were updated to use that required proof.
- The root's earlier operations-persistence check encountered a missing import in the newly added forecast hook. The import was repaired before the passing forecast/retry checks. Its initial log remains in the root ledger.
- Initial formatting/type logs retain mechanical long-line/import corrections and one executor type annotation fix. These did not require changing calculation results or weakening tests.

## Explicit limits

This is local allowance enforcement, not subscriptions or payment-derived activation. Processing counts logical upload/query operations rather than CPU seconds; a retry can repeat bounded work, while original evidence replay stays free of new admissions. There is no universal response cache. Global workload safeguards and the independent cost ledger remain in force.

No tokenizer-backed financial upper bound is claimed. Byte sizes are not tokens, configured exposure is not invoiced cost, and no hosted model quality/cost/latency measurement was attempted. Production deployment, customer-scale acceptance, operational billing and independent security review remain open.
