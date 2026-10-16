> **File use case:** Records the exact chronological seasonal anomaly method and its limits.
> **What it does:** Defines source eligibility, private reproducible calculations,
> review/export behavior and explicit evaluation limitations.

# Seasonal anomaly method

Status on October 16: domain, governed source preparation, private API/history/review,
four export formats and explicit UI controls are implemented locally. Focused
verification is recorded in [the ledger](verification-calendar-analysis.md); no
deployment is claimed. Existing snapshot/grouped methods and saved results remain
compatible. Feature 58 stays Partial: multivariate detection, automatic monitoring
and representative alert-quality acceptance remain open. A separate
[two-window comparison](distribution-drift-method.md) supplies descriptive drift.

## Inputs and eligibility

`seasonal-residual-mad-iqr-v1` consumes exact decimal observations indexed by real
calendar dates. It accepts only:

- Complete, unique, ordered, consecutive daily periods with an explicit seven-day
  cycle, or monthly periods starting on the first day with a twelve-month cycle.
- At most 1,200 periods. Gaps, incomplete periods and invalid values are refused;
  absent periods never become zero.
- An explicit included training-end date, at least 28 daily or 36 monthly training
  observations, at least twenty training residuals, and at least three later
  observations for chronological scoring.
- An explicit threshold from 3 to 10, default 3.5, and nonnegative absolute
  materiality in the measure's own unit. Input numbers are finite, smaller than
  `1e38` in absolute value and have at most 38 decimal places.

The domain accepts no guessed date, unit, period completeness or population. The
service establishes these from the confirmed governed measure, matching required/user
filters and explicit complete historical calendar coverage. Period values, present
measure counts and all matching row counts are checked separately. Missing dates,
missing measures, calendar gaps and future/unfinished periods are refused. The
user's completeness declaration remains an assumption; row presence alone does not
prove real-world coverage.

## Application and saved evidence

Choose **Anomalies & decisions → Unusual periods · seasonal reference**. The form
requires the date field, fixed-unit measure, total/average, coverage dates, training
boundary and explicit completeness confirmation. Seven-day or twelve-month season
length follows the selected daily/monthly frequency; dates or units are never guessed.
The API route is
`POST /workspaces/{w}/datasets/{d}/uploads/{u}/decision-analysis/seasonal-anomalies`.

Three private `aggregation="analysis"` receipts retain period values, nonmissing
measure counts and matching records. Unlike ordinary workspace queries, these
receipts are creator-private, including from workspace administrators. The saved
analysis keeps projected definitions, exact source/policy references, every period,
method output and checksums. Opening replays all receipts and independently rebuilds
the deterministic result before final authorization. Historical source meanings
remain immutable; changed access rules hide the old run rather than broadening it.

The view shows every observed period, a separate later-period reference view, exact
training/full-history tables, method limits and append-only private human review.
Warmup/training periods are not scored and are explicitly distinguished. PDF, Excel,
CSV evidence ZIP and PNG use reopened source evidence, not browser values or a new
model call. All included periods remain in exact export tables. PNG/PDF plots are
approximate displays with visible limitations; downloads are size bounded and
retain existing final permission/source checks. Restricted source fingerprints are
withheld in public responses/exports while private replay evidence remains intact.

## Frozen training calculation

For cycle length `s`, each training residual is `r[t] = y[t] - y[t-s]`. Only
observations through the chosen training end contribute to the training median
`m`, median absolute deviation `MAD`, first/third quartiles and interquartile range
`IQR`. Quantiles use linearly interpolated positions `(n-1) * fraction`, preserving
the existing exact numerical convention.

For each later observed period:

1. The reference is the already observed value one cycle earlier, `y[t-s]`.
2. Its expected comparison value is `y[t-s] + m`.
3. The residual is `y[t] - y[t-s]`, with absolute deviation `abs(r[t]-m)`.
4. For positive MAD, flag only when
   `0.67448975 * abs(r[t]-m) > threshold * MAD` and the deviation is at least the
   declared materiality. Cross-products are evaluated exactly; a rounded displayed
   score never determines the flag.
5. When MAD is zero, use strict fences `Q1-threshold*IQR` and
   `Q3+threshold*IQR`, with the same inclusive materiality condition. When IQR is
   also zero, these become the constant residual reference. No statistical score
   is reported for either fallback.

