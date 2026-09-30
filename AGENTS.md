> **File use case:** Persistent handoff and operating guide for humans and coding agents working on ExecPlus.
> **What it does:** Records current state, non-negotiable rules, commands, boundaries, and the next approved slice of work.

# ExecPlus Engineering Handoff

Read this file, `ROADMAP.md`, and `docs/decisions/architecture.md` before changing the project.

## Current state

- Phase 0: Engineering Foundation remains complete; its four exit criteria were reverified on 2026-09-07.
- The repository is a Python and TypeScript modular monorepo.
- The API has liveness and dependency-aware readiness endpoints for migrated PostgreSQL and the configured object bucket.
- Language models and vector databases are represented by provider-neutral protocols.
- No vector database vendor has been selected.
- The local-model path expects an OpenAI-compatible endpoint so Ollama, vLLM, or another server can be evaluated later.
- Runtime model selection is composed in `execplus/bootstrap.py`; routes and use cases must not branch on vendors.
- Metadata profiling uses deterministic standard-library computation; DuckDB now executes validated Phase 2 snapshot queries.
- PostgreSQL is reserved for control-plane metadata, permissions, conversations, lineage, and audit records.
- MinIO provides an S3-compatible local object-store target.
- Week 1 implements local/test opaque-session identity behind an identity port; production identity remains a separate decision.
- Workspaces, roles, invitations, seat limits, retained CSV/XLSX uploads, and audit events have real PostgreSQL/MinIO integration coverage.
- Phase 1 is complete for supported local/test operation as of 2026-09-08.
- Profiles, quality scores, immutable cleaning/mapping recipes, synthetic samples, onboarding and usage foundations are implemented.
- Phase 2 was audited from teammate commit `7d70cd7`; verified local/test analytics now include exact decimals, isolated SQL, replayable receipts, private threads and workspace sharing.
- Current Phase 4B evidence: 458 backend tests on isolated PostgreSQL/MinIO plus 46 final targeted hardening/foundation checks, 2 frontend tests, 10 real-service browser journeys including live mixed chat, plus a final refresh journey after declaring the upload parser. Ruff/mypy (109 files), TypeScript, lint and production builds pass. All 8/8 concurrent deployed refresh browsers passed exact activation, alerts, original evidence replay and mobile layout. See `docs/verification-phase4b.md`; this is not a sustained-load benchmark.
- Phase 3 is Complete for the approved local/test and private-demo scope as of 2026-09-30; its approved fictional demo is verified: six documents, twenty known answers, 16/16 top-three retrieval and 20/20 live DeepSeek cases. Production evaluation work is deferred with mandatory gates.
- Document passages live in object storage; metadata and immutable citation offsets live in PostgreSQL. The reference hybrid ranker is not a selected production vector provider.
- Migration 0006 adds execution receipts; 0007 adds activation/document/report metadata; 0008 adds record/overview conversation kinds and model routes; 0009 adds immutable business meanings and private goals. Migration 0011 adds organizations/departments, study versions, six-pin boards and private view dismissals; migration 0012 adds staged refresh heads/candidates, monitoring jobs and private alerts. Readiness requires 0012, now deployed. Legacy executions without receipts cannot be replayed reliably.
- Reports default to disabled email. `python3 -m execplus.manage deliver-reports` processes due slots; SMTP delivery needs explicit operator configuration. No real email was sent during verification.
- Decimal results and integers outside JavaScript's safe range are JSON strings. Preserve this wire contract and frozen profile-v1 reconstruction.
- Runtime model summaries select server-rendered evidence statements; never restore free-form prose guarded only by a number regex.
- Migration 0002 preserves uploads; existing uploads receive their initial profile on first access.
- Preserve profile-v1 reconstruction semantics and synthetic sample versions; introduce new versions for incompatible changes.
- On 2026-09-17 the user approved fictional demo documents/answers and hosted DeepSeek V4 Pro for current development. Generated material lives in ignored `data/phase3-demo-v1/`; recreate with `make demo-corpus`.
- The existing provider-neutral adapter uses `https://api.deepseek.com`, model `deepseek-v4-pro`, reasoning disabled, explicit JSON mode and a 1024-token response limit. Credentials stay in ignored `.env`.
- On 2026-09-17 the user identified `Qwen/Qwen3-4B` as the intended model candidate; the VPS trial below supersedes the then-pending hosting request. It is not selected for production. See `docs/ceo-request-qwen-hosting.md` for the original request and remaining pre-production needs.
- On 2026-09-28 the user authorized a private VPS demo for about eight users and deferred domain/public access. The VPS runs an isolated Qwen3-4B Q4_K_M service, API, web, PostgreSQL and MinIO. The subsequent explorer request selected hosted DeepSeek V4 Pro as primary, with Qwen for advisory route/column selection and summary evidence selection. Bootstrap composes separate provider-neutral adapters; routes must not branch on vendors. Local development `.env` remains unchanged. Historical Q4/Q8 document scores (19/20 and 16/20) do not clear production quality gates.
- The private workspace now includes a column/flow diagram, chart interactions, reduced-motion support, paired chat turns, bounded record queries and the fictional `cities-v1` sample. Record responses add `matched_records` while preserving `records_analyzed` and historical checksum semantics. Invalid/unavailable helper hints fall back to primary planning; the primary retains the full schema. See `docs/conversational-explorer.md`.
- Model files live under `/sdb-disk/AIML-Models/OISOL_ExecPLUS`; app/data/secrets/backups live under `/sdb-disk/OISOL_ExecPLUS`. Other VPS applications and their ports remain separate. Eight short-lived app sessions and individual restricted SSH keys support private access on ports 18400/18401. Never publish credentials, private keys or generated demo data.
- Daily private-demo backups run at 03:00 UTC and briefly pause ExecPlus writes. A separate restore verified migration 0007 and all nine seed objects. Off-server disaster recovery and production validation remain open. Read `docs/vps-demo-runbook.md` before operating the VPS.
- Representative-customer, learned embedding/vector-provider, local/hosted comparison and operational production reviews were explicitly deferred to Phase 5, before any external customer deployment. Track them in `docs/production-readiness.json`.
- `make production-preflight` and production runtime construction require reviewed evidence with intact artifact checksums. Demo completion must never clear those production gates.
- No product feature should be represented as implemented unless tests prove it.
- On 2026-09-30 the user requested a roadmap revision for a persistent data partner and then authorized starting Phase 3. Slice 3A is now Complete for the private demo; 3B–3C are verified locally and deployed, 3D is complete as a reviewed rejection of the optional judge, and Phase 4A (adaptive dashboards/studies) and 4B (refresh/alerts) are Complete for the private demo; 4C–4E (basic forecasts, exports, first connectors) remain Planned.
- Google Sheets and a read-only PostgreSQL source are now planned in Phase 4E after semantic and refresh foundations. Broader connectors, new file formats and advanced research/decision methods remain Frozen in Phase 6. No new connector, production learned search provider, runtime judge or Parquet serving optimization is selected. Unified document/data chat is now implemented in 3B.
- Phase 3A implements optional domain/goal prompts, inferred row/column meaning, focused confirmation, versioned workspace definitions, reviewed declared relationships and inspectable history. Only the dataset creator or owner/admin edits shared meaning; goals remain private. Saved unconfirmed/stale definitions block new calculations. Sources without saved meaning retain their legacy inferred behavior. Read `docs/phase3-data-understanding.md` before extending.
- Confirmed roles, metric aggregation/required filters and unit rules apply to planners, dashboards and joins. Receipts retain understanding IDs; replay uses original definitions. Changed definitions during planning clarify before execution. Joined right-side measures require unique left keys as well as the existing right-key guard. No automatic conversion, join discovery or scheduled refresh is implied. Phase 4A now adds goal-aware recommendations in the separate Studies & dashboards view.
- Slices 3B–3C are verified locally and deployed: bounded mixed document/data chat, private history, retry idempotency, current authorized catalog and measured offline representations. Migration 0010 adds durable turn claims/evidence references. See `docs/phase3-unified-conversation.md` and `docs/verification-phase3b-c.md`. VPS deployment verification is recorded in that ledger.
- The learned search candidate failed (18/21 versus reference 20/21); typed Parquet preserved exact results and improved repeat-query timings but is not adopted without lifecycle integration. No persistent cache was added. `docs/decisions/0007-representation-and-judge-trials.md` records the decision.
- Phase 3D is Complete: the user explicitly approved all twelve labels on September 30, followed by a fresh DeepSeek V4 Pro trial with 5/12 exact matches, six timeouts, one misclassified defect and p95 10012.89 ms. The judge is rejected and remains disabled. See `docs/verification-phase3d.md`; this closes the assessment, not production acceptance.
- The September 30 final judge evaluator now binds reviews to case/rubric hashes, refuses changed or incomplete observations and preserves prior reports. 34 targeted evaluation/architecture tests plus Ruff/mypy pass. See `docs/phase3-judge-evaluation.md`. A reviewed run requires explicit `--review`; unreviewed runs require `--preliminary` and a fresh output path. Human approval and the reviewed run are now recorded; no repeat label approval is needed for these unchanged cases.
- The preceding 0010 release passed 5/5 live combined-conversation/catalog checks. Backup `20260930T095357Z`, `pre-phase3bc` image tags and `releases/pre-phase3bc-source` preserve 3A. The user authorized starting Phase 4 on September 30; 4A is now verified and deployed on 0011. The September 30 target does not waive live-source rehearsals, external setup, or any of the eight production gates. Private-demo backup `20260930T053553Z`, rollback images tagged `pre-phase3a`, and `releases/pre-phase3a-source` preserve the preceding release. Eight sessions were renewed into ignored `data/vps-private/sessions.json`; never publish their tokens.

