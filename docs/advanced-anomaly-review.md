> **File use case:** Defines the locally implemented Phase 2 anomaly review methods.
> **What it does:** Records prerequisites, exact evidence, permission boundaries and interpretation limits.

# Advanced anomaly review

The existing snapshot MAD/IQR, fixed seasonal residual and two-window distribution
methods remain available. Two additional private methods use the same governed
source reconstruction, immutable `AnalysisRun`, query receipts, review history and
protected result downloads. They require no provider or new runtime dependency.
Implementation is being verified locally; this document is not deployment acceptance.

## Earlier-window comparisons

`rolling-reference-mad-iqr-v1` compares an observed daily/monthly value with the median
of 20–120 strictly earlier comparable observations. The user declares the complete
coverage window, first evaluation period, reference size, threshold and materiality.
At least three evaluation periods and at most 1,200 total periods are supported.
Missing, duplicated, unordered or partial periods are refused, never replaced by zero.

Adjacent-period mode uses the preceding observations. Seasonal mode uses the same
weekday (lag seven) or calendar month (lag twelve); it requires enough earlier cycles
for the entire reference window. Current and future observations never fit a point's
reference. Every scored period retains the reference start/end/count/step, median,
MAD, quartiles, IQR, rule, distance and flag. The complete source series remains in
the saved evidence and exports.

Flags require the exact comparison `0.67448975 × |actual − median| > threshold × MAD`
and inclusive declared materiality. Zero MAD uses IQR fences; a constant reference
can flag a changed value without a statistical score. Displayed scores are rounded,
not probabilities. Earlier flagged observations stay in later windows: sustained
changes can move the reference and hide later changes. No automatic retraining from
review feedback, source correction or calibrated alert guarantee is claimed.

## Unusual combinations

`reference-mahalanobis-squared-v1` requires a confirmed unique record identifier,
separate text group field and two to four confirmed fixed-unit measures with matching
governed filters. The user names different reference/comparison groups and a positive
squared-distance threshold. Only those groups are selected using two bound SQL values.
The execution boundary accepts only a column `IN (?, ?)` expression; expressions,
literal lists, subqueries, longer lists and unrelated Boolean operations remain denied.

The selected population is capped at 1,000 complete rows, with 30–500 reference rows
and at least one comparison row. A cap-plus-one query refuses oversized results.
Missing measures/IDs, duplicate IDs, mixed text-group coercion and float inputs fail
explicitly. Values remain within the existing magnitude/38-decimal-place limits.

Only reference records fit the mean and sample covariance (`n−1`). Exact rational
max-absolute-centered scaling handles different units without adding or converting
them. Exact Gaussian elimination inverts the small normalized covariance; constant,
singular or nearly dependent reference measures are refused. The normalized infinity
condition limit is 100,000,000 and the rational intermediate budget is 8,192 bits.

Each comparison retains `(x−mean)ᵀ covariance⁻¹ (x−mean)` as numerator/denominator plus
a marked exact or rounded decimal display. Strict comparison with the declared
threshold determines the flag. All reference/comparison rows, units, scales,
covariance, inverse, identities and source receipts remain inspectable. Reference
rows are fitting evidence, not independently evaluated alerts.

The method assumes the chosen reference is useful for the intended comparison.
Contamination, multiple populations and non-elliptical shapes can hide or exaggerate
flags. Distances are not chi-square probabilities, causal findings or proof of fraud.
Other groups are explicitly outside the analysis. Row order does not imply time.

## Privacy, operations and experience

Both methods are selected from Anomalies & decisions. Existing themed selects,
charts with exact table inspection, reduced-motion behavior and download controls
are reused. Users save findings privately, replay original evidence, record a review
or download PDF/Excel/CSV/PNG reports. A failed protected read clears prior options,
history and results; reload rechecks access. A committed save followed by a failed
history read reports that the result is already saved and does not automatically
repeat the write.

Current source, meaning and dataset policies are checked before analysis, after
calculation and when publishing/reopening/exporting. Workspace membership alone
does not reveal another person's runs or receipts. Source/permission changes during
calculation prevent publication. New model computation uses the shared atomic
processing admission in addition to governed query admission; replay does not admit
a new model operation. Reviews do not modify saved calculations or source records.

## Verification scope

`test_rolling_anomalies.py` independently checks reference medians/MAD, past-only
fitting, seasonal alignment, exact materiality, dirty inputs and adaptation limits.
A labelled constant-shift fixture intentionally detects only five of forty shifted
periods (recall 12.5%); it demonstrates adaptation, not reliable persistent-shift
detection. The isolated spike fixture is also measured separately.

`test_multivariate_anomalies.py` compares exact scores against independent NumPy
sample covariance and SciPy Mahalanobis distance, checks scale/shift/field-order
invariance and comparison-only perturbations, strict thresholds, invalid populations
and the 1,000-row bound. Fixed labelled fixtures measure precision/recall only for
their synthetic labels. Product responses keep those measures unknown for user data.

`test_advanced_anomaly_integration.py` covers API replay, original-data preservation,
private findings/reviews, exports, access revocation, publication races and tampering.
`test_multivariate_query_boundary.py` checks the narrow SQL extension. Browser
journeys in `advanced-anomalies.spec.ts` cover both methods and denied-read clearing;
existing calendar journeys retain write retry and read-only saved-result recovery.
Final commands, results and retained initial failures belong in the Phase 2 gate
report. No customer data, live model quality or production-scale acceptance is implied.
