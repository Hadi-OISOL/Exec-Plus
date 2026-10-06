> **File use case:** Records the forecasting priority audit before implementation.
> **What it does:** Maps VC items 34–39 to existing evidence and the authorized October 6 slice.

# October 6 forecasting and management priorities

Baseline: clean `phase2` at `9c2445d`. This commit now contains the previously
uncommitted foundation and repairs; historical release ledgers remain historical.
Reviewed repository instructions, roadmap, architecture, studies, refresh,
analytics, query validation, persistence, UI and integration fixtures.

| VC item | Existing foundation | Work in this slice |
|---|---|---|
| 34 Basic time-series forecasting | Exact aggregates, confirmed units, immutable sources | Bounded daily/monthly forecasts, explicit complete coverage, sufficiency checks, estimated ranges, saved private history |
| 35 Accuracy measurement | No forecasting evaluation | Chronological selection and untouched holdout; MAE/RMSE and carefully defined percentage metrics; baseline comparison |
| 36 Actual versus forecast | Historical study comparisons | Immutable forecasts compared with separately authorized later actuals; pending periods stay missing; exact actual receipts |
| 37 Scheduled refresh | Verified staged CSV/XLSX activation, schedules and alerts | Reuse existing flow; compare accepted refreshed snapshots without rewriting the original forecast |
| 38 Management commentary | Server-authored actual evidence summaries | Grounded actual/forecast/accuracy commentary with limitations and no invented causal or prescriptive claims |
| 39 Audit history | Manager-only raw event API, private job activity | Bounded searchable user history with explicit visibility rules and forecast/comparison events |

Implementation order is forecasting/evaluation, saved comparisons, refresh linkage,
commentary and audit experience. The upload flow will offer descriptive analysis,
basic predictive analysis and all currently supported analysis. Prescriptive analysis
is visibly planned, not enabled by a selector. Existing upload-first findings remain
available without completing optional forecast setup.

ARIMA and Prophet require explicit evaluation against simple baselines, appropriate
history and honest deployment costs. Method names alone are not quality evidence.
The runtime method decision and any isolated research trials will be recorded with
their results. Forecasts are estimates, never exact verified business facts.

Acceptance requires temporal leakage tests, missing/incomplete period refusals,
finite/zero-value handling, exact source receipts, immutable training/holdout windows,
same-definition comparisons, current workspace and private-owner checks, source
replay/tamper checks, meaningful browser journeys and migration preservation.
No new public access, production gate clearance, advanced prescriptive methods,
connectors or exports is implied.
