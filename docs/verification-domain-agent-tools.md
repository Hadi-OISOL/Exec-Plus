> **File use case:** Records evidence for domain-agent routing, diagrams, PDF reports and guided preferences.
> **What it does:** Separates planned behavior, actual checks, retained failures and release identity.

# Domain-agent tools verification

Status: final application `919dd0a` is deployed on unchanged schema 0018.
Live API checks pass for v2 saved roles, immutable v1 replay, PDFs, a fresh named
chart and a fresh hosted explanation. Final responsive browser checks and the
checked post-release backup pass. Initial failures remain below.
See [the bounded contract](domain-agent-tools.md).

## Starting evidence and retained failures

The user supplied a real failed experience: a structural diagram request returned
a generic file description. The runtime lacked a diagram answer/tool branch and
an export action. Existing private memory required visiting a separate editor;
upload context could be saved after the first reading had already started.

The preceding chart release's first hosted retail-reading probe returned saved
guidance with `invalid_response`. The exact failed validation rule was not recorded;
no raw model prose or private prompt was retained. This slice adds fixed typed
validation codes and corresponding correction hints, retaining the same two-call,
forty-second limits and no replay of rejected content. The initial targeted run
passes 81 and fails four assertions that expected only one safe diagnostic line.
Assertions are updated to require both fixed reason and fixed issue lines while
continuing to reject private exception content. The corrected focused run passes
85 reading cases in 21.46 seconds. These diagnostic changes alone do not resolve
the deployed fallback; the later live result is recorded below.

PDF setup initially cannot run pip because the project venv has no pip executable;
the existing project uv installation installs the reviewed packages successfully.
This is a tooling failure, not a passing application check. Exact dependencies,
licenses, supported answer types and rendering bounds belong in the PDF contract.

## Acceptance and release

Focused diagram/report/plan/conversation checks pass 93 cases, followed by 28
scope/paraphrase rechecks containing two additional cases: **95 distinct**. These
cover the exact reported wording, unknown fields, row restrictions, reserved field
names, clarification continuation, model subset mismatch and all-field requests.
The PDF group passes **36 cases** in 13.26 seconds, including real extraction,
pagination, Unicode, exact values, limits, private access, source races and
cancellation. ReportLab's shared font state requires serialized builds; concurrent
distinct-document extraction verifies that repair. The five architecture checks
also pass. The independent fixed reading-correction group above passes 85 cases.

The full backend/architecture run passes **1,448 tests** in 575.37 seconds with one
retained warning. Ruff and mypy pass, with 190 source files checked by mypy. The
complete offline browser run passes **59 journeys**, with **three explicit
model-dependent skips** and zero failures in 8.2 minutes. Skipped journeys are not
passes and this run does not establish hosted-model quality.

Before the v2 repair, all 53 frontend unit tests, types and lint pass. Eight affected
browser journeys pass in 52.7 seconds; a final diagram/PDF journey passes in 15.6
seconds after the diagram-opening scroll fix. Desktop/mobile field maps, optional
preference review and rendered PDF pages are visually inspected. The local
production build passes. The restricted candidate image checks pass a source
diagram, four concurrent PDF renders, exact text and unsupported-glyph refusal,
plus eight ordinary computations/forecasts, eight pattern/daily computations and
48 grouped/allocation computations. These results describe the initial candidate,
not an unbuilt later repair.

After the live role failure, **104 focused backend tests** pass in 28.967 seconds.
They cover exact saved identifier/ordinal/ignored roles, role-based subsets,
unconfirmed fields, unchanged v1 graph/model-route replay, private reports and
existing plan/conversation behavior. The final frontend run passes **54 unit
tests**, types and lint. The focused diagram/PDF browser journey passes in 15.7
seconds, including desktop/390/320 resizing, exact field inspection, current-map
labels, explicit PDF download and saved reopening without automatic downloads.
These overlapping focused runs are reported separately; their counts are not
added to the earlier full suite as if all were distinct new tests.

