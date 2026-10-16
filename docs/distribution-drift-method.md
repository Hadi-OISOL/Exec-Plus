> **File use case:** Defines a bounded distribution comparison without causal or probability claims.
> **What it does:** Records exact rational evidence, governed eligibility, private
> application behavior and remaining evaluation work for feature 58.

# Calendar-window distribution comparison

Status on October 16: domain, source preparation, private result history/reviews,
explicit UI and four export formats are implemented locally. See the
[verification ledger](verification-calendar-analysis.md). Deployment is pending;
this does not close broader anomaly detection or representative alert-quality
acceptance.

`empirical-window-distance-v1` compares the distributions of one governed measure's
observed period totals or averages across two explicitly chosen calendar windows.
Each window has at least eight complete consecutive daily or first-of-month
observations. Together they contain at most 1,200 periods. The comparison window
starts strictly after the reference window; a declared gap between windows is
allowed. Gaps inside either window, overlaps, missing values and unfinished periods
are refused. No record value is invented to fill coverage.

The source integration establishes a single confirmed unit/currency, aggregation,
matching required and user filters, complete historical coverage, and current
source/policy access for both windows. The pure domain receives already checked
exact Decimal values and real dates; it does not infer business comparability.

## Recorded calculations

For each unique observed value, retain its frequency and cumulative frequency in
each window. Divide each cumulative frequency by its own window count to obtain
the two empirical cumulative distributions. Preserve the maximum absolute
separation, its first location in ascending value order, and its direction.

Wasserstein distance is the integral of the absolute gap between the two cumulative
distributions: for each adjacent pair of distinct values, multiply their separation
by the cumulative-probability gap and sum. It has the original measure's units.
This definition is documented in
[SciPy's Wasserstein reference](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.stats.wasserstein_distance.html).
The maximum empirical-CDF difference also appears in the
[two-sample KS reference](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.stats.ks_2samp.html);
this method does not call the KS significance test or return a p-value.

Calculations use exact Fraction arithmetic for distances. Every probability,
interval contribution and final distance keeps its integer numerator and
denominator. A decimal display is exact when the reduced denominator has only
factors two and five; otherwise it is marked rounded and shown to 28 significant
digits. Original input values, medians and quartiles remain exact decimal strings.
All observations and all distinct distribution support values are retained.

A review flag requires both a strictly greater maximum separation than the user's
explicit threshold from zero to one, and positive Wasserstein distance at least
the user's nonnegative materiality. This is a declared screening rule, not a
calibrated error rate. There is no automatically chosen threshold or fitted model.

## Meaning and limits

For four observations at zero and four at two, compared with four at one and four
at three, maximum separation is exactly `1/2`, Wasserstein distance is exactly
`1`, and the median rises by exactly `1`. With eight zeros compared with eight
zeros and one three, the corresponding distances are exactly `1/9` and `1/3`;
their decimal displays are explicitly approximate.

Equal distributions can hide a change in time order. A wider distribution can be
different despite an unchanged median. Different weekday/season mixes, holidays,
record coverage or population composition can explain differences. No distance
identifies a causal driver, labels an individual record anomalous or proves data
is wrong. This is descriptive comparison of two observed windows, not prospective
monitoring, a forecast or automatic refresh detection.

No labels, significance level, false-alarm rate or confidence interval are supplied.
Customer alert-quality claims require an independently reviewed evaluation design
and representative labels. Human investigation does not silently retrain anything.

## Local checks and remaining release work

The initial 29 cases pass. They include fifty independent quantile-coupling
Wasserstein oracles with unequal sample sizes, direct rational CDF comparisons,
hand-calculated distributions, strict threshold and inclusive materiality edges,
unchanged distributions with reordered values, variance changes with unchanged
median, negative high-precision values, independence from the caller's Decimal
context, monthly windows, invalid/missing/incomplete/overlapping periods and the
1,200-period cap. Ruff and mypy pass. The initial collection failure used pytest's
reserved `request` parameter name; the corrected fixture and original log remain.

## Application and export contract

Choose **Anomalies & decisions → Compare distributions · two time windows**. The
form requires both windows, a confirmed date/measure/unit, total or average, explicit
review thresholds and complete-coverage acknowledgement. The API route is
`POST /workspaces/{w}/datasets/{d}/uploads/{u}/decision-analysis/distribution-drift`.

Each window retains three creator-private analytical receipts: values, present
measure counts and matching record counts. All six receipts, projected definitions,
exact policy scope, declared windows and rational output are immutable. Reopening
replays every receipt, rebuilds the result, checks retained object integrity and
reauthorizes the actor. Saved review targets the whole window comparison, never an
invented individual row anomaly. A review does not adjust thresholds or source data.

The interface shows exact distance fractions, optional decimal displays, both
window summaries and every observed period, with an exact cumulative-frequency and
distance-contribution table. The period plot uses all point marks without joining
the windows or inventing values across gaps. It is a view of observed values, not a
learned trend or a causal chart. The initial snapshot anomaly choice stays unchanged.

PDF/Excel/CSV evidence ZIP preserve every observation and distribution support row,
including exact numerators/denominators and whether a decimal is rounded. PNG
contains the recorded window series, explicit limitations and original evidence
metadata; no browser-supplied values are trusted. Restricted source fingerprints
are redacted from public exports; hidden column meanings and out-of-scope rows
never enter the saved projection. Existing size, privacy and freshness guards remain.

The remaining acceptance work is the normal private release gate and representative
evaluation on independently reviewed customer populations. Automatic refreshed
monitoring, multivariate drift and calibrated alert probabilities are not delivered.
