> **File use case:** Records the evidence for the September 30 data-understanding delivery.
> **What it does:** Separates tested local/deployed behavior from remaining Phase 3 and production work.

# Phase 3A verification — 2026-09-30

Phase 3A is complete for the supported local/test and private-demo scope. Phase 3
overall remains **In progress**; 3B–3D have not been implemented by this delivery.
The working branch remains `phase2`, based on teammate commit `7d70cd7`. Existing
uncommitted Phase 2/3/explorer work was preserved. No commit, merge or push occurred.

## Gap audit and delivered change

The prior explorer inferred a profile and supported exact queries, but did not
offer persisted, editable business meaning or private user goals. Profiles could
not distinguish a human correction from an inferred suggestion. Receipts had no
definition version, and a model could finish planning after a definition changed.
Declared joins checked right-key uniqueness, but repeated left keys could multiply
or reweight a right-side measure.

This delivery adds optional upload context, a review editor, immutable shared
definitions, private goals, relationship reviews, historical inspection and
explicit definition/revision conflict checks. Metric filters and aggregation apply
to executed results, with exact historical replay. The executor now rejects
right-side aggregation when left keys repeat. See [the contract](phase3-data-understanding.md).

## Results

| Check | Result |
| --- | --- |
| Full backend suite | **343 passed**, one existing dependency warning, 98.51 seconds |
| Frontend shell tests | **2 passed** |
| Real PostgreSQL/MinIO browser journeys | **7 passed**, 34.7 seconds |
| Ruff, mypy, frontend lint and TypeScript | Passed; mypy checked 94 source files |
| Production Next.js build | Passed |
| Python compilation, Node script syntax, whitespace | Passed |
| Private VPS API/web builds | Passed |
| Pre-migration database/object backup | Both artifact checksums passed |
| Deployed migration/readiness | **0009**, PostgreSQL and object bucket healthy |
| Deployed definition/model journey | **6/6 passed** |
| Eight simultaneous deployed browser sessions | **8/8 passed**, live model answers and citations |
| Production preflight | Expected exit 1; all **8 gates remain blocked** |

Local backend/browser checks used isolated PostgreSQL **16.10**, MinIO
**RELEASE.2025-09-07T16-13-09Z**, Python **3.10.12** and Node **22.22.2**.
Each test schema/bucket was disposable. Existing local applications were not reused.
The live VPS retains its existing PostgreSQL, MinIO, DeepSeek primary and Qwen helper.

Eighteen new understanding cases cover unfamiliar names/category hints, identifiers,
ratings, grain, invalid definitions, mixed/missing units, private goals, scoped reads,
edit permissions, competing writes, source changes, revocation, required filters,
average dashboards, immutable historical definitions/replay, three planning races,
and relationship cardinality/revocation. Five additional executor cases exercise
every supported aggregation against duplicate left keys with a right-side measure.
The browser journey checks clarification, correction, the exact `0.10` filtered
dashboard, persistence after navigation, historical inspection, revocation and mobile layout.

The live fictional walkthrough starts with two amounts, `0.10` paid and `0.20`
cancelled. Confirming the paid-only rule changes new answers to `0.10` in two
separate live conversations, while replay of the earlier unrestricted query stays
`0.30`. Definition history and mobile layout also pass. These are fictional checks,
not representative-customer model evaluation or an expanded load benchmark.

## Commands executed

The focused checks were run during implementation; the final `make check` and
browser runs above validate the final application source.

```bash
git status --short
git branch --show-current
python3 -m ruff format apps/api/src/execplus/domain/understanding.py apps/api/src/execplus/application/services/understanding.py apps/api/src/execplus/application/services/joins.py apps/api/src/execplus/presentation/routes/understanding.py apps/api/src/execplus/domain/kpi_library.py apps/api/src/execplus/infrastructure/query/duckdb_executor.py apps/api/tests/test_understanding.py apps/api/tests/test_duckdb_executor.py
python3 -m ruff check --fix apps/api/src/execplus/application/services/joins.py
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
npm run lint --workspace @execplus/web
npm run typecheck --workspace @execplus/web
npm run test --workspace @execplus/web
npx --offline prettier@3.6.2 --write apps/web/src/app/workspace/understanding-panel.tsx apps/web/e2e/workspace.spec.ts
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 -m pytest apps/api/tests/test_understanding.py apps/api/tests/test_duckdb_executor.py -q --tb=short
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 scripts/check_browser.py --grep 'confirm business meaning'
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 scripts/check_browser.py
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 make check > /tmp/execplus-phase3a-check.log 2>&1
python3 -m compileall -q apps/api/src scripts migrations
node --check scripts/check_understanding_demo.mjs
python3 scripts/check_production_gates.py
sha256sum docs/production-readiness.json
git diff --check
```

Temporary local service setup used dedicated containers:

