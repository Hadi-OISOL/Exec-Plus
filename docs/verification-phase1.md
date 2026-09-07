> **File use case:** Records the remaining Phase 1 audit and completion evidence.
> **What it does:** Maps implementation gaps to acceptance checks without advancing Phase 2.

# Phase 1 completion audit — 2026-09-08

Baseline: clean `main`. The new instruction authorizes all remaining Phase 1;
the earlier Week 1 task's Week 2 exclusion no longer defines this task's scope.

| Area | Audit finding before implementation | Required verification |
| --- | --- | --- |
| Foundation | Framework boundaries, CI, health and provider ports exist | Compile, architecture, static checks, build |
| Workspace ingestion | Sessions, roles, seats, invitations, validation and private originals exist | Existing tests against configured PostgreSQL 16 and MinIO |
| Profiling | Only structural counts exist | Deterministic column types, ranges, roles, tags |
| Quality | Structure rejection exists; no quality score | Fixed missing, duplicate, conflict and invalid-date fixtures |
| Cleaning/mapping | Absent | Preview, immutable recipes, checksums, undo, tenant isolation |
| Samples | Absent | Versioned synthetic finance, sales and inventory generators |
| Onboarding | Workspace/invite/upload forms exist | Browser journey through sample and own-file profiles |
| Usage | Audit exists; no usage counters | Transactional events without row values |

## Result

Phase 0 remains verified. Week 1's pending operational check is closed: the
configured PostgreSQL reports **16.10**, MinIO accepts the configured credentials,
and the actual API's `/health/ready` returns 200 with both dependencies healthy.
The unrelated PostgreSQL on port 5432 was left alone; this repository uses 55433.
The user-started Compose services were reused; this session did not need Docker
socket access to run the acceptance tests or apply migrations.

All Phase 1 acceptance criteria pass for the documented local/test identity flow.
Phase 2 is still Planned and no Phase 2 implementation was added.

| Acceptance | Evidence |
| --- | --- |
| Tenant isolation | Existing bidirectional workspace/upload/storage tests plus every new profile, history, cleaning, restore, sample and usage route; composite revision references; revoked membership before reads |
| Parser fixtures | Existing CSV/XLSX, malformed, oversized, multi-sheet, merged, unsafe-content and exact-size coverage retained |
| Reproducible profiles | Fixed quality/type/date/identifier fixtures, CSV/XLSX equivalence and frozen sample SHA-256 tests |
| Reconstructable cleaning | Preview does not write revisions or usage; retained original, cumulative recipes, parent/output checksums, reconnect/replay, restoration, stale-edit conflict, 20-step bound and failure rollback |
| Quality explanations | Golden 90.00 score with one missing cell, duplicate, numeric conflict and invalid date; missing columns, boolean conflicts and three sample scores |
| Nontechnical journey | Real browser creates workspace, invites/accepts teammate, uploads, sees profile, explores sample, previews mapping/cleaning, applies, restores and checks usage; narrow-screen checks |

## Tests added and checks

- `test_profiling.py`: 27 tests, including parameterized type, mapping and sample fixtures.
- `test_profile_integration.py`: 14 real PostgreSQL/MinIO tests.
- `workspace.spec.ts`: one new full preparation journey; all three existing browser tests retained.
- Existing migration assertion advances from 0001 to 0002; schema drift and migration round-trip checks remain intact.
- Existing shell status assertions now distinguish completed preparation from planned analytics.

Final results: **134 backend tests passed, zero skipped; 2 frontend tests passed;
4 Chromium browser tests passed**. Ruff, strict mypy (41 source files), ESLint,
TypeScript, Python compilation and the Next.js production build passed.

An additional generated capacity probe validated and profiled the full supported
1,000,000-cell bound (99,999 data rows × 10 columns plus headers) in **2.32 seconds**;
process peak RSS was **59,348 KiB** on this host. This is a local measurement, not
a production load-test guarantee. No fixture data was saved to the repository.

The first browser preparation run exposed missing explicit column-header semantics
in preview tables. Adding `scope="col"` corrected accessibility and the full suite
then passed twice. Intermediate Ruff line-length failures were fixed before the
successful `make check`; no assertions were weakened or tests removed.

