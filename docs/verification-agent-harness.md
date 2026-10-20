# Agent harness verification — October 18, 2026

Private release **`831c6e06a8b55bdb`** is active on unchanged schema **`0029`**. The local acceptance gate, restricted image checks, isolated canary and four-task hosted API check pass. Live browser and checked post-release backup verification also pass. This is bounded private-demo acceptance, not production certification.

## Scope and evidence

- Candidate source checkpoint: `5247867`; accepted test checkpoint: `577d183`.
- Private evidence: `data/verification/2026-10-18/agent-harness/`.
- Tests used isolated PostgreSQL and object storage. Hosted checks used new fictional accounts, then disabled the accounts and revoked their sessions.
- The hosted sample contains four fixed tasks. It measures those tasks only and is not representative model-quality, cost or performance evidence.
- Provider configuration was not changed. Numerical results, receipts and access decisions remain server-authoritative; the model can only select and order verified narrative statements.

## Baseline retained before implementation

- Root source `6bca30e` stayed unchanged during baseline execution.
- Full backend baseline: **3,008 passed / 1 failed** in 2,105.69 seconds. The failure was a stale capability assertion that omitted the already implemented `compare_cohort` operation.
- Existing offline evaluation: **111/112 passed**, with the same stale capability assertion retained.
- Frontend baseline: **63/63 passed** in 2.210 seconds.
- Hosted baseline on release `c34536b8540f7c6d`: **2/4 task checks passed** in 51.268 seconds. Exact total and tied extrema passed; the verified follow-up lost prior calculation context and the compound request was incomplete. Synthesis was disabled.
- The checked pre-task runtime backup `20261018T030005Z` passed archive and checksum inspection. It was not restored.

## Final local candidate evidence

| Gate | Result | Practical limit |
| --- | --- | --- |
| Backend primary run | 3,153 passed / 1 failed in 2,098.56 seconds | The one old prompt-label assertion failed; its behavior assertions passed. |
| Latest backend reconciliation | **3,168 distinct nodes passed**, zero unresolved | Uses the complete primary run plus 83 final, 6 polling and 15 partner-file supplemental cases. This is not one clean run at the final source checkpoint. |
| Original requirement map | **37/37 passed** | Test coverage for the retained original requirement map, not external acceptance. |
| Frontend | **69/69 passed** in 4.336 seconds | Different count from baseline; runtimes are not a product performance comparison. |
| Offline browser | **111 passed / 3 explicit model skips** in 18.7 minutes | Web source was identical from `da18eb9` to `5247867`. |
| Static/build | Ruff passed; mypy passed for 266 source files; frontend types, lint and production build passed | Local source checks only. |
| Restricted images | Exact archive, manifest, build and restricted computation checks passed | Does not by itself verify activation. |

The retained primary-run failure was
`test_model_guidance_handles_natural_and_roman_urdu_phrasing_without_saving_meaning`.
The implementation intentionally says “Interpret ordinary English”; all behavioral assertions passed. The assertion was updated to that English-only contract and all **15/15** cases in the file passed on recheck. The original failure remains in the primary log.

Focused coverage includes verified narrative packet validation and fallback, bounded two-query compound answers, exact receipt replay, private follow-up context, source/access/memory invalidation, English resolution, compound PDF/Excel/CSV exports, cancellation and tamper refusal. The real export test replays both receipts and checks private denial without replanning.

## Before and after runtime evidence

| Measurement | Before | After | Interpretation |
| --- | --- | --- | --- |
| Three disposable scripted API/runtime cases | 0/3 in 7.540 s | 3/3 in 8.284 s | Measures harness execution, replay and document ranking with scripted planner replies; not language quality. |
| Four hosted private-demo tasks | **2/4** in 51.268 s | **4/4** in 52.567 s | Same fixed corpus and synthetic-account scope. Elapsed times do not establish a speed improvement. |
| Hosted narrative selection | Disabled | **4 selected / 0 fallback** | Every after-case diagnostic records `mode=selected`, `reason=selected`, route `hosted:deepseek-v4-pro`. |

The final hosted-after diagnostic contains seven provider attempts for the four allowlisted turns: **12,175 input tokens**, **425 output tokens** and **11,776 cached input tokens**. Every accounting state is `unknown`; the evidence does not establish provider billing or cost. The before diagnostic recorded 13,743 input, 488 output and 9,472 cached input tokens, but synthesis was disabled, so token totals are not a like-for-like efficiency comparison.

