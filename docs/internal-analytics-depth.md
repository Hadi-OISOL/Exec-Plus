> **File use case:** Defines the bounded October 16 analytics and internal evaluation contracts.
> **What it does:** Records supported inputs, exact evidence, exclusions, compatibility and repeatable checks.

# Internal analytics depth and fixed evaluation

This slice implements phases 3 and 4 of [the clean-experience plan](clean-experience-plan.md).
It extends existing private conversations and decision analyses. It does not change
schema 0017, model providers, network exposure or the eight production acceptance
gates. Broad feature statuses remain Partial; no causal discovery, general prediction
system or full competitor parity is claimed. Deployment and measured operational
results belong in the separate verification ledger.

## Relationship comparison within groups

A user chooses two numerical measures and one distinct category in **Compare groups**.
The same private conversation workflow performs one governed projection, computes
the pooled relationship, and compares it with relationships inside each eligible
group. This supplements the existing broad pattern scan; ordinary requests retain
their original methods and output.

| Contract | New version | Existing version retained |
| --- | --- | --- |
| Request | `group-relationship-request-v1` | `pattern-request-v1` |
| Result | `group-relationship-comparison-v1` | `pattern-exploration-v1` |
| Private evidence envelope | `group-relationship-evidence-v1` | `pattern-evidence-v1` |
| Registered conversation operation | `compare_group_relationship` | `explore_patterns` |

The new operation declares two selected measures plus `group_by`, uses the existing
one-query budget, and returns the existing `kind="patterns"` answer with a versioned
result. New lineage identifies `deterministic:group-relationship-comparison-v1`.
Historical ordinary pattern evidence is rebuilt with its original request/result
functions; it is not migrated or reinterpreted as a grouped comparison.

### Eligible inputs and exact coverage

- Meanings must be confirmed. Both measures need a fixed declared unit or currency,
  numeric values, and the same governed required filters. Identifier/ignored roles,
  conflicting types, missing fixed units and globally constant fields are refused.
  Confirmed roles remain authoritative. A saved non-average calculation does not
  become an average: this method compares the original per-row values.
- The category uses the existing dimension/ordinal eligibility and cannot be a
  date. It must meet the existing profile cardinality check as well as the projected
  limit of twelve observed levels. The current profile check can conservatively
  refuse a high-cardinality source even when required filters would reduce its levels.
- Use all matching projected rows, up to 10,000. An additional guard row detects a
  larger population and refuses a partial calculation. No random sample or hidden
  row restriction substitutes for the governed population.
- A usable group needs at least twenty complete pairs and variation in both
  measures. At least two usable groups are required for a pooled comparison.
  Sparse, constant or numerically unstable groups remain visible with their status
  and counts. They do not silently inherit a global relationship.
- `missing_category_rows` includes every row without a category. `missing_pair_rows`
  counts incomplete pairs only among rows with a category. Sparse, constant and
  unstable group exclusions count those groups' remaining complete pairs. These
  categories are mutually exclusive and sum to `excluded_rows`.
- `covered_rows` is the total complete-pair count of eligible groups. The pooled
  coefficients use exactly those rows, once each, with no equal-group weighting.
  With fewer than two usable groups or an unavailable pooled computation, return
  `insufficient_data`, a specific reason and coverage; no pooled result is invented.

Each category retains a typed scalar record and stable identity. Display labels
are disambiguated when different typed values render alike. Source values remain
exact strings in charts and exact typed values in the private receipt. The scatterplot
shows at most 200 evenly selected points from sorted covered evidence; the statistics
still use every covered pair. The plotted subset may omit a small group and is not
an equal-group or random sample.

### Coefficients and interpretation

The existing statistics port uses pinned SciPy 1.15.3 and NumPy 2.2.6. Pearson
summarizes linear association; Spearman summarizes rank association. Zero or weak
correlation does not establish independence or rule out another relationship shape.
See the primary [Pearson documentation](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.stats.pearsonr.html)
and [Spearman documentation](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.stats.spearmanr.html).

Domain code normalizes exact Decimal values and derives average tied ranks before
calling that port. If float conversion merges distinct observations, the Pearson
score is withheld while a valid exact-order Spearman score can remain. Coefficients
are shown approximately to six decimal places; directions use the unrounded score.

