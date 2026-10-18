# Agent harness implementation — 18 October 2026

Status: **implemented and active in the private demo** as release **`831c6e06a8b55bdb`** on unchanged schema **`0029`**. Local acceptance, restricted images, the isolated canary and the hosted API check pass. Live browser and checked post-release backup also pass; this is not production certification.

## Delivered behavior

- Compound questions can execute at most two independently validated data queries. Both steps must succeed before publication, and each result keeps its own exact receipt.
- Follow-ups reuse only bounded, typed, replay-verified result context bound to the actor, workspace, source and memory revision. Topic-changing questions stop reuse. Private table cells are never placed in the planning packet.
- Verified narrative packets contain server-authored statement variants, evidence IDs, scope and limitations. The model returns only a complete statement ordering and variant choices. Invalid, unavailable or timed-out selection uses the existing deterministic renderer.
- Saved narratives are revalidated against authorized historical receipt replay before delivery. Access, source, definition or memory changes prevent unsafe reuse.
- Confirmed units come from the receipt's definition. Missing units stay explicit. Record counts, named-field counts, null handling and tied extrema keep their existing semantics.
- Compound PDF, Excel and CSV exports replay and authorize both receipts. They preserve both result sections and do not replan the question.
- Narrow English resolution supports plural operations, bounded temporal follow-ups, metric-operation pairing and exact visible category labels. It does not create field/value aliases or evidence.
- Feature switches preserve the legacy path when disabled. Historical saved answers remain readable through the compatible reader.

## Integration record

| Workstream | Delivered scope | Final state |
| --- | --- | --- |
| Verified synthesis | Fact packets, constrained selection, exact fallback, save/replay validation and UI presentation | Integrated, locally accepted and active |
| Context and compound execution | Private result context, clarification boundaries, two-query plans, receipts and publication guards | Integrated, locally accepted and active |
| Evaluation and exports | Synthetic before/after runner, adversarial replay checks and compound PDF/Excel/CSV coverage | Integrated and locally accepted |
| Shared runtime | Flags, budgets, serializers, routes, worker/bootstrap wiring, prompt repair and bounded synonym discovery | Integrated, locally accepted and active |
| Release verification | Pinned build, restricted checks, fresh-resource canary, activation and hosted checks | Accepted within documented private-demo bounds |

The implementation began from `6bca30e`. Candidate source checkpoint `5247867` and accepted test checkpoint `577d183` produced release `831c6e06a8b55bdb`. No schema migration was required.

## Security and evidence boundaries

- Definitions, required filters, calculations, evidence authorization and publication remain application-authoritative.
- A compound answer is published only after both queries succeed and source/access checks still pass. Partial results are not presented as a complete answer.
- Context carries verified scalar result data and bounded receipt/schema/scope metadata. It excludes full transcripts, prior model prose and private record rows/cells.
- The narrative model cannot add numbers, claims, units or evidence IDs. Every mandatory scope and limitation statement must appear exactly once.
- Model selection has an eight-second bound and one call. Failure falls back to deterministic rendering.
- Provider credentials remain server-side. No provider name or credential changed as part of this release.
- Installed development skills are not executable product plugins. Retrieval synonyms only find candidates; they do not rename fields or establish meaning.

## Final local verification

- Backend primary run: **3,153 passed / 1 failed** in 2,098.56 seconds. The failure was an obsolete Roman-Urdu prompt-label assertion; the requested English-only behavior and all other assertions passed.
- Reconciled latest backend status: **3,168 distinct nodes passed**, zero unresolved, across the complete run and explicit 83-case, 6-case and 15-case supplements. The original failure remains in the log, so this is not one clean final-source run.
- Original requirement mapping: **37/37 passed**.
- Frontend: **69/69 passed**. Offline browser: **111 passed / 3 explicit model skips** in 18.7 minutes.
- Ruff, frontend types/lint/build and mypy for **266 source files** passed.
- Exact candidate archives, manifests, VPS builds and restricted computation checks passed.
- Focused tests cover packet validation, fallback, private context, cancellation/races, compound execution/export/replay, English resolution, source and memory changes, and tamper refusal.

The baseline remains separate: **3,008 backend passes / 1 stale capability failure**, **63 frontend passes**, and **111/112 offline evaluation checks**. Focused and supplemental results are not added to the primary full-run count.

## Runtime comparison

The same four fixed hosted tasks improved from **2/4 passed in 51.268 seconds** on release `c34536b8540f7c6d` to **4/4 passed in 52.567 seconds** on `831c6e06a8b55bdb`. The after run selected verified narratives for **4/4** cases with zero fallbacks. This small synthetic corpus does not establish general language quality or speed.

After-run diagnostics for the four allowlisted turns record seven `deepseek-v4-pro` attempts: **12,175 input**, **425 output** and **11,776 cached input tokens**. Their accounting state is `unknown`, so no billing or cost claim is supported.

The final isolated VPS canary used fresh loopback PostgreSQL and object storage. It passed **4/4 tasks**, selected **4/4 narratives**, verified worker readiness and removed all owned containers in 33.666 seconds. It did not read the live database or storage.

## Active private runtime

- Release: `831c6e06a8b55bdb`; source checkpoint: `5247867`; schema: `0029`.
- Checked pre-release backup: `20261018T175026Z`; checked post-release backup: `20261018T175717Z`.
- Activation preserved **77 tables** and **218 files / 4,016,809 bytes** before writer startup. Exact API/jobs/web image IDs and existing secret-file checksums were verified.
- Harness flags are enabled. Existing web origin is retained; outbound webhooks and external connectors remain disabled.
- The hosted after-check used two new fictional accounts, passed all four task checks, then disabled both accounts and revoked their sessions.

## Final live acceptance and remaining limits

The fresh browser check passes in 35.114 seconds: actual compound values and both evidence
references, selected narrative, keyboard controls and 1440/390/320 layouts. Nine confirmed
background signal cancellations during navigation are recorded separately; no actual request,
HTTP or page error remains. Earlier checker failures are retained. All fictional browser
accounts are disabled, sessions revoked and subsequent login denied.

The final checked backup passes both archive listings and checksums. Readiness/web, five
services, six loopback listeners, model/timers, unchanged schema/table set, configuration and
container identities pass. The first preflight failure is retained; the fresh check passes
without an application repair. No restore occurred.

All eight production gates remain open. Two independent queries do not mean arbitrary
multi-step analysis, dependent arithmetic or causal recommendations. Broader representative
model-quality and performance acceptance remains unmeasured. No push occurred.

Full evidence, original failures, measured provider usage and practical limits are in
[the verification report](verification-agent-harness.md). Private evidence remains under
`data/verification/2026-10-18/agent-harness/`. Use compatible flag rollback or forward repair;
never restore old data over later work or use a reader that discards compound results.
