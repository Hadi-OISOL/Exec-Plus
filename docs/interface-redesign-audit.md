> **File use case:** Audits the ThoughtSpot-referenced interface request before implementation.
> **What it does:** Maps observable layouts and interactions to verified ExecPlus capabilities and records the acceptance boundary.

# Analytics interface redesign — October 6, 2026

The user requested ThoughtSpot-style interface and data presentation as the first
step toward broader product parity. This audit starts from clean local `phase2`
commit `769acea`, which now retains the preceding forecasting and operations work.
An optional clarification asked whether to start with the analytics application
or also redesign the marketing website. No answer was received within the offered
response window, so work proceeds under the stated analytics-first assumption.
This is a routine scope choice, not approval inferred from silence. The existing
marketing website remains outside this delivery. Existing APIs, exact receipts,
private conversations and production gates remain authoritative.

## Reference evidence

Public official documentation and screenshots were reviewed on October 6:

- [Home and navigation](https://docs.thoughtspot.com/cloud/26.9.0.cl/thoughtspot-homepage)
- [Insights workflows](https://docs.thoughtspot.com/cloud/26.9.0.cl/business-user)
- [Conversational exploration](https://docs.thoughtspot.com/cloud/26.9.0.cl/spotter-getting-started)
- [Dashboard interaction](https://docs.thoughtspot.com/cloud/26.9.0.cl/liveboards)

Observed layout: a compact dark application header, grouped left navigation, light
canvas, central question/source composer, recent-content panels, wide answer cards
with chart/table controls, and dashboard grids combining metric, chart and table
cards. The public marketing site alone does not reveal every authenticated screen.
The reference images remain ignored under `data/interface-reference/`; no external
branding, screenshots, proprietary code or customer data becomes an ExecPlus asset.

## Audited implementation map

| Experience | Existing capability | Interface work |
| --- | --- | --- |
| Home and navigation | Workspace/source state, upload-first flow, on-demand optional panels | Group navigation; bring questions and current data to the foreground; improve responsive shell |
| Search and chat | Durable private jobs, cancellation, history and cited answers | Wider answer canvas, clear source context and reusable result presentation |
| Discoveries and charts | Bounded exact source queries, KPI/trend/breakdown and record drill-down | Consistent card chrome, visible chart/table choices and submitted filter state |
| Saved answers | Permission-aware save/replay/share; result currently shown as raw JSON | Searchable library and readable result/evidence presentation |
| Dashboards/studies | Versioned studies, six-pin boards, explicit sharing/rerun | Library-first layout and clearer board/visualization controls |
| Data and management | Upload/preparation/catalog, forecasts, monitoring, support/admin | Consistent navigation, forms and tables; retain all existing workflows |

## Non-negotiable boundaries

No control may pretend to perform an unsupported operation. Existing board pins
refer to immutable study versions; an arbitrary query answer cannot be pinned via
that contract. Saved boards require explicit reruns, and are not advertised as
always-current dashboards. Supported filters must execute through the existing
server query path, not only hide displayed rows. Plot coordinates may approximate;
labels, evidence and tables retain exact numeric strings, nulls and signed values.
Do not invent sample values or business insights for a polished empty state.

Keep first-upload discovery useful without requiring setup, optional views lazy,
all resources permission-scoped, and private state cleared on sign-out/source
changes and revoked access. No source/model/server exposure change or schema
migration is required by this presentation slice. Marketing-site work, missing
connectors/exports, universal visualization editing and advanced analysis are
separate from verified interface parity; Phase 6 and production gates stay unchanged.

## Acceptance

Retain existing real-service browser journeys for upload, jobs, calculations,
receipts, meaning review, saved/shared content, six-pin studies, forecasts, refresh,
admin/support and session privacy. Add focused coverage for the new navigation,
search, chart/table views, saved-result display and keyboard/mobile interactions.
Inspect desktop and 390/320-pixel renders, reduced motion, empty/loading/error states
and unchanged numerical evidence. Run frontend unit tests, lint/types and production
build; run relevant backend contract checks for any changed integration. Update the
handoff, roadmap and maintained DOCX from actual evidence. Do not claim A–Z product
or visual parity from public screenshots alone.
