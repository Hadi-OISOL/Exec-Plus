> **File use case:** Audits the October 4 platform proposal against the existing product.
> **What it does:** Defines additive implementation slices, contracts, compatibility risks and acceptance evidence before implementation.

# Platform foundation: audited delivery plan

Published before implementation on October 4, 2026. This plan incorporates the
requested platform evolution into the existing roadmap; it does not declare future
capabilities delivered. The earlier uncommitted September 30 and October 2 repairs
remain the baseline. Production gates remain mandatory.

## A. Verified gaps and reuse

| Proposal area | Existing implementation | Useful gap / disposition |
| --- | --- | --- |
| Assets and artifacts | Immutable uploads/revisions, documents/passages, execution receipts, study versions | Add typed capability and artifact projections over these aggregates; no duplicate asset database |
| Jobs | Durable thread request claims, refresh observations and report slots | Add PostgreSQL jobs/attempts/events with leases, budgets, cancellation and owner-scoped progress for conversation execution first |
| Compute | QueryExecutor port, isolated DuckDB, parameter binding, exact decimals, interruption and replay | Add a compatible bounded broker with operator-owned engine registration; preserve every existing execution path |
| Ingestion/preparation | Bounded CSV/XLSX parser, retained dialects, immutable preview/apply recipes | Parser registry and versioned quality projections can extend existing contracts; more formats and process isolation require separate evidence |
| Meaning | Versioned definitions, units, grain, reviewed joins, current authorized catalog | Reuse; never auto-confirm interpretations or invent units |
| Analysis | Bounded numerical/record/document/mixed routing and immutable evidence | Represent supported steps as a small typed plan; unsupported methods remain unsupported |
| Privacy | Permission-first access, minimized schema/passages, configured model endpoints | Central classification/disclosure policy and secret-provider adapters remain explicit next-slice work; authorization alone is not a privacy policy |
| Statistics/sandbox/ML | Descriptive methods and exact governed queries | New methods need deterministic registries and method-specific tests; no arbitrary Python, packages, network or generated UI |
| Observability | Audits/receipts and partial operational reports | Actual durable action events now; full metrics/traces and retention need later operational acceptance |
| UX | Upload-first findings, chat, immutable evidence, studies/boards | Real resumable progress/cancellation and Simple/Expert evidence views; never synthetic reasoning or fabricated progress |

## B. Selected foundation architecture

Keep the modular monolith and PostgreSQL control plane. Introduce domain value
objects for artifacts, supported capabilities, job states/budgets and bounded
analysis steps. Application services own authorization, orchestration, compute
selection and progress publication. Infrastructure owns SQL claiming/leases and
DuckDB execution. HTTP and browser code use explicit DTOs.

Artifact descriptions are projections of existing resources, including their
source/method versions and bounded lineage. Every traversal rechecks current
access, including private documents and studies. Descriptors expose opaque IDs,
never physical storage locations. Metadata availability is not source integrity.

Conversation jobs reuse the existing private thread/turn and idempotency rules.
One logical request has one turn and job; attempts are separate. Claims are fenced,
terminal publication is transactional, and expired leases cannot publish an answer.
Recovery must report interruption honestly; at-least-once execution is not exactly
once. Existing refresh/report workers retain their existing contracts in this slice.

The compute broker implements the existing QueryExecutor contract and delegates
only to registered operator-selected engines. Initially DuckDB is the sole engine.
Budgets are enforced before execution and within the adapter; a declared budget
must not be described as an OS-level process limit. No arbitrary endpoints or code
are accepted from a model or browser.

## C. Migration plan

Add migration 0013 for workspace-scoped jobs, attempts and ordered events, linked
to existing conversation turns. Enforce tenant relationships and idempotency in
PostgreSQL. Upgrade tests must preserve 0012 uploads, definitions, receipts, studies,
refresh jobs and conversations. Readiness advances only with the new migration.
Artifact views, quality projections and the compatible compute broker do not need
replacement tables or changes to historical receipts.

Before any VPS migration, preserve source, API/web images and a database/object
backup. Deploy the worker with the maintenance/backup coordination documented in
the VPS runbook. Rollback must retain new metadata and profile-v2 compatibility.