A separate three-question selector probe answered **3/3** in both modes. Direct planning took 4.599 seconds and planning with the local selector took 11.921 seconds; main-provider input/output totals were 4,949/194 and 5,004/194. Local-selector tokens were not collected. This small synthetic result supports only the bounded context-path bypass that was tested.

## Isolated canaries and activation

- Intermediate candidate `1012483d25f43fa9` answered all four tasks correctly in 37.655 seconds, but all four narratives fell back. Its **0 selected / 4 fallback** result failed the stronger canary gate and remains retained.
- A later isolated attempt on `202d6aa0bb006265` failed after a successful first case when a second job request returned HTTP 409. It also remains retained.
- The final disposable canary for `831c6e06a8b55bdb` passed **4/4 tasks**, **4 selected / 0 fallback**, in 33.666 seconds. Worker readiness, diagnostics and owned-container cleanup passed; it used fresh loopback PostgreSQL/object storage and did not read live resources.
- Activation used checked pre-release backup **`20261018T175026Z`**. Before writer startup, it preserved **77 tables** and **218 stored files / 4,016,809 bytes**, verified the object-tree fingerprint and existing secret-file checksums, and activated the pinned API/jobs/web image IDs on schema `0029`.
- The after-hosted check passed all four exact task checks and cleaned up both fictional accounts. Release flags were enabled while outbound webhooks and external connectors remained disabled.

## Live browser verification

The fresh final browser journey passes in **35.114 seconds**. It verifies an actual hosted
compound answer (6 USD and 3 records), both receipts, units, scope and selected narrative.
All 1440/390/320-pixel layouts pass keyboard evidence and overflow checks; root inspected
synthetic desktop/mobile captures. No page errors, HTTP rejections or actual network failures
remain. The fictional account is disabled, its token revoked and a fresh login rejected.

The first run failed because its checker treated all interrupted requests as network errors.
A retained diagnostic run identified nine `net::ERR_ABORTED` background panel requests during
navigation. The final checker observes each actual fetch signal's abort and matches only the
known background route/method during navigation. It records these nine separately; it does
not exempt analysis requests, connection resets or unobserved cancellations. Six checker
unit tests pass. No application error was repaired or hidden by that classification.

Checked post-release backup **20261018T175717Z** passes database archive listing,
object archive listing and both SHA-256 checksums. Final readiness/web return 200;
all five services, six loopback listeners, model service and two maintenance timers pass.
Schema remains 0029 with the same 77 application tables. API/jobs/web identities and
restart counts match before/after backup; all three existing configuration hashes match.
No database restore occurred. The first post-check stopped during runtime preflight before
backup, with an empty image map; its exact cause was not captured. A fresh check with
fixed source-line diagnostics passed without an application change. Both reports remain.
The post-check helper's 37 unit cases also pass.

## Retained failures and corrections

- Baseline stale capability assertion: retained, then corrected in candidate expectations.
- Early evaluator assumptions about integer/nested response shapes, an overbroad table-context assertion, optional document-fixture wiring and an empty-population SUM fixture: corrected with passing rechecks.
- Two browser dependency-startup failures: retained; worktree-local dependency copies resolved Turbopack's rejection of dependency symlinks without adding a dependency.
- An early candidate run was interrupted during collection after review found an elliptical metric-operation mismatch; it is not counted as a pass.
- The full primary-run English prompt-label failure, the first fallback-only canary and the HTTP 409 canary failure remain retained as described above.
- The two initial browser checker failures remain retained alongside the diagnostic and passing, signal-observed recheck.

Rollback remains forward repair or compatible flag rollback. An old reader must not silently discard saved compound results, and no old database restore may overwrite later work.

## Supported limits and operator handoff

This adds at most two independent data queries, bounded verified context and constrained
factual wording selection. It does not add arbitrary reasoning loops, dependent calculations,
causal advice or automatic access to every advanced analysis panel. The fixed hosted cases
are not representative acceptance. All eight existing production gates remain open and the
64-requirement ledger is unchanged. No new dependency, schema change, push or public exposure.

See [the implementation map](agent-harness-implementation.md) and
[the contracts and compatible fallback procedure](agent-harness.md). Open the existing private
workspace, refresh the page and ask a new question; old answers remain immutable.
