> **File use case:** Provides a review inventory for the Phase 2 audit and Phase 3 work.
> **What it does:** Lists changed source, migration, test and documentation paths without generated artifacts.

# Change inventory

Based on teammate commit `7d70cd7` on branch `phase2`. No secrets, customer datasets,
model weights, generated builds or local volumes are included. The implementation
and supporting records are currently local, uncommitted changes.

## Backend

- `apps/api/src/execplus/application/ports.py`
- `apps/api/src/execplus/application/services/activation.py`
- `apps/api/src/execplus/application/services/analytics.py`
- `apps/api/src/execplus/application/services/intent_router.py`
- `apps/api/src/execplus/application/services/joins.py`
- `apps/api/src/execplus/application/services/knowledge.py`
- `apps/api/src/execplus/application/services/lineage.py`
- `apps/api/src/execplus/application/services/reports.py`
- `apps/api/src/execplus/application/services/saved_items.py`
- `apps/api/src/execplus/application/services/summaries.py`
- `apps/api/src/execplus/application/services/threads.py`
- `apps/api/src/execplus/bootstrap.py`
- `apps/api/src/execplus/config.py`
- `apps/api/src/execplus/domain/activation.py`
- `apps/api/src/execplus/domain/evidence.py`
- `apps/api/src/execplus/domain/intent.py`
- `apps/api/src/execplus/domain/join_paths.py`
- `apps/api/src/execplus/domain/knowledge.py`
- `apps/api/src/execplus/domain/kpi_library.py`
- `apps/api/src/execplus/domain/models.py`
- `apps/api/src/execplus/domain/profiling.py`
- `apps/api/src/execplus/domain/saved_items.py`
- `apps/api/src/execplus/domain/semantics.py`
- `apps/api/src/execplus/infrastructure/email.py`
- `apps/api/src/execplus/infrastructure/knowledge.py`
- `apps/api/src/execplus/infrastructure/object_storage.py`
- `apps/api/src/execplus/infrastructure/persistence/repository.py`
- `apps/api/src/execplus/infrastructure/persistence/schema.py`
- `apps/api/src/execplus/infrastructure/query/duckdb_executor.py`
- `apps/api/src/execplus/infrastructure/query/validation.py`
- `apps/api/src/execplus/infrastructure/readiness.py`
- `apps/api/src/execplus/main.py`
- `apps/api/src/execplus/manage.py`
- `apps/api/src/execplus/presentation/routes/activation.py`
- `apps/api/src/execplus/presentation/routes/analytics.py`
- `apps/api/src/execplus/presentation/routes/saved_items.py`
- `apps/api/tests/conftest.py`
- `apps/api/tests/test_analytics_integration.py`
- `apps/api/tests/test_duckdb_executor.py`
- `apps/api/tests/test_intent_router_integration.py`
- `apps/api/tests/test_join_paths.py`
- `apps/api/tests/test_phase2_hardening.py`
- `apps/api/tests/test_phase3_integration.py`
- `apps/api/tests/test_semantics.py`
- `apps/api/tests/test_workspace_integration.py`

## Web

