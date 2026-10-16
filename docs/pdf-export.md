> **File use case:** Defines the first bounded saved-answer PDF tool.
> **What it does:** Records exact content, privacy, rendering limits, dependencies and verification boundaries.

# Saved-answer PDF export

This slice adds an actual PDF download for a completed private conversation answer.
It supports saved calculations, result tables and source-backed data explanations.
Use **Download PDF** on an eligible answer, or ask **“Make a PDF of this answer.”**
The chat response offers a download button; reopening that response does not
start a download automatically.

The export is an existing answer with its evidence, not a new analysis. It does
not close the broader Phase 4D dashboard/report, Excel, CSV or PNG export scope.
Charts are represented by their exact returned table, not by a chart image.
Patterns, document answers, diagrams, forecasts/scenarios/allocations and entire
conversations or source datasets are not supported report targets in this slice.
Unsupported requests receive an explanation rather than an unrelated older answer.

## Content and reproducibility

A numeric export includes the original question and save time, every returned
row, exact strings/decimal values, operation, groups, filters, executed SQL,
complete execution receipt, source identifiers/checksums, recorded business
definitions/units and generation-time freshness relative to recorded revisions.
A qualitative export includes the saved explanation and suggestions, clearly
marked as fallible interpretation/questions rather than calculated results,
plus its recorded source/definition evidence. No model is called for export.

Existing replay checks verify the retained source bytes and the executed numeric
answer. The exporter does not generate a new plan, write a new query receipt,
replace a saved reply or read the latest data as a substitute for old evidence.
A saved answer can still export as a **Historical source snapshot** after a newer
meaning or source exists. Its PDF retains the earlier definitions; it never
claims freshness beyond the imported file.

Missing cells are displayed as `Missing (null)`, separately from zero. The
execution receipt retains typed numeric/table evidence. Category whitespace is
preserved; layout may introduce line/page breaks. Wide tables use successive
bands of up to five data columns with the same original row numbers. Every table
page repeats headers. No rows or columns are silently omitted to fit a page.

## Protected API and saved action

`GET /workspaces/{workspace_id}/threads/{thread_id}/turns/{turn_id}/export.pdf`
returns `application/pdf`, `Content-Disposition: attachment` with a UUID-based
filename, `Cache-Control: no-store`, and `X-Content-Type-Options: nosniff`.
The authenticated response exposes the filename header through the existing CORS
boundary. Tokens are never placed in download URLs.

A chat report uses this typed reference:

```json
{
  "kind": "report",
  "report": {
    "thread_id": "existing-conversation-id",
    "turn_id": "existing-answer-id",
    "label": "Download this saved answer as PDF",
    "format": "pdf",
    "download_url": "/workspaces/.../threads/.../turns/.../export.pdf"
  }
}
```

The existing private conversation evidence stores that descriptor. It does not
store a PDF blob or a public object URL. Reopening it reauthorizes the referenced
source answer. Natural requests such as “I want a PDF of this answer,” “Can I get
a PDF?” and “export as PDF” select the latest completed real answer in the same
thread. A previous PDF action resolves to its original target. Requests for the
first/all answers, different scope, exclusions or added content clarify instead.

The exporter checks membership, private thread ownership, saved answer identity,
source/receipt integrity and current metadata before rendering and again before
delivery. A source/definition change or revoked access during rendering discards
the bytes. Workspace owners/admins cannot export a teammate's private answer.
Successful generation records actor-private `pdf.exported` audit metadata;
shared/manager audit allowlists do not expose that event. A downloaded copy cannot
be recalled or access-revoked once the user has it.

Errors preserve the existing `401`/private `404`/integrity `409` behavior.
`pdf_export_unsupported`, `pdf_export_scope`, `pdf_export_text` and
`pdf_export_limit` are explicit `422` refusals; an incomplete answer is
`409 pdf_export_unavailable`; occupied renderer capacity is `429 pdf_export_busy`.

## Rendering boundary

- At most **1,000 returned rows**, **20 columns**, **250,000 characters** across
  content/evidence, **100 pages** and **4 MiB** of output. These independent caps
  may reject an answer below the row cap when its evidence is large.
