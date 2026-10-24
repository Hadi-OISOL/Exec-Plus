> **File use case:** Records the requested Lieflat Charts inspection and safe product fit.
> **What it does:** Records the project-only skill installation, the noncommercial template adaptation and its license, data and execution boundaries.

# Lieflat Charts assessment

The user supplied [Lieflat Charts](https://github.com/larashero3-dotcom/lieflat-charts)
as a chart and agent-design reference. The inspected source is pinned to
ed436ba56b3cbeee20b9b9966b38a9a9689e239c, observed on October 16, 2026.
The source clone, earlier reference copy and newly installed coding skill stay
local and ignored:

- data/agent-tools/references/larashero3-dotcom--lieflat-charts/
- data/agent-tools/reference-skills/lieflat-charts/
- .agents/skills/lieflat-charts/

At the user's explicit request, the official skill-installer helper installed the
unmodified repository at that exact commit into `.agents/skills/lieflat-charts/`.
The skill is available to the coding agent after the client discovers it on a
subsequent turn. All **146 installed files** match both the pinned clone and the
previously scanned reference copy byte-for-byte, including `LICENSE`,
`THIRD_PARTY_NOTICES.md` and `agents/openai.yaml`. The ignored receipt
`data/agent-tools/references/lieflat-charts-project-installation.json` records every
file hash. The older reference-installation receipt remains historical evidence.

The first chart pass used general guidance for independently authored components.
The owner subsequently confirmed that Syntelio will remain **noncommercial** and
explicitly requested actual template reuse. The current implementation adapts the
G10 diverging-bar renderer into a bounded React/ECharts component; it retains the
template license and attribution. The skill remains a coding tool, not an arbitrary
HTML or code-execution capability available to the product agent.

## Observed scope and license

The repository contains a chart/report authoring skill, chart catalogs, HTML/SVG
templates, design tokens and validation/smoke scripts. Some templates load Chart.js,
ECharts or fonts from public CDNs. It is not a dataset-analysis backend, persistent
memory service or permission-aware query tool. Its browser examples do not establish
Syntelio numerical accuracy or authorization behavior.

The repository's
[license](https://github.com/larashero3-dotcom/lieflat-charts/blob/ed436ba56b3cbeee20b9b9966b38a9a9689e239c/LICENSE)
is **PolyForm Noncommercial 1.0.0**. The
[README](https://github.com/larashero3-dotcom/lieflat-charts/blob/ed436ba56b3cbeee20b9b9966b38a9a9689e239c/README.en.md)
states that commercial use requires separate permission. The owner's explicit
noncommercial scope now permits the licensed G10 adaptation under the published
terms. The local skill remains unmodified; shipped notices and license texts are
listed in [third-party notices](../THIRD_PARTY_NOTICES.md). No commercial permission
is assumed, and installing the skill does not remove its terms.

Its [third-party notices](https://github.com/larashero3-dotcom/lieflat-charts/blob/ed436ba56b3cbeee20b9b9966b38a9a9689e239c/THIRD_PARTY_NOTICES.md)
separately identify Chart.js as MIT, ECharts as Apache-2.0 and Inter as SIL OFL-1.1.
Those licenses do not make Lieflat's surrounding template code permissively licensed.
No permission from the toolkit author is assumed.

## Concrete Syntelio adaptation

The useful comparison is how readily a reader can identify the question, unit,
series and source. The earlier studio release used original React/SVG components
and established this baseline:

| Existing result | Original improvement | Evidence boundary |
| --- | --- | --- |
| Category comparisons and exact-value cards | More readable value labels, clearer controls and restrained visual emphasis | Preserve returned numeric strings, signs, zero, nulls and table order |
| Grouped relationships | Native HTML axis endpoints and visible measure/unit headings stay readable on mobile | Plot coordinates remain approximate; exact rows, coverage and receipts remain available |
| Forecast history and estimates | Filled observed points and hollow forecast points, with uncertainty band and a clear legend | Preserve missing observations, uncertainty and exact tables; no connecting lines were added |
| Conversation charts | Consistent title, concise explanation and source access | A model's wording cannot create or modify numerical evidence |

Those earlier improvements were independently implemented. The new actual G10
adaptation is separate: `lieflat-chart-presets.ts` derives from
`templates/glance-gallery.html`, the G10 card at lines 103–108 and renderer at
lines 502–534 of the pinned source. It retains horizontal signed bars, a zero
baseline, sign-specific rounded caps and the finite 900ms quartic-out/80ms stagger.
Syntelio replaces sample data, copy, colors and typography; caps automatic bar
width at the original 16px, suppresses overlapping category labels and caps
stagger duration; respects reduced motion; and supplies exact native inspection
and view-only navigation. Geometry normalization cannot replace the original
returned strings. Upstream demo records, arbitrary HTML, CDN loaders and gallery
replay timers are not included. The dashboard request makes Glance an explicit
fit; cumulative G18 was rejected for ordinary noncumulative observations.

The follow-up [chart experience](chart-experience.md) extends actual dashboard,
answer, pattern and forecast presentation. Its [reference audit](chart-experience-reference-audit.md)
records the three gallery images inspected, the seven-repository use map and the
required behavior. That follow-up's implementation and release checks are recorded
separately; the baseline table above is not a claim that newer changes have passed.

Syntelio keeps its own readable type sizes, keyboard interaction, reduced-motion
behavior and current palette. It does not adopt unusually tiny gallery text,
decorative synthetic records, arbitrary axis cuts, inferred causal stories, or an
HTML/code execution tool for the runtime agent. A chart-selection suggestion must
still fit the existing allowlisted visualization and current source evidence.

## Verification boundary

Source inspection checked the pinned skill, catalog, license/notices, network
references and script behavior. No upstream template was executed against customer
data. Static source scanning is recorded separately and does not certify a toolkit
or grant a commercial license.

The unchanged files reuse the earlier source-aware review: **CAUTION**, with raw
SkillSpector score **96 / CRITICAL**, 40 findings and **37.8% fully inspected text
components / partial coverage**. Explanations of flagged comments do not close the
JavaScript parser coverage gaps. The whole-repository review remains partial; it
is not a safety certificate for every template. The specifically adapted G10 block
was read separately, and its compiled application component receives normal
frontend checks. No upstream gallery script or optional installer is automatically
executed. No additional model scan or provider call was made for installation. See
[project skill adoption](project-skill-adoption.md).

The UI change requires Syntelio's exact-value, null/missing-point, responsive,
keyboard and reduced-motion checks plus the normal build. Results belong in the
current release verification ledger; this assessment alone is not a passing test
or a claim that additional chart types, exports or arbitrary agent skills now run.