The only backend warning is an existing Starlette `python_multipart` import
PendingDeprecationWarning. Browser logs also contain Node FORCE_COLOR/NO_COLOR
warnings. Neither produced a failed check.

## Exact verification and development commands

Commands were run from `/home/it-admin/OISOL`. Focused checks were followed by the
full gates; repeated invocations are listed once here.

```bash
git status --short
git branch --show-current
python3 -m ruff check apps/api/src migrations --fix
python3 -m ruff format apps/api/src migrations
python3 -m mypy
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts
python3 -m pytest apps/api/tests/test_profiling.py -q
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus python3 -m pytest apps/api/tests/test_profile_integration.py -q
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus python3 -m pytest -q
npm run lint:web
npm run typecheck:web
npm exec --yes --package=prettier@3.6.2 -- prettier --write apps/web/src/app/workspace/profile-panel.tsx apps/web/src/app/workspace/page.tsx apps/web/e2e/workspace.spec.ts apps/web/next.config.ts apps/web/playwright.config.ts
python3 scripts/wait_infra.py
python3 -m compileall -q apps/api/src migrations scripts
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus make check
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus make test-browser
make migrate
make init-storage
python3 -m pytest --collect-only -o addopts='' -q
make api
make web
git diff --check
```

`make check` executed Ruff, ESLint, mypy, TypeScript, pytest, Node tests and
`next build`. Browser testing started temporary API/web servers and used disposable
schemas/private buckets, cleaning them afterward. Its build directory is isolated
at `.next/browser`, allowing local development to run separately.

Operational probes executed `SHOW server_version` using SQLAlchemy with
`Settings().database_url`, then HTTP GETs using httpx to:

- `http://127.0.0.1:8000/health/ready` — 200, both dependencies ready.
- `http://192.168.0.120:3000/workspace` — 200.

`make migrate` applied the additive 0002 migration to the local database.
`make init-storage` verified the existing bucket. Existing uploads and workspace
records were preserved. API and web development servers were started for local use.

## Remaining boundaries

No open Phase 1 acceptance gaps for the supported local/test flow. Production
identity, production deployment and recovery, billing-grade metering and load/security
hardening remain later roadmap work. Crash-time orphan-object reconciliation remains
the previously documented deployment limitation. Analytical SQL/DuckDB execution,
KPI dashboards and conversational analytics are Phase 2 work and were not started.
See [the public contract](phase1-data-preparation.md) for conservative type inference,
ISO-only date handling, synchronous processing and recipe compatibility boundaries.

The implementation was verified on `main`. The subsequent user instruction
authorizes committing and publishing it to the OISOL GitHub repository and
synchronizing its existing branches without rewriting history.


## Files changed

- `AGENTS.md`
- `Makefile`
- `README.md`
- `ROADMAP.md`
- `apps/api/src/execplus/application/ports.py`
- `apps/api/src/execplus/application/services/workspaces.py`
- `apps/api/src/execplus/domain/ingestion.py`
- `apps/api/src/execplus/domain/profiling.py`
- `apps/api/src/execplus/domain/samples.py`
- `apps/api/src/execplus/infrastructure/file_parser.py`
- `apps/api/src/execplus/infrastructure/persistence/repository.py`
- `apps/api/src/execplus/infrastructure/persistence/schema.py`
- `apps/api/src/execplus/infrastructure/readiness.py`
- `apps/api/src/execplus/main.py`
- `apps/api/src/execplus/presentation/routes/workspaces.py`
- `apps/api/tests/test_profile_integration.py`
- `apps/api/tests/test_profiling.py`
- `apps/api/tests/test_workspace_integration.py`
- `apps/web/e2e/workspace.spec.ts`
- `apps/web/next-env.d.ts`
- `apps/web/next.config.ts`
- `apps/web/playwright.config.ts`
- `apps/web/src/app/globals.css`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/workspace/page.tsx`
- `apps/web/src/app/workspace/profile-panel.tsx`
- `apps/web/tests/shell.test.mjs`
- `apps/web/tsconfig.json`
- `docs/phase1-data-preparation.md`
- `docs/verification-phase1.md`
- `docs/verification-week1.md`
- `docs/week1-api.md`
- `migrations/versions/0002_profiles.py`
