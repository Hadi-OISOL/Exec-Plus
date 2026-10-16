> **File use case:** Records evidence for seasonal and calendar-window anomaly extensions.
> **What it does:** Separates deterministic, application, privacy, rendering and browser
> verification from pending deployment and representative method acceptance.

# Calendar analysis verification

October 16 local/test implementation; **not deployed**. No feature ledger count or
production gate is promoted. Contracts:
[seasonal reference](seasonal-anomaly-method.md) and
[two-window distribution comparison](distribution-drift-method.md).

## Deterministic and application evidence

The combined focused backend run passes **164 cases in 89.12 seconds**:

- 39 seasonal cases, including fifty independent Fraction populations, frozen
  training/future perturbation checks and synthetic spike/level-shift limitations.
- 29 drift cases, including fifty independent quantile-coupling Wasserstein
  comparisons, exact rational CDF fixtures and nonterminating display boundaries.
- 32 real-service calendar cases covering three/six private governed receipts,
  exact saved reopening, reviews, eight invalid requests, missing periods/values,
  evidence tampering, restricted positive workflows and policy-revision rejection.
  Both methods pass all four real PDF/XLSX/CSV/PNG extraction checks with every
  period, private denials and restricted fingerprint redaction.
- Three report oracles independently check every historical row, null training
  reference gaps, exact `1/9` and `1/3` evidence, unjoined window series and unchanged
  private source fingerprints.
- 37 existing report-builder cases and 24 existing anomaly/allocation integration
  cases protect old method/export behavior.

The initial service run passes 24 cases; the subsequent eight export checks pass.
They are included in the 164 count, not additional distinct tests. Source modules
pass focused Ruff/mypy. Web types and lint pass after two initial TypeScript
narrowing mistakes were corrected; these were compilation failures, not passing runs.

## Browser and visual review

The initial real-service browser run passes **three journeys in 50.7 seconds**:
seasonal, drift and the existing snapshot-anomaly/allocation journey. Both new
journeys exercise explicit date/coverage declarations, acknowledgement reset on
edits, a failed save, successful save followed by history failure, safe reload,
exact replay, append-only review, a real XLSX download and unchanged source bytes
and meanings. Their 1440/390/320 layouts fit without page overflow or page/React
key errors. Hosted qualitative reading is deliberately unavailable in this offline
run; the unrelated reading fallback does not establish model quality.

Screenshot review found a real shared chart issue despite the journey passes:
ECharts' automatic point-symbol suppression hid most points in narrow observed-only
plots when the line was intentionally absent. A new real ECharts SVG regression
reproduces **3 of 27 marks before the fix** and **27 of 27 afterward**. Explicit
`showAllSymbol: true` retains every included non-null point without changing any
query, geometry value or source. Date-axis text may still thin to avoid overlap.
The preset's seven cases pass. Calendar views now distinguish the later-only
seasonal reference from unscored training and show exact distance fractions in
concise cards. The misleading empty per-row columns for a whole-window finding
were removed.

The final two calendar browser journeys pass **34.5 seconds**, with all 21 later
reference marks or all 28 observed window marks counted at each width. Two existing
shared-chart journeys also pass after the preset change; together with the initial
legacy decisions case, **five distinct relevant journeys have passing executions**.
All **56 frontend tests**, final types and lint pass. Final narrow screenshots were
visually inspected: complete point marks, exact inspectors and concise fraction
cards are visible; wide evidence tables stay horizontally scrollable inside their
own containers.

The intermediate calendar rerun had two test failures because a color-specific
symbol selector omitted the one actively highlighted point. The unchanged template
passed the stronger final geometry-based count that includes highlighted symbols.
Those failures and error contexts are retained; they are not counted as passes.
No application relaxation or assertion about merely having an SVG replaced the
all-points check.

## Retained artifacts and remaining gates

Ignored artifacts are under `data/verification/2026-10-16/remaining-work/`:

- `calendar-analysis-integration-initial.log`, `calendar-exports-initial.log`,
  `calendar-focused-final.log`;
- `calendar-browser-initial.log` and `calendar-browser/` screenshots;
- `calendar-browser-refined.log`, `calendar-symbol-browser-failure/` and
  `calendar-browser-final.log` retain the failed selector and passing final run;
- `calendar-symbol-regression-before.log` and `calendar-symbol-regression-after.log`;
- `calendar-types-final.log`, `calendar-types-refined.log`, `calendar-lint-final.log`.
- `calendar-web-tests-final.log`, `calendar-types-freeze.log` and
  `calendar-lint-freeze.log` record the final frontend checks.

The separate domain documents retain earlier fixture/assertion/collection failures.
No original failure evidence is overwritten. Private release, restricted-image
checks, deployed replay/denials and source-preservation verification remain pending.
Representative data, independent alert labels, automatic monitoring and calibrated
false-alarm claims are not established by these fictional fixtures.