- Phase 4A is Complete for the approved local/test and private-demo scope. New studies
  require confirmed meaning and explicit units; deterministic domain/goal suggestions,
  ordered distributions, missingness/coverage, immutable study runs and exact comparisons
  preserve receipts. Private goals are never copied into shared study evidence.
- Six-pin dashboards enforce ownership, explicit study sharing, current access and
  optimistic edits. Departments are separate workspaces grouped under an organization;
  organization ownership/membership never grants workspace data access.
- The 4A release verified migration 0011; 4B now runs 0012 below. Backup `20260930T131523Z`, images tagged `pre-phase4a`
  and `releases/pre-phase4a-source` preserve the preceding release. Eight simultaneous
  study browsers passed on September 30; no production gate or model configuration changed.
- Phase 4B is Complete for local/test and the private demo. Scheduled refresh consumes
  staged CSV/XLSX files, validates before activation, preserves prior sources on failure,
  and requires explicit replacement/append/merge and keyed duplicate behavior. Schema
  drift and changed meaning need review. The catalog/default selection follows the feed head.
- At most six shared active monitors per dataset capture immutable sources and governed
  methods. Queries calculate metric/sample/present counts and optional SUM segments;
  comparisons and drivers replay receipts. Complete-month comparisons require declared
  coverage. No driver is a causal claim. Alerts are self-subscribed, private, in-app,
  transactional, cooldown-limited and permission/freshness/coverage checked at delivery.
