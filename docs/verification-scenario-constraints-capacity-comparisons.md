> **File use case:** Evidence for the Phase 2 scenario/allocation additions to original requirements 57 and 59.
> **What it does:** Separates observed synthetic local results from pending combined and deployment checks.

# Verification — scenario limits and capacity comparisons

Date: October 17, 2026. Contract:
[`scenario-constraints-capacity-comparisons.md`](scenario-constraints-capacity-comparisons.md).
Work extends the accepted Phase 1/connector source; existing uncommitted work was
preserved. No VPS commands, provider calls, customer records, dependencies or
migrations were used for this slice.

## Evidence completed

Evidence lives under ignored `data/verification/2026-10-17/two-phase/`. Local runners
explicitly select disposable PostgreSQL schemas and object-store fixtures, disable
models/email/vector integrations and remove inherited provider settings.

| Verification | Result | Evidence |
| --- | --- | --- |
| Initial new and old scenario/allocation domain cases | 117 passed, 17.43 s | `phase2-scenario-allocation-domain.{log,xml}` |
| Final domain plus existing source scenario and larger-allocation integration regression | 162 passed, 124.57 s | `phase2-scenario-allocation-regression.{log,xml}` |
| New protected API/export/quota scenarios | 23 passed, 92.74 s | `phase2-scenario-capacity-integration.{log,xml}` |
| Atomic computation admission | Passed in two-case run; second case had a test harness failure | `phase2-model-admission-extra.{log,xml}` |
| Source changes between sequential solves | Corrected test passed, 4.58 s | `phase2-model-source-change-recheck.{log,xml}` |
| All-infeasible alternatives: exact Excel tables and no fabricated PNG chart | Passed, 4.88 s | `phase2-infeasible-capacity-export.{log,xml}` |
| Frontend unit suite | 59 passed, no skipped tests | `phase2-scenario-capacity-web-unit.log` |
| Frontend typecheck and lint | Passed | `phase2-scenario-capacity-types.log`, `phase2-scenario-capacity-lint.log` |
| Final frontend typecheck and lint after browser repair | Passed | `phase2-scenario-capacity-types-final2.log`, `phase2-scenario-capacity-lint-final2.log` |
| Mypy for eight changed domain/service/route files | Passed after local-variable type repair | `phase2-scenario-capacity-mypy-recheck.log` |
| Ruff for five owned domain files and three new test files | Passed | Command below |
| Both existing v1 browser journeys | 2 passed; two new journeys initially failed | `scenario-capacity-browser-attempt1/browser.{json,log}` |
| New capacity comparison journey | Passed, including three layouts; scenario overflow remained | `scenario-capacity-browser-attempt2/browser.{json,log}` |
| New scenario limit journey after final sizing repair | 1 passed, 21.798 s | `scenario-capacity-browser-attempt4/browser.{json,log}` |
| Combined final stylesheet gate | All six selected journeys passed, 107.541 s; new scenario 15.137 s and capacity 20.565 s | `p2-anomaly-scenario-browser-final/browser.json` |

The 117 initial domain cases overlap the 162 regression cases; do not add them.
There are 26 distinct new integration cases with passing executions across the
listed runs, giving 188 distinct backend cases for this slice. This is combined
passing coverage, not one clean 188-case run. Root owns the final combined gate.

## What the tests establish

- Exact independent `Fraction` checks distinguish a rounded `100/3` margin display
  from its true boundary. Zero/negative sales produce unavailable v2 margins;
  historical v1 behavior remains unchanged. Declared thresholds, confirmed units,
  simultaneous alternatives and every sensitivity point are checked.
- Six real bounded capacity solves agree with independent rational enumeration on
  the fixture. Mandatory prerequisite quantities produce exact resource shortfalls;
  retained evidence distinguishes independent arithmetic proofs from solver-only
  conclusions. Unknown and feasible-only outcomes retain their actual limitations.
- Reopening does not call the allocation solver. Tampered results and exact checks
  fail replay/export. Original v1 source and allocation paths remain compatible.
- PDF, Excel, CSV/evidence and PNG exports contain authorized exact results and
  omit restricted rows/columns. Current permission revocation prevents reopening
  and exporting previously saved private results; a workspace administrator cannot
  read another actor's private run.
