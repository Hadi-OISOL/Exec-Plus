> **File use case:** Defines the bounded Phase 4C forecasting and comparison contracts.
> **What it does:** Explains source evidence, evaluation, uncertainty and the measured method decision.

# Basic forecasting and grounded commentary

This contract describes the October 6 implementation. Release verification and
deployment acceptance are recorded separately; this document does not declare
Phase 4 complete or clear any production gate. Forecasts estimate periods after
the chosen source window. With an old source window, those periods may themselves
be historical relative to today.

## Eligible data and source evidence

A forecast uses one retained CSV/XLSX snapshot, a confirmed date column, a
confirmed numeric measure with an explicit unit, and its governed aggregation
and required filters. Source revision and understanding IDs are explicit in the
request. Unconfirmed or changed meanings require review before calculation.
Inventory snapshots currently support daily forecasting; monthly stock aggregation
requires a separate governed method and is refused.

The user declares `coverage_start`, `coverage_end` and
`coverage_confirmed: true`. Coverage must end before the server's current date.
Monthly coverage starts on the first day and ends on the last day of complete
calendar months. Daily coverage uses consecutive whole dates. Observed records
alone cannot prove completeness; the declaration is an assumption retained with
the forecast, not an automatic certification.

Three read-only, parameterized DuckDB queries produce the period aggregate,
present-measure count and sample count. Existing compute budgets, strict source
conversion, permissions and execution receipts apply. Calendar grouping adds
bounded `DATE_TRUNC` use to the validated grammar. At most eighteen user filters
leave room for the two coverage filters. The measure's governed filters still
apply. Ambiguous dates, missing dates or missing measures require correction.
Multiple source rows in one period are aggregated using the declared method;
they are not silently deduplicated. Source cleaning remains explicit.

Every expected period must exist for fitting; absence is never filled with zero.
There is no imputation or automatic removal of incomplete periods. The engine
accepts only ordered, unique, contiguous period starts and finite bounded Decimal
actuals. It supports at most 1,200 periods, thirty forecast days or twelve forecast
months. The source queries retain their normal receipts, full source references,
meaning versions and checksums.

## Method selection and evaluation

The runtime is standard-library-only and makes no model-provider calls. It
compares a fixed, small set of methods:

| Method | Calculation | Eligibility |
|---|---|---|
| Last value | Repeat the last observed value | Every supported series |
| Recent mean | Repeat the mean of the last seven days or three months | Every supported series |
| Linear trend | Fit a least-squares line against sequential period index | Every supported series |
| Seasonal naive | Repeat the last declared seven-day or twelve-month cycle | Explicit seasonal choice and two cycles in initial training |

There is no automatic search over arbitrary model orders, learned season length,
holiday effects, regressors or causal structure. If seasonal history is insufficient,
the candidate is omitted with an explicit limitation; the eligible basic methods
can still run.

The holdout length `H` is the larger of the requested horizon and four periods
for daily data or three for monthly data. The series splits chronologically into:

1. Initial training: everything before the final `2H` periods.
2. Validation: the following `H` periods; candidates predict this entire window
   without using its actuals for fitting. Lowest reported validation MAE selects
   the method. Ties use the fixed candidate order above.
3. Test: the final `H` periods. The selected method is refitted on initial training
   plus validation, then predicts the entire untouched test window. Test actuals
   cannot change method selection or these predictions.
4. Forecast fitting: the selected method is refitted on all supplied actuals to
   estimate the requested periods after the source window.

Minimum history is `max(base minimum, minimum training + 2H)`: base minima are
28 days and 12 months; initial training minima are 14 days and six months. A
30-day horizon therefore needs at least 74 days; a 12-month horizon needs at
least 30 months. Seasonal eligibility can require more history. The error message
states the applicable count.

Stored windows are `training`, `validation`, `test_training`, `test` and
`forecast_training`, each with start, end and count. The result retains candidate
validation scores, selected method/version/parameters, exact historical actuals,
test predictions and future predictions. The untouched test also scores a last-value
baseline. `beats_baseline_mae` and `mae_difference` disclose when the selected
method performs worse; this comparison never reselects the method using test data.

This is a bounded chronological holdout assessment, not rolling-origin
cross-validation across many historical regimes. Small test windows and changing
business conditions limit the conclusions.

## Numbers, errors and uncertainty