## D. API and UI changes

- Preserve synchronous `POST /workspaces/{workspace}/threads/{thread}/ask`.
- Add asynchronous conversation submission, owner-scoped job status, ordered
  activity, result resolution and explicit cancellation. The worker executes the
  same governed application services. Polling uses authenticated headers.
- Add authorized artifact/capability/lineage and quality descriptions over current
  resources; preserve existing catalog response fields.
- Chat shows recorded actions, resumable work and confirmed cancellation. A browser
  disconnect detaches without pretending to cancel the server operation.
- Simple/Expert changes presentation only. Both retain exact answers, limitations,
  source access, verification distinctions and replay. No query reruns on view change.

Progress contains server-owned action codes, timestamps and identifiers, never
hidden chain-of-thought, model token streams, source row values, secrets or invented
percentages. Animations respect reduced motion and do not fabricate work stages.

## E. Compatibility contract

Preserve profile-v1 reconstruction, profile-v2 inheritance, retained CSV dialects,
immutable transforms, exact decimal/wide-integer wire strings, historical checksum
serialization, original-source replay and current private/shared access rules.
Keep old `/ask` and saved-turn result shapes usable. Add fields and APIs instead of
rewriting aggregates. Do not move private goals into shared artifact descriptions.

## F. Security and failure risks

Tests must cover cross-workspace and private-owner job/artifact access, revoked
permissions, changed/deleted sources, stale leases, duplicate submissions, worker
crashes, cancellation/completion races, exhausted budgets and untrusted plan inputs.
Only authorized work may start or resume, and current access is checked again before
returning results. Failed/cancelled computations retain audit/receipt evidence.
One slow model or worker must not monopolize the queue; concurrency is bounded.

Production identity, domain/HTTPS, representative-customer evaluation, model privacy,
off-server recovery and the other release gates are not satisfied by this slice.

## G. Verification plan

Run domain/unit and architecture checks, real PostgreSQL/MinIO integration tests,
migration upgrades, independent exact-result comparisons, and targeted job recovery,
privacy and cancellation tests. Run Ruff/mypy, frontend tests/lint/types/build, and
real-service browser journeys at desktop/mobile widths. Verify that action stages
come from actual execution, resume does not duplicate a turn, and view changes do
not calculate again. Exercise the clean worker/runtime configuration before a
private-demo release. Record exact commands, failures and remaining limitations in
the delivery verification record; do not infer acceptance from implementation alone.

## H. Dependency-ordered roadmap incorporation

1. **Foundation A (current implementation):** compatible artifacts/capabilities,
   durable conversation jobs, real progress/cancellation, bounded compute, supported
   typed steps and quality descriptions. Deliver and verify one complete chat flow.
2. **Preparation B:** parser registry/process budgets, richer versioned quality
   rules, classification/disclosure policy, approved transform extensions and
   retention/rebuild contracts. Preserve Phase 1 and historical evidence.
3. **Analysis C:** deterministic statistics/method registry and bounded multi-step
   plans. Phase 4C forecasts require coverage/assumptions/backtests; 4D exports require
   authorized reproducible renderers. Neither is completed by a foundation API.
4. **Execution D:** isolated Python executor only after sandbox/network/filesystem,
   resource, package and reproducibility acceptance. No arbitrary code in the API.
5. **Experiment E:** reproducible feature/experiment/ML artifacts and evaluations
   only after method and sandbox foundations. Keep advanced Phase 6 work frozen
   until its activation criteria are explicitly met.
6. **Integration F:** Phase 4E approved read-only Sheets/PostgreSQL adapters, a secret
   provider and endpoint controls; future remote compute registers through the same
   broker only after evidence. Broader connectors retain Phase 6 gating.

Phase 5 operational and production evidence runs alongside eligible work and remains
a hard gate before external customer deployment. No date or UI redesign waives it.

The implemented foundation decisions are recorded in
[ADR 0008](decisions/0008-durable-analysis-foundations.md). The
[verification ledger](verification-platform-foundation.md) records acceptance and
retained failures separately from this preimplementation plan.
