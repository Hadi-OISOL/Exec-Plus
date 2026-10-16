> **File use case:** Describes the bounded portable-result export contract.
> **What it does:** Records delivered formats, authorization boundaries, exactness rules and remaining external delivery dependencies.

# Portable results

The workspace offers explicit downloads for saved conversation calculations, tables,
source-backed explanations, data maps and measured patterns; saved forecasts and
actual comparisons; scenarios, anomaly findings and allocations; saved study versions
and pinned dashboards; and the query results currently displayed on a source dashboard.
No download asks a model to calculate or changes a dataset, definition, review or result.

The current-dashboard request contains up to twelve distinct executed query IDs and a
label. The server reopens those receipts. It rejects client-supplied rows or values.
Saved dashboards instead reopen their pinned immutable study versions and current
sharing permissions. This distinguishes a displayed dashboard snapshot from a saved
board and from a full raw-data export.

## Formats

- **PDF:** locally rendered figures, exact tables, explanations, limitations and source
  evidence. Diagram figures show field membership, never inferred causes or joins.
  Tall bar charts and maps use consecutive page slices; exact tables remain complete.
- **Excel:** original returned scalar strings in explicit text cells. Long numbers
  never pass through Excel's numeric precision. Ordered JSON chunks in the Evidence
  sheet preserve original scalar types, null versus empty string, scopes and receipts.
- **CSV + evidence (.zip):** one quoted UTF-8 CSV per table, a full typed `evidence.json`
  and a short guide. Formula-like text is prefixed with an apostrophe; the sidecar
  preserves its original value. Spreadsheet applications may still infer dates or
  numbers when opening CSV, so the evidence or Excel text cells are authoritative.
- **PNG:** a trusted local Pillow drawing of one selected recorded chart. All returned
  chart positions are included or the export refuses. Null line values break paths;
  scatter plots use actual numeric x values; signed comparisons share a zero baseline.
  Exact chart values, all report tables and source evidence are embedded as PNG text
  metadata. Plot coordinates and compact axis labels are presentation approximations.
  This is a portable rendering, not a screenshot of the interactive browser chart.

Forecast observations, estimates and heuristic or empirical ranges retain their saved
labels and limitations. Scenario assumptions and pattern sampling/causality notes are
visible. PNG choices only appear for known chart encodings. A result containing several
charts offers an explicit chart selector.

## Permissions and races

Downloads use the existing bearer-authenticated routes and return no-store attachments,
never public object URLs. Conversation answers and private analyses remain owner-private,
including from workspace administrators. Study sharing follows existing visibility.

The service replays authorized content before rendering and again afterward with the
same generation timestamp. It refuses a changed source, definition, saved result or
review. The final workspace-locked transaction rechecks membership, policy audience,
private ownership/shared visibility, source evidence and review state before recording
an actor-private export audit event. A downloaded copy cannot be recalled after sharing.

## Explicit limits

An export supports at most 200,000 cells, 100 columns per table, two million characters
including report text, and 16 MiB of output. Excel rejects cells exceeding 32,767 UTF-16
code units or unsupported XML control characters instead of silently truncating them.
CSV retains supported control text safely inside quoted fields and JSON evidence.

PDF retains its existing 100-page, four-MiB and 250,000-character limits. Analysis report
tables split at 1,000 rows and twenty columns; ordinary saved-answer PDFs retain their
1,000-row and twenty-column limit. Oversized answers are refused, never silently truncated. PNG is
bounded to sixteen million pixels, four series and supported bundled-font glyphs.
Large categorical images and unsupported glyphs receive a clear refusal with a
spreadsheet alternative. Two render operations per service instance bound concurrency;
cancellation waits for the running worker to finish before releasing its slot.

Scheduled outbound email, public links and external delivery integrations are not
introduced here. Downloads require an explicit user action, including after reopening
a saved report request. Whole-conversation PDFs and source-file bulk export are outside
this result-export contract.