Actual values remain exact decimal strings. Estimates and aggregate error metrics
are approximate strings rounded to eighteen significant digits using half-even
rounding, independent of the caller's Decimal context. There is no conversion of
source actuals through binary floats. A per-period error is `actual - estimate`;
its sign and absolute difference refer to the stored approximate estimate.

| Metric | Meaning | Zero-value handling |
|---|---|---|
| MAE | Mean absolute error, in the measure's unit | Defined for zero actuals |
| RMSE | Square root of mean squared error, in the measure's unit | Defined for zero actuals |
| WAPE | `100 × sum(abs(error)) / sum(abs(actual))` | Null when all actuals are zero |
| MAPE | Mean of `100 × abs(error) / abs(actual)` | Null if any evaluated actual is zero |

Metrics include evaluated count, zero-actual count and nonzero-actual count. With
no observed comparison periods, error metrics are null. These are error measures,
not a percentage-accurate product guarantee. Negative actuals and estimates are
not silently clipped.

Each range extends two prior-holdout RMSEs multiplied by the square root of steps
ahead around its estimate. Test ranges use the earlier validation RMSE; future
ranges use the later test RMSE. These are **heuristic error ranges**, not calibrated
confidence intervals or promises of 95% coverage. The record states
`coverage_guaranteed: false`. It also reports how many actual test points lay inside
the earlier ranges, labelled as observed holdout coverage only.

Zero test error produces collapsed future ranges and an explicit warning that
future error can still occur. External changes, unusual events and model-selection
uncertainty are not adequately captured by this simple range rule.

## Saved forecasts, comparisons and commentary

Forecasts are private to their creator within a workspace. Listing, opening,
comparison and evidence replay require current membership and the private owner.
At most fifty forecasts per dataset/person and fifty comparisons per forecast are
retained. The limit is checked again during publication. This is a technical bound,
not a paid-plan entitlement.

A saved forecast retains immutable request, numerical result, method version,
three source query receipts and a result checksum. Reopening replays the source
queries and reconstructs the calculation before returning it. Source tampering,
deletion, lost access or different reconstructed results fail verification. Forecast
estimates must not receive the exact-business-number Verified label merely because
their source arithmetic is replayable.

A comparison selects a later authorized snapshot in the same dataset, supplies
its current revision/understanding IDs and declares complete coverage. The original
metric, date column, aggregation, filters and frequency remain fixed. The confirmed
meaning must equal the original definition; changed units or business meaning
require a new forecast. Accepted staged refreshes can supply this snapshot using
the existing refresh workflow. Comparing does not activate an upload or rewrite
the original forecast.

Only matching forecast periods with complete actuals are scored. Missing future
periods remain `pending`; history and unrelated periods are not scored. The pure
comparison helper also labels incomplete supplied periods as pending. No missing
period becomes an invented zero. Each comparison retains its own source evidence,
result checksum and deterministic commentary and can be reopened independently.

Commentary is rendered from authorized actuals, estimates, ranges and error
metrics. It explains what was measured and its limitations without claiming a
cause or recommending an external action. Forecasting and this commentary do not
call DeepSeek, Qwen or any other language model.

## HTTP interface

All paths below require the normal authenticated workspace identity. `base` is
`/workspaces/{workspace_id}/datasets/{dataset_id}`.

| Method and path | Purpose |
|---|---|
| `GET base/uploads/{upload_id}/forecasts/options` | Eligible dates/measures, current IDs and setup limitations |
| `POST base/uploads/{upload_id}/forecasts` | Create a private forecast; returns 201 |
| `GET base/forecasts` | List the caller's saved forecasts |
| `GET base/forecasts/{forecast_id}` | Reopen and verify a saved forecast |
| `POST base/forecasts/{forecast_id}/compare` | Save a comparison with another snapshot; returns 201 |
| `GET base/forecasts/{forecast_id}/comparisons` | List private comparisons |
| `GET base/forecasts/{forecast_id}/comparisons/{comparison_id}` | Reopen and verify a comparison |

Creation requires `name`, `revision_id`, `understanding_id`, `time_column`, `metric`,
`aggregation`, `frequency`, `horizon`, coverage dates and confirmation. `filters`
defaults to empty and `season_length` to null. Aggregations are sum, average,
minimum, maximum or count (`sum`, `avg`, `min`, `max`, `count` in JSON). Monthly
horizon limits and seasonal combinations are additionally enforced in the domain.
Comparison requires `upload_id`, current revision/understanding IDs and the new
coverage declaration. Extra request fields are forbidden.

