> **File use case:** Research evidence for the personal data assistant and studio interface.
> **What it does:** Separates documented Google capabilities, public REA observations and Syntelio design choices.

# Google data tools and personal assistant references

Reviewed October 16, 2026. No Google account, private tenant, customer dataset or
credential was supplied to the reference sites. This work does not connect
Syntelio to BigQuery, switch providers or demonstrate feature parity.

## Documented behavior and adaptation

| Primary reference | Documented behavior | Syntelio adaptation and boundary |
| --- | --- | --- |
| [BigQuery conversational analytics](https://docs.cloud.google.com/bigquery/docs/conversational-analytics) | Data agents combine selected sources with metadata, instructions, business terms and verified queries. Conversations retain answers and source metadata. | Reuse confirmed dataset meanings, private goals and registered operations. Add explicit personal context for wording and suggestions. Personal memory cannot establish units, filters or permissions. |
| [BigQuery data insights](https://docs.cloud.google.com/bigquery/docs/data-insights) | Generates suggested questions/queries and descriptions using metadata and available profile scans; inferred descriptions and relationships can be reviewed. | Keep real profiles, reviewable meaning and executable starter questions. Generated prose is not a measured finding. Existing pattern services supply calculations and coverage. |
| [BigQuery Data Canvas](https://docs.cloud.google.com/bigquery/docs/data-canvas) | Find, query and visualize data in an iterative workflow, with result summaries and visualization controls. | Expose focused task choices and make chart results prominent. A graph editor and arbitrary SQL generation are unnecessary for the present beginner-oriented interface. |
| [Google ADK tools](https://adk.dev/tools-custom/) and [memory](https://adk.dev/sessions/memory/) | Tools and memory are distinct agent capabilities. | Keep the existing typed tool plan and PostgreSQL-backed private context. A second framework or hosted memory service is not required to implement this bounded capability. |

These descriptions are from public documentation, not independently measured
quality or latency. Google has broader services and integrations; those are not
implemented by adding memory or restyling our workspace.

## REA observations

The project-local REA 6.4.0 CLI passively inspected the public Data Canvas page in
an owned, separate Chrome profile. Discovery preceded captures. Playwright only
scrolled to the public illustration; REA inspected the page and captured pixels.
No private application source was recovered or copied.

| Capture | Observation | Retained evidence under ignored `data/agent-evidence/` |
| --- | --- | --- |
| G1 | Documentation presents a dedicated navigation column, a main content area and secondary page navigation. This is the docs shell, not the application itself. | `20261016T054943974738Z`; page `ev_30080e1acc683d3267ec69ca9395022af1d27bc9b45266c0bd16bcf7e28e3078`; screenshot `ev_2492fabd382bfa472e7e1c2ab2adaa8fb0ded3ed9a731d3e094cc94c1596c2f4` |
| G2 | A Data Canvas illustration places a short result description above one dominant bar chart, with visualization details below. | `20261016T055026148398Z`; page `ev_96baf40c88edb0b183cbf9abb2f04decbbf53b64d0d7a60bf231e89d1da9fc3d`; screenshot `ev_4d51473606ea5db80d00834c87ec8d686db0204908d2f6f9daf5c4e0ffcdf2a3` |

Both target `https://docs.cloud.google.com/bigquery/docs/data-canvas` with origin
restricted to `https://docs.cloud.google.com`. PNG signatures and SHA-256 checks
passed. Discovery is retained in `data/agent-tools/browser/oct16-google-targets.json`.
The inspection browser was stopped afterward. Captures cover the visible page,
not animation timings, active product interactions or an unseen backend.

The light studio styling, optional personal-memory editor and sample launch cards
are original Syntelio design choices. Existing [ThoughtSpot and Metabase evidence](clean-experience-reference-audit.md)
also informs task separation and chart/evidence placement. No new chart library,
agent framework or third-party runtime dependency is required by this research.

## Existing tool boundary

| User task | Current execution surface |
| --- | --- |
| Understand a file | Profile inspection plus optional validated qualitative reading |
| Calculate, filter or compare totals | Validated read-only query with exact execution receipt |
| Find patterns or compare groups | Registered numerical methods with private source receipts |
| Find information in documents | Permission-filtered document retrieval with source citations |
| Forecast, test a what-if, find unusual values or choose actions | Dedicated analysis forms/services with explicit prerequisites and assumptions |

Calling these skills describes a useful task repertoire; it does not add arbitrary
code execution or guarantee that every dedicated analysis can be requested through
chat. Missing inputs continue to require review. Saved memory is advisory context,
not executable instructions or a replacement for current evidence.

## Requested development skills and libraries

The [project skill adoption record](project-skill-adoption.md) retains exact source
pins, licenses, local installation locations, scanner findings and source-reviewed
limits. UI UX Pro Max informs accessible spacing, controls and hierarchy. Documd
guidance informs the local demo walkthrough. The general EDA skill contributes a
structure/quality/interpretation checklist. SkillSpector supplies static evidence
for reviewing those downloaded sources; a scanner score is not a certification.

The [data-tool review](data-tool-adoption-review.md) maps oneDAL and SQL examples to
current or future numerical methods. The [Lieflat assessment](lieflat-charts-assessment.md)
keeps its noncommercial template workflow outside product implementation and
records original chart improvements. None of these downloads changes the runtime
agent's authorized tool set or enables arbitrary generated HTML/Python execution.
