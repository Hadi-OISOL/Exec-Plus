# Agent harness implementation — 18 October 2026

Status: **In progress.** No new release is active or accepted. This ledger records the current authorized implementation, not production certification.

## Ownership and integration

Base `6bca30e`, branch `phase2`. Preserve the existing modified `apps/web/next-env.d.ts`, coordination document, historical PDF, independent-tools verification and architecture review handoff. The root application stays unchanged while baseline tests run.

| Owner | Model | Isolated branch | Write scope |
| --- | --- | --- | --- |
| Agent 1 | GPT-6 Astra, Medium | `agent/harness-synthesis-20261018` | New verified narrative modules/tests; ask panel and narrative presentation. |
| Agent 2 | GPT-6.1 Sol, Medium | `agent/harness-context-20261018` | Router, private thread context, bounded compound plans, capability contracts and focused tests. |
| Agent 3 | GPT-5.6 Sol, Medium | `agent/harness-evaluation-20261018` | New synthetic evaluations, independent code/security review, verification plan. |
| Lead | Current session | `agent/harness-integration-20261018` | Shared configuration, provider/job budgets, response serialization, exports, integration, release and final evidence. |

No agent can push, activate VPS changes, modify another worktree or change provider credentials. Lead integrates reviewed commits and runs combined gates.

## Implementation map

| Phase | Scope | Acceptance evidence | State |
| --- | --- | --- | --- |
| 0 | Source/runtime inventory and frozen baseline | Actual health/version checks, baseline failures retained, isolated fixtures | Running |
| 1 | Verified facts and conversational statement variants, optional bounded model selection, exact fallback | Invented numbers/claims/IDs rejected; units and caveats retained; UI exact data still accessible | Integrated; focused tests pass, browser gate running |
| 2 | Bounded authorized result context, clarification and follow-up continuity | Scope/source/memory/access invalidation; topic boundaries; historical replay | Integrated; focused source/access/privacy tests pass |
| 3 | At most two independently validated data steps using existing analytic services | Complete requested steps or explicit failure, two receipts, no arbitrary SQL; compound exports | Integrated; compound export gate running |
| 4 | Synthetic before/after evaluations, privacy regressions, API/browser/build checks | Recorded actual outcomes, no invented hosted quality/cost | Baseline running |
| 5 | Checked backup, exact candidate images, synthetic canary, controlled activation | Current schema/data/config preservation; health/worker/replay/exports; rollback instructions | Not started |

Feature switches default off. Existing saved answers and original service paths remain supported. No schema migration is planned unless implementation demonstrates a need. Definitions, required filters and exact math remain application-authoritative.

## Initial runtime inventory

| Service | Location | Version/status observed this session | Dependencies / health | Deployment and rollback |
| --- | --- | --- | --- | --- |
| Developer source | Local checkout | `phase2`, `6bca30e`, existing unrelated WIP | Python venv and project Node | Separate worktrees; integrate reviewed commits, no reset of user work |
| Local application | Developer machine | No existing web/API listeners before task | New restricted tunnel restores browser access to VPS | Tunnel only; not a local application deployment |
| Test database/storage | Local disposable Docker containers | Started for this task; PostgreSQL and MinIO readiness pass | Loopback ports 25432/29000; per-test schema/bucket | Test-owned resources only, never production database |
| Private web | VPS through existing restricted identity | HTTP 200; image `487ed108360d` | API | Existing immutable image pipeline; retain old images/source |
| Private API | VPS through restricted tunnel | `/health/ready`: ready, PostgreSQL/storage healthy | PostgreSQL, object storage | Existing maintenance-lock pipeline; data-preserving rollback/forward repair |
| Worker, schema, model, timers | VPS | Current schema `0029`; API/jobs image `8c12e8f9500e`; all five services running, zero restarts; model and refresh/backup timers active | Same API code, queue, local selector and hosted provider | Must verify before activation |
| Hosted language model | External configured endpoint | Confirmed configured main tiers `deepseek-v4-pro`, selector `qwen3:4b`; no provider call in discovery | Server-held configuration/credentials | No provider-name change authorized by inference |

The user restored the administrator control session, verified on October 18. Read-only inventory confirms the current images, schema and configured model names; the restricted loopback app tunnel works. Current environment is `local`, so private-demo deployment is not independent production certification. Aggregate queue metadata showed 225 succeeded jobs and no active queued/running jobs at inspection. Latest backup `20261018T030005Z` passes archive checksums, object-tar listing and PostgreSQL archive listing; this is readability/integrity, not a fresh restore rehearsal. Historical handoff headings contain older releases and must not override actual observations.

## Shared contracts

- `EvidenceAnswer.additional_data` is an additive tuple; first numerical result remains `data`. Compound turns retain existing `mixed` kind and use `coverage=data`, without pretending document retrieval occurred.
- Two data steps plus assembly fit the existing four-step plan maximum. Resource budget permits two queries only when orchestration is enabled; original default remains one.
- Narrative packets contain verified server-authored factual variants and evidence IDs. Model selection cannot add facts. Mandatory scope/limitations remain. Saved narrative is validated against authorized replay before delivery.
- Unit metadata comes from the receipt's actual confirmed definition, not a current replacement or model guess. Explicit private preferences remain separate from numerical filters.
- Relevant source/definition/access checks remain mandatory at execution and publication; partial compound results are never silently presented as a full answer.
- Installed development skills are not loaded as arbitrary runtime code. Retrieval improvements are candidate discovery only, not evidence or semantic column aliases.

## Verification ledger

Root baseline uses the unmodified source and isolated database/storage. Full backend run is in progress. Frontend baseline: 63 passed, zero failures, 2.210 seconds. Root foundation/upload-brief recheck: 36 passed with isolated services; an earlier run skipped eight service-dependent cases and is not counted as equivalent coverage. Agent-specific first failures and passing rechecks will be recorded separately. No deployment acceptance or hosted evaluation is claimed yet.

Private evidence directory: `data/verification/2026-10-18/agent-harness/`. It must remain ignored and contain synthetic or redacted operational evidence only.
