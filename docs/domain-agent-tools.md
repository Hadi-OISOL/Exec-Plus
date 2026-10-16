> **File use case:** Defines the authorized domain-agent tool and guided-context enhancement.
> **What it does:** Turns the user's missed diagram/PDF requests into bounded registered actions with source evidence, private context and measurable acceptance.

# Domain agent tools

Status: implementation in progress, not deployed or accepted.
The October 16 user example asks for a diagram of how data converges and receives
a generic profile instead. The user authorizes better tool selection, remembered
preferences, simple upfront choices and PDF generation inside ExecPlus's domain.
This extends the repository/chart integration already undergoing release.

## Requested behavior

- A structural diagram request executes a registered dataset-map operation. The
  map uses the selected source, saved row meaning and fields grouped by actual
  roles. Edges show membership, not inferred causality, joins or statistical
  relationships. Confirmed and unreviewed meanings remain distinguishable.
- A named numerical visualization uses existing authorized query/chart tools.
  Ambiguous measures or unsupported causal/join requests ask useful bounded
  questions instead of silently returning a generic overview.
- A PDF request exports an eligible prior saved private answer. The report contains
  its exact returned values, saved explanation and source/receipt context. It does
  not rerun a model, invent missing data or execute arbitrary HTML, URLs or code.
  No previous eligible answer produces an explicit next step.
- Optional role, usual goal and explanation-style choices use explicit private
  memory. Back and Skip preserve user control; existing memory avoids repeated
  setup. These preferences never confirm dataset meanings or add query filters.
  Upload preferences must finish saving before the first reading begins; a failed
  optional save must not lose a successful upload.

## Implementation boundaries

The existing registered-tool, validated-plan, durable-job and owner-private thread
system remains the execution boundary. DeepSeek stays the configured planner;
there is no provider change or unrestricted agent shell. Diagram payloads are
validated, source-bound and immutable on reopening. Use the bundled ECharts tree
renderer and an exact accessible node list. Wide-source limits must be visible.

A narrow PDF rendering port uses a reviewed maintained library, with authenticated
private/no-store download responses and safely generated filenames. Render every
returned table row across pages, retaining exact strings and escaping user text.
Supported answer types, Unicode/font handling and limits must be explicit. This
bounded PDF slice does not imply every Phase 4D format is implemented.

New tools must preserve workspace and owner access, source freshness, accepted
refresh checks, old saved answers, cancellation/publication behavior and the
existing model budgets. New skill/tool material is reviewed and attributed before
use. Development skills are not automatically product runtime capabilities.

## Evidence required

Tests must cover the user's exact diagram wording, structural versus causal
meaning, named chart requests, ambiguous choices, private saved reopening, stale
sources and old-answer compatibility. PDF checks cover real bytes, page layout,
exact values, multi-page tables, hostile text, ownership denial, no prior answer
and the chat-to-download journey. Guided setup tests cover explicit save, skip,
back, existing memory and delayed/failed upload-context persistence.

Record actual failures and passing reruns. Build and activate only verified tracked
source under the maintenance lock, with checked backups and data/configuration
preservation. The current feature ledger and eight production gates retain their
status until evidence justifies a specific bounded update. No perfection or full
competitor-parity claim follows from a working synthetic example.