- Approval covers only the original allocation. Source meaning changes preserve
  historical evidence but make the old approval ineffective.
- Same-key identical retries deduplicate admissions; changed budgets or scenario
  limits admit new computation even when the governed projection is unchanged.
  Concurrent attempts cannot bypass a one-operation limit. Exhaustion or revoked
  source scope between solves stops subsequent computation and publication.
- Six saved-replay cases cover zero and expired processing plans for scenarios,
  allocations and calendar analyses. Reopening is unchanged and uncharged; new
  computation is refused. New exports retain their separate allowance.

## Retained failures and limits

The first static pass found formatting and a reused local variable with an
incorrect inferred type. Owned files were formatted and the final scenario report
variable was given its own name; no arithmetic changed. The initial mypy output
is retained in `phase2-scenario-capacity-mypy.log`.

The initial source-change test called synchronous `TestClient` from the fake async
solver's event-loop thread, causing a redacted 500. Two diagnostic logs retain the
failure. Moving the fixture's source update to `asyncio.to_thread` allows the real
source-currentness rejection to pass; no production exception handler was weakened.

All four distinct browser journeys have passing executions across retained runs,
with no skips or retries. The new journeys exercise actual Radix controls,
source-confirmed units, exact outcome checks, saved reopening, unchanged source
content, original-only approval, successor drafts and explicit Excel/PNG downloads.
Both new result screens fit 1440, 390 and 320 pixels without page overflow or page
errors. Six final captures are in `scenario-capacity-browser/`; desktop and mobile
captures were visually inspected. These are local real-service checks, separate
from deployment. The primary session's final shared-stylesheet gate also passes
both new journeys together with four anomaly/calendar journeys, with no failures,
skips, retries or flaky passes. It repeats these two cases and does not add new
distinct scenario/allocation journeys.

The first browser attempt retains a scenario overflow and a new-test capacity
selector that did not account for helper text in the label. The second attempt
passes capacity but retains scenario overflow; the third shows that changing the
form's grid track alone was insufficient. The diagnostic proves Chrome expanded
the review fieldset to 669 pixels around a 640-pixel table at a 390-pixel viewport.
Explicit zero inline minimum and bounded fieldset width fix that layout while the
exact table keeps its own horizontal scroll. The fourth attempt passes the entire
scenario journey. All four failed executions and the original overflow capture
remain in their attempt logs/JSON and diagnostic files.

This slice uses synthetic rows only. It does not establish representative customer
quality, arbitrary optimization, causal uplift, production load, deployment,
independent security review or any external integration readiness. Source scenarios
remain fixed-mix conditional arithmetic; allocations remain small integer models
with explicit additive assumptions and bounded searches.

## Reproduce locally

```bash
python3 data/verification/2026-10-17/two-phase/local_verify.py pytest \
  apps/api/tests/test_scenario_constraints.py \
  apps/api/tests/test_allocation_sensitivity.py \
  apps/api/tests/test_source_scenarios.py \
  apps/api/tests/test_large_allocation.py \
  apps/api/tests/test_source_scenarios_integration.py \
  apps/api/tests/test_large_allocation_integration.py \
  apps/api/tests/test_scenario_capacity_integration.py

python3 data/verification/2026-10-17/two-phase/local_verify.py ruff check \
  apps/api/src/execplus/domain/scenario_constraints.py \
  apps/api/src/execplus/domain/allocation_sensitivity.py \
  apps/api/src/execplus/domain/source_scenarios.py \
  apps/api/src/execplus/domain/large_allocation.py \
  apps/api/src/execplus/domain/large_allocation_queries.py \
  apps/api/tests/test_scenario_constraints.py \
  apps/api/tests/test_allocation_sensitivity.py \
  apps/api/tests/test_scenario_capacity_integration.py

data/agent-tools/bin/with-node npm --workspace @execplus/web run typecheck
data/agent-tools/bin/with-node npm --workspace @execplus/web run lint
data/agent-tools/bin/with-node npm --workspace @execplus/web run test
```

Use the tracked `scripts/check_browser.py` convention or the ignored sanitized
`local_browser.py` wrapper for `source-scenarios.spec.ts`,
`large-allocations.spec.ts` and `scenario-capacity.spec.ts`. The browser runner
owns ports 8001/3001; coordinate with other verification work before starting it.