Retained initial failures include a ReportLab page-limit exception converted to
a server error (fixed), incorrect audit/membership test expectations, obsolete
browser selectors, an ECharts tree transition crash when replacing its root on
resize (fixed with a bounded tree reset), and an SSR-only fixture attempting
browser resize after clear (corrected; real browser resizing passes). The first
diagram captures showed only the bottom of the answer; the final scroll assertion
and new chart captures verify its heading opens first. An unsorted root import is
fixed. A broad format probe also finds nine pre-existing unrelated formatting
differences; only the three new PDF files are formatted, and no whole-repository
format-pass claim is made.

## Initial deployment and observed live failures

Application `0d385b6` was activated after checked backup `20261016T092501Z`.
The database/object archives pass checksums, and services restart. Activation
preserves table fingerprints, migration metadata and the environment checksum;
readiness passes on schema 0018. These checks do not replace final post-release
backup or successful application journeys.

The first live diagram request returns a real diagram, but its exact metadata
assertion fails: the fictional retail source's saved `Record_ID` role is
`identifier`, while v1 returns `dimension`. This is an application defect, not a
selector or fixture error. Source profile, meanings, revisions and private memory
remain unchanged. The browser verifier does not run against the failed API gate.
The original failed answer and summary remain in the private evidence directory.

The repair introduces `dataset-structure-v2` for saved roles and matching role
subsets. Existing v1 results remain immutable and use the legacy reconstruction.
The UI gives v1 an explicit earlier-analysis-role notice; v2 uses “Saved role.”
Its local tests pass as stated above; the repaired live result is recorded below.

A separate hosted retail-reading probe on `0d385b6` is **not accepted**: fixed
diagnostics identify `prose_evidence`, and the saved reply uses deterministic
guidance after `invalid_response`. A fresh exact calculation still succeeds,
old receipt/reading evidence reopens unchanged, six private denials pass, and
source/memory preservation passes. The final prompt patch requires short single-line prose and keeps exact field
identifiers in structured fields. The same rejection checks now report fixed
number/link/markup/control subtypes, without recording rejected content. Its
reading/private-memory group passes 84 tests in 22.438 seconds, including 30 new
subtype, privacy and correction checks. The final full Ruff/mypy (190 files),
web production build and types pass. The old failure's subtype remains unknown;
a new hosted-reading probe is still required.

## Repaired application and live API evidence

Application `5372e95` is built from committed source. Final local/VPS builds and
restricted network-disabled, read-only, non-root image checks pass, including the
diagram, four concurrent PDFs, unsupported-glyph refusal and earlier numerical
methods. Checked pre-release backup `20261016T094035Z` verifies database/object
archive checksums. Activation uses the maintenance lock and preserves all **48**
table fingerprints and the environment checksum. No migration is performed.
Checkpoint: `pre-integration-5372e95-20261016`.

The gated live API run passes in 93 seconds on existing fictional data:

- The user's exact wording selects a v2 map with all thirteen fields and exact
  saved roles, meanings, units and source metadata.
- The complete original v1 answer reopens unchanged. Canonical UTF-8 JSON bytes
  are compared, not original HTTP whitespace. The v2 answer also reopens exactly.
- Three protected PDFs retain the exact numeric string `8235156.600000000000`,
  source/receipt evidence and the saved qualitative explanation. The report action
  reopens exactly. Diagram-PDF requests explicitly clarify the unsupported target.
- Twenty private-access denials pass, together with authorized controls and the
  durable diagram/report tool plans.
- One fresh hosted named revenue-by-region chart succeeds on its first request
  and matches all three exact governed comparison rows.
- Source bytes, profiles, definitions, revisions and private memories are unchanged.

The separate hosted retail-reading probe succeeds in twenty seconds with two
valid metric suggestions. A fresh exact total equals `8235156.60`; old receipt
and reading evidence remain unchanged; six private denials and source/memory
checks pass. This is one observed successful explanation after the prompt patch,
not a guarantee of future model output or representative quality acceptance.
The earlier `invalid_response`/`prose_evidence` failures remain retained.

