> **File use case:** Records evidence for the remaining October 16 improvement phases.
> **What it does:** Separates numerical, workflow, performance and private-release evidence from broader acceptance.

# Verification — internal analytics depth and cross-feature reliability

Scope: phases three and four of [the saved plan](clean-experience-plan.md), with
[versioned method contracts](internal-analytics-depth.md). Both bounded phases are complete for local/test and the private demo at dfddb8c. Schema remains 0017. The 64 feature IDs, 37 Done / 16 Partial / 11 Not
yet counts and eight blocked production gates are unchanged.

## Numerical and cross-feature evidence

New grouped-comparison fixtures use independent Pearson and tied-rank oracles for
balanced and uneven groups, pooled/group direction reversal, weak nonlinear data,
missing/sparse/constant rows, exact-rank precision, typed category identities and
complete-population limits. Allocation tests compare 120 small one-/two-resource
models with an independent exhaustive rational oracle, plus ties, exact bounds,
conflicts, cycles, mandatory minima and the feasible do-nothing baseline. A runtime
checker independently verifies selected quantities, totals and constraints; it is
not a second runtime optimality or infeasibility proof.

The fixed manifest contains **18 named cases / 42 exact deduplicated checks**.
Its first execution passes without skips (pytest 26.54 seconds). It covers saved
private context, missing units/dates, malformed and repeated-invalid readings,
budgets/deadlines, changed sources, revoked permission, new method edge cases,
saved compatibility and cancellation. These are fictional internal regressions,
not representative human-labelled model-quality acceptance. The runner retains
JUnit, logs, manifest checksum and per-case status and refuses missing, duplicate,
failed or skipped checks.

The durable conversation test caught and fixed a real integration issue: reopening
a new group result used the legacy method-route label. Reopening now derives the
label from the verified saved result version. Root conversation/publication checks
pass all 37 selected cases. Other initial failures were fixture expectations:
uneven-group Spearman need not be strong; typed decimals retain their scale; changed
meaning follows the existing 422 clarification response. These attempts remain in
the ignored evidence, not counted as successful runs.

## Local workload

The tracked runner uses isolated PostgreSQL schemas and object-store buckets with
fictional data, eight concurrent actors, explicit meanings, disabled model calls
and real application services. Baseline source is archived from 71dcadc. Each
common run warms up once per actor and measures three rounds of exact sum/replay,
pattern/reopen and allocation/reopen (144 requests). The candidate additionally
measures two rounds of grouped-comparison/reopen and constrained-allocation/reopen
(64 requests). Fixtures, exact expected answers and environment are shared.

Final paired runs execute sequentially after backend/browser checks stop, with
BLAS/OMP/MKL threads fixed to one. This machine has an Intel i7-1165G7 (eight logical
CPUs), about 14.8 GiB RAM, Python 3.12.14 and Linux 7.0.0-38. Both common runs pass
144 requests with zero errors and matching fixture hashes. The new-method run passes
an additional 64 requests.

| Common operation (24 samples each) | Before median / p95 ms | After median / p95 ms |
| --- | ---: | ---: |
| Exact query | 207.555 / 239.060 | 197.353 / 285.431 |
| Query replay | 180.815 / 275.740 | 167.731 / 239.285 |
| Pattern scan | 522.506 / 591.508 | 468.561 / 581.826 |
| Pattern reopening | 335.870 / 418.506 | 350.881 / 405.199 |
| Allocation | 430.446 / 640.265 | 311.986 / 379.612 |
| Allocation reopening | 173.933 / 440.712 | 190.909 / 281.264 |

Common elapsed time is 6.068 seconds before / 5.241 after; process CPU is
6.892 / 6.327 seconds and process peak RSS is 269,368 / 269,152 KiB. This single
short pair has mixed per-operation changes and does not establish a speedup or
capacity improvement. No speculative optimization was made.

New-method medians / p95 in milliseconds are: grouped comparison 573.744 /
578.454; grouped reopening 377.259 / 538.964; selection rules 381.845 / 417.726;
selection reopening 237.089 / 275.773. The additional phase takes 3.160 seconds,
3.651 CPU seconds, with final process peak RSS 272,932 KiB.

Early harness attempts used an invalid one-seat
workspace and an incomplete allocation endpoint; both were corrected. A corrected
baseline trial passes 144 requests with zero errors. That trial overlapped other
functional checks and is not used for a before/after performance claim.

Each actor has a separate workspace; at most eight journeys overlap, so this is
not shared-workspace contention or a constant-concurrency test. Common operations
have 24 timed samples each after warm-up. New operations have sixteen samples and
no separate warm-up; their nearest-rank p95 equals the maximum. The new rule fixture
changes the exact optimum from benefit 22 to 18 and asserts method, rules, quantities
and verification, so ignoring constraints cannot pass. Grouped and ordinary pattern
checks assert the known coefficients and method versions.

