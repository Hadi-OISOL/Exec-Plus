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
explicit. This threshold, twenty-pair minimum and all resource limits are Syntelio
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

## October 22 additions: ranked change fields and declared driver ranges

- Contribution studies accept optional `dimensions` (one to three other category
  fields, identical count on both sides). The calculation then adds `root_cause`
  (`dimension-concentration-v1`): for the segment and each field, the exact signed
  change per member, the top member, and its concentration (top absolute change ÷
  total absolute movement, exact fraction). Fields rank by concentration, then by
  declared order; more than 128 members marks a field `too_many_groups`. A one-level
  drilldown inside the top member ranks the other fields the same way and reconciles
  to that member's change. Missing amounts make the ranking `undefined_missing_values`.
  This is accounting attribution, not causation. Studies without `dimensions` keep
  identical evidence, `segment-contribution-v1` and replay.
- Source scenarios accept optional `ranges` (one to four drivers with low < high
  percent changes, other drivers zero). `vertex-interval-bounds-v1` evaluates every
  low/high combination (at most 16) with the existing exact formula. Each output is
  multilinear or, for margin, monotone in every driver, so corner extremes are exact
  bounds; margin bounds are unavailable if any corner has zero revenue. Ranges are
  declared assumptions, not probabilities. Runs without `ranges` are unchanged.
  The web form and exports do not yet display these scenario ranges.

## October 24 additions: root-cause display, month comparisons and period scheduling UI

- The study result shows the `root_cause` block under “Where the change is
  concentrated”: ranked fields with exact concentration, the drilldown inside the
  top member, and an adds-back line that requires both the server's `reconciled`
  flag and an independent BigInt fraction sum in the browser. It is labelled
  “Accounting attribution, not cause”. Missing amounts and no-movement states are
  stated instead of ranked.
- “Explain a change” adds up to three optional “also rank by” fields per side and a
  quick month picker that fills inclusive windows for the month before or the same
  month last year. It reuses period mode, the same receipts and
  `segment-contribution-v1`; no new method or schema.
- Contribution PDF/Excel exports add the ranked fields (exact concentration
  numerator/denominator), the top-member drilldown and its adds-back status. Studies
  without ranked fields export exactly as before.
- “Choose actions within several limits” adds **Plan by period**
  (`cp-sat-scheduled-allocation-v1`): 2–12 period budgets plus ordering rules
  (“B only after A”). It cannot be combined with the capacity comparison. Results
  show a per-period table (actions that start, budget, used, remaining), the
  ordering rules and the independent verification list. Saved runs reopen from
  retained evidence without re-solving. Allocation exports add per-period budgets
  and ordering rules.

## October 24 additions: simulated scenarios and detector false-alarm targets

### Probability-based source scenarios (`triangular-monte-carlo-v1`)

Source scenarios accept an optional `simulation` block: one to four drivers, each
with `low ≤ likely ≤ high` percent changes (low < high), `draws` 1,000–10,000
(default 10,000), an integer `seed` 0–2³²−1 (default 20261024, stored in the request)
and an optional `target` (`field`, `above`/`below`, `value`). Each draw takes one
`random.Random(seed).random()` per declared driver in fixed driver order, maps it
through the inverse triangular CDF in 50-digit Decimal arithmetic, rounds the
percentage to six decimals and runs the existing exact `outcome` formula. Results:
nearest-rank P10/P50/P90, minimum and maximum for every outcome field, and the share
of draws strictly above/below the target with its Monte Carlo standard error
√(p(1−p)/n). Drivers are independent; unlisted drivers stay at zero. Margin
percentiles are unavailable when any draw has zero revenue. The block is labelled
"Simulation under the stated assumptions, not a forecast or guarantee". Replay
re-runs the stored seed and is byte-identical; requests without `simulation` keep
their exact earlier shape and result. The web form offers it under step 2 and shows
the percentiles and target share.

Analytic validation (`apps/api/tests/test_scenario_simulation.py`): price triangular
(−10, 0, 20) on the fixed two-row fixture gives remaining = 80(1+p/100) − 43, so
P(remaining > 40) = (20 − 3.75)²/(30·20) = 0.4401 and P10/P50/P90 have closed forms.
With 10,000 draws the simulated share lies within 4 standard errors (≈0.02) and each
percentile within 0.4 of the closed form. A two-driver case is recomputed draw by
draw with separate float/Fraction code: P10/P50/P90 agree to 1e-9 and the beating
count is identical.

### False-alarm targets for grouped, seasonal and rolling detectors