The real reported user's five source artifacts also match their latest baseline.
Runtime checks show five running containers with zero recorded restarts, healthy
readiness, workspace HTTP 200, unchanged model/timers and six loopback listeners.

## Browser verification and final clarification-button repair

The initial chart-compatibility run passed two journeys and thirty layouts before
a saved-answer GET hit `ECONNRESET`. No page errors, prohibited writes, source
changes, container restarts or OOM were observed. The helper now permits one
recorded retry only for an idempotent GET with that transport failure; HTTP errors
and other failures are not retried. Five helper checks verify that boundary.
The next full run passes three journeys and 36 layouts in **45.884 seconds**, with
zero page errors and **zero retries actually needed**. The earlier failure is
retained and its root cause is not established.

The first domain browser attempt stops because it assumes every historical turn
has an answer to load. The deliberately unsupported diagram-PDF clarification
has no answer, but the UI still shows a no-op Load saved answer button. This is
both a harness assumption and a confusing product action. A corrected verifier
loads only real saved answers; five deployed journeys and **21 layouts** pass in
**63.822 seconds**, including every field inspector, the earlier v1 notice,
exact current roles, two explicit PDF downloads, no automatic downloads, the fresh
chart and existing private preferences. There are no page errors or prohibited
writes; source and memory fingerprints match. Desktop/mobile captures and the
first deployed PDF page are visually inspected.

A final narrow UI repair retains each saved turn's kind, hides load actions for
clarifications/refusals, and records successful null reads without leaving a
no-op button. Failed reads remain retryable. The patch at `919dd0a` passes all
54 frontend tests, types, lint, a fresh production build and the focused browser
journey in **18.3 seconds**. That journey covers fresh/reopened clarifications,
real saved maps/reports, a failed GET followed by successful retry, and a
successful null response. API, dependency, deployment and migration source are
byte-identical to `5372e95`; no new hosted-model result is claimed for this UI-only
change. Checked backup `20261016T095238Z` preserves the live 5372e95 work and
serves as the pre-update backup. Candidate images and all restricted-image
checks pass. `919dd0a` is activated under the maintenance lock with all 48
fingerprints/configuration preserved on 0018. Checkpoint:
`pre-integration-919dd0a-20261016`.

The final read-only browser run against `919dd0a` explicitly reuses retained
`5372e95` fixtures. It passes **five journeys / 21 layouts in 61.707 seconds**,
including the removed clarification load action, every field inspector, unchanged
v1 history, exact saved charts and two explicit PDF downloads. There are zero
page errors, automatic downloads or prohibited writes; source and memory
fingerprints remain unchanged. This run makes no new hosted-model requests.
Checked final backup **`20261016T095854Z`** passes database/object archive
checksums and restarts services normally. This preserves the new saved work,
not just the pre-release snapshot. It is archive integrity evidence, not a
latest-version restore or off-server disaster-recovery drill. Preserve all new
saved work on rollback; no database restore or downgrade was performed.

## Limits

Maps show declared file membership, not causal effects or joins. PDFs currently
support saved calculations/tables and source-backed explanations, not diagram or
chart images, pattern/forecast/scenario reports or whole conversations. Personal
setup is optional and explicit; it does not learn silently from every message or
change numerical filters. The fictional-source checks are functional evidence,
not representative acceptance, sustained-load evidence or full competitor parity.
ID 13 becomes Partial for this PDF slice: **37 Done / 17 Partial / 10 Not yet**,
with all 64 original IDs preserved. All eight production gates remain blocked.

Private evidence is retained under
`data/verification/2026-10-16/domain-agent-tools/` and the sibling
`domain-agent-*.log` / `domain-agent-v2-*.log` files. Tokens, browser profiles,
generated PDFs and detailed source records remain ignored and uncommitted.
