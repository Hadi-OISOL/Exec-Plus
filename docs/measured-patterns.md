> **File use case:** Contract for measured pattern exploration and date-free daily assumptions.
> **What it does:** Explains supported behavior, evidence, limits and the distinction between observations and predictions.

# Measured patterns and daily what-ifs

Asking “Find patterns in this data” now runs a registered computation over the
current confirmed file. It returns measured relationships rather than a column
description. Home and the no-date forecast screen lead into the same private
conversation workflow. Existing definitions, declared units, required filters
and source permissions remain authoritative.

## Supported observations

- Numerical relationships: Pearson and Spearman coefficients, complete-pair
  coverage and a scatterplot. Exact Decimal ordering supplies tied ranks; scaled
  values avoid high-offset float loss. A straight-line score is withheld if the
  float conversion merges distinct values. Almost-perfect relationships carry
  a duplicate/derived-field or prediction-leakage warning.
- Group differences: a measure's observed arithmetic mean within categories,
  with counts and an eta-squared descriptive separation score. Means are rounded
  to twelve decimal places and this is disclosed. An explicitly declared
  non-average calculation does not silently become a group average.
- Category associations: exact co-occurrence counts and Cramer's V, with the
  underlying count matrix available for inspection.

At most six stronger findings are displayed, with representation across the
three supported types. Up to two weaker evaluated comparisons are shown
separately. A scan may honestly report no strong pattern or insufficient usable
data. Display thresholds (0.5 absolute correlation, 0.2 eta-squared, 0.3 Cramer's
V) are exploration rules, not confidence levels, calibrated significance or
prediction accuracy. Scanning many combinations can surface chance patterns.
Zero Pearson/Spearman does not rule out nonlinear relationships.

The scan selects up to eight eligible measures and four categories in source
order. One explicitly named field becomes the focus; multiple named fields
bound the comparison. Exclusions explain missing units, constants, identifiers,
inconsistent types, cardinality or different governed populations. Unknown units
are not guessed. Confirmed field roles take precedence over identifier-like names.
Different required metric filters cannot be silently intersected. User-requested
row subsets require clarification or a separately prepared governed source.

Every comparison needs at least twenty complete rows, and category levels need
at least five. Missing values and small groups are excluded with coverage shown.
At most twelve category levels are supported. All matching projected rows are
used up to 10,000; a guard row detects larger populations and refuses a partial
scan. A scatterplot may display 200 evenly selected points from sorted evidence;
its score still uses all complete pairs. Related/repeated rows may overstate
independent support. This is bounded exploration, not a general ML or causal
discovery system.

## Evidence and runtime

One validated DuckDB projection creates an owner-private `aggregation=analysis`
receipt. `pattern-evidence-v1` stores the source binding, `pattern-request-v1`,
statistics engine version, `pattern-exploration-v1` result and checksums in the
existing private thread evidence. Durable jobs record an `explore_patterns`
step and evidence assembly within the existing one-query budget. No schema
migration or arbitrary model-generated code is introduced.

Reopening reauthorizes the source, reconstructs the saved request, checks the
private receipt and its typed replay, then recomputes and checks the result.
Engine-version changes fail explicitly rather than silently reinterpret saved
evidence. Current-source and accepted-refresh guards run before calculation and
publication; historical authorized answers retain their historical definitions.
Private pattern projections never become ordinary shared answers or follow-up
aggregate context. Cancellation waits for the bounded computation to clean up.

SciPy 1.15.3 and NumPy 2.2.6 are pinned infrastructure dependencies behind the
`PatternStatistics` port. Domain code uses standard-library Decimal calculations.
API/jobs images restrict native BLAS/OMP/MKL threads to one and retain wheel
license notices. See [the reference audit](pattern-exploration-reference-audit.md)
for public REA evidence, compatibility, resource cost and independent trials.

## Missing dates and daily assumptions

A date-free file cannot support a time-series forecast. The forecast screen
offers pattern discovery or a daily what-if, and retains saved forecast history.
The latter asks for an eligible baseline measure, an explicit daily change,
one to 3,650 days and assumption confirmation. No daily rate is inferred.

`constant-daily-scenarios-v1` computes `baseline + daily change × days` using
Decimal arithmetic. Up to five checkpoints retain exact values; crossing below
zero warns without silently clipping the result. Existing scenario receipts,
privacy, immutable successors, source guards and numerical bounds apply. Old
aggregate and compound methods retain their original versions and outputs.

The result is a conditional arithmetic scenario. It does not model physical
limits, response delays, weather, causality, uncertainty or learned dynamics.
Predicting an outcome from other fields remains a separate task requiring a
declared target, suitable examples and held-out evaluation. These additions do
not complete broad predictive/prescriptive feature parity or production gates.
