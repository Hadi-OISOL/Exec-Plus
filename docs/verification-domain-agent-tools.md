> **File use case:** Records evidence for domain-agent routing, diagrams, PDF reports and guided preferences.
> **What it does:** Separates planned behavior, actual checks, retained failures and release identity.

# Domain-agent tools verification

Status: initial application `0d385b6` is deployed on unchanged schema 0018.
Its first live diagram check found a real saved-role mismatch. The v2 repair is
locally verified but pending deployment. Live tool verification and the final
release record remain incomplete; a fresh hosted reading also fell back safely.
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
Its local tests pass as stated above; deployment and live confirmation are pending.

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

## Remaining verification and limits

Pending: final repair builds and activation; gated live v2/v1, chart, PDF,
privacy/source/memory and responsive-browser checks; the follow-up hosted probe;
checked final post-release backup; final handoff/report updates. Do not describe
pending work as passed.

Maps show declared file membership, not causal effects or joins. PDFs currently
support saved calculations/tables and source-backed explanations, not diagram or
chart images, pattern/forecast/scenario reports or whole conversations. Personal
setup is optional and explicit; it does not learn silently from every message or
change numerical filters. The fictional-source checks are functional evidence,
not representative acceptance, sustained-load evidence or full competitor parity.
The existing feature ledger and eight blocked production gates are unchanged.

Private evidence is retained under
`data/verification/2026-10-16/domain-agent-tools/` and the sibling
`domain-agent-*.log` / `domain-agent-v2-*.log` files. Tokens, browser profiles,
generated PDFs and detailed source records remain ignored and uncommitted.
