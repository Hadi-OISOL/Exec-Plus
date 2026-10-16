> **File use case:** Records actual repository reuse and reading-reliability evidence.
> **What it does:** Separates the superseded styling-only release from imported runtime code, targeted checks and final deployment.

# Repository integration verification

Status: implementation and verification in progress; no final release claim.
The user clarified that actual reusable code/tools should drive the app, then
explicitly confirmed on October 16 that the project will remain noncommercial.
See [the integration map](repository-integration.md),
[chart contract](chart-experience.md) and [notices](../THIRD_PARTY_NOTICES.md).

## Implemented scope under verification

- Actual pinned Lieflat G10 signed-bar code is adapted to governed returned rows,
  the ExecPlus theme, React lifecycle and exact-value inspection.
- A separate attributed documd ECharts option handles eligible observed lines;
  ECharts 6.1.0 is installed as a real bundled dependency. Dots are a separate
  engine view. All returned rows remain accessible through selection and view
  controls; chart zoom does not recalculate or change the query population.
- MIT EDA/SQL analysis guidance is adapted into immutable supported reading
  recipes, restricted to the columns and operations available to the prompt.
  The model receives the explicit eligible measure/group catalog instead of
  guessing the validator's allowed fields.
- A typed truncated-response signal allows one fresh qualitative correction within
  the existing two-call/forty-second limits. Repeated failures still fall back
  honestly. Messages distinguish an explanation failure from absent data; logs
  contain only a reason enum, never raw model content or private context.
- No arbitrary skill execution, upstream example dataset, model provider change,
  new numerical method or schema migration is introduced. oneDAL remains a
  reviewed library, not a deployed engine or claimed accuracy improvement.

## Retained earlier evidence

The original chart release `879d90f` and local layout repair `47977a8` are recorded
in [the chart ledger](verification-chart-experience.md). Their 38 frontend tests
and 13 distinct browser journeys are prior evidence, not a fresh test result for
the new renderer. Initial live layout defects were real: narrow KPI cards and an
oversized record picker. A later three-journey/27-layout functional pass did not
waive those visual defects. Both received local fixes and regression checks.

## Current local checks

Reading tests initially pass 113 cases and fail two old wording assertions. Those
assertions are updated to the new specific explanation-failure notice while
retaining profile/saved-data checks. The frozen focused suite passes **115 cases**
in **33.32 seconds**, no skips. It covers actual provider truncation, one fresh
correction, deadlines/call budgets, private diagnostics, source freshness,
permissions, saved answers and allowed exploration fields.

The full backend/architecture suite passes **1,351 cases in 399.89 seconds**;
Ruff and mypy (180 source files) pass. The 115 focused reading cases are included
in that full result, not added to inflate its count.

Six imported-chart preset tests pass. The first six-journey browser run passes
four and fails two assertions expecting different decimal formatting: the API
correctly returns zero as `0E-12` and integers as `4`/`45`. Assertions now preserve
the actual returned strings. That run also reveals a missing ECharts Tooltip
module and disposal cleanup warnings; both are fixed. An independent numerical
review fixes the all-negative Dot axis upper bound to zero, with a renderer
regression. The corrected focused run passes all **six journeys in 47.3 seconds**.

An early frontend typecheck during package replacement cannot find Next
declarations; the normal post-installation typecheck passes. Initial lint also
misidentifies ECharts' imported `use` as a React hook; a descriptive alias fixes
that failure. These initial failures remain in the private evidence.

Installing ECharts changes only four dependency entries initially. The audit
reports eleven existing advisories, including Next.js and browser/image tools;
none names ECharts or its newly added dependencies. Compatible-range remediation
without `--force` updates Next/eslint-config-next to 16.4.2, Playwright to 1.64.1
and sharp to 0.35.5. The production-only npm audit then reports zero advisories.
Five high development-only entries remain in the braces → micromatch → fast-glob
→ Next lint plugin chain; npm offers a breaking downgrade, which is not applied.
A clean production dependency audit is not a complete application security audit.
The full browser suite is required to check the changed framework/test versions.

All **49 frontend unit/renderer tests**, TypeScript and ESLint pass. The real SVG
renderer tests cover signed/null/zero values, exact high-precision cells, negative-only
axes, escaped labels, repeated categories and navigation to the last of 365 rows.
Root review inspects desktop and 320px captures. A later independent review adds
an explicit missing-row list so a narrow zero-width bar cannot hide a missing
value, and labels Minimum/Maximum clearly. The full browser run includes these
last presentation changes; the prior six-pass run predates them.

Final build/full-browser results and private release checks will be recorded
here after execution. Private evidence lives under
`data/verification/2026-10-16/runtime-tool-adoption/` and
`data/verification/2026-10-16/chart-experience/`.

## Private release

Checked pre-release backup `20261016T083202Z` passes database/object archive
checksums and restarts services successfully. Pending: candidate API/web images; unchanged 0018 activation with
all table fingerprints/config preserved; hosted retail reading and exact/privacy
checks; browser/visual checks; post-release backup and healthy services.
Earlier failure reasons are not retrospectively invented. A successful new
synthetic reading does not prove every dataset will receive a valid explanation.
All 64 original feature IDs, counts 37/16/11 and eight production gates remain
unchanged; this does not establish full competitor or predictive capability.
