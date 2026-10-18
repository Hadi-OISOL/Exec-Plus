# Conversational replies and responsive activity — 19 October 2026

## Request and observed cause

The user reported that a casual check-in received a dataset explanation, asked for animated
request progress, and reported dark-theme and mobile layout problems. They explicitly
rejected a hardcoded answer to one phrase. Read-only inspection of their authorized recent
thread confirms “hey how are you” was recorded as overview; no user source data was modified.
Private questions/replies are retained only in ignored evidence, never general application logs.

## Implementation

The existing hosted planner can select a conversational overview focus and write a short
plain reply. Model-enabled greetings/acknowledgements use that route rather than a fixed
phrase response. Mixed social/data requests retain analytical intent checks and existing tools.
The prompt distinguishes social conversation from dataset meaning and analysis; no new
provider, independent agent framework or additional model call is introduced. Social replies
retain private ownership/reopening guards but are not presented/exported as verified analysis.

This bounded social contract is at most400 characters and excludes numeric claims, markup
and links. It is not unrestricted general chat. Prompt instructions are not a proof of semantic
truth, and unseen phrasing requires hosted evaluation; offline fakes establish the contracts.
A disabled-interpretation greeting fallback remains for that existing offline configuration.

Request progress uses a decorative animated orbit and actual server stage labels, with
plain-language explanations, cancellation status and a reduced-motion alternative. There
are no invented percentages, fabricated tool steps or displayed private model reasoning.
Recorded actions remain inspectable. Sending is distinct from server acceptance/processing.

Dark-mode borders/selected surfaces and forecast legend colors are corrected. Reply cards,
semantic accents and result hierarchy use existing application content; no synthetic insights
are added. Mobile conversation flows with the document rather than a cramped nested viewport;
exact result tables retain their scrollable region. No new dependency or schema migration.

## Verification

In progress. Evidence lives in `data/verification/2026-10-19/conversation-experience/` and
`data/verification/2026-10-19/conversation-appearance/`. Deployment acceptance is not yet claimed.

### Review and local checks

The independent review found that plain text alone did not enforce the social prompt's
no-claims rule. A conservative generic guard now refuses visible-field claims, pretend
save/compute actions and explicit private-goal/notes disclosure. The demonstrated saved
preferences and confidential goal payloads are rejected. An invented claim about an absent
field can still evade these heuristics (for example, revenue doubling when revenue is not
in the schema). This is an explicit residual limitation, not verified factual prose or a
claim that all possible unsupported statements are caught. Social replies carry no verified
analysis badge/evidence decoration and cannot export as analytical reports.

Local backend:110 broader cases pass, final31 social cases pass; overlapping earlier42-case
run had41 passes and one incorrect assertion that a completed refusal could not have status
complete. Corrected assertion checks the unsupported kind, no answer and safe validation
message; runtime was unchanged. Ruff and mypy269 pass. Frontend72 unit tests, types and lint
pass. The checker smoke test initially used system Python without httpx; the project venv
passes valid ten-case scoring and rejects a changed mixed-request calculation.

Final local browser run:13 passed, one explicitly model-dependent continuation skipped,
in1.5minutes. It includes real app sending-before-acceptance, cancellation, recovery and
reduced-motion checks, overview/theme behavior and synthetic actual-CSS contrast/keyboard
scroll checks at320/390/768/1024/1440 in both themes. Three initial test assertion failures
(End key used for horizontal scrolling twice, stale pending wrapper selector once) are
retained; corrected final rerun passes. Runtime source was unchanged. Root inspected real
app dark320 progress and completed reply captures. This is not an all-device guarantee.

Candidate runtime checkpoint `07c7b47`, immutable content release `9ce1f703b13b957f`:
1,045 files, archive SHA-256
`4194ac61ab8f885f141dafb1e361f18ed0f21f677b0c2dd634d7322d3c0903ad`.
Later test-only assertion/cancellation supplements do not change runtime bytes.
