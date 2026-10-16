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

Pending: focused/full backend checks; frontend types/lint/unit/browser tests;
actual diagram/PDF visual inspection; production/restricted-image builds; gated
live tool/routing/privacy/source checks; backup and schema/configuration
preservation; final handoff/report updates. Do not describe pending work as passed.
