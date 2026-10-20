> **File use case:** Contract for the locally executable Phase 2 extensions to requirements 57 and 59.
> **What it does:** Defines explicit scenario limits, bounded capacity comparisons, retained solver evidence and their authorization/accounting boundaries.

# Declared outcome limits and capacity comparisons

These additions extend the existing source-derived scenarios and CP-SAT allocation
paths. They use the existing source receipts, permissions, private analysis runs,
review history, export service and UI. They add no dependency, schema, provider,
external action or network delivery.

## Scenario limits — requirement 57

`POST .../uploads/{id}/decision-analysis/source-scenarios` accepts the existing
`source-unit-economics-v1` model and the new
`source-unit-economics-constrained-v2`. The new version requires 1–12 explicit
`constraints`, each containing `field`, `operator` (`minimum` or `maximum`), an
exact decimal `value` and a confirmed `unit`.

Supported fields are quantity, sales (`revenue`), variable cost, included fixed
cost, total included cost, contribution, remaining after included costs, and
margin percent. Quantity uses the confirmed quantity unit; money fields use the
confirmed source currency; margin uses `%`. Duplicate boundaries, minimum greater
than maximum, mismatched units and invalid numbers are refused. Constraints sent
to the old method cannot silently disappear.

Every baseline, simultaneous-change alternative and single-driver sensitivity
point retains `passed`, `violated` or `unavailable` checks. Amount checks use exact
rational conversions of the recorded decimal amounts. Margin checks compare
`100 × remaining / revenue` as an exact rational number, before the separate
28-significant-digit display. Zero or negative revenue makes the new method's
margin unavailable; signed source amounts are preserved. Old saved v1 calculations
and their historical margin behavior remain unchanged.

The existing bounds still apply: at most 10,000 complete authorized source rows,
five named simultaneous alternatives, and 2–21 ordered sensitivity points. Users
can name alternatives Conservative or Optimistic; neither label creates a
probability. Source mappings, selected population and saved definitions remain
explicit. Passing a boundary does not establish operational feasibility, demand
response, causality or net profit. The existing fixed-mix assumption still applies.

An immutable v1 source scenario can acquire a v2 successor, and v2 can acquire a
v2 successor. Source mappings, basis, population and relevant meanings must remain
compatible. A v2-to-v1 successor is refused; the user can deliberately create a
separate independent comparison instead.

## Capacity comparisons — requirement 59

`POST .../uploads/{id}/decision-analysis/large-allocations` retains
`cp-sat-integer-allocation-v1` and adds `cp-sat-capacity-sensitivity-v2`. The new
version requires `capacity_sensitivity` containing one already-declared resource
`column`, its confirmed `unit`, and 2–5 distinct increasing nonnegative decimal
`capacities`. The original budget/resource model is retained unchanged.

One original solve plus the declared alternatives means at most six sequential
bounded CP-SAT solves. Every solve reuses the existing constraints: 1–50 complete
unique action rows, whole quantities 0–100, a budget and at most three additional
resources, positive costs, nonnegative resource consumption/benefits, explicit
minimum/maximum quantities, prerequisites and exclusions. Exact decimal-to-integer
scaling refuses unsafe sizes instead of rounding. Each solver subprocess retains
its existing four-second wall bound; the six-solve limit is not a promise of a
particular end-to-end latency.

Each usable outcome is independently checked against the exact source quantities,
objective, capacities and selection rules. `optimal`, `feasible`, `infeasible` and
`unknown` remain distinct. A feasible-only selection is not claimed optimal.
Differences are exact differences from the original usable selection, not a proof
of optimal sensitivity. When either outcome has no usable solution, the difference
is absent rather than invented as zero.

For infeasible models, independent arithmetic explains directly provable conflicts:
mandatory quantities plus prerequisite closure can exceed an action maximum,
require excluded actions, or exceed a nonnegative resource capacity. Evidence
includes the forced quantities and exact shortfall. Where those simple proofs do
not establish the conflict, the retained solver result is explicitly labeled; no
independent minimal conflicting constraint set is claimed.

Reopening reconstructs the authorized source model and checks the retained solver
outcomes and complete result equality. It never solves again. Solver status,
termination reason, problem checksum, quantities and exact objective remain in
the evidence. This prevents time-bounded reruns from silently changing a saved
answer.

