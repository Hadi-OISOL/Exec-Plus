> **File use case:** Records evidence for domain-agent routing, diagrams, PDF reports and guided preferences.
> **What it does:** Separates planned behavior, actual checks, retained failures and release identity.

# Domain-agent tools verification

Status: implementation and verification in progress. The deployed baseline is
`7b46db2` on schema 0018; this next slice is not deployed yet.
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
85 reading cases in 21.46 seconds. The next full suite and hosted probe remain
pending; this does not resolve the deployed fallback by itself.

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

All **53 frontend unit tests**, types and lint pass. Eight affected browser journeys
pass in 52.7 seconds; a final diagram/PDF journey passes in 15.6 seconds after the
diagram-opening scroll fix. Root inspects desktop/mobile field maps, optional
preference review and rendered PDF pages. These focused results are separate from
the currently running full suites.

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

Pending: full backend/browser results; final production/restricted-image builds;
gated live tool/routing/privacy/source checks; backup and schema/configuration
preservation; final handoff/report updates. Do not describe pending work as passed.
