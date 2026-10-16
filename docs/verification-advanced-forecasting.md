> **File use case:** Records verification of the bounded advanced forecasting implementation.
> **What it does:** Separates measured local results, retained initial failures and pending private-demo/customer acceptance.

# Advanced forecasting verification

Date: October 16, 2026. Scope and method contract: [advanced forecasting](advanced-forecasting.md). This ledger covers the local implementation; it does not claim a VPS release or production acceptance.

## Final private-demo release

Application `867c5a0` is deployed on schema `0020`. Combined final backend coverage,
restricted images, live API/browser acceptance, preserved data/configuration and
checked pre/post backups are recorded in the
[release ledger](verification-remaining-work-release.md). Earlier pending-deployment
statements below describe their historical checkpoints. Production acceptance
remains separate; no production gate is cleared.


## Observed results

| Check | Observed result | Scope |
| --- | --- | --- |
| Forecast numerical suite | 65 passed in 0.54 seconds | 26 new advanced cases and 39 existing numerical cases |
| Combined forecast, export-builder and access-policy suite | 148 passed in 51.53 seconds | Advanced/basic numerical and integration cases, then-current builder cases and thirteen analytical policy cases; overlapping runs below are not additional distinct passes |
| Final transaction guards, label changes, studies and architecture | 117 passed in 94.09 seconds | Forecast integrations, policy tests, study compatibility, export builders and architecture after final workspace-lock changes |
| Final export builders | 37 passed in 1.35 seconds | Added exact four-date/null chart labels, fixed-unit evidence and nested restricted fingerprint redaction |
| Final restricted analytical paths | 15 passed in 15.95 seconds | Rechecked the thirteen analytical policy cases and two advanced forecast policy cases after the public fingerprint-redaction marker was added |
| Earlier analytical policy compatibility | 95 passed in 84.79 seconds | Existing studies, decision analysis, patterns, grouped relationships and scenarios |
| Frontend unit checks | 55 passed | Includes advanced minimum-history eligibility calculations |
| Final advanced browser journey | One passed in 11.9 seconds; 19.1 seconds including runner startup | Real API/database/storage, method selection, exact saved result, three layouts and actual Excel download |
| Existing forecast browser journeys | Both passed in the first browser execution | Basic forecast/source comparison/audit and incompatible successor handling |
| Static checks | Ruff and mypy passed for owned backend files; frontend types passed | Seven production Python modules, new tests and shared frontend types |

The advanced browser fixture contains fifty consecutive daily amounts. It selects Holt, returns the independently expected next estimate **5.1**, exposes three chronological selection windows, opens the exact period inspector and reopens the same immutable result. Explicit seasonal selection without a declared cycle cannot submit. The downloaded file is an actual XLSX response, not a renamed text file.

Desktop 1440px and mobile 390px/320px checks found no page or chart overflow. Method selectors are at least 44px and at most 64px high. All three result screenshots were inspected: observed points, hollow estimates, visible uncertainty notice, exact inspector, table and collapsed evidence sections remain readable. Narrow tables scroll within their own container. The existing chart intentionally displays the last 48 historical periods; the saved tables and exports keep all history. This does not claim that every historical point appears simultaneously in the plot.

## Independent numerical and safety cases

- Hand-calculated smoothing fixtures check SES 12.5, Holt 16.75/19 and damped Holt 15.536/16.7008. Synthetic linear and seasonal fixtures check expected future values, seasonal alignment, naïve baseline comparisons and stable ties.
- Constant/zero/negative series, long horizons, daily/monthly eligibility, missing/incomplete periods, non-finite input and unstable caller Decimal settings are covered. Negative predictions are retained rather than clipped.
- Perturbing only the later test observations cannot change the chosen candidate or validation-derived range. Every candidate receives the same chronological windows. The fixed registry/work counter is bounded and checked at the maximum history size.
- The test window scores serialized displayed estimates. Empirical validation-error ranges are explicitly not calibrated probabilities. A perfect fictional trend is not evidence of future/customer accuracy.
- Existing forecast-v1 request shape and result calculation remain unchanged. New v2 forecasts and later-actual comparisons reopen exactly. Tampered requests, method/version mismatches and changed source/meaning are refused.
- Integration checks exercise protected PDF, Excel, CSV evidence ZIP and PNG exports for both the saved v2 forecast and later comparison. Exact recorded values and uncertainty limitations are extracted from the real file formats.
- Creator privacy, cross-workspace and revoked-membership denials remain enforced. Opt-in row/column policies calculate only the granted projection, retain actor-bound policy references, hide incompatible history and refuse publication/replay/export after policy changes. Concurrent changes during fitting are rejected before saving a result.
- Analytical policy tests also cover permitted studies, boards, scenarios, anomalies, allocations, patterns and grouped comparisons. Shared policy-bound results remain actor-bound; sharing does not expand another person's source grant. No-policy sharing retains its existing behavior.

## Initial failures retained

Private evidence lives under ignored `data/verification/2026-10-16/remaining-work/`; no generated data, browser images or secrets are published.

- `advanced-forecast-unit-initial.log`: twelve failures exposed raw recursive Decimal states hitting the existing estimate-exponent guard. Estimates now use the declared 18-significant-digit serialization before scoring/validation. Independent fixtures verify the retained numerical result.
- `advanced-forecast-unit-second.log`: two test expectations incorrectly required a particular zero representation or unrounded estimate. Numeric/declared-precision expectations were corrected; final numerical run passes all 65 cases.
- `advanced-forecast-final-backend.log`: an incorrect architecture-test path stopped collection with exit 4; no test pass is counted from that attempt. The corrected architecture path is covered in the 117-case run.
- `advanced-forecast-browser-initial.log`: the new journey attempted review before selecting Predictive; corrected fixture navigation. Both existing forecast journeys passed in that execution.
- `advanced-forecast-browser-second.log`: a genuine 42px method selector failed the minimum 44px target. Scoped CSS fixes its height; the final third execution passes.
- `analysis-policy-new-initial.log`: reentrant TestClient usage from an async callback failed two race fixtures; two other checks expected 404 where the existing calculation contract correctly returned a safe 422 clarification. Tests now exercise the service race directly and assert the applicable denial contract.
- `analysis-policy-legacy-initial.log`: the first dismissal repair called a helper that acquired a second workspace lock, causing a real deadlock. The operation now captures a policy reference before entering the final write transaction. Only that test query was cancelled; normal teardown removed its isolated schema. The corrected compatibility run passes 95 cases.
- A final mypy check required an explicit dictionary type for recorded unit metadata; the annotation was added and all seven owned production modules pass.

The final browser runner records unavailable-model fallback during onboarding because it runs without hosted credentials. Forecast computation, evidence, replay and export are deterministic and passed; this is not a hosted reading-quality evaluation.

## Pending acceptance

Private-demo deployment/verification, representative customer forecasting quality and sustained performance remain unobserved for this slice. No production gate is cleared. Additional forecast families, calibrated uncertainty and external regressors remain outside the explicitly documented method set. The broader policy and portable-export changes have their own acceptance ledgers; this document does not substitute for their final release checks.
