> **File use case:** Records Phase 2 consolidation, customer API and embedded-view evidence.
> **What it does:** Distinguishes tested local behavior from deployment and external acceptance.

# Governed distribution verification — October 17

Subsequent combined local acceptance is recorded in [Phase 2 verification](verification-codex-phase2.md).
The separately authorized [private release](verification-codex-private-release.md)
does not change the local-only scope of the focused executions below.

These changes extend the existing services; they add no migration, dependency,
provider, credential requirement or external delivery. All tests use synthetic
data and isolated PostgreSQL/MinIO. No deployment or production-data access occurred
in this slice. The root Phase 2 gate and release ledger remain separate.

| Requirement | Delivered local behavior | Code and test evidence | Remaining bounds |
| --- | --- | --- | --- |
| 61 | Organization-owner authority plus full access to every selected company source; private saved worksheets and protected exports; owner-only UI choices | `company_consolidation.py`, `consolidation-panel.tsx`, `test_company_consolidation_integration.py`, `consolidation.spec.ts` | Existing explicit prepared-ledger scope remains: 2–8 companies, exact supplied currency rates/mappings and balanced approved entries; no guessed accounting or automatic private sharing |
| 62 | Eight scoped read operations, saved study/forecast/analysis/job reads using existing replay, all-source key limits, current-policy checks, OpenAPI bearer declaration, multi-dataset owner UI | `integration_access.py` domain/service, `routes/integrations.py`, `test_customer_results_api.py`, `integrations.spec.ts` | Read-only existing results; no billing activation or external connector/delivery acceptance; existing signed metadata outbox remains disabled without explicit deployment configuration |
| 63 | Existing short-lived private embed path plus all-source replay checks, redacted read audit, runnable local host and actual browser handshake/revocation | `IntegrationAccessService.read_embed`, `examples/local-embed-host`, `test_customer_results_api.py`, `integrations.spec.ts` | Production HTTPS/domain deployment unverified; authorized data already displayed remains until expiry or next access check |
| 40/64 compatibility | Disabled native/external identities disappear from active-staff choices without deleting grants/history; ordinary sessions, API keys and embed sessions remain separated | `persistence/operations.py`, `test_operations_persistence.py`, integration negative cases | Independent privacy/security review and certification remain external gates |

## Passing commands and observed results

All backend commands use ignored `data/verification/2026-10-17/two-phase/local_verify.py`,
which removes inherited provider settings and supplies explicit synthetic endpoints,
disabled model/email/vector modes and the project virtual environment.

| Check | Observed result | Retained evidence under `data/verification/2026-10-17/two-phase/` |
| --- | --- | --- |
| `pytest test_company_consolidation.py test_company_consolidation_integration.py -q` | **60 passed**, 44.343s | `p2-consolidation-owner.{log,xml}` |
| `pytest test_integration_access.py test_integration_access_integration.py test_customer_results_api.py test_operations_persistence.py -q` | **64 passed**, 56.810s | `p2-integration-access.{log,xml}` |
| Final complete `test_customer_results_api.py` after two added cases | **15 passed**, 31.224s; 13 overlap the previous run | `p2-customer-results-final.{log,xml}` |
| Final key-sharing correction: integration domain, integration API and customer-result suites | **61 passed**, 78.778s; overlapping prior coverage plus three new boundary regressions | `p2-key-sharing-final.{log,xml}` |
| Scoped mypy for consolidation, integration service/routes and operations repository | Four source files pass | `p2-integration-mypy.log` |
| Web TypeScript | Pass | `p2-integration-types.log` |
| Ruff on changed backend/test files; targeted ESLint on integration/consolidation UI and browser fixtures | Pass after corrections | Final terminal runs; root full gate records combined checks |
| `local_browser.py …/p2-governed-distribution-browser consolidation.spec.ts integrations.spec.ts` | **2 passed**, no skips/flaky/failures, 57.346s including startup | `p2-governed-distribution-browser/browser.{log,json}` |

Backend tests cover users belonging to **both** company workspaces but lacking
organization ownership: options, field review, account preview, create, history,
reopen and every export are denied. Changing organization owner during projection
saves no result; changing it during PDF rendering discards rendered bytes. Earlier
full-source policy, membership, exact conversion/elimination, export and replay
cases remain in the same passing suite.

For each added API operation, responses equal the ordinary authorized response.
Wrong operation, wrong dataset/workspace, another owner's private result, ordinary
session substitution and revoked key are denied. Revocation during each core read
discards the response. A genuine two-source contribution study and shared dashboard
reject a key containing only the baseline dataset; a key containing both gets the
same exact display. Revoking the second source denies the API and existing embed.
Embed checks cover forged bootstrap/session, expired bootstrap, protected export
separation and read audit records containing no secret. Existing rate-limit,
membership-replacement and policy-race tests also pass.

The browser uses the real UI/API and a loopback TLS host with a synthetic certificate.
It verifies exact saved result reads through an owner-created multi-dataset key,
one-use parent/frame exchange, actual `frame-ancestors` rejection, revoked reads,
no credential storage and a failed post-create list read. That failure hides prior
private metadata and the new secret; a read-only retry shows exactly one created
key. The actual local-host HTML/CSS/JS refuses an API key, accepts an embed bootstrap,
clears its input, renders the saved dashboard and clears/revokes correctly.

Fifteen captures cover mapping/result forms, keys, embedded data and local host at
1440/390/320. Overflow assertions pass. Desktop key management and the 320px local
host were visually inspected. Captures are copied into the current browser evidence
under `captures/`; the two fixtures now derive future capture directories from the
runner's JSON report path, avoiding reuse of the historical October 16 directory.
That capture-path-only adjustment occurred after the passing journey; it changes
no product or assertion behavior.

## Corrections and limits

Initial static checks identified long lines/import ordering and an unnecessary
synchronous state reset in a React effect. Formatting and removal of that reset
resolved them; failed reads still clear state in their asynchronous error path.
One first lint command used a nonexistent workspace-local binary; the root-installed
ESLint was then run from the web workspace. A final shell initially lacked Node on
PATH; repeating with the project-local Node path passed after the capture-path
adjustment. There were no failing backend or browser
cases in the three runs above. Disabled-model fallback messages are expected in
the offline browser setup and do not claim hosted-model quality.

An independent agent read the new all-source/key/result/job checks and found no
concrete additional permission gap in that first review. A later follow-up identified
a separate sharing race: study/dashboard sharing or dashboard version could change
after the inner read's check but before the final API-key transaction. Three new
tests reproduced HTTP200 after those changes. The original failures remain in
`p2-key-sharing-race-initial.{log,xml}`. Study visibility/all-source authorization and
dashboard sharing/pin identity now run inside the final locked key transaction;
all61 relevant cases pass, along with scoped Ruff/mypy. The exact two-file change
from the parent gate's frozen snapshot is retained in `p2-key-sharing-final.patch`
and its hash manifest. These reviews and fixes are not a penetration test.
No full production readiness, external webhook delivery, independent privacy review
or real-world embedding acceptance is claimed. Parent-owned full regression/build
and the updated feature ledger determine the overall two-phase status.
