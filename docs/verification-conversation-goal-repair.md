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
Hosted candidate verification, private activation and live synthetic checks pass; checked post-release backup and final operational verification pass. No UI/schema/dependency
or model-provider change, no push. Prior unrelated working files remain preserved.

## Hosted candidate

Checkpoint `ff1f27e`, release `0d6af5f7b68d02d3`; exact 1,040-file archive SHA-256
`d8165412e298532d9c5d5512b7b807af854eda3bd3f062960a62aa6603392ea5`.
Fresh VPS images and restricted computation checks pass. The unchanged frontend is
byte-compared with accepted `4345109`; its prior71 unit/23 browser evidence is reused,
not reported as a fresh frontend run. The current web production image build passes.

In disposable candidate PostgreSQL/object storage, the previous four hosted harness tasks
pass in33.166seconds, and all seven reported-style turns pass in30.879seconds. The sequence
uses forty fictional farm rows, repeated greetings, capabilities, ideal conditions before
and after a grouped calculation, and the exact full harvest-purpose wording from the user.
The comparator returns Harvest10/other30; irrigation means40/20mm and exact difference20.
Mean-by-stage values10/20/30/40 agree. Private replay and outsider denials pass. All created
accounts are disabled/revoked and owned containers removed. Root reads the synthetic replies.
The capability reply is a field-grounded explanation with executable suggestions; it is not
newly computed exploration or a claim of ideal crop interventions.

The first checker draft used invalid domain/grain values; source review caught this before
execution. The corrected fixture uses other/record, and offline checks now run actual API
request models and domain validation. The earlier mock-only checks did not prove valid API
payloads. That checker issue never changed application data. The checker also explicitly
accepts only the documented cohort replay route transition while preserving all other values.

## Active private release and live checks

Release `0d6af5f7b68d02d3` is active on unchanged schema0029 from runtime checkpoint
`ff1f27e`. Activation preserves all77 prior tables,185 stored files (3,985,284 bytes)
and configuration hashes. Checked pre-release backup: `20261018T191344Z` (UTC).

The running application's four legacy hosted checks pass in53.267seconds. The seven-turn
reported-style sequence passes in63.537seconds, including exact grouped calculations,
Harvest comparison, receipt reopening and outsider denials. This measures these synthetic
requests only, not universal language accuracy or production-scale performance.

Fresh live browser checks pass at1440/390/320 widths in both themes, including numerical
results, narrative evidence and the ideal-conditions clarification. The first mobile capture
was taken during the transition and above the answer; a fresh passing repeat waits for the
answer's opacity, scrolls it into view and asserts visibility. Root visually inspected the
settled320px dark capture. Both runs are retained. All six fictional live accounts across
the API and two browser runs are disabled and their sessions revoked. Existing user sessions
and saved answers are preserved; old immutable replies are not rewritten.

Evidence: `live-api.json`, `live-goals.json`, `live-browser.json`,
`live-browser-settled.json` and `activation-evidence/` under the private evidence directory.

## Scope and remaining limits

This is a focused repair, not a fresh full-repository regression or general-agent parity.
The exact full harvest clarification is tested; arbitrary short outcome continuations and
all paraphrases are not established. Comparisons describe observed differences and cannot
prove a crop intervention or a universally ideal recipe. Capability readings describe
available fields and possible exploration; they are not new computed findings. Existing
permission, source-freshness, unit and evidence boundaries remain. All64 feature IDs,
41 Done/17 Partial/6 Not yet statuses and eight external production gates remain unchanged.

## Checked completion

Post-release backup `20261018T191744Z` passes database/object SHA-256 checks, database
archive listing and object archive listing. `post-release.json` passes readiness/web,
all five services, six loopback listeners, model/timers, unchanged image identities,
configuration and schema0029 after backup. No database restore occurred. Original unrelated
working files are preserved. No push, public exposure, provider change or live connector call.