Amounts and comparisons use an isolated 256-digit Decimal context. Displayed MAD
scores use 28 significant digits with half-even rounding; values remain exact
decimal strings. Negative observations and expected values are retained. Stable
finding IDs use the method and period, not a claimed individual source-row identity.

The seasonal comparison follows the basic earlier-season idea in
[Forecasting: Principles and Practice](https://otexts.com/fpp3/toolbox.html#seasonal-naïve-method).
The frozen robust residual correction and fallback rules above are ExecPlus's
explicit versioned contract, not a claim to implement STL. The modified-MAD
statistic and conventional 3.5 screening threshold are described by
[NIST](https://itl.nist.gov/div898/handbook/eda/section3/eda35h.htm); our fixed
`0.67448975` constant is recorded in every result. This application does not infer
a calibrated false-alarm probability from that convention.

## Evidence and honest evaluation

The result retains every input period with a warmup, training or evaluation phase;
actual value; earlier reference period/value; residual; expected value; deviation;
score; and flag. Warmup and fitting periods are not labelled as held-out detection
results. All training statistics, declared thresholds, counts and limitations are
saved with the method version.

Later observations are scored chronologically after their actual values exist.
This is detection evaluation, not a set of forecasts made before those observations
arrived. The residual reference and threshold never use later values or labels.
Earlier later-period observations may serve as the seasonal reference for a
subsequent period, exactly as documented; they never refit the frozen scale.
This distinction follows the separation of fitting and later evaluation in
[time-series cross validation](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation).

Ordinary result evidence explicitly records no supplied labels, no threshold
selection on evaluation periods, and unavailable precision, recall and false-alarm
rate. A flag count is not an accuracy estimate. No human review automatically
trains the method or establishes ground truth.

The fixed synthetic tests deliberately retain these limitations:

| Test population | Later-period outcome | Interpretation |
| --- | --- | --- |
| Repeating weekly cycle | No flags | Legitimate seasonal variation is not treated as a spike in this fixture |
| One injected spike | Spike and opposite residual one cycle later | One true positive and one false positive under the supplied artificial labels |
| Sustained level shift for 21 later days | First seven days flagged, remaining fourteen not flagged | The changed level becomes the seasonal reference after a cycle; this is not a persistent drift detector |

These deliberately small artificial examples check method behavior. They do not
establish customer accuracy, representative false-alert rates or business value.
Multiple seasons, holidays, changing slopes, multivariate effects, population drift
and automatic refresh monitoring remain outside this version.

## Local verification

`test_temporal_anomalies.py` has 39 passing cases, including fifty independently
calculated Fraction populations within one case, exact threshold/materiality
boundaries, constant/zero/negative/high-precision values, calendar gaps, duplicate
and unordered dates, incomplete periods, monthly boundaries, caller Decimal-context
independence and the 1,200-period cap. Future perturbation and dataset extension
tests prove that training statistics and all earlier scored rows are unchanged.
Ruff and mypy pass for the new module.

Initial test evidence is retained: two assertions failed because the artificial
oracle included a zero-spread seed and another assertion assumed insignificant
trailing zeros. Those fixture/assertion errors were corrected; no failed algorithm
comparison was concealed. A subsequent boundary check adds explicit rejection of
unordered inputs at the maximum supported calendar date. Its first two assertions
exposed an existing forecast-helper error message; rejecting unordered dates before
advancing the calendar now gives the temporal method's own clear validation error.

Ignored domain logs are under `data/verification/2026-10-16/remaining-work/` with the
`temporal-anomalies-domain-` prefix. Application/privacy/export and browser evidence
is separately recorded in [the verification ledger](verification-calendar-analysis.md).
These fictional checks do not establish representative alert quality or deployment.

## Required integration before release

Expose a separate explicit method choice with training-end and cycle controls;
retain the snapshot default. Build the full bounded series from authorized exact
query receipts, preserve projected definitions and all access-policy source keys,
and check sources/permissions again at publication and replay. Keep immutable
private history and existing review behavior. Do not silently use an unrelated
older result or change existing receipts.

Show actual and expected period values with the cutoff, flags, coverage and the
visible echo/adaptation warning. Exact tables and PDF/Excel/CSV/PNG exports must
retain all recorded observations, thresholds and limitations. Add integration
tests for missing/incomplete/future dates, unit/population mismatch, source and
policy changes, cross-user access, old/new replay, export exactness and responsive
browser interaction before calling the application slice complete.