- `apps/web/e2e/workspace.spec.ts`
- `apps/web/src/app/globals.css`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/workspace/activation-panel.tsx`
- `apps/web/src/app/workspace/ask-panel.tsx`
- `apps/web/src/app/workspace/dashboard-panel.tsx`
- `apps/web/src/app/workspace/knowledge-panel.tsx`
- `apps/web/src/app/workspace/page.tsx`
- `apps/web/src/app/workspace/profile-panel.tsx`
- `apps/web/src/app/workspace/saved-panel.tsx`
- `apps/web/tests/shell.test.mjs`

## Migrations

- `migrations/versions/0006_execution_receipts.py`
- `migrations/versions/0007_activation_knowledge.py`

## Tools

- `scripts/evaluate_phase3.py`

## Documentation

- `docs/decisions/0005-verified-execution.md`
- `docs/decisions/0006-retrieval-evaluation.md`
- `docs/decisions/architecture.md`
- `docs/phase2-analytics.md`
- `docs/phase3-activation-knowledge.md`
- `docs/verification-phase2.md`
- `docs/verification-phase3.md`

## Root configuration and handoff

- `.env.example`
- `AGENTS.md`
- `Makefile`
- `README.md`
- `ROADMAP.md`
- `pyproject.toml`

## Demo and production-gate follow-up

- `scripts/create_demo_corpus.py`: reproducible fictional documents and known answers.
- `scripts/evaluate_demo_model.py`: bounded live evidence-selection evaluation.
- `scripts/evaluate_phase3.py`: separate answerable retrieval scoring.
- `scripts/check_production_gates.py`: release evidence preflight.
- `apps/api/src/execplus/infrastructure/release_gate.py`: production startup evidence gate.
- `apps/api/tests/test_demo_readiness.py`: generator, provider and release-gate regressions.
- `docs/production-readiness.json`: deferred requirements and review/evidence fields.
- `docs/phase3-demo-and-production-gates.md`: approved deferral, setup and operating guide.
- Existing configuration, provider adapter, model response contract, Makefile, roadmap
  and handoff updated for the DeepSeek demo and mandatory production follow-up.

Generated demo documents, answer sheets and evaluation reports live in ignored
`data/phase3-demo-v1/`. The local API key and hosted settings remain in ignored `.env`.

## Private VPS deployment follow-up (2026-09-28)

- `deploy/vps/`: isolated Compose deployment, pinned base images, private credential
  initialization, model/backup systemd units, restricted per-user SSH forwarding,
  backup workflow and nearby backend-test runner.
- API/web Dockerfiles: packaged migrations/operator scripts, reproducible frontend
  dependency install, configurable base images and frontend API build address.
- `scripts/provision_demo.py`: eight separate identities, idempotent fictional seeding,
  private session output and renewal of the saved session set.
- `scripts/check_demo_load.py`, `scripts/check_vps_browser.mjs` and
  `scripts/check_restored_demo.py`: deployed concurrent API/browser and recovery checks.
- Summary service: temporary short model-facing aliases mapped to immutable receipt
  IDs; no change to the prohibition on model-supplied business numbers.
- `apps/api/tests/test_vps_demo.py`: six test cases for seeding, isolation, secret
  preservation and summary alias integrity. Integration/browser fixtures now accept
  private test-storage credentials from environment rather than fixed defaults only.
- Model evaluation reports now include the prompt checksum. Q4/Q8 failures are
  preserved in the ignored evaluation artifacts and summarized in verification docs.
- `docs/vps-demo-runbook.md`, `docs/verification-vps-demo.md`, README, roadmap, handoff,
  CEO checklist and Phase 3 records reflect the private demo and remaining launch gates.

VPS data, model weights, generated source/evaluation archives, credentials and SSH
private keys remain outside version control. No Git commit, push or merge was performed.

## Data understanding follow-up (2026-09-30)

- New domain/application/route modules named `understanding.py`, plus migration
  `0009_data_understanding.py`: bounded definitions, immutable history, relationship
  review, private goals and optimistic concurrency.
- Repository ports, SQL metadata/repository, bootstrap, API composition and readiness:
  scoped persistence and migration 0009 wiring.
- Analytics, intent routing, joins, semantic views, KPI matching and DuckDB executor:
  confirmed meaning, required filters, exact replay and duplicate-join safeguards.
- `apps/web/src/app/workspace/understanding-panel.tsx`, workspace page and styles:
  pre-upload prompts, editable definitions, review/revocation and inspectable history.
- `apps/api/tests/test_understanding.py`, DuckDB tests, integration wiring/readiness
  expectation and browser journey: inference, privacy, concurrency, revision changes,
  live calculations, original replay and join cardinality coverage.
- `scripts/check_understanding_demo.mjs`: fictional live deployed browser/model check.
- `docs/phase3-data-understanding.md`, `docs/verification-phase3a.md`, roadmap,
  README, architecture and handoff: contracts, evidence and remaining Phase 3 work.