- `python3 -m execplus.manage process-refreshes` runs bounded durable jobs. The VPS
  `execplus-refresh.timer` runs every minute, sharing `/run/lock/execplus-maintenance.lock`
  with backups. Do not run an uncoordinated worker during a backup. The explicit
  `python-multipart>=0.0.32,<0.1` runtime dependency is required for staged-file intake.
- VPS 0012 is healthy; backup `20260930T141138Z`, `pre-phase4b` images and
  `releases/pre-phase4b-source` preserve 0011. Eight private sessions were renewed after
  expiry. Fictional refresh walkthrough workspaces show an exact 0.30 to 0.50 PKR update.
  All eight production gates remain blocked, and model/network settings did not change.
- Next Phase 4 slice: 4C basic forecasting, then 4D exports and 4E first connectors.
  None is implemented by 4B. Work remains uncommitted on `phase2` with prior work preserved.

## Non-negotiable engineering rules

1. Never ask an LLM to calculate or supply a business number.
2. Execute validated, read-only queries and build answers from returned results.
3. Scope every resource lookup and mutation by `workspace_id`.
4. Apply permissions before query execution and before hybrid retrieval.
5. Return clarification for ambiguous requests and a supported-scope explanation for impossible requests.
6. Record model route, generated query, execution outcome, lineage, and returned answer in the audit trail.
7. Keep domain and application modules independent from web frameworks and infrastructure SDKs.
8. Add or update tests with each behavior change.
9. Update `ROADMAP.md` and this current-state section only when evidence supports the status change.
10. Do not commit datasets, secrets, model weights, generated exports, or local database volumes.
11. Put a file-level use-case and responsibility header at the top of every new file.
12. Do not add inline explanatory comments; prefer clear names, small functions, tests, and architecture documents.
13. Next.js can regenerate `next-env.d.ts`; restore its required file-purpose header before committing.

