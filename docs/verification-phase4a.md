> **File use case:** Records verified Phase 4A delivery and the remaining Phase 4 scope.
> **What it does:** Binds implementation, checks and private deployment to an honest acceptance checkpoint.

# Phase 4A verification — September 30, 2026

**4A is complete for approved local/test and private-demo operation. Phase 4 is
In progress overall.** 4B refresh/alerts, 4C basic forecasts, 4D exports and 4E live
connectors remain Planned. All eight production gates remain blocked. The optional
judge remains disabled; model/provider choices are unchanged.

The audit preceded implementation: [gap audit](phase4-gap-audit.md). Public behavior
and limits are documented in [study contracts](phase4-studies.md).

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| Adaptive supported views and questions | Confirmed meaning/unit checks, domain-tag priorities, private goal matching, correction-sensitive ranking, scoped dismissal/restoration; deterministic components only |
| Reproducible studies | Exact 0.10 + 0.20 result; stored source/definition/preparation/method evidence; original replay after new upload; refreshed rerun creates version 2; exact compatible delta and changed-unit refusal |
| Descriptive surveys | Explicit ordinal order, invalid/incomplete order refusal, null responses, group distributions, missingness, executed sample coverage and small-group limitations; no ordinal sums |
| Data sufficiency and safety | Required filters applied to values and counts, inventory date guard, no-match limitation, source-change conflict, deleted-object replay refusal |
| Private and shared work | Member/admin privacy, explicit study sharing before board sharing, revoked membership and sharing, post-replay permission recheck, private goal exclusion, cross-workspace IDOR rejection |
| Six-pin dashboards | Six real result versions reopen; seventh rejected by service/API, database count constraint, optimistic competing update conflict; remove/clear controls |
| Organizations/departments | Workspace roles/invitations retained, dual-owner organization attachment, permission-filtered departments and no inherited data access |
| Browser usability | Full run/save/share/pin/rerun/reopen/compare flow, reload persistence, keyboard dismissal, mobile width and reduced-motion setting; mobile screenshot inspected |
| Deployment | 0011 migration, healthy API/dependencies, preserved rollback artifacts and 8/8 concurrent deployed study browsers |

Full `make check` passed:

- **420 backend tests**, one warning, 160.51 seconds, using isolated PostgreSQL
  16/MinIO services. Existing migration roundtrip/schema comparison tests passed.
- **2 frontend tests**, Ruff, mypy (**104 source files**), ESLint, TypeScript and
  the Next.js production build.
- **9/9 real-service Chromium journeys**, including live DeepSeek combined
  document/data conversation and the new study workflow, in 1.0 minute.

After the final permission recheck adjustment, **25/25 study tests** plus Ruff/mypy
passed again. After adding the clear-pins repair control, the full study browser
journey passed again (**1/1**, 16.5 seconds), as did ESLint/TypeScript and the VPS
production build. The final deployed release passed **8/8 simultaneous Chromium
study journeys** at `2026-09-30T13:16:55.804Z`. Each journey created fictional data,
calculated exactly 0.30, saved/pinned/reopened evidence, reran version 2, reopened
version 1 and checked mobile overflow. Whole journeys took 28.0–31.0 seconds,
including setup/navigation/multiple operations; this is not per-query latency or
a sustained capacity benchmark. No new model call was required for these studies.

Initial targeted runs exposed a too-long new aggregation label and a department
lookup that assumed every table had `created_at`; both were fixed before full
verification. A reentrant HTTP call in the race-test fixture was replaced with a
direct application operation. No failing test was waived.

Local logs are `/tmp/execplus-phase4-check.log`,
`/tmp/execplus-phase4-browser-full.log`, `/tmp/execplus-phase4-studies-final.log`,
`/tmp/execplus-phase4-browser-final.log` and
`/tmp/execplus-phase4a-vps-browser.log`. Ignored live evidence is
`data/vps-private/phase4a-browser.json` and `phase4a-browser.png`; neither contains
session tokens. Generated fictional data remains outside version control.

## Changed files in this slice

Compared with the preserved pre-4A workspace, not the already-dirty branch base:

- New domain/application/transport: `domain/studies.py`,
  `application/services/studies.py`, `presentation/routes/studies.py` under
  `apps/api/src/execplus/`.
- API composition/persistence: `application/ports.py`, `bootstrap.py`, `main.py`,
  `infrastructure/persistence/{repository,schema}.py`, `infrastructure/readiness.py`.
- New migration `migrations/versions/0011_studies.py`; original migrations preserved.
- New `apps/api/tests/test_studies.py` (**25 cases**); integration fixture wiring in
  `conftest.py` and expected migration head in `test_workspace_integration.py`.