Approval applies only to the original capacity model. An alternative needs a
separately saved model and review. Current source/meaning checks still invalidate
effective approval after inputs change, while preserving original review history.
Approval never executes an action outside ExecPlus.

## Authorization, accounting and exports

The shared `DecisionAnalysisService._admit_model` admits each new v2 computation
under the existing workspace processing allowance. Its retry fingerprint contains
actor, workspace, dataset, upload, full model request, method, source descriptors
and variant. A stable `Idempotency-Key` deduplicates the same request; changed
budgets or limits cannot reuse an unchanged projection's computation admission.
This is admission accounting, not payment accounting or a result cache.

The governed source query is counted separately: a constrained scenario typically
admits one query plus one computation; capacity comparison admits one query plus
3–6 computations. A retry can recompute while reusing its prior admissions. New
operations without an explicit retry key get fresh admissions. Failed started
work counts. Admission is atomic under the workspace lock, but no database lock
is held during calculation or solver execution.

Current actor, source and policy are checked before each computation and again
before publication. A cap or revocation between solves prevents the next solve
and prevents publication of a partial model. Existing receipt replay and retained
saved opening remain readable under a zero or expired processing allowance,
subject to current authorization. Export remains a separately admitted operation.

The existing protected PDF, Excel, CSV/evidence and PNG routes reopen the saved
analysis before rendering. Scenario reports include every exact constraint check.
Capacity reports include every alternative's exact quantities, resource use,
infeasibility evidence and retained solver metadata. Charts label confirmed units,
preserve absent results and do not supply a chart when all alternatives are absent.
Workbook exact-text conventions and original evidence types remain unchanged.

The Simple/Expert architecture is retained. New inputs are contextual within the
existing source scenario and larger-allocation panels, using the shared Radix
select component. Exact tables, recorded limitations and private history remain
available alongside the charts.

## Demonstrate with fictional local data

Start the application using `docs/start-project.md` and a local synthetic account.
Upload this CSV and explicitly confirm quantity as `items` and sales/cost/fixed as
`USD`, with one non-overlapping record per row:

```csv
region,quantity,sales,cost,fixed
North,2,10,6,3
South,3,20,8,4
```

In Expert → Anomalies & decisions → What-if → source model, map those four columns.
Compare a Conservative price change of −10% and Optimistic change of +10%, keeping
other changes at zero. Add a minimum remaining amount of 35 USD. The source
remaining amount is 37; the alternatives are 29 and 45. The first fails the stated
limit and the second passes. Save, reopen, export and create a successor; original
source rows and saved checks remain unchanged.

For the larger-allocation path, use this fictional decision input and confirm cost
and benefit as USD and hours as hours. These benefits are declared assumptions:

```csv
action,cost,benefit,hours
A,0.03,0.07,0.2
B,0.05,0.11,0.1
```

Set budget 0.11, maximum quantity 2 and hours capacity 0.5. Enable capacity comparison
on cost with 0.03, 0.08, 0.11, 0.13 and 0.16 USD. Their optimal conditional benefits
are respectively 0.07, 0.18, 0.25, 0.29 and 0.29 USD. The original selection is
two A and one B, using exactly 0.11 USD and 0.5 hours. Reopen it without another
search; approving the original model does not approve the alternative capacities.

## Code and verification map

| Scope | Code | Tests |
| --- | --- | --- |
| Exact scenario checks | `domain/scenario_constraints.py`, `domain/source_scenarios.py` | `test_scenario_constraints.py`, existing source scenario tests |
| Retained capacity variants and conflict proofs | `domain/allocation_sensitivity.py`, `domain/large_allocation.py`, `domain/large_allocation_queries.py` | `test_allocation_sensitivity.py`, existing larger-allocation tests |
| Admission, routing, private replay | `application/services/decision_analysis.py`, `presentation/routes/decision_analysis.py` | `test_scenario_capacity_integration.py` |
| Protected exact reports | `application/services/analysis_report_documents.py` | Four-format scoped export cases in the new integration file |
| Guided controls and results | `source-scenario-panel.tsx`, `source-scenario-types.ts`, `large-allocation-panel.tsx` | `e2e/scenario-capacity.spec.ts` and existing v1 journeys |

Read the companion verification document for observed results. These contracts do
not establish production acceptance, causal recommendations or universal model
capability.