```bash
docker run -d --rm --name execplus-phase3-postgres -p 127.0.0.1:15433:5432 -e POSTGRES_USER=execplus -e POSTGRES_PASSWORD=execplus -e POSTGRES_DB=execplus postgres:16-alpine
docker run -d --rm --name execplus-phase3-minio -p 127.0.0.1:19000:9000 -e MINIO_ROOT_USER=execplus -e MINIO_ROOT_PASSWORD=change-me minio/minio:latest server /data
```

Deployment used the existing authenticated SSH control socket, copied only
Git-visible source files and staged builds before replacing the previous source.
Credentials remained in the pre-existing VPS secret directory.

```bash
git ls-files -z --cached --others --exclude-standard | tar --null -T - -czf /tmp/execplus-phase3a-source.tar.gz
sha256sum /tmp/execplus-phase3a-source.tar.gz
scp -o ControlPath=/tmp/execplus-phase3-ssh -o BatchMode=yes /tmp/execplus-phase3a-source.tar.gz administrator@173.208.151.137:/sdb-disk/OISOL_ExecPLUS/ops/phase3a-source.tar.gz
```

Commands executed on the VPS, in order:

```bash
cd /sdb-disk/OISOL_ExecPLUS
mkdir source-phase3a-stage
sha256sum ops/phase3a-source.tar.gz
tar -xzf ops/phase3a-source.tar.gz -C source-phase3a-stage
sudo -n docker tag oisol-execplus/api:demo oisol-execplus/api:pre-phase3a
sudo -n docker tag oisol-execplus/web:demo oisol-execplus/web:pre-phase3a
cd source-phase3a-stage
sudo -n docker compose -f deploy/vps/compose.yaml build api web > /sdb-disk/OISOL_ExecPLUS/ops/phase3a-build.log 2>&1
cd /sdb-disk/OISOL_ExecPLUS
sudo -n bash source/deploy/vps/backup.sh > ops/phase3a-backup.log 2>&1
sudo -n docker compose -f source/deploy/vps/compose.yaml stop api
sudo -n docker compose -f source-phase3a-stage/deploy/vps/compose.yaml run --rm operator python -m alembic upgrade head > ops/phase3a-migrate.log 2>&1
mkdir -p releases
mv source releases/pre-phase3a-source
mv source-phase3a-stage source
sudo -n docker compose -f source/deploy/vps/compose.yaml up -d --no-deps api web
cd source
curl -fsS http://127.0.0.1:18401/health/ready
sudo -n docker compose -f deploy/vps/compose.yaml exec -T postgres psql -U execplus -d execplus -Atc "select version_num from alembic_version"
sudo -n docker compose -f deploy/vps/compose.yaml run --rm operator python scripts/provision_demo.py --confirm-fictional-demo --output /run/execplus-demo/sessions.json
```

Renewed sessions were retrieved privately, then these live checks ran locally:

```bash
node scripts/check_understanding_demo.mjs data/vps-private/sessions.json data/vps-private/phase3a-live.json
node scripts/check_vps_browser.mjs data/vps-private/sessions.json data/vps-private/phase3a-eight-browser.json
```

Initial failures were resolved before the passing runs: an expired foreground SSH
tunnel caused infrastructure connection errors, replaced by isolated local test
services; a Playwright label lookup needed the accessible combobox role; the race
test needed a worker thread for concurrent TestClient requests; and lint briefly
raced Playwright's removal of its generated test-results directory. The sequential
final `make check` passed. VPS `rg` was unavailable; a read-only log check used `grep`.

## Artifacts, rollout and remaining gaps

- Source archive SHA-256: `37baa6f4cd87c65a7cbccda842018d2e517ebf45f3490b375f56f485b1a92e20`.
  Final handoff/evidence documentation and the standalone live checker were synced
  after the application build; they do not change the tested application source.
- Backup: `/sdb-disk/OISOL_ExecPLUS/backups/20260930T053553Z`.
  This is a pre-migration recovery point, not a new restore rehearsal.
- Rollback source: `releases/pre-phase3a-source`; prior API/web images:
  `oisol-execplus/api:pre-phase3a` and `oisol-execplus/web:pre-phase3a`.
  Restoring the old runtime needs a deliberate compatible schema/data recovery;
  do not drop new definition records casually.
- Local sanitized live reports: `data/vps-private/phase3a-live.json` and
  `data/vps-private/phase3a-eight-browser.json`. These generated files stay ignored.
- Production ledger SHA-256 remains
  `8f2b92715756aab3b6c969b1001b1bc2f461176b9600cf29464342e5f24dcef9`.
  All eight production gates remain open.

Remaining scope: 3B unified conversation/history/tool orchestration, 3C analytical
and learned-search benchmarks/catalog, 3D advisory judge evaluation, and Phases
4–5. Automatic relationship discovery, time-zone/currency conversion, refreshed
connectors and goal-driven studies were not added by 3A. Legacy unsaved definitions
remain visibly inferred. No public-domain exposure or production identity change
was made. See [the change inventory](change-inventory-phase2-phase3.md) for files.