A direction is highlighted only when its absolute coefficient is at least 0.5.
A reversal marker needs opposite signs and that threshold for both the pooled and
within-group coefficient of the same kind. Weak or unavailable scores remain
explicit. This threshold, twenty-pair minimum and all resource limits are ExecPlus
design decisions, not significance thresholds or guarantees endorsed by the sources.
No p-values, causal effects, calibrated error rates or prediction accuracy are shown.

The contextual reference is Judea Pearl's
[Understanding Simpson's Paradox](https://ftp.cs.ucla.edu/pub/stat_ser/r414.pdf).
A reversal after grouping is an observed association difference. The product does
not infer that grouping identifies a cause, that adjustment is correct, or that the
within-group result is the right answer for a decision. That requires substantive
causal assumptions outside this method. Repeated records, selected groups and almost
perfect duplicate/derived fields also require care before using observations for
prediction or decisions.

### Explicit UI request and private replay

The chooser serializes field names as JSON string values inside this canonical text:

```text
Compare the relationship between "first measure" and "second measure" within groups of "category".
```

The complete request must fit the existing 500-character conversation limit.
Very long or heavily escaped field names can exceed it even when each individual
field is valid; they require a shorter named source or another supported analysis.
The UI prevents submission of an oversized generated request. The parser requires
the complete canonical form and known distinct field names. Other grouped phrasing
or appended row restrictions clarifies rather than silently discarding the request's
scope. This slice does not introduce a general natural-language grouped-query parser.

The existing chat action labelled “Generate AI summary” still summarizes dataset
insights; it is not a narrative of the currently visible grouped comparison. The
group result supplies its own deterministic explanation. Clarifying that older
action label is a small follow-up usability improvement.

The envelope binds source/revision/confirmed meaning, request, engine version,
private query ID and checksums. Reopening reconstructs the governed request,
reauthorizes the source, checks owner-only receipt access, replays typed evidence,
and recomputes the exact versioned result. Engine changes fail explicitly. Source,
accepted refresh and permission guards remain active before publication. Cancelled
work waits for bounded computation cleanup and does not publish unfinished evidence.
Neither workspace nor staff administration grants another actor access to a private
thread or its projection receipt.

## Allocation prerequisites and exclusions

The existing `bounded_allocation` request accepts optional explicit rule lists:

```json
{
  "prerequisites": [{"candidate": "A", "requires": "B"}],
  "exclusions": [{"first": "A", "second": "C"}]
}
```

A selected action has a positive integer quantity. Selecting A requires **at least
one** B, regardless of A's quantity. Excluding A and C prevents both having positive
quantities. These are selection constraints; they express no time order, scheduling
dependency, causal benefit or executed external action.

Nonempty rules select result version `selection-allocation-v1` and method
`selection-rules-enumeration-v1`. Empty or absent rules retain the exact older request
shape and `integer-budget-v1` or `two-resource-enumeration-v1` method. Existing kinds,
tables, immutable saved results, reviews and receipts remain compatible.

Rules refer to exact action labels in the governed, filtered projection. Unknown,
self-referential or duplicate rules are rejected; an exclusion pair has one canonical
order. At most forty rules of each kind are accepted. Prerequisite cycles are refused
explicitly rather than automatically converted into bundles. A prerequisite and
exclusion may conflict: optional actions can then remain unselected; mandatory
minimums can make the declared problem infeasible. Neither case relaxes the rules.

The solver retains the existing assumptions and bounds:

- One to twenty uniquely identified actions, positive unit costs, nonnegative fixed
  additive benefits, and integer minimum/maximum quantities from zero to ten.
- A nonnegative budget with a positive quantum; budget and costs must be exact
  quantum multiples. At most 5,000 budget units and the existing one-million-step
  validation bound remain enforced.
- An optional second nonnegative resource capacity and nonnegative additive per-unit
  resource use. Costs, benefits and capacities use bounded finite Decimal values.
- At most 100,000 quantity combinations, counting the full product of declared
  bounds before feasibility pruning. Larger searches are refused.
- Exact enumeration maximizes benefit, then minimizes cost, then resource use when
  present, then the lexical quantity tuple over sorted action labels.

The zero-quantity baseline is reported with feasibility determined by the declared
minimum quantities. When no selection satisfies the constraints, the result says
infeasible, contains empty allocations and cannot receive recommendation approval.
A feasible do-nothing result is
allowed; the system does not force a beneficial action.

### What independent verification establishes

Before persistence, a separate checker reconstructs selected quantities and exact
line-item/total costs, benefits and resource use from the original projected rows.
It checks identities, integer bounds, prerequisite/exclusion rules, remaining budget
and the method/rule binding. A mismatch withholds the recommendation. The application
invokes the checker independently of the solver's own call.

This runtime checker verifies a feasible proposal's arithmetic and constraints. It
does **not** independently prove global optimality or re-enumerate infeasibility;
an infeasible result receives shape checks and no verification badge. Exact optimality
within the bounded model comes from exhaustive enumeration, supported by independent
rational-oracle tests on declared fixtures. It is not an external optimality certificate
or evidence that user-supplied benefits will occur in the real world.

The existing source/owner/publication checks apply to creation, reopening and review.
An approval remains a recorded private decision, not an external action. Changed
source or meaning invalidates current approval while preserving authorized historical
results.

## Fixed internal evaluation

[`analysis-evaluation-cases.json`](analysis-evaluation-cases.json) declares eighteen
named failure cases and forty-two exact pytest node IDs. It reuses meaningful
regressions for saved/private context, missing units/dates, invalid reading recovery,
budgets, source/permission changes, grouped statistics, allocation rules, replay and
cancellation. These are fictional records and scripted-provider checks; they do not
establish representative model quality or customer acceptance.

Run against the existing isolated local PostgreSQL/object storage services:

```bash
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:5432/execplus \
  .venv/bin/python scripts/check_analysis_evaluation.py \
  --output data/verification/2026-10-16/analytics-depth/fixed-evaluation-repeat
```

The output directory must be new and Git-ignored. The runner deduplicates exact
nodes into one pytest execution and retains `pytest.log`, `junit.xml` and
`summary.json`, including the manifest checksum, case expectations, status and
durations. Failed, skipped, missing, unexpected or duplicate results fail the run.
An absent integration database setting is rejected before testing; no skipped
integration check is counted as evidence. Case timings reflect those regression
tests, not independent user journeys or hosted model latency.

## Declared local workload

`scripts/measure_analysis_workload.py` uses eight fictional actors, disposable
database schemas/object buckets, forty observation rows and three declared actions.
It requires loopback local infrastructure and disables model calls. One warm-up per
actor precedes three measured rounds of the existing query, exact replay, pattern,
pattern reopening, allocation and allocation reopening operations. `--new-methods`
adds two rounds of grouped comparison/reopening and rule-allocation/reopening.

```bash
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:5432/execplus \
  .venv/bin/python scripts/measure_analysis_workload.py \
  --source data/verification/2026-10-16/analytics-depth/baseline-source \
  --output data/verification/2026-10-16/analytics-depth/workload-before-repeat.json

EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:5432/execplus \
  .venv/bin/python scripts/measure_analysis_workload.py \
  --source . --new-methods \
  --output data/verification/2026-10-16/analytics-depth/workload-after-repeat.json
```

The baseline path must be a retained checkout of the intended earlier application.
Use fresh output filenames and retain unsuccessful attempts. Compare the same
fixture checksums and common operations across versions; the new methods have
no prior-version equivalent. Reports contain per-operation median/nearest-rank p95/
maximum timings, request counts, CPU time and peak process RSS. CPU/RSS cover the
application/test process, not the database/storage processes. The ASGI TestClient
omits real browser and network overhead. This short local workload supports a
declared regression comparison, not sustained load, production capacity or hosted
model-quality claims. Any optimization needs measured evidence before adoption.

## Remaining boundaries

No new schema, statistics library, model provider or external integration is needed
for this slice. Existing anomaly/scenario methods remain available. Seasonal,
multivariate and drift detection; broader scenario uncertainty; learned prediction;
causal decision models; fine-grained access policies; and representative evaluation
remain separately planned work. Feature counts and production gates do not improve
merely because these bounded methods or internal checks pass.