- Two admitted rendering requests per API process; the font-dependent build
  runs under a process-local lock because ReportLab forbids sharing one TTFont
  object across simultaneous documents. Cancellation drains the renderer before
  releasing its slot. This is a resource bound, not sustained-load acceptance.
- Pinned ReportLab constructs text/tables from immutable typed content in memory.
  User/model text is escaped before Paragraph parsing. No arbitrary HTML,
  JavaScript, shell, upstream skill script, file path or remote resource is accepted.
- The packaged Manrope font is embedded offline. Tested text includes accented
  Latin, Greek, Cyrillic and the euro sign. Every character is checked against
  the font; unsupported writing systems, emoji and unsafe control characters
  receive an explicit refusal instead of tofu or silent replacement. This is
  not universal Unicode/complex-script shaping support or PDF/UA certification.

## Research and dependencies

[ReportLab 5.0.1](https://pypi.org/project/reportlab/5.0.1/) is the actual runtime
library, pinned after checking its BSD terms and Python compatibility (>=3.9,<4).
The verified wheel SHA-256 is
`1c36e6bb0e71780c72331eba60da7f602e8d4389a8723825af71342e49d791e8`.
Local resolution uses Pillow 12.3.0 and charset-normalizer 3.5.2. Their license
texts are shipped alongside ReportLab's; no optional browser, bidi, shaping or
remote rendering extra was installed. The font and SIL OFL are copied unchanged
from ExecPlus's existing Manrope asset; its checksum is in the adapter assets
README. `pypdf==6.20.1` is a development-only independent PDF text extractor.

The public [Anthropic PDF skill](https://github.com/anthropics/skills/blob/main/skills/pdf/SKILL.md)
was inspected as workflow guidance; its proprietary skill licensing is not an
application-code license. It was not copied or installed. The pinned AIpoch
`scientific-skills/Other/html-to-pdf/SKILL.md` was inspected locally: its Puppeteer
HTML/URL execution surface is unnecessary for this tool, so it was not executed
or embedded. [fpdf2](https://github.com/py-pdf/fpdf2) was evaluated as an alternative;
ReportLab's BSD library and explicit table pagination were selected. These
references do not make an unrestricted PDF skill available inside the application.
The actual runtime tool is the protected descriptor/download service described here.

## Verification ledger

The final PDF-specific group passes **36 tests** in 13.26 seconds in the final concurrency recheck; the five
architecture checks and targeted Ruff/mypy (six source files) also pass. A built
wheel includes the adapter, font and OFL license. Targeted local tests cover real PDF extraction, 1,000-row pagination and repeated
headers, all twenty columns, long split cells, exact large decimal strings,
zero/missing distinction, whitespace, supported Unicode, unsupported glyphs,
literal hostile markup without link annotations, and text/page/byte refusals.
Real PostgreSQL/object-storage tests cover exact scalar/grouped replay, source
and definition preservation, historical qualitative content, creator-only access,
owner/admin/outsider denials, revoked membership, private export audit events,
source corruption, source/access changes during rendering, cancellation slots,
and concurrent distinct-document font/text isolation.
Conversation tests independently cover the durable PDF tool plan, references,
reopening and unsupported-target clarification.

Initial failures remain under ignored
`data/verification/2026-10-16/domain-agent-tools/`. The first dependency command
found no pip in the project venv; project uv installation succeeded. The first
page-limit test exposed ReportLab's exception rewriting and was repaired with an
internal exception translated to the normal 422. Initial test-only route/status
expectations were corrected to the existing `audit-history`, private 404 and
`lineage_mismatch` contracts. Generated fictional PDF pages were rendered through
Poppler and inspected visually; generated exports are not committed.

Application `919dd0a` is deployed on unchanged schema 0018. Three real protected
downloads pass exact-value, saved qualitative text, receipt and private-access
checks. The first page of a deployed numeric PDF is rendered and visually
inspected. The [combined release ledger](verification-domain-agent-tools.md)
records browser checks, preserved data, earlier failures and backups. Broader
export formats and production gates remain open.
