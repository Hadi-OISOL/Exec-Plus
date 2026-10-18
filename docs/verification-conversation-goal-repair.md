# Conversation goal repair — 19 October 2026

The user supplied a conversation where greetings, a capabilities question and a request
for perfect crop conditions repeated the same next-step menu. A later response offered
eleven unrelated input maxima, and a harvest comparison was refused as an extra filter.

Source reproduction shows three distinct problems: accepted `overview/next_steps` always
rendered static guidance; ideal conditions lacked an outcome question; and the cohort
scope guard treated the purpose phrase “in order to” as a restriction. Prior numerical
context contamination is not established by this transcript.

## Changes and local evidence

- Simple greetings use a brief, source-bound response without a model call. Capability
  questions and model-selected next steps use the existing validated qualitative reading
  when enabled; metadata, saved meanings and private-access checks remain authoritative.
- Ideal/perfect/optimal/best conditions ask which outcome matters before offering an input
  maximum or calculating. This is a bounded objective clarification, not automatic discovery
  of ideal interventions. The prompt requests at most three meaningful clarification choices.
- The cohort guard removes only the complete purpose phrase, retaining subsequent actual
  time, region, exclusion and numeric restrictions. The exact transcript computes a real
  governed comparison in synthetic integration tests.
- New-task reset also clears prior_result defensively. This is not claimed as the observed
  cause of the reported menu loop.

Focused tests pass34 cases; broader guidance/reading/context/cohort/router regression passes
156 cases. A later78-case supplement includes the new calculate-ideal goal case, actual
Harvest conversation and context regressions. These counts overlap. Full source mypy269 and
Ruff pass. Initial missing-test-filename and assertion-contract failures are retained.
Synthetic fixtures preserve exact means, counts, saved source definitions, receipt reopening
and private access. Cohort reopening's pre-existing model-route attribution difference is
explicitly checked; all substantive saved result/evidence fields agree.

Private evidence: `data/verification/2026-10-19/conversation-goal-repair/`.
Hosted candidate verification and private activation are pending. No UI/schema/dependency
or model-provider change, no push. Prior unrelated working files remain preserved.
