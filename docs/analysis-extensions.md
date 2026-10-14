> **File use case:** Defines the October 14 bounded extensions to Partial analytics features.
> **What it does:** Records method versions, inputs, limits, replay compatibility and remaining work.

# Grouped anomalies, compound scenarios and resource recommendations

The user authorized work on Partial features 57–59 and merging the branch pushed
the previous night. `origin/phase3` at `2a93080` adds the data-reading journey and
was merged into `phase2`, retaining its existing interface polish. This analytics
slice extends existing private analyses; it does not complete the broad features.
Deployment and acceptance evidence is recorded in `verification-analysis-extensions.md`.

## Within-group anomaly detection

The anomalies endpoint accepts optional `segment_column` and
`minimum_segment_size` (default 8, allowed 8–1,000). An eligible group is a
confirmed dimension or identifier distinct from the measure. The source query
retains group, exact measure and weighted frequency under all governed filters.
An extra sentinel result refuses truncation beyond 1,000 distinct group/value
pairs. There may be at most 32 groups and 200,000 eligible source records.

`segmented-mad-iqr-v1` applies the existing weighted MAD/IQR method separately
within each sufficiently supported group. Missing group labels, missing measures
and small groups are reported as excluded. A sparse group never silently receives
a global baseline. `sample_count` includes excluded records; `covered_records`
and `excluded_records` show the coverage explicitly. Each group retains complete
and missing counts, status and its baseline when evaluated. Finding IDs include
both group and value, so equal values in different groups have separate reviews.

The UI shows group coverage, medians and findings. Thresholds and materiality
retain their existing definitions. Scores are exploratory, not probabilities;
there is no calibrated false-alarm guarantee across multiple groups. Seasonality,
multivariate detection, drift and representative reviewed evaluation remain open.

## Compound scenario assumptions

An alternative can now use `operation="compound_percent"` with one to three
`drivers`, each containing a distinct name and an exact string `percent_change`.
Changes must fall between -100% and 10,000%. There are still at most five
alternatives per run; legacy replacements and percentage changes can coexist.

`compound-scenarios-v1` calculates:

```text
conditional value = observed baseline * product(1 + driver percentage / 100)
```

For example, a baseline of 100 with a declared volume change of 10% and price
change of 20% gives 132, not 130. Driver names describe user assumptions; the
application does not infer their relationship to the baseline. This is not a
general quantity/price model, causal estimate, demand model or forecast.

The same three source receipts prove baseline, present measures and population.
Complete coverage remains mandatory. Compound amounts use 256-digit Decimal
precision, enough for all three bounded factors without rounding; percentage
differences retain 28 significant digits. Output magnitude remains below 1e38.
Successors preserve the original and retain existing metric, meaning, unit,
grain and population compatibility checks. Approval remains unavailable for
hypothetical comparisons. Uncertainty and source-derived multi-measure models
remain future work.

## A second allocation resource

The allocations endpoint accepts paired `resource_column` and `resource_capacity`.
The resource column must be a separate confirmed numeric measure with a fixed
unit. Capacity uses that unit; its nonnegative source values represent fixed
per-unit consumption. Missing values are refused. The existing cost/benefit
meaning, source uniqueness, bounds and explicit assumption confirmation apply.

`two-resource-enumeration-v1` searches all declared quantity combinations under
both limits using exact Decimal arithmetic. It refuses workloads beyond 100,000
combinations, before enumeration. Existing limits remain: at most 20 actions,
quantities 0–10, 5,000 budget quantum units and exact cost/quantum divisibility.
The existing DP validation also retains its one-million-work guard.

Feasible results have `solver_status="optimal"`; otherwise the result is
`infeasible`, with no recommendation or numerical objective. Ties prefer highest
benefit, then lowest money cost, then lowest additional resource use, then lexical
candidate quantities. Results preserve total and per-action consumption, unused
capacity, assumptions and the do-nothing baseline. Current feasible results may
be approved privately; approval never executes actions. Business-specific modules,
precedence/exclusions, nonlinear effects and larger solver-backed models remain open.

The bounded exhaustive method was chosen because this slice can prove an exact
optimum without adding a solver dependency. Larger OR-Tools trials from the research
plan remain separate work, not an implied runtime adoption.

## Evidence and compatibility

Existing kinds and migration **0017** remain unchanged. Method selection depends
on explicit extension fields. Old requests without those fields preserve old
query construction, method IDs and serialized results; legacy methods are not
silently reinterpreted. New receipts identify the extended deterministic method.
Reopening validates request checksums, definitions, units, original typed source
receipts and regenerated results. Private-owner and current-source review guards
remain shared across methods, including workspace-admin denial.

An older application cannot replay the new method versions. A rollback must retain
the new analysis metadata and restore compatible code before opening those runs.
No database downgrade or deletion of saved results is required or authorized.

Local dependency installation exposed SQLAlchemy 2.1 typing incompatibilities in
existing reporting/operator code. The supported range is now explicitly 2.0.x,
verified with 2.0.54, pending a separately tested 2.1 migration. Browser tests may
select an installed browser using `EXECPLUS_BROWSER_EXECUTABLE`; the default remains
Playwright's managed Chromium.
