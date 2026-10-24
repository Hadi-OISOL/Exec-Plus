> **File use case:** Shows exactly how each requested repository is used by Syntelio.
> **What it does:** Maps pinned upstream material to real application imports or development commands, and states what is still only a reviewed reference.

# Repository integration map

The owner confirmed on October 16, 2026 that Syntelio will remain **noncommercial**
and requested actual repository reuse. This supersedes the earlier assumption
that Lieflat must remain reference-only. The current change adapts actual chart
code and analysis guidance where it fits the existing product. Installation alone
does not give the product agent new executable tools.

This document describes source integration. Test results, deployment identity and
live observations belong in the current verification ledger; a source map is not
proof that a release has passed. Licenses, attribution and modification notices
are retained in [third-party notices](../THIRD_PARTY_NOTICES.md).

## What is reused

| Requested repository and pin | Actual material and integration point | Current scope |
| --- | --- | --- |
| [Lieflat Charts, ed436ba56b3cbeee20b9b9966b38a9a9689e239c](https://github.com/larashero3-dotcom/lieflat-charts/tree/ed436ba56b3cbeee20b9b9966b38a9a9689e239c) | The G10 card and signed-bar renderer in `templates/glance-gallery.html` are adapted in [lieflat-chart-presets.ts](../apps/web/src/app/workspace/lieflat-chart-presets.ts), imported by [echarts-answer-plot.tsx](../apps/web/src/app/workspace/echarts-answer-plot.tsx) | Actual browser runtime code reuse under PolyForm Noncommercial. The renderer receives authorized returned rows; it does not execute the gallery or agent-generated HTML |
| [documd visuals, 2672b6920f6c055caf72a916b414ede62ecbfc2e](https://github.com/markdown-viewer/skills/tree/2672b6920f6c055caf72a916b414ede62ecbfc2e) | The ECharts option in `documd-visuals/examples/ops-monitoring/trend-line-multi-series.md` is adapted in [documd-chart-presets.ts](../apps/web/src/app/workspace/documd-chart-presets.ts), selected by the same React adapter for eligible Line views | Actual CC-BY-4.0 option reuse in a separate chart family. No Lieflat/documd template mixing within one chart; no documd CLI or GPL exporter is included |
| [AIpoch exploratory data analysis, 686e09dfdb45d9fa1a08664f06bb93769b3c9d91](https://github.com/aipoch/medical-research-skills/tree/686e09dfdb45d9fa1a08664f06bb93769b3c9d91) | The CSV checklist in `scientific-skills/Data Analysis/exploratory-data-analysis/references/general_scientific_formats.md` and `assets/report_template.md` are adapted into [reading_catalog.py](../apps/api/src/execplus/domain/reading_catalog.py) | Actual MIT guidance adaptation in new qualitative-reading context: structure, quality and suitable next steps. This is a curated recipe catalog, not the upstream Python EDA engine |
| [DataWithBaraa SQL analytics, b99f16a26197ff0d36131867af319238aec23dd8](https://github.com/DataWithBaraa/sql-data-analytics-project/tree/b99f16a26197ff0d36131867af319238aec23dd8) | The date-range, measures and magnitude progression in `03_scripts/03_date_range_exploration.sql`, `04_measures_exploration.sql` and `05_magnitude_analysis.sql` is adapted into the same [reading catalog](../apps/api/src/execplus/domain/reading_catalog.py) | Actual MIT analysis-guidance adaptation. Syntelio's registered profile/query operations perform calculations; upstream SQL scripts and sample datasets are not executed or imported |
| [UI/UX Pro Max, 56ea9cf174ed86786187daa9de0e6247cb0747e4](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/56ea9cf174ed86786187daa9de0e6247cb0747e4) | The installed local search implementation and chart/UX CSV catalogs are used by the coding agent to inspect chart, label, touch, motion and accessibility guidance | Actual project development tool use, not a product runtime component or a second chart engine. Native exact inspectors, keyboard navigation, touch-sized controls and reduced motion are application work informed by those results |
| [NVIDIA SkillSpector, 8ccf9201c57ae89afcb84737d8c9d58f7fccf952](https://github.com/NVIDIA/SkillSpector/tree/8ccf9201c57ae89afcb84737d8c9d58f7fccf952) | The real pinned scanner CLI performed five static scans; the ignored `data/agent-tools/scan-skill.py` wrapper invokes that installed CLI with an explicit local target and report path | Actual development/security tool execution, not customer-data analysis. Raw findings and incomplete coverage remain recorded; source-aware review is still required |
| [oneDAL, eeb645077424fe8534060d74a044a120384db325](https://github.com/uxlfoundation/oneDAL/tree/eeb645077424fe8534060d74a044a120384db325) | Source, license and numerical integration requirements were reviewed | **Reviewed reference only.** No runtime package, numerical adapter, learned model or performance gain is claimed. A defined prediction/segmentation problem and evaluated method are still needed before adding it |

The local skill installations and full clones remain ignored. Only the selected,
attributed application adaptations and their license texts are shipped. No
upstream demo records become customer data. Source pins identify what was reviewed;
the mutable repository default branches do not define this implementation.

## Chart adaptations and preserved evidence

Lieflat G10 is selected because the user explicitly requested an interactive
dashboard, and signed category comparisons fit its horizontal bars. The adapted
block retains its zero baseline, sign-specific rounded ends and 900ms quartic-out
animation with 80ms stagger. Stagger is capped; reduced motion disables animation.
Automatic width is capped at the original 16px so Show all can display many rows
without thick overlapping bars. Dense category/value labels yield to the exact
inspector. Syntelio replaces the demo data, wording, colors, font, static sizing
and gallery reveal lifecycle. It does not copy the unrelated G18 cumulative
renderer for ordinary observations.

The documd Line view preserves the source option's category axis with
`boundaryGap: false`, value axis, explicit grid and six-pixel line symbols. It
removes both demo series, all invented titles/units, the second axis and target
threshold. One returned measure supplies the real data. Smoothing is disabled,
nulls remain gaps, and a caller can request points without connecting lines.
Neither chart template generates forecasts, fitted values or new totals.

The pinned **Apache ECharts 6.1.0** runtime bundles the selected chart modules and
SVG renderer locally. Original gallery CDN scripts, remote fonts, map downloads,
generic HTML execution and the documd export pipeline are not included. The Dot
view is an application-specific ECharts configuration; it is not described as a
Lieflat template.

Every row supplied to the chart stays in its existing order and keeps its index.
Navigation changes the visible window using `dataZoom` with `filterMode: none`;
it does not change the server query or silently sample the population. Native
controls offer zoom, Show all, a result-position slider and an exact row selector.
The keyboard path can reach the first/last row even when the original view showed
only a short window. Geometry is normalized to avoid floating-point overflow;
raw decimal strings remain authoritative in the inspector and table. Signs,
zero and nulls are distinct. If the server returned a limited result, chart
navigation covers that returned result, not unseen source records.

## Reading guidance and tool boundaries

The adapted EDA/SQL catalog enumerates structure, quality, date coverage, original
records, measures and grouped comparisons. Recipes are filtered to registered
`inspect_profile` and `query` operations and supplied dataset fields. At most
eighty fields enter the reading context. Explicit metric/group names accompany
the guidance so a model is not asked to guess the acceptable names.

The model still produces a fallible qualitative reading, not numerical evidence.
Saved meanings, units, required filters, source revisions and permissions keep
their existing checks. The catalog cannot make a missing date, unit or confirmed
meaning exist. It does not permit arbitrary SQL/Python, file-system access,
unreviewed imputation, PCA, clustering, automatic confirmation or causal claims.
The bounded response-recovery change is separately tested; the catalog alone is
not evidence of hosted model quality.

## What remains outside this change

- A general drag-and-resize dashboard builder, arbitrary new measures, cross-card
  filter propagation and streaming results are not supplied by chart templates.
- Full customer-data EDA, custom training, learned predictions and oneDAL numerical
  acceleration need their own contracts, evaluation and resource limits.
- Skill installation is a coding-agent capability. The product agent receives
  only the explicit curated catalog and existing registered tools.
- The previous five scans remain partial where recorded. The new static wrapper
  was syntax/dry-run checked; unchanged targets were not rescanned simply to claim
  additional security work. A scan score is not a safety certificate.

See [the chart audit](chart-experience-reference-audit.md),
[skill adoption](project-skill-adoption.md) and
[data-tool review](data-tool-adoption-review.md) for retained reference findings.