`synthetic-detector-calibration-v1` (seed 20261024) runs the production detectors on
synthetic data with no injected changes: grouped (40 trials, groups of 10/25/50/100
with different centres and scales, minimum support 8) and seasonal/rolling
(30 trials of 200 days, weekly sine amplitude 10 plus noise; seasonal trains on the
first 140 days, rolling uses 20 earlier matching weekday phases). Both normal and
Student-t(3) noise are measured. A target maps to the smallest registered threshold
whose measured false-alarm rate is at most the target on both families:

| Detector | Target 0.05 | Target 0.01 | Target 0.005 |
| --- | --- | --- | --- |
| Grouped (`segmented-mad-iqr-calibrated-v1`) | 3 (heavy 0.049189, normal 0.007830) | 6 (0.007838 / 0.000275) | 8 (0.003649 / 0.000137) |
| Seasonal (`seasonal-residual-mad-iqr-calibrated-v1`) | 3 (0.022222 / 0.007778) | 5 (0.007222 / 0) | 6 (0.005000 / 0) |
| Rolling (`rolling-reference-mad-iqr-calibrated-v1`) | 3.5 (0.045556 / 0.008889) | 8 (0.005000 / 0) | 8 (0.005000 / 0) |

Heavy-tailed noise drives every choice; at the default 3.5 the rolling detector
measured 0.045556 and grouped 0.031757 false alarms on heavy-tailed data. Grouped
recall on injected 8-scale spikes falls from 1.0 at threshold 3 to 0.45 at 8.
The grouped method is selected by `target_false_alarm_rate` plus `segment_column`
(previously refused); seasonal and rolling use the new calibrated `model` names with
a required target and the default threshold. Results carry a `calibration` block
with the measured rates and the label "Synthetic calibration; not a customer
false-alarm guarantee." Legacy requests keep their method versions and shapes.
The snapshot, grouped, seasonal and rolling forms now offer the target, which
disables the manual threshold. `test_detector_calibration.py` derives every table
from a fresh report run and checks one seasonal trial against independent float code.

### False-alarm targets for drift and multi-measure detectors (October 24)

`synthetic-distance-calibration-v1` (seed 20261024, `execplus.domain.distance_calibration`)
runs the production detectors on unchanged synthetic data under normal and
Student-t(3) noise; a target maps to the smallest registered threshold whose measured
rate is at most the target on both families.

- **Drift** (`empirical-window-distance-calibrated-v1`). 400 window pairs for each of
  8/8, 14/14, 30/30, 60/60 and 90/30 independent daily values (2,000 per family). The
  separation threshold scales like a two-sample Kolmogorov-Smirnov test:
  `coefficient × √((n+m)/(n·m))`, capped at 1, computed from the chosen windows.
  The request carries the target instead of `minimum_cdf_separation`.
- **Multi-measure** (`reference-mahalanobis-calibrated-v1`). Per measure count 2/3/4,
  reference cohorts of 30/100/300 records, 20 trials each with 50 comparison records
  drawn from the reference distribution (3,000 per family and count). The squared-
  distance threshold depends on the number of measures. The request carries the
  target with the default threshold.

| Target | Drift coefficient (normal / heavy) | 2 measures | 3 measures | 4 measures |
| --- | --- | --- | --- | --- |
| 0.05 | 1.36 (0.030500 / 0.033500) | 10 (0.011667 / 0.045333) | 14 (0.007333 / 0.043000) | 20 (0.003667 / 0.037000) |
| 0.01 | 1.63 (0.005000 / 0.007500) | 30 (0 / 0.009667) | 40 (0 / 0.008667) | 50 (0 / 0.008333) |
| 0.005 | 1.73 (0.003000 / 0.005000) | 75 (0 / 0.003333) | 75 (0 / 0.003333) | 75 (0 / 0.003333) |

Drift rates are close to the asymptotic KS values (1.36/1.63/1.73) because the test
is distribution-free for independent values; autocorrelation, seasonality or a
different weekday mix will raise them. Heavy tails drive every multi-measure choice:
under normal noise the 0.01 thresholds flagged nothing, so the method is conservative
for well-behaved data and loses sensitivity. No detection (recall) rate was measured
for these two detectors. Results carry `calibration` evidence and
`evaluation.calibrated=True` with `false_alarm_rate` set to the measured rates;
legacy requests keep their versions, shapes and `calibrated=False`. The drift and
multi-measure forms now offer the target. `test_distance_calibration.py` derives all
tables from a fresh run and checks one drift trial (KS statistic) and one
multi-measure trial (numpy Mahalanobis distances) with independent float code.

## Remaining boundaries

No new schema, statistics library, model provider or external integration is needed
for this slice. Existing anomaly/scenario methods remain available. Seasonal,
multivariate and drift detection; broader scenario uncertainty; learned prediction;
causal decision models; fine-grained access policies; and representative evaluation
remain separately planned work. Feature counts and production gates do not improve
merely because these bounded methods or internal checks pass.