## Dependency direction

```text
presentation -> application -> domain
infrastructure -> application ports and domain
domain -> standard library only
```

Framework imports are forbidden in `execplus/domain`. Application services depend on protocols in `execplus/application/ports.py`, not concrete providers.

## Commands

```bash
make install
make check
make test
make api
make web
make dev-infra
make down
```


## Definition of done

- Acceptance criteria have automated coverage.
- Unit tests and architecture tests pass.
- Static analysis passes.
- Tenant isolation and numerical lineage are considered explicitly.
- Public contracts and configuration are documented.
- Logs contain identifiers and outcomes, not uploaded row values or secrets.
- Roadmap and handoff state reflect the tested implementation.

## Next approved slice

The user authorized auditing the teammate's Phase 2 branch and proceeding into
Phase 3, followed by the private explorer and the September 30 roadmap revision.
Work is on local branch `phase2`, based on `origin/phase2` at `7d70cd7`.
The teammate's commit is preserved. The audit/Phase 3 work has not been pushed or
merged into main. Keep `.env` and customer documents out of version control.

Phase 2 acceptance is verified for local/test operation. Current Phase 3 work uses
the user-approved fictional corpus and private VPS explorer, with DeepSeek primary planning
and Qwen3-4B advisory routing/evidence selection. The requested interactive explorer is
verified and deployed. The user has now authorized Phase 4; 4A is verified and deployed.
The user instructed completion of Phase 3 and then explicitly approved the twelve
judge labels. Phase 3A–3C are verified and deployed; Phase 3D's reviewed assessment
is complete with a do-not-adopt decision. Phase 3 is Complete for the private-demo
scope. Phase 4 was subsequently authorized; 4A is verified and deployed while the
explicitly deferred production reviews remain open. Do not
interpret the requested same-day deadline as acceptance evidence or silently
start Phase 6. Keep experimental optimization/judge adoption separate from claims
that those components improve quality or performance.
The user approved the private eight-user/investor demo slice; public customer access
and a domain are deferred. Do not expose the local/test identity deployment publicly.
Use `make evaluate-demo`
and `make evaluate-demo-model`; report any failures honestly. No customer corpus is
needed for this demo milestone. Representative-customer, model/provider, privacy,
restore and operational validation remains mandatory before production under Phase 5.
Do not mark these deferred gates passed from demo results. Phase 3A updated the
private VPS runtime without changing its network exposure. Read
`ROADMAP.md`, `docs/phase3-demo-and-production-gates.md`,
`docs/phase3-activation-knowledge.md`, `docs/phase3-data-understanding.md` and the
verification records before extending. Phase 4 is now authorized; Phase 6 remains frozen.

Phase 4 was authorized by “start phase4” on September 30. Read
`docs/phase4-gap-audit.md` and `docs/phase4-studies.md` for the audited gaps and
4A contracts. Preserve the previous source/image/database checkpoint before
any VPS migration. Phase 4 completion requires its own exit evidence.


The user's “start 4b?” instruction authorized the completed 4B slice. Read
`docs/phase4b-gap-audit.md`, `docs/phase4-refresh-monitoring.md` and
`docs/verification-phase4b.md` before extending. Local checks and eight deployed
browser journeys verify its private-demo scope. The first clean API startup found
an undeclared multipart package; it was corrected, clean-import checked and all
release checks passed. Do not repeat that partial release as the final state.
Next is 4C when instructed; 4B did not implement forecasts, exports or connectors.
Preserve the 0011 source/image/database checkpoint and all new 0012 user metadata.