The numerical result has `version: forecast-v1`, `method`, `windows`, `selection`,
`history`, `backtest`, `accuracy`, `benchmark`, `predictions`, `uncertainty` and
`limitations`. Dates are ISO strings; numeric actuals/estimates/errors are strings,
while bounded period counts are integers. Comparison results contain `rows`,
`metrics`, `observed_count` and `pending_count`. Service records wrap these with
workspace/owner/source IDs, evidence and timestamps. Normal errors preserve the
existing API error envelope. Insufficient or invalid series return actionable 422
errors; meaning/source conflicts require review, and inaccessible resources retain
the repository's non-disclosure behavior.

## ARIMA and Prophet research decision

Both libraries were tested in an isolated environment, not added to the runtime.
ARIMA supports explicit integration/seasonal orders, and its forecast result can
include prediction intervals. These capabilities still require choices and validation
for the source series. [ARIMA documentation](https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html),
[forecast result documentation](https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMAResults.get_forecast.html).

Prophet documents evaluation from historical cutoffs and cautions that its uncertainty
assumptions do not guarantee nominal coverage. Our limited holdout and heuristic
ranges should not be confused with a full Prophet evaluation or calibrated intervals.
[Prophet diagnostics](https://facebook.github.io/prophet/docs/diagnostics.html),
[Prophet uncertainty](https://facebook.github.io/prophet/docs/uncertainty_intervals.html).

`scripts/evaluate_forecast_models.py` compares identical chronological windows on
seven fixed fictional fixtures. It records fixture hashes, library versions,
candidate scores, failed convergence and process timings. Each optional fit has a
15-second process deadline. ARIMA evaluates fixed `(1,1,0)` and `(0,1,1)` orders,
selects by validation error and uses at most fifty optimization iterations. Prophet
uses a small fixed configuration with declared weekly/yearly seasonality and no
uncertainty sampling. The script never chooses a new runtime provider.

The initial report is retained at
`data/forecast-evaluation/research-20261006.json`. Prophet 1.1.7 could not initialize
its packaged backend with CmdStanPy 1.3.0. The isolated environment was corrected
to CmdStanPy 1.2.5; the successful comparison is retained at
`data/forecast-evaluation/research-compatible-20261006.json`. Other versions were
statsmodels 0.14.5, NumPy 2.2.6, pandas 2.3.3 and SciPy 1.15.3. No application
dependency or model-provider configuration changed.

| Fictional fixture | Runtime test MAE | ARIMA test MAE | Prophet test MAE |
|---|---:|---:|---:|
| Constant daily | 0 | No converged validation candidate | 0 |
| Linear daily | 0 | No converged validation candidate | 0.00000314 |
| Noisy daily trend | 9.285714 | 7.325296 | 3.941526 |
| Repeating weekly | 0 | 13.469371 | 0.012732 |
| Repeating yearly/monthly | 0 | 18.765343 | 18.061511 |
| Zero-containing monthly | 0 | 8.296300 | 8.563645 |
| Abrupt late regime change | 196 | No converged validation candidate | 195.999929 |

ARIMA and Prophet **improved the noisy-trend case**. This is a demonstrated weakness
of the simple selector, not a result to hide. The sudden regime change defeated both
the runtime and Prophet despite strong earlier validation. ARIMA's two configured
orders converged on four of seven fixtures; Prophet completed seven after the
environment correction. This limited trial does not establish a universal winner.

Runtime calculations took 0.496–1.839 ms in that local trial. Optional final fits
took approximately 411–477 ms including fresh-process startup and imports. These
are different execution paths, not a claim about warm fitting performance or an
eight-user production service. A separate `python3 -S` check completed eight
concurrent 1,200-period domain forecasts correctly in 48.72 ms total; its evidence
is `data/forecast-evaluation/minimal-runtime-20261006.json`.

Decision: keep the tested fixed basic methods for this bounded slice. ARIMA and
Prophet remain research candidates. Adoption needs representative histories,
rolling temporal evaluation, operational convergence/fallback and deadline tests,
interval calibration review and clean deployment/dependency verification. Neither
a familiar library name nor these seven synthetic fixtures justify advanced
predictive or prescriptive product claims.

To reproduce the optional comparison in a separate environment, install the six
versions listed above and run the script with `PYTHONPATH=apps/api/src`, a fresh
`--output` path and optionally `--fit-timeout-seconds`. Existing reports are never
overwritten. Generated research evidence remains ignored; no customer datasets,
secrets or model weights belong in the commit.
