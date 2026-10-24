> **File use case:** Defines the bounded advanced forecasting method and saved-result contract.
> **What it does:** Records eligibility, numerical choices, evaluation, uncertainty, compatibility and limits for feature 56.

# Advanced forecasting

Status: verified locally and deployed on the private demo at `867c5a0`/0020, including real-service API/browser workflows. See [the verification ledger](verification-advanced-forecasting.md). This extends the existing forecasting feature. It does not prove accuracy on customer data or close the production evaluation gates.

## What a user can do

In Forecasts, choose **Advanced — compare smoothing and trends**, then select all eligible methods or one smoothing family. Confirm the complete date range as before. A particular family still competes with a simple baseline: the system does not force a more complex method to win.

The result shows its selected method, original historical values, forecast estimates, empirical error range, untouched-test accuracy and the simple last-value benchmark. Expanding the method evidence shows all candidate parameters and three chronological validation windows. Saved forecasts and later-actual comparisons can download the same retained evidence through the protected PDF, Excel, CSV-bundle and PNG export paths.

The model does not do this arithmetic. Deterministic Decimal routines use the authorized source and confirmed measure. No new provider, third-party fitting package, schema or external account is required for this method.

## Eligibility and bounds

- One confirmed real date column, daily or monthly frequency, an eligible aggregation, and a fixed declared unit/currency are required. Existing mandatory measure filters apply. Dates are never inferred from row order.
- A user declares complete source coverage. Every calendar period must exist and have complete measure values. Missing periods/values are refused, not filled or treated as zero.
- The existing maximum is 1,200 consecutive complete periods. Forecast horizons remain 1–30 days or 1–12 months. Advanced forecasting never expands those limits silently.
- Let `H = max(requested horizon, 4 daily / 3 monthly)`. The engine reserves three validation windows and a separate test window, each of length `H`. Earliest training has at least 14 daily or six monthly periods. Therefore the ordinary minimum is `training + 4H` (30 days or 18 months at the smallest horizon).
- Seasonal methods require an explicitly declared seven-day or twelve-month cycle and two complete cycles in the earliest training window. Choosing the seasonal family explicitly raises its minimum training to 14 days / 24 months (30 days / 36 months at the smallest horizon). In automatic mode an ineligible seasonal family is omitted with a recorded explanation.
- A fixed registry contains at most 43 candidates. Its conservative fitting-work bound is below 160,000 series-step visits, checked and retained with the result. There is no unrestricted optimizer, arbitrary Python, user-supplied expression or model-selected code.

## Versioned numerical method

Requests opt in with `engine="advanced-v2"` and a registered `method_family`. Stored results identify `forecast-v2` and registry `smoothing-grid-v1`. `basic-v1` remains the default and its saved request omits both new fields. The existing `forecast-v1` algorithm and stored evidence are unchanged.

| Family | Registered parameters | Starting state |
| --- | --- | --- |
| Last value | None | Last training observation |
| Seasonal naive | Explicit cycle | Last complete training cycle |
| Simple exponential smoothing | Alpha 0.2, 0.5, 0.8 | First observation |
| Holt additive trend | Alpha above; beta 0.1, 0.3 | First observation and first difference |
| Damped Holt | Holt grid; phi 0.8, 0.95 | Same initial level/trend |
| Additive Holt-Winters | Alpha above; beta 0.1, 0.3; gamma 0.1, 0.3; phi 1 or 0.9; gamma ≤ 1−alpha | First two cycle means establish initial trend; first cycle is detrended around its mean |

For seasonal initialization with cycle length `m`, first and second cycle means `a` and `b` give initial trend `(b−a)/m`. The state at the end of the first cycle is `a + trend*(m−1)/2`; first-cycle seasonal residuals subtract `a + trend*(i−(m−1)/2)`. Subsequent updates start at the next cycle. All starting observations belong to the current fitting prefix.

The standard additive component equations are used. For level `l`, trend `b`, prior seasonal component `s`, and observation `y`:

```text
projection = previous_level + phi * previous_trend
level      = alpha * (y - old_season) + (1 - alpha) * projection
trend      = beta * (level - previous_level) + (1 - beta) * phi * previous_trend
season     = gamma * (y - projection) + (1 - gamma) * old_season
forecast(h)= level + (phi + ... + phi^h) * trend + future_season
```