Latency excludes browser/network. CPU deltas cover each phase. Peak RSS is the
application/test process lifetime high-water mark including setup and warm-up,
not a phase memory delta; PostgreSQL/MinIO memory is excluded. Completed reports
with zero errors mean every request/assertion passed; failures abort and retain logs.
This is a short local workload, not sustained load
or a production capacity certificate. No optimization is claimed without measured
evidence.

## Browser, static checks and private release

The full backend/architecture suite passes **1,300 cases**, with zero failures,
errors or skips (470.718 seconds). All 29 frontend unit tests, TypeScript, ESLint
and Ruff pass. The focused browser run had ten existing passes and two new
selector failures before requests; corrected rechecks pass both new journeys.
A native disabled option needed a DOM-property assertion because Playwright
reported the rendered disabled option as enabled. No product validity check was
removed. Narrow-screen evidence tables have bounded scrolling, oversized generated
questions are blocked explicitly, and the result labels distinguish usable rows
from an available pooled comparison. The full offline browser suite then passes **51 journeys**, with **three explicit
live-model skips**, zero failures, in 5.8 minutes. These skips are not claimed as
passes. The new group/rule journeys cover upload, explicit meaning confirmation,
selected inputs, execution, private saved reopening, keyboard and reduced motion
at 1440/390/320 widths. Viewport screenshot inspection confirms readable coverage,
pooled/within-group scores and rule cards. Initial tall element screenshots were
clipped by the existing chat scroller; corrected viewport captures are retained.
The final local and VPS production builds both pass.

Initial static checks exposed local annotation issues in
the router and new workload script; corrected mypy passes all 174 source files.
All initial logs and corrections are retained.

Read-only pre-release checks confirm the previous demo is healthy: five running
containers, zero restarts, migration 0017, web/readiness 200, six loopback listeners,
active model/refresh/backup units and zero application-error lines in the inspected
30-minute window. Inspection caused no restart. Pre-release backup **20261016T044108Z** passes both
database/object archive checksums and restarts services successfully. This proves
archive integrity, not current-version restore or off-server recovery.
API/web candidate **dfddb8c** builds pass. The non-root, read-only, network-disabled
image passes eight prior exact/forecast computations, the three earlier extensions,
eight pattern/daily computations and 48 new group/rule computations across eight
workers. Application **dfddb8c** is activated on unchanged **0017** under the
maintenance lock. All **47 table fingerprint entries** and the environment-file
checksum match before/after activation. Source/images checkpoint:
`pre-dfddb8c-20261016`. Activated runtime has five running containers with zero
restarts, web/readiness 200, six loopback listeners, active model/timers and no
application-error lines in the checked thirty-minute window.

Deployed API verification passes in **179.936 seconds**: eight fictional actors,
eight durable group jobs, eight rule allocations, eight approvals/review reopens,
sixteen exact receipt replays, **224 cross-actor privacy denials** and sixteen
authorized shared-source controls. The shared forty-row fixture returns pooled
Pearson −0.973749 / Spearman −0.500938 while both groups return +1, and the exact
constrained choices retain their rules and resource limits. The original farm
bytes/profile/definitions/revision history and fictional source snapshots match
before/after. Old ordinary, pattern, forecast, scenario and October 15 reading
evidence reopen. A fresh configured hosted response uses the saved private goal
and reopens immutably with route `hosted:deepseek-v4-pro:dataset-reading-v1`; it is
accepted model output, not a fallback counted as model success.

This is functional evidence, not representative model-quality or sustained-load
acceptance. Both deployed browser journeys pass on their first execution in
**49.8 seconds**, across six 1440/390/320 layouts with zero page errors. They check
the keyboard chooser, saved reversal, exact forty-row chart table, reduced motion,
context retention, saved rules, exact cost 3 / benefit 9 / resource use 2, two
retained reviews, verification disclosure and replay. Viewport screenshots are
readable without page overflow. The actual farm and fictional source snapshots
still match after browser verification. No live API/browser harness failure
occurred. Checked post-release backup **20261016T050051Z** preserves the new saved
work; database/object archive checksums pass and services restart successfully.
Final readiness and workspace return HTTP 200; migration remains 0017, all five
containers run with zero restarts, all six listeners remain loopback, model/refresh/
backup units are active and the checked thirty-minute application log has zero
error lines. Preserve all new results and
reviews when rolling back application code; no database restore or migration
downgrade occurred.

The absent independent demo tunnel was restored. Demo1 authentication then returned
401; only that expired account was renewed privately for eight hours. Other account
records/sessions remain intact, and the token file/key retain mode 0600.

## Evidence and limits

Detailed fictional fixtures, logs and measurements remain ignored under
`data/verification/2026-10-16/analytics-depth/`; additional targeted relationship
and allocation logs retain their original paths. No user source data, sessions,
private keys or generated reports are published. Public reference work from the
October 15 audit is reused; no new REA capture or competitor-backend access is
claimed. Broader causal/predictive methods, external integrations, representative
evaluation and production operations remain open.

The maintained audit and October 16 Desktop DOCX preserve all 64 original IDs
and counts 37 Done / 16 Partial / 11 Not yet. All eight production gates remain
blocked on a fresh preflight. The user-supplied October 13 PDF is untouched.
