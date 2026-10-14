> **File use case:** Records evidence for the October 14 branch integration and analytics extensions.
> **What it does:** Distinguishes local checks, failures, remaining validation and unchanged VPS scope.

# October 14 analytics extension verification

## Scope and source

Merged `origin/phase3` (`2a93080`, October 13 at 23:27 Pakistan time) into `phase2`.
The branch adds the data-reading journey; the merge preserves existing interface
polish, startup documentation and local agent tools. The user also authorized
starting the Partial anomaly, scenario and recommendation work. The implemented
contracts are in [analysis extensions](analysis-extensions.md).

This is a local/test delivery. The existing VPS deployment was started/checked at
the user's request and returned dependency-ready health and HTTP 200 for the
workspace. No new application source, image or database migration was deployed.
An owner session was issued and authenticated; its token and restricted tunnel
key are saved only in ignored private local files. Existing sessions were not revoked.

## Verification ledger

- The initial 128-case analysis/scenario/merged data-brief regression selection passed.
- The first new 38-case run had 36 passes and two fixture failures: a median retained
  its valid Decimal scale (`100.0`), and a meaning fixture incorrectly used null for
  a string currency field. Corrected fixture expectations passed all 38 cases.
- Coverage includes local-baseline separation, missing/sparse groups, weighted
  reference statistics, distinct review IDs, bounded work and invalid numbers.
- Two-resource outcomes match an independent rational-arithmetic oracle across
  25 generated problems. Large exact benefits, infeasibility, mandatory quantities
  and zero/nonnegative resource constraints are checked.
- Compound scenarios verify multiplication rather than additive percentages,
  high-precision three-driver outputs, zero baseline behavior and invalid assumptions.
- Real PostgreSQL/MinIO HTTP checks cover source receipts, private admin denial,
  feedback, current/stale approval, compatible successors and tamper rejection.
- Full real-service backend/architecture suite: **1,046 passed** in 551.28 seconds.
  A final 71-case focused run passed, including two additional legacy-request
  compatibility cases and two malformed-model-name cases: **1,050 distinct passing
  backend cases** across these runs. The 40 analysis-extension cases are new.
- Frontend unit suite: **19 passed**. Python lint, mypy (160 source files),
  TypeScript, ESLint and the production web build pass.
- Browser checks: **seven distinct journeys pass**. The first run passed six
  (four merged data-reading journeys plus existing decisions and scenarios) and
  timed out in the new test on an exact label selector for a select element.
  Using its combobox role corrected the test; the new journey then passed in
  18.0 seconds. It covers grouped coverage, constrained recommendations,
  approval/replay, compound scenarios/successor inputs and 1440/390/320 layouts.
  Browser error lists were empty. The full historical browser suite was not rerun.
- Generated the October 14 Desktop DOCX; verified all 64 feature IDs remain in
  order. Status counts and the October 5 competitor-review date are unchanged.
- Fresh production preflight still blocks all eight gates, as expected.

Local detailed logs are retained under ignored `data/verification/2026-10-14/`,
including the initial browser failure and successful recheck. The successful
backend runs reported Starlette's deprecation warning for its HTTPX test client;
this is not a failed test. No unrequested HTTP client migration was made.

The initial full type check exposed SQLAlchemy 2.1 typing changes in existing
reporting and operator code. The supported dependency range is now 2.0.x and the
checks use 2.0.54. The merged data-brief parser also needed an explicit string-name
guard; malformed names now fail validation instead of indexing incorrectly.

The first Docker pull failed because registry DNS resolved to unreachable IPv6.
Local tests use isolated project containers/volumes with already cached PostgreSQL
16 (`pgvector/pgvector:pg16`, no vector feature enabled) and MinIO images. No shared
application containers or system network configuration were changed. Browser
verification uses installed Google Chrome through the optional executable setting.

The first app link supplied during VPS startup used `127.0.0.1`; browser sign-in
failed because the deployed API permits `http://localhost:18400`. An OPTIONS
check reproduced the 400 rejection for the numeric host and 200 for localhost.
The corrected `http://localhost:18400/workspace` link passed a real browser login
using the private session file. The startup guide and local memory now record
that exact origin. No CORS relaxation or VPS configuration change was needed.

## Limits and remaining work

No live model-inference quality evaluation, clean non-root application-image
rehearsal, sustained load test or new VPS release is claimed by this delivery.
The data-reading browser test uses a disclosed canned response over the real
governed API; it is not a live-provider result. Existing historical private-demo
evidence remains in its original ledgers.

Features 57, 58 and 59 remain Partial; totals remain 37 Done / 16 Partial / 11 Not
yet. Seasonality, multivariate/drift evaluation, representative labels, uncertainty,
source-derived multi-measure scenario models and larger business-specific decision
methods remain open. No production gate, provider or network exposure changed.