Nonseasonal methods omit `season`; simple smoothing has no trend. Additive methods can produce negative values and these are never clipped. This fixed initialization and grid are Syntelio's declared bounded choices; they are not a claim to reproduce another package's fitted parameters.

Calculations run in a private 128-digit Decimal context with half-even rounding. Retained source actuals keep their original exact decimal strings. Predictions and error summaries use the existing declared 18-significant-digit estimate representation. Accuracy is computed from those serialized estimates, so it scores the number the user can inspect. Candidate ties at reported validation-MAE precision use stable registry order, favoring baselines first.

The component equations follow [Forecasting: Principles and Practice, exponential smoothing](https://otexts.com/fpp3/exponential-smoothing.html). The chronological evaluation design follows its [forecasting toolbox and time-series cross-validation guidance](https://otexts.com/fpp3/toolbox.html). No upstream source code was copied and no statistical runtime library was installed for this slice.

## Evaluation and uncertainty

For `N` observations, the expanding training prefixes end at counts `N−4H`, `N−3H`, and `N−2H`. Each candidate forecasts the following `H` observations. The mean absolute error across these three disjoint validation windows selects one candidate. Its final test fit uses only the first `N−H` observations; the last `H` observations are untouched by selection and range construction. A separate full-history fit supplies the future estimates.

The result compares selected-model test MAE with last-value test MAE on identical periods. It retains RMSE, WAPE, applicable MAPE, zero-value counts and exact per-period errors. A method that fails to beat the simple baseline is explicitly identified; past performance is not a future guarantee.

The display range is estimate ± the nearest-rank 90th percentile of the selected candidate's pooled absolute validation errors. It uses the same width for every horizon. **This is not a calibrated 90% confidence or prediction interval.** Method selection and range construction reuse validation data, errors differ across horizons, and three origins provide limited evidence. Observed test coverage is reported separately without promising future coverage. Zero validation errors collapse the range but do not guarantee a correct future result.

## Calibrated ranges (engine `advanced-v3`, record `forecast-v3`)

The opt-in `advanced-v3` engine keeps v2 selection, test and future estimates and
changes only the ranges. Nine extra one-period-apart calibration origins end before
the first selection window, so calibration windows neither choose the method nor
measure test error. For each horizon step the selected method's absolute errors are
ranked and the 8th of 9 (split-conformal rank ⌈(n+1)·0.8⌉) becomes that step's
half-width: a nominal 80% range. It needs `8 + H` more periods than v2. Exchangeable
errors are assumed; trend breaks or seasonal shifts can lower coverage, so
`coverage_guaranteed` stays false and observed test coverage is still reported.
v2 records are byte-identical to the earlier release (pinned hashes in
`apps/api/tests/test_calibrated_forecasting.py`). On 60 seeded random-walk series
(240 test points) observed coverage was 76.7% for v3 (nominal 80%) and 80.4% for
v2's 90th-percentile display width. This is synthetic evidence, not customer accuracy.

## Access, immutability and exports

The forecast remains creator-private, including from workspace owners. Existing source revision, confirmed meaning, accepted refresh, byte-integrity and query-receipt checks remain. Opt-in dataset policies project allowed rows/columns before calculation; exact policy/actor references are retained in evidence. A changed policy blocks publication or opening old-scope results, and history omits inaccessible results. Exports reopen the same authorized saved result and perform the export service's final authorization check.

Replay dispatches by the saved engine version and recomputes the recorded deterministic method against its retained source. Parameters, method version, result checksum and source receipts must agree. Later-actual comparisons reuse the existing exact comparison-row contract without mutating the saved v2 forecast. Historical v1 forecasts are never silently upgraded.

## Remaining boundaries

This slice does not implement ARIMA, probabilistic ETS likelihood fitting, multiplicative seasonality, multiple seasonal cycles, learned regressors, event/holiday effects, hierarchical reconciliation, causal effects or automatic refresh scheduling. It does not establish calibrated uncertainty, representative customer quality or production throughput. Those need their own explicit method and acceptance evidence, not a more confident label.
