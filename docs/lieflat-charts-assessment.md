> **File use case:** Records the requested Lieflat Charts inspection and safe product fit.
> **What it does:** Pins the local reference, distinguishes its license from its dependencies, and bounds original ExecPlus chart improvements.

# Lieflat Charts assessment

The user supplied [Lieflat Charts](https://github.com/larashero3-dotcom/lieflat-charts)
as a chart and agent-design reference. The inspected source is pinned to
ed436ba56b3cbeee20b9b9966b38a9a9689e239c, observed on October 16, 2026.
The source clone and installer-produced reference copy stay in ignored local tools:

- data/agent-tools/references/larashero3-dotcom--lieflat-charts/
- data/agent-tools/reference-skills/lieflat-charts/

The official skill-installer helper uses the explicit commit and project-local
destination. This reference copy is outside automatic skill discovery. Its workflow
requires copying template structure; that workflow is not enabled for ExecPlus.
No global skill, runtime package, provider, CDN, user-data transfer or model-written
code execution is installed.

## Observed scope and license

The repository contains a chart/report authoring skill, chart catalogs, HTML/SVG
templates, design tokens and validation/smoke scripts. Some templates load Chart.js,
ECharts or fonts from public CDNs. It is not a dataset-analysis backend, persistent
memory service or permission-aware query tool. Its browser examples do not establish
ExecPlus numerical accuracy or authorization behavior.

The repository's
[license](https://github.com/larashero3-dotcom/lieflat-charts/blob/ed436ba56b3cbeee20b9b9966b38a9a9689e239c/LICENSE)
is **PolyForm Noncommercial 1.0.0**. The
[README](https://github.com/larashero3-dotcom/lieflat-charts/blob/ed436ba56b3cbeee20b9b9966b38a9a9689e239c/README.en.md)
states that commercial use requires separate permission. No template, token file,
example artwork or renderer from this repository is copied into the ExecPlus
product or deployment. Local source and notices are retained for assessment.

Its [third-party notices](https://github.com/larashero3-dotcom/lieflat-charts/blob/ed436ba56b3cbeee20b9b9966b38a9a9689e239c/THIRD_PARTY_NOTICES.md)
separately identify Chart.js as MIT, ECharts as Apache-2.0 and Inter as SIL OFL-1.1.
Those licenses do not make Lieflat's surrounding template code permissively licensed.
No permission from the toolkit author is assumed.

## Concrete ExecPlus adaptation

The useful comparison is how readily a reader can identify the question, unit,
series and source. The implementation uses ExecPlus's existing React/SVG components
and original styles rather than the toolkit's template-copy workflow:

| Existing result | Original improvement | Evidence boundary |
| --- | --- | --- |
| Category comparisons and exact-value cards | More readable value labels, clearer controls and restrained visual emphasis | Preserve returned numeric strings, signs, zero, nulls and table order |
| Grouped relationships | Native HTML axis endpoints and visible measure/unit headings stay readable on mobile | Plot coordinates remain approximate; exact rows, coverage and receipts remain available |
| Forecast history and estimates | Filled observed points and hollow forecast points, with uncertainty band and a clear legend | Preserve missing observations, uncertainty and exact tables; no connecting lines were added |
| Conversation charts | Consistent title, concise explanation and source access | A model's wording cannot create or modify numerical evidence |

These are ordinary chart-design ideas implemented independently within the existing
codebase. No derivative template or full competitor-style clone is claimed.

ExecPlus keeps its own readable type sizes, keyboard interaction, reduced-motion
behavior and current palette. It does not adopt unusually tiny gallery text,
decorative synthetic records, arbitrary axis cuts, inferred causal stories, or an
HTML/code execution tool for the runtime agent. A chart-selection suggestion must
still fit the existing allowlisted visualization and current source evidence.

## Verification boundary

Source inspection checked the pinned skill, catalog, license/notices, network
references and script behavior. No upstream template was executed against customer
data. Static source scanning is recorded separately and does not certify a toolkit
or grant a commercial license.

The UI change requires ExecPlus's exact-value, null/missing-point, responsive,
keyboard and reduced-motion checks plus the normal build. Results belong in the
current release verification ledger; this assessment alone is not a passing test
or a claim that additional chart types, exports or arbitrary agent skills now run.
