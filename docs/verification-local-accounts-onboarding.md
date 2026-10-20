> **File use case:** Records local password-account and private setup verification.
> **What it does:** Maps requirements 1/47 and related security repairs to implementation, synthetic tests and remaining gates.

# Local account and onboarding evidence — October 17, 2026

Scope is the local-only two-phase implementation. No VPS, production database,
real customer data, email service, external identity provider or payment system
was accessed. The original operator session flow remains supported. The contract
and operator commands are in [local accounts and guided setup](local-accounts-onboarding.md).

## Requirement traceability

| ID | Delivered local behavior | Main implementation | Verification |
| --- | --- | --- | --- |
| 1 | Native registration, password login/logout/change, expiration, disable and explicit operator recovery | `application/services/accounts.py`, `infrastructure/passwords.py`, `infrastructure/identity.py`, `presentation/routes/accounts.py`, `manage.py`, migration `0025` | `test_local_accounts.py`, `test_local_accounts_integration.py`, `test_local_account_migration.py` |
| 1 / 40 | Existing operator identities cannot be claimed; native invitation and staff authority require exact account approval | `services/workspaces.py`, `services/operations.py`, `persistence/repository.py`, native invitation approval route | Duplicate signup, provisioning refusal, invitation proof, staff proof and revoked-authority tests |
| 40 | Bounded request streams, origin/media checks, committed throttles, two hashing slots, active-account checks, revocation ordering | `presentation/account_request_guard.py`, `persistence/accounts.py`, shared repository/operations guards | Forged/missing lengths, chunk limits, foreign/duplicate origin, parallel rate admission, disabled jobs/keys/embeds and credential races |
| 47 | Private versioned setup guide with resume/pause/skip and explicit finish | `domain/accounts.py`, `services/accounts.py`, `workspace/onboarding-guide.tsx`, private table in `0025` | Guide privacy/conflicts, observed-versus-skipped activity, membership-removal cascade and browser journey |
| 1 / 47 | Password forms, account controls, original token sign-in and teammate approval UI | `workspace/account-access.tsx`, `account-security.tsx`, `page.tsx`, `local-accounts.module.css` | `e2e/local-accounts.spec.ts`; frontend typecheck |

No new dependency was added. Python's standard-library scrypt uses fixed
memory-hard parameters; the two-slot bound is per API process. Production worker
count and memory sizing remain deployment review work. Email is an unverified
identifier. Password recovery is an authorized local operator procedure; no
email-verified or self-service recovery claim is made.

## Focused runs

All backend commands used the sanitized local runner and synthetic PostgreSQL
`127.0.0.1:25432` / object store `127.0.0.1:29000`, disabled models/email/vector,
separate temporary schemas and buckets, and no inherited provider credentials.
Retained evidence is ignored under `data/verification/2026-10-17/two-phase/`.

| Evidence file | Observed result |
| --- | --- |
| `identity-unit-initial.xml` | 26 passed in 3.43 seconds |
| `identity-integration-initial.xml` | 16 passed in 38.46 seconds |
| `identity-security-regression.xml` | 94 passed, 5 failed in 106.8 seconds; failures below |
| `identity-final-focused.xml` | 55 passed, 1 failed in 72.16 seconds; final failure was a test UUID conversion |
| `identity-credential-race-recheck.xml` | Both create/revoke race cases passed in 5.06 seconds after the fixture repair |
| `identity-admin-guard-terminal.xml` | 35 unit cases passed in 3.98 seconds, including streamed admin JSON bounds and refusal of an echoing recovery terminal |
| `identity-join-lock-regression.xml` | Three existing join cases passed; two new race assertions initially expected the wrong denial status |
| `identity-join-lock-recheck.xml` | Both disable-versus-join races passed in 4.97 seconds with the existing service-level 403 contract |

The owned focused set has **65 distinct cases with passing executions across the
retained runs**, not one clean 65-case invocation. Earlier overlapping counts are
not added. Seven new backend source files pass mypy. Ruff passes the new account
source, migration and tests plus modified identity, management and operations
service files. Current frontend TypeScript checking passes.

The diagnostic browser run is retained in `identity-plans-incidents-browser/`:
3 passed, 4 timed out, 1 interrupted and 1 not executed in 607.057 seconds.
Decision/review compatibility, the operational incident UI, and native password
rotation/disable passed through real services. Three forecasts retained a loaded
helper that selected an already-active Radix option without navigating to the
Forecasts page. The signup case used an incorrect exact label selector for the
native workspace select; its snapshot showed the correctly loaded owned workspace
and private guide. Both helpers are repaired, with original assertions preserved.

The diagnostic run was deliberately stopped after the password journey to avoid
repeating those already-loaded selector failures. Interrupted/unexecuted cases
are not passes. The fresh full browser gate and corrected recheck below cover
all cases, cleared private state after membership revocation, and reviewed
desktop/mobile captures.
Numerical export/dashboard consistency belongs to the shared Phase 1 gate.