- New `apps/web/src/app/workspace/{studies-panel,organization-panel}.tsx`; workspace
  navigation in `page.tsx`, styles in `globals.css`, new real-service journey in
  `apps/web/e2e/workspace.spec.ts`. Generated `next-env.d.ts` was restored to its
  original purpose header and normal build references (no final 4A difference).
- New `scripts/check_studies_demo.mjs` for eight simultaneous private-demo browsers.
- `AGENTS.md`, `ROADMAP.md`, `README.md`, `docs/decisions/architecture.md`,
  `docs/vps-demo-runbook.md`; new `docs/phase4-gap-audit.md`, `docs/phase4-studies.md`
  and this ledger.

The prior Phase 2/3 work remains intact and uncommitted on `phase2`. No branch was
reset, merged or pushed. A pre-edit git-visible source archive is retained at
`/tmp/execplus-before-phase4.tar.gz`; it excludes ignored private data/secrets.

## Commands and environment

Repository inspection included `git status --short`, `git branch --show-current`,
`rg`, `rg --files`, and targeted reads of engineering instructions, roadmap,
architecture, services/schema/routes/tests and installed Next.js component docs.
The development/test containers were isolated from existing user services:

```bash
docker run -d --rm --name execplus-phase4-postgres -p 127.0.0.1:15433:5432 -e POSTGRES_USER=execplus -e POSTGRES_PASSWORD=execplus -e POSTGRES_DB=execplus postgres:16-alpine
docker run -d --rm --name execplus-phase4-minio -p 127.0.0.1:19000:9000 -e MINIO_ROOT_USER=execplus -e MINIO_ROOT_PASSWORD=change-me minio/minio:latest server /data

EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 make check
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 -m pytest apps/api/tests/test_saved_items_integration.py -x -q
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 -m pytest apps/api/tests/test_studies.py -q
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 -m pytest apps/api/tests/test_studies.py apps/api/tests/test_workspace_integration.py -x -q
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 scripts/check_browser.py --grep 'adaptive studies'

python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps --output-format concise
python3 -m mypy
npm run lint:web
npm run typecheck:web
node --check scripts/check_studies_demo.mjs
git diff --check
python3 scripts/check_production_gates.py
sha256sum docs/production-readiness.json
node scripts/check_studies_demo.mjs data/vps-private/sessions.json data/vps-private/phase4a-browser.json
```

Ruff formatting and the locally cached Prettier executable formatted changed
sources; no dependency or provider upgrade was introduced. The production gate
command returned its expected failure with all eight pending gates. Its manifest
SHA-256 remains `8f2b92715756aab3b6c969b1001b1bc2f461176b9600cf29464342e5f24dcef9`.

## VPS release and recovery

SSH used the existing verified master at `/tmp/execplus-phase3-ssh` for
`administrator@173.208.151.137`. Source was bundled from
`git ls-files --cached --others --exclude-standard -z`, explicitly rejecting private
environment/data files, uploaded with `scp`, and extracted into the existing
`/sdb-disk/OISOL_ExecPLUS/source` after preserving its previous copy.

Commands on the VPS, from the application source directory:

```bash
sudo -n docker image tag oisol-execplus/api:demo oisol-execplus/api:pre-phase4a
sudo -n docker image tag oisol-execplus/web:demo oisol-execplus/web:pre-phase4a
sudo -n docker compose -f deploy/vps/compose.yaml build api web
sudo -n docker compose -f deploy/vps/compose.yaml build web
sudo -n bash deploy/vps/backup.sh
sudo -n docker compose -f deploy/vps/compose.yaml run --rm operator python -m alembic upgrade head
sudo -n docker compose -f deploy/vps/compose.yaml up -d --no-deps api web
sudo -n docker compose -f deploy/vps/compose.yaml exec -T postgres psql -U execplus -d execplus -Atc "select version_num from alembic_version"
curl -fsS http://127.0.0.1:18401/health/ready
```

Verified backup **20260930T131523Z** retains `database.dump`, `objects.tar.gz` and
passing checksum verification. Rollback source is `releases/pre-phase4a-source`;
images are tagged `pre-phase4a`. The new schema reports **0011**, the API healthcheck
is healthy and dependency readiness passes. Operator containers were removed.
Existing user sessions, original uploads, model service, other applications and
loopback-only ports were preserved. Runtime image builds and operations are logged
under `ops/phase4a-{build,backup,migrate}.log`.

Do not downgrade away newly saved studies during rollback; preserve their metadata
and receipts first. This release does not clear the production restore gate or
claim public/customer readiness. Next implementation slice is **4B**.
