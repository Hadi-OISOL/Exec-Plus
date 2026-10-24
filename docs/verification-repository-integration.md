> **File use case:** Records actual repository reuse and reading-reliability evidence.
> **What it does:** Separates the superseded styling-only release from imported runtime code, targeted checks and final deployment.

# Repository integration verification

Status: chart/template integration is verified for local/test and the private
demo at `7b46db2`; the hosted retail-reading fallback remains open. The subsequent
domain-agent tools and targeted correction work are tracked separately.
The user clarified that actual reusable code/tools should drive the app, then
explicitly confirmed on October 16 that the project will remain noncommercial.
See [the integration map](repository-integration.md),
[chart contract](chart-experience.md) and [notices](../THIRD_PARTY_NOTICES.md).

## Implemented scope under verification

- Actual pinned Lieflat G10 signed-bar code is adapted to governed returned rows,
  the Syntelio theme, React lifecycle and exact-value inspection.
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

The full browser attempt passes **55 journeys**, fails one obsolete native-bar
selector and explicitly skips three model-dependent journeys in **6.5 minutes**.
The replacement renderer exposes all ten returned category options instead of
native list items. Its discovery caption is also corrected to describe all
returned groups. The repaired discovery case plus both visualization cases pass
in a focused **three-journey / 25.8-second** rerun. Thus **56 distinct offline
journeys** have passing executions; no single clean full run or executed local
hosted-model cases is claimed. The scale-caption wording changed during the full
run before the focused visualization cases; the rerun checks the final source.

Local production build, final lint and types pass. Candidate VPS API/web builds
pass. Non-root network-disabled images pass eight minimal exact/forecast checks,
three extension checks, eight pattern/daily checks, and an eight-worker/48-operation
grouped/allocation check. New reading imports and shipped notices also pass.
Upstream license files preserve their original bytes, including CRLF/EOF whitespace;
`git diff --check` flags those verbatim assets, not application-code whitespace.

Private release results follow below. Private evidence lives under
`data/verification/2026-10-16/runtime-tool-adoption/` and
`data/verification/2026-10-16/chart-experience/`.

## Private release

Application **7b46db2** is activated for API/jobs/web on unchanged **0018**.
All **48 table fingerprints**, including migration metadata, and the environment
checksum match across activation. Checkpoint:
`pre-integration-7b46db2-20261016`. Candidate `f16dc5f` was built but superseded
before activation by the discovery-caption/test correction; it was never activated.

Checked backups `20261016T083202Z` and fresh pre-activation
`20261016T084552Z` pass database/object checksums and restart services successfully.
Before activation, source monitoring detects an actual saved-definition update:
version 3 becomes version 4, both units are filled and no questions remain. Source
bytes/profile/revisions stay unchanged. Original snapshots and the failed comparison
are retained; the new pre-activation baseline preserves the latest definitions.
All five reported-source artifacts match that baseline after activation and backup.

Three live browser journeys pass **36 layouts at 1440/390/320 widths in 46.336
seconds**, with no page errors, prohibited requests or horizontal overflow. They
exercise actual Lieflat bars, documd lines and ECharts dots, all 365 returned daily
rows, keyboard/end/previous selection, zoom/Show all, every exact table row, authorized
drill, saved forecasts and saved pattern/group comparisons. Root visually inspects
the live dashboard and mobile line capture. KPI values fit and record pickers retain
44px height. Three publicly served license/attribution assets match tracked bytes.

The first fresh hosted retail-reading probe **fails** with the retained
`invalid_response` category and returns saved guidance. Exact total **8235156.60**,
old receipt replay, immutable old reading, six privacy denials, source definitions
and personal memory all pass. There is no blind second retry and no claim that the
earlier retail fallback is resolved. The broad category does not identify the
particular validation rule; the next agent-tools slice adds fixed issue codes and
targeted correction hints without logging model prose or weakening validation.

Checked post-release backup **20261016T085923Z** retains the live saved work.
After restart, five containers run with zero restarts, readiness and workspace
return successfully, six listeners remain loopback-only, and model/refresh/backup
units are active. The runtime check observes no application-error lines in its
thirty-minute window; the separately retained reading fallback still occurred.
No model provider, configuration or public exposure changed.

All 64 original feature IDs, counts 37/16/11 and eight production gates remain
unchanged. Functional synthetic results do not establish representative model
quality, sustained load, complete competitor capability or acceptance of the
user's existing browser tab. The earlier tab mismatch remains undiagnosed.
