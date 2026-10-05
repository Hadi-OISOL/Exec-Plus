> **File use case:** Records the September 30 column-explanation conversation repair.
> **What it does:** Documents the audit, regression coverage and private deployment evidence.

# Dataset guidance verification

The user reported repeated generic overview text for column meanings, help and “??”,
plus an empty supporting-document response for a question about a numeric field.
The router lacked an explicit schema-explanation selection and overview assembly
was a constant menu. Overview turns also retained no column topic or source evidence.

The repair adds metadata-grounded column/dataset explanations, bounded exact-name
matching, optional model column selection, immutable private explanation evidence,
contextual follow-ups and browser suggestions. Confirmed meanings take precedence;
drafts/inferences are labelled. Calculation and document routes retain their existing
execution and permission boundaries. No source data or shared definition is edited.

## Checks

- 27 new backend cases cover the reported sentences, normalized and longest name
  matching, calculations/document requests retaining their routes, unknown/model-
  invented columns, inference labels, common-term explanations, context and related
  columns, confirmed/draft/rejected/stale meaning, no implicit definition mutation,
  private history, source deletion, replay after definition changes, ignored model
  prose and exact totals after explanatory turns.
- The new real-service Chromium journey passed in 11 seconds including setup;
  explanation content, follow-ups, suggestion buttons, mobile layout and historical
  reopening are checked. The complete browser suite subsequently passed **11/11**
  in 1.4 minutes, including live mixed data/document chat.
- Frontend lint, TypeScript, both frontend tests and the production build pass.
  Ruff and mypy pass across 110 source files. The generated Next type header was restored.
- Final full backend/architecture suite: **512 passed**, one warning, 271.34 seconds.
  This includes the 27 new guidance cases and all earlier precision, permission,
  study and monitoring regressions.
- Private VPS Chromium passed all **four exact reported messages** on the authorized
  ERP upload at **2026-09-30T15:27:48.056Z**. The ambiguous follow-up retains its
  column, hypotheses are labelled, metadata explanations have no numerical Verified
  badge, mobile layout fits, and a subsequent live-planned total matches execution.
- The API and web are deployed and dependency readiness passes. Seven running API
  source digests match local files, including the preceding decimal fix. No production
  manifest or source data changed. No migration was required.

## Commands and deployment

```bash
docker run -d --rm --name execplus-guidance-postgres -p 127.0.0.1:15433:5432 \
  -e POSTGRES_USER=execplus -e POSTGRES_PASSWORD=execplus -e POSTGRES_DB=execplus postgres:16-alpine
docker run -d --rm --name execplus-guidance-minio -p 127.0.0.1:19000:9000 \
  -e MINIO_ROOT_USER=execplus -e MINIO_ROOT_PASSWORD=change-me minio/minio:latest server /data
export EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus
export EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000
python3 -m pytest apps/api/tests/test_dataset_guidance.py --tb=short
python3 -m pytest --tb=short
python3 scripts/check_browser.py --grep 'column meanings'
EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
npm run lint:web
npm run typecheck:web
npm run test:web
npm run build:web
git diff --check
node data/vps-private/guidance-live.mjs
docker stop execplus-guidance-postgres execplus-guidance-minio
```

Local PostgreSQL and MinIO use isolated disposable schemas/buckets; unrelated
services are preserved. Prior decimal-fix work remains in the same working tree.
Preceding deployed API source was compared with its running container before the
seven-file code-only patch was uploaded. Rollback images are tagged
`pre-guidance-20260930`; prior source is under `releases/pre-guidance-20260930/`.
Remote build output is `ops/guidance-build.log`; clean API imports pass. Activation
uses the existing maintenance lock and requires no database migration.

Activation ran `docker compose -f deploy/vps/compose.yaml up -d --no-deps api web`
under `/run/lock/execplus-maintenance.lock`. Private verification reports/logs are
retained under ignored `data/vps-private/guidance-*`; the live checker reads tokens
locally and reports outcomes without printing uploaded values or credentials.

Production gates, source data and model/network configuration are unchanged. This
repair does not implement another Phase 4 slice or establish production readiness.