The first full browser run was interrupted when the editor closed, at journey
10 of 79, without a final report. Its log is retained in `phase1-full-browser/`.
The first restart (`phase1-full-browser-resumed/`) collected no tests because
orphaned synthetic test API/web processes still owned ports 8001 and 3001.
Their local test database, browser-bucket and disabled-model markers were checked
before stopping only those processes. The fresh isolated schema/bucket run in
`phase1-full-browser-resumed2/` finished with **74 passed, 3 explicit model skips,
2 failed test expectations and zero flaky/retried cases**, in 1,087.573 seconds.
The three native-account journeys, actual plan enforcement, operational alerts,
and all four corrected diagnostic journeys passed. The failures retained are:

- `operations.spec.ts`: the test expected the new identity before its intentionally
  held workspace response was released. Session loading correctly waits for the
  complete identity/workspace/account checks. The test now asserts pending sign-in
  and cleared old private/admin data, then the new identity after release.
- `result-exports.spec.ts`: its workbook verifier required the old `Result ` sheet
  prefix. The professional export now uses descriptive worksheet names. The test
  locates the exact `region` / `__value` table and still verifies every precise
  value, typed null, zero and negative number. Original XLSX/PNG/CSV artifacts and
  failed assertions remain in the full-run evidence.

A fresh isolated `phase1-browser-corrected/` run of **both complete files passes
all five journeys**, without skips/retries, in 88.411 seconds. It includes the
remaining real PDF download and data-preservation assertions. Together these
runs provide passing executions of **all 76 distinct offline journeys**, with
three explicit model-dependent skips; this is combined coverage, not one clean
full-suite execution. Only test expectations changed between these two runs.
Mobile and desktop account/guide, allowance and incident captures were reviewed;
controls remain readable, with the browser overflow checks passing at 1440,
390 and 320 pixels. No live model, external identity, production or customer-data
check is claimed.

Reproducible commands (the local runner sanitizes inherited provider credentials
and provisions disposable synthetic PostgreSQL schemas and object-store buckets):

```bash
python3 data/verification/2026-10-17/two-phase/local_browser.py data/verification/2026-10-17/two-phase/phase1-full-browser-resumed2 --reporter=line,json
python3 data/verification/2026-10-17/two-phase/local_browser.py data/verification/2026-10-17/two-phase/phase1-browser-corrected e2e/operations.spec.ts e2e/result-exports.spec.ts --reporter=line,json
```

Use a new output directory for a repeat run; the runner refuses to overwrite old
evidence.

### Retained initial failures and corrections

- The disabled queued-job assertion initially expected no conversation turn.
  Existing behavior correctly retains a failed turn. The repaired test asserts
  failed/unauthorized status, no query ID and no published numerical evidence.
- The historical `0024` snapshot test initially used current metadata containing
  a later incident column. It now reflects the actual historical schema before
  comparison. Upgrade preserves all prior table counts and retained-data downgrade
  guards pass in isolated disposable schemas.
- The revoke-race test initially passed an already typed UUID to the UUID string
  parser. It now passes the typed ID. Both concurrent credential cases pass.
- Both new join-race checks initially expected HTTP authentication status 401.
  They retain a direct service actor, so the established disabled-account service
  denial is 403. Corrected assertions pass; creation/listing waits safely for
  disable to commit, then denies access without a database deadlock. The join
  services now lock their workspace before the active-account authorization.
- Two shared readiness expectations still named `0024`, and an operations test
  expected an uncaught exception instead of the new safe 500 response. The parent
  implementation owns those shared corrections and their subsequent verification.
- Two Ruff test-style findings were corrected. One static-check invocation used
  the wrong identity file path; the corrected invocation passes. An initial web
  typecheck lacked the project Node path; the pinned Node invocation passes.
- Native session loading now uses the existing global busy/error handler, and
  account/guide read failures clear previously displayed private state. A failed
  guide write requires a fresh read before another update. The browser invitation
  journey includes actual membership removal and verifies the guide clears.
- The final frontend check initially flagged the guide's async reload call from
  an effect under the existing state-in-effect lint rule. It now starts from a
  microtask, retaining the failure-state clearing without suppressing the rule.

## Reproduction and remaining gates

Using the repository's local synthetic test environment:

```bash
PYTHONPATH=apps/api/src .venv/bin/python -m pytest apps/api/tests/test_local_accounts.py apps/api/tests/test_local_accounts_integration.py apps/api/tests/test_local_account_migration.py
```

Integration tests require the documented `EXECPLUS_TEST_DATABASE_URL` and local
object-store test settings. Use a disposable test database; do not point these
checks at production. The parent Phase 1 gate runs the complete regression,
migrations, build and browser workflows after coordinated integration.

External identity proof, verified-email recovery, public HTTPS and trusted proxy
configuration, independent penetration/privacy review, production capacity and
representative customer acceptance remain open. Disabling an account preserves
its data and historical evidence; it is not account deletion or retention erasure.

## Completed-guide browser follow-up

The existing signup/resume journey now explicitly skips the remaining unobserved
steps through the UI, clicks Finish, signs out/in and reopens the saved completed
guide. Recommendations remain unobserved and explicitly skipped; finishing never
invents activity. The focused execution passes in **22.949 seconds** with no
retries or page errors. Evidence: `phase1-onboarding-finish/browser.json` under
the October 17 two-phase evidence folder. This is the same journey already counted
in the 76 distinct passing offline cases, with stronger assertions.
