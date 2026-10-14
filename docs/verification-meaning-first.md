> **File use case:** Records verification of the meaning-first agent and Home enhancement.
> **What it does:** Distinguishes model interpretation, deterministic evidence and release checks.

# Meaning-first verification — October 14

## Scope and reference

This follows the deployed `d40bc6d` context repair. The user requested a useful
explanation of what their file means, reuse of saved answers, earlier clarification
of unknown details and improvements to existing agent/dashboard presentation.
[Contracts](meaning-first-reading.md) define the bounded change. REA inspected
public ThoughtSpot documentation examples; [the audit](meaning-first-reference-audit.md)
separates those observations from vendor descriptions and unknown private behavior.

## Local evidence

- Ninety-three selected backend/architecture cases pass across dataset reading,
  saved context, guidance, unified conversation and conversational exploration.
  Nine new reading cases also pass a final focused recheck. Existing exact-query
  and private-history regressions remain in that selection; no new calculation
  method was added. The preceding context repair's full-suite evidence remains
  separately recorded as 1,060 distinct cases across its full and final runs.
- The new cases cover saved descriptions/notes/goals, cross-user exclusion,
  immutable reopening, missing-unit questions, no query execution during reading,
  invalid fields/numeric prose/provider failure and a context change during a call.
  Initial targeted execution had one test-harness failure: a synchronous test
  client was called from its event loop. Moving that simulated concurrent change
  to a worker thread fixed the harness; the final race regression passes.
- Ruff and mypy (163 files), 22 frontend unit tests, TypeScript, ESLint and the
  production web build pass. Four distinct real-service browser journeys pass,
  plus focused completed-answer and pending-follow-up scroll rechecks. The first
  new Home test found that Review opened the preparation page rather than the
  definitions editor; wiring the existing review callback corrected it.
- The presentation browser case explicitly substitutes answer text to test
  section rendering, escaped source text, keyboard disclosure and 1440/390/320
  layouts without browser errors. It is presentation evidence, not model-quality
  evidence. Hosted interpretation is checked separately after release.

## Interpretation limits

The structured validator checks shape, bounds, field references and prohibited
numeric/markup/link output. It does not prove qualitative semantic correctness.
The model sees saved metadata and authorized reading notes, not raw rows in this
path, and receives no task to calculate a business value. A reading has no verified
calculation badge. No representative accuracy or latency benchmark is claimed.

The earlier generic twenty-column hosted-reading fallback remains in
[context repair verification](verification-context-reuse.md). It is a separate
onboarding-model quality limitation, not erased by these explanation tests.
Production gates and all 64 feature statuses remain unchanged.

## Private release

Application **e663a50** is deployed to the private VPS on unchanged migration
**0017**. Candidate API/web builds and clean non-root, read-only, network-disabled
computation checks pass. Source/images checkpoint: `pre-e663a50-20261014`.
All 47 control-plane fingerprint entries and the environment checksum are unchanged
across activation. Pre-release backup `20261014T121820Z` and post-release backup
`20261014T122102Z` pass database/object checksums. This is archive integrity, not a
restore rehearsal. API/jobs/web have zero recorded restarts; readiness/workspace
return 200, model/refresh/backup remain active and all six listeners stay loopback.

Two live hosted-model checks pass on their first attempt: fictional dated source
in 29.3 seconds and the reported agricultural source in 29.7 seconds, 60.0 seconds
total including browser work. Both use `dataset-reading-v1`, include saved meanings
and accessible notes, retain exact private API/UI reopening, and pass accessible
context details plus 1440/390/320 layouts with zero page errors. Profiles,
definitions and revisions match their pre-test snapshots. No user answer was changed.

The farm interpretation identifies agricultural conditions and groups soil,
weather, crop and irrigation fields. It proposes average rainfall by region,
asks for the missing soil-moisture unit and explicitly explains that dates are
absent. These are suggestions, not calculated findings. Its general agronomic
“affect/influence” wording and generic “field record” paraphrase illustrate the
semantic limit: neither establishes a measured causal effect or a more specific
confirmed row grain. Context disclosure marks the output as AI interpretation.
Representative semantic accuracy remains an open production requirement.

Evidence remains ignored under `data/verification/2026-10-14/meaning-first/`.
Application commit `e663a50` was pushed to personal `phase2`; later handoff/report
commits do not imply a different deployed application. Feature counts remain
37 Done / 16 Partial / 11 Not yet, all eight production gates remain blocked,
and no provider, network exposure or database schema changed.

The maintained feature audit and October 14 Desktop DOCX were updated together,
retaining all 64 original IDs, unchanged status counts and the original competitor
comparison date. Previous report copies are preserved by the report builder.
