> **File use case:** Explains the question-led analytics workspace and its data-presentation contracts.
> **What it does:** Maps visible controls to existing authorized calculations, saved evidence and private conversations.

# Analytics workspace

The October 6 interface uses a grouped navigation rail, a compact header and a
light analytics canvas. The [reference audit](interface-redesign-audit.md) records
the public ThoughtSpot layouts reviewed. ExecPlus retains its own components,
branding, source contracts and supported methods.

## Where to start

- **Overview:** choose your source, ask a question from the central composer, open
  saved work for that source, or continue to its calculated first findings.
- **Ask ExecPlus:** continue the same private conversation in a wider view. Existing
  history, real request activity, cancellation, explanations and evidence remain.
  A question submitted while another request is active stays as an explicit draft;
  send it after the current answer finishes.
- **Search data:** search the authorized workspace catalog, select a source and
  explore its calculated dashboard. The header search opens this view. It is not
  a search across other workspaces or every type of saved content.
- **Saved work:** search names, filter private/shared content or item types, and
  switch between card and list layouts. Opening an analysis replays its original
  evidence. Questions and dashboard configurations execute using their existing
  current-revision contracts.
- **Studies & dashboards:** browse saved studies and six-pin boards, share explicitly,
  reopen original versions, rerun a study or compare its versions. A saved board
  never silently reruns its studies.

Forecasts, refresh/alerts, data preparation, documents, team settings, audit,
support and authorized usage/admin views remain in the grouped navigation.
Optional panels load on demand. A first upload still creates useful findings
without requiring business-definition setup first.

## Reading and exploring an answer

Eligible aggregate results have **Chart** and **Table** controls. Expanded charts
use a keyboard-accessible dialog; Escape or Close returns focus to its trigger.
Selecting an eligible breakdown category runs the existing matching-record query.
Selecting inside an expanded chart closes that view so the matching rows are visible.
Raw record results stay tables. Exact tables support bounded row pagination.

Chart coordinates approximate returned values only for drawing. Table cells,
tooltips, value labels and saved evidence retain exact numerical strings, including
decimals and integers beyond JavaScript's safe range. Negative bars extend from
the shared zero baseline; exact zero has zero width. Explicit nulls stay gaps.
Study date views show observed points without interpolating missing periods.
Derived aggregate headers may use readable labels; source columns and raw evidence
keep their original names.

The dashboard's **Viewing** strip shows submitted filters. Editing a form does not
change the displayed evidence until its server calculation succeeds. Saved dashboard
configurations use the applied template and filters. Removing a filter still goes
through the authorized calculation endpoint.

Explanations and document passages do not acquire numerical verification labels.
Calculated responses retain their execution receipts, source revision and original
definitions. Raw structured evidence is available in a disclosure after the readable
result. Display switches do not change business meaning or authorize a calculation.

## Limits

This interface does not add arbitrary chart builders, conversational board editing,
global cross-workspace search, automatic live-board refresh, exports, new connectors,
public identity or new analysis methods. Arbitrary answers cannot be pinned through
the study-only board contract. Full ThoughtSpot product or visual parity is not
established by public reference screenshots. Remaining product work stays governed
by the [roadmap](../ROADMAP.md) and existing production gates.

See the [verification ledger](verification-interface-redesign.md) for tested
interactions, retained failed attempts and deployment evidence.
