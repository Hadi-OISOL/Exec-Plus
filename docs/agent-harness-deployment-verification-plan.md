> **File use case:** Read-only release verification plan for the agent harness change.
> **What it does:** Separates local, hosted and VPS evidence and defines stop/rollback gates.

# Agent harness deployment verification plan

This plan does not authorize a release. Root owns configuration, migrations, image builds,
backups, activation, hosted calls and VPS access. Workstream C made no VPS or hosted-provider call.

## Evidence lanes

Keep these results separate:

1. **Offline scripted:** disposable PostgreSQL on `127.0.0.1:25432`, disposable MinIO on
   `127.0.0.1:29000`, scripted models and fictional data only.
2. **Hosted synthetic:** newly generated fictional accounts and files only, with the configured
   provider. Record actual model calls, provider-reported tokens, measured latency and verified
   cost when available. Unknown cost stays `null`.
3. **Private VPS:** health, compatibility, authorization, persistence, worker and rollback checks.
   A VPS pass is not customer-scale or public-production acceptance.

Never compare an offline score with a hosted score. The replay scorer rejects comparisons whose
corpus hash or mode differs. Retain initial failures and corrected rechecks as separate runs.

## Pre-integration checks

- Review Agent 1's fact-packet synthesis for exact numbers, confirmed units, filters, limitations,
  causal wording, evidence IDs, invalid selection, timeout and deterministic fallback.
- Review Agent 2's context and compound execution for actor/workspace/source/memory binding,
  topic-switch barriers, two-step limit, revocation between steps, source changes before
  publication, cancellation and no partial answer when either step fails.
- Keep all four feature flags off by default until root wires configuration and job serializers.
- Run the focused unit/integration tests, the fixed two-phase evaluation manifest, then the frozen
  full backend and frontend gates. Do not add overlapping focused counts to the full-suite count.

## Measured evaluation

Use `scripts/run_agent_harness_evaluation.py` with a task-owned adapter that exercises the merged
application. The adapter receives one synthetic case on standard input and returns normalized
intent, tool sequence, filters, values, evidence IDs, claim types, model-call count and verified
cost. It must not return raw prompts, raw replies, secrets or customer data.

Run the unchanged baseline and candidate against the same corpus bytes. Report:

- task and follow-up success rates;
- clarification quality and claim mismatches;
- exact tool sequence, filter, value, unit and evidence failures;
- model-call count, median/maximum wall latency and provider-verified cost;
- unavailable or unsupported cases as failures, never inferred passes.

Hosted evaluation starts only after offline gates pass and root explicitly coordinates the call.
It uses separate evidence directories and a fresh synthetic identity that is disabled afterward.

## Release gate

Before activation, root should verify the accepted commit, migration head, API/jobs/web image IDs,
restricted-image checks, backward-compatible flags, current table/object/config fingerprints,
maintenance lock and a readable checked backup. Stop if the backup, source manifest, image IDs,
schema transition, environment names or rollback target are uncertain.

The implemented flags are process-wide, not per-account. Validate all enabled paths first in
a disposable VPS API/worker with fresh PostgreSQL/object storage and fictional accounts.
Only then activate the exact tested images through the maintenance-lock release helper.
The release-owned nonsecret env file opts in; existing app.env overrides it. Verify readiness,
web, workers, loopback listeners, model/timers, saved-answer replay, permission denial,
exact evidence, saved reopen/export and deterministic fallback. Do not claim per-user rollout.

## Rollback conditions and method

Rollback on an authorization leak, stale-source publication, numeric/unit mismatch, missing
requested filter, partial compound publication, saved-answer incompatibility, worker backlog,
readiness failure or material error increase. First disable the new flags while retaining the compatible new reader images. After new
compound answers have been saved, an older reader can omit their second calculation and is
not a safe rollback. If health does not recover, stop affected writers and forward-repair the
compatible implementation. Returning to old code is permitted only before candidate writers
start and after proving unchanged stored state, as enforced by the activation helper.
Do not restore an older database over later saved work. Restore data only through the separately
approved recovery procedure after proving that a data rollback is required and safe.

After rollback, verify the same table/object/config fingerprints, old saved receipts, services,
listeners and synthetic permission denials. Preserve the failed run, logs with private content
excluded, exact deployed identities and the corrected recheck.
