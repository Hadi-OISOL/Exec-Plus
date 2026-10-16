> **File use case:** Defines the optional larger linear allocation method and dependency boundary.
> **What it does:** Records exact inputs, bounded search, immutable evidence, privacy and honest solver outcomes.

# Larger resource allocation

This is an additional, explicit method for feature 59. The original single-budget,
two-resource and selection-enumeration methods keep their defaults and saved results.
The new method is `cp-sat-integer-allocation-v1`, result version
`multi-resource-allocation-v1`. It does not complete nonlinear, causal or
representative customer acceptance work.

## Inputs and meaning

One complete source row is one unique action. Choose an identifier, positive
per-unit cost, nonnegative additive benefit and up to three additional nonnegative
per-unit resource columns. The budget is the first resource, giving four limits
in total. Each measure needs a confirmed fixed unit; mixed per-row units are
refused. All measures must have the same governed required-filter population.
Explicit actor filters and row/column policies still apply.

The source projection retains every matching row and uses a 51st-row sentinel:
more than 50 actions are refused rather than truncated. Missing measures,
duplicate action identifiers and reused identifier/measure columns are refused.
Quantity bounds are whole numbers from zero through 100. Unspecified actions use
zero minimum and the explicit default maximum. Up to 40 prerequisites and 40
exclusions are supported. Selecting an action means a positive quantity, so a
prerequisite requires at least one unit. Prerequisite cycles are refused.

The user confirms fixed resources and linear additive benefits. These are
assumptions supplied by the user, not learned effects, probabilities or causal
estimates. The model does not infer demand response, action timing or nonlinear
interactions. Approving a result records a private decision and executes nothing.

## Exact arithmetic and search limits

Input decimals have the existing finite, absolute-value-below-`1e38`,
at-most-38-decimal-place bounds. Every resource and the benefit objective has its
own exact rational scale, reduced by the greatest common divisor. No float
conversion or budget-quantum rounding is used. Integer coefficients, capacities
and each column's maximum weighted sum must be at most `2^53-1`; unsupported
scales are explicitly refused. This is deliberately stricter than the solver's
integer representation.

CP-SAT receives only integer arrays, bounds and index pairs. It receives no source
filenames, user IDs, credentials, column names or arbitrary executable text.
The infrastructure adapter runs a fixed packaged worker with an isolated Python
environment, one search worker, seed zero, a 1.5-second solver wall limit and a
0.25 deterministic-time limit. The parent enforces a four-second process wall
limit, kills the process group and waits for cleanup on timeout/cancellation.
The child sets a 768 MiB address-space limit, CPU and file-descriptor limits,
zero core/file-output limits and one-thread numerical environment settings before
loading the vendor library. Output is capped at 32 KiB. Two searches may run per
API process; a request that cannot obtain a slot within 250 ms receives a retryable
busy response. These are local worker bounds, not a distributed capacity plan.

Every returned selection is independently recalculated from the original
Decimals with sufficient precision. The checker verifies every quantity, resource
capacity, prerequisite, exclusion and total benefit, including the integer
objective's exact scale. This checks feasibility and arithmetic; it is not a
second independent proof of optimality.

| Solver outcome | Saved presentation |
| --- | --- |
| `OPTIMAL` | Feasible quantities; the solver proved maximum benefit for this declared model. |
| `FEASIBLE` | Checked usable quantities; maximum benefit was not proved. |
| `INFEASIBLE` | Solver proved no selection satisfies every declared constraint; no actions or invented totals. |
| `UNKNOWN` | No usable selection/proven outcome; no actions or invented totals. A parent wall-time stop uses this outcome. |

Malformed output, vendor failure and invalid returned quantities do not publish a
recommendation. No float-derived bound, exact optimality gap or calibrated
probability is reported. Tied optima have no promised cost or lexical tie-break.
A bounded rerun may find a different feasible selection. The do-nothing baseline
is shown explicitly and is feasible only when all minimum quantities are zero.

## Saved evidence, access and exports

The endpoint is `POST /workspaces/{workspace}/datasets/{dataset}/uploads/{upload}/decision-analysis/large-allocations`.
Normal decision-analysis list/open/review paths retain their existing interface.
One owner-private `aggregation="analysis"` receipt holds the exact governed source
projection. The saved run retains request, projected definition and units, all
source-access keys, integer-problem checksum, solver version/status/termination,
selected quantities, exact contributions and result checksum.

Reopening re-executes the immutable source projection and verifies its full typed
receipt, then independently rebuilds the retained result from the saved quantities.
It does **not** rerun a time-bounded search or replace saved answers. Historical
meanings remain readable, while approval requires the current accepted source and
definitions. Membership/policy revocation hides result metadata, receipts, reviews
and exports. A source/policy change during search blocks final publication.

PDF, Excel, CSV/evidence ZIP and PNG use the same authorized retained result.
Exports include every resource limit, exact per-action contribution, assumptions,
solver status and review/source evidence. PNG is available only when there is a
selection to chart. Original source fingerprints remain withheld for restricted
views. No protected values are supplied by the browser or recalculated by a model.

## Dependency and numerical references

- [OR-Tools CP-SAT documentation](https://developers.google.com/optimization/cp/cp_solver)
  specifies integer models and distinguishes optimal, feasible, infeasible and
  unknown outcomes. ExecPlus uses the real solver behind an application port.
- [OR-Tools v9.15 source](https://github.com/google/or-tools/tree/551ad10d94835c99e5e1e684500d3db398c0e345)
  is the reviewed upstream revision. Runtime package: `ortools==9.15.6755`;
  `pandas==2.3.3` preserves the project's Python 3.10 compatibility boundary and
  existing `numpy==2.2.6`. Actual execution was checked on Python 3.12.
- [SciPy 1.15.3 MILP](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.optimize.milp.html)
  converts inputs to double precision. That route was not selected for this exact
  integer contract. Existing SciPy and NumPy methods remain unchanged.
- The reviewed cp312 Linux x86_64 OR-Tools wheel SHA-256 is
  `033836c0eb33bc72697a299e0caedbb25fc9d1cee0b13832d69cb30405f57b3e`.
  The pandas wheel SHA-256 is
  `b3d11d2fda7eb164ef27ffc14b4fcab16a80e1ce67e9f57e19ec0afaf715ba89`.

The OR-Tools main license is Apache 2.0. Its unmodified wheel also distributes
COIN-OR EPL 2.0, Eigen MPL 2.0, SCIP/SoPlex Apache 2.0, HiGHS MIT and support
libraries. [Retained license texts and corresponding source locations](../apps/web/public/third-party/ortools/NOTICE.txt)
ship with the application. Only CP-SAT is called. The upstream build pins most
native sources, but declares bzip2 `master`; the bundled binary reports 1.1.0.
Its exact upstream source commit cannot be inferred from that declaration. The
verified wheel hash fixes the actual binary artifact; this is not a claim of an
independently reproduced upstream wheel build.

See [verification evidence](verification-large-allocation.md) for the observed
checks, initial failures and current deployment boundary.
