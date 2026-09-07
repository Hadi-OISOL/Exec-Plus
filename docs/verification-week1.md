> **File use case:** Records the Phase 0 and Week 1 gap audit and acceptance evidence.
> **What it does:** Separates observed baseline behavior from implementation and verification results.

This is the historical Week 1 record. The PostgreSQL 16 operational gap was closed
on 2026-09-08: configured PostgreSQL 16.10 and MinIO accepted credentials and the
full Phase 1 suite passed. See [current evidence](verification-phase1.md).

# Audit before implementation — 2026-09-07

Inspected `AGENTS.md`, `ROADMAP.md`, `README.md`, the saved
`docs/codex_phasecomplete.md`, all existing backend source/tests, frontend source/tests,
ADRs, architecture, build configuration, and CI. `docs/CODEX_PHASE0_WEEK1.md` was
absent; the saved task document supplies the Week 1 specification. Architecture
exists at `docs/decisions/architecture.md`, rather than the stale handoff path.
Initial branch: `main`; initial work: untracked user-owned task document (preserved).
Implementation branch: `feat/phase0-week1`.

| Criterion or foundation | Baseline classification | Evidence / gap |
| --- | --- | --- |
| Python compilation | IMPLEMENTED | `python3 -m compileall -q apps/api/src` passes |
| Baseline backend and frontend tests | IMPLEMENTED | 13 backend and 2 frontend tests pass |
| Frontend lint/types/build | IMPLEMENTED | `make check` passes |
| Vector vendor neutrality | IMPLEMENTED | Ports and disabled adapter; no selected runtime vendor |
| Invariants and boundaries | PARTIALLY IMPLEMENTED | Documented; architecture path stale; no application dependency test |
| Modular API and project shell | IMPLEMENTED | Health routes and informational page, existing tests |
| Domain dependency protection | PARTIALLY IMPLEMENTED | Small denylist misses other third-party and internal upward imports |
| LLM routing and retrieval ports | IMPLEMENTED BUT NOT PROVEN BY TESTS | Routing selection covered; HTTP contract and disabled failure behavior untested |
| Configuration validation | PARTIALLY IMPLEMENTED | Model names checked only for emptiness; configuration not loaded at startup |
| PostgreSQL and MinIO | IMPLEMENTED BUT NOT PROVEN BY TESTS | Compose defined; no integration tests; local Docker socket access denied |
| Health/readiness | PARTIALLY IMPLEMENTED | Empty readiness always succeeds; no actual dependency probes or failure coverage |
| CI, developer tools, environment | IMPLEMENTED | Existing check passes; build regenerates type file without purpose header |
| Authentication and users | MISSING | No identity port, persistence, or routes |
| Workspaces, memberships, roles | MISSING | Only a query scope value object exists |
| Invitations and seat limits 3–50 | MISSING | No model, reservation policy, or concurrency enforcement |
| Dataset/upload/audit persistence | MISSING | No database adapter or migrations |
| Workspace object storage | MISSING | Compose only; no storage port or adapter |
| CSV/XLSX parser and 20 MiB bound | MISSING | Setting exists, no enforcement or parsing |
| Valid/invalid parser fixtures | MISSING | No parser tests |
| Upload wizard and lists | MISSING | Informational shell only |
| Tenant isolation / IDOR proof | MISSING | No authenticated resource API or adversarial tests |

Week 1 excludes all profiling, quality scores, cleaning, semantic tagging, and
conversational query generation. The size policy is at most 20 MiB (20,971,520
bytes), consistent with the roadmap and existing setting; larger files fail.

# Implemented results

| Deliverable | Current status and implementation | Automated evidence |
| --- | --- | --- |
| Phase 0 compile/tests/frontend checks | IMPLEMENTED and reverified | `make check`, compileall: all pass |
| Core dependency and vector neutrality | IMPLEMENTED | `tests/test_architecture.py`: stdlib-only domain, inward application imports, imports and manifests free of vector vendors |
| Provider contracts | IMPLEMENTED and tested | `test_provider_contracts.py`: both model tiers use the real HTTP adapter; disabled model and retrieval methods fail explicitly |
| Readiness | IMPLEMENTED | Mixed healthy/failed probes return sanitized 503; real migrated PostgreSQL and bucket probes pass; missing migration fails |
| Configuration and numerical boundary | HARDENED | Whitespace model settings and excessive upload limits rejected; secret repr/errors hidden; nonfinite numbers and negative row selection rejected |
| Identity/users | IMPLEMENTED for local/test | Provisioning, hashed expiring tokens, rejection of invalid/expired/revoked sessions, production guard, browser sign-in/sign-out |
| Workspaces/roles/memberships | IMPLEMENTED | Owner creation, manager/member role matrix, removals, scoped member lists; revocation during parsing blocks storage |
| Invitations | IMPLEMENTED | Creation, email-bound acceptance, single use, duplicate rejection, expiration, revocation, browser link acceptance |
| Seats | IMPLEMENTED | 3/50 accepted, 2/51 rejected, reserved-seat capacity, removal/revocation/expiration release, reduction rejection, concurrent invite and accept races |
| Metadata/audit/migrations | IMPLEMENTED | Real PostgreSQL transactions, composite tenant foreign keys, indexes, schema drift comparison, upgrade/downgrade/upgrade, safe audit contents |
| S3-compatible originals | IMPLEMENTED | Real MinIO put/head/read/delete, retained originals, checksum verification, private bucket rejects anonymous access, SQL failure compensation |
| Parsing/size limits | IMPLEMENTED | Generated valid CSV/XLSX and malformed, oversized, multiple-sheet, merged-cell, bad MIME/extension, path, formula, markup, XML entity, ZIP bomb, and misleading-dimension cases |
| Upload API | IMPLEMENTED | Raw streamed body, declared/actual byte limits, no invalid objects or upload records, metadata excludes storage keys |
| Tenant isolation | IMPLEMENTED | Bidirectional workspace tests plus valid foreign dataset/upload IDs substituted under an authorized workspace; read/write/member/audit/object paths deny access |
| Browser wizard | IMPLEMENTED | Real API/DB/S3 journey: sign-in, workspace, invitation, dataset, upload, rejection, teammate acceptance, tenant switch; mobile-width sign-in error |
| Configured Compose startup | NOT FULLY VERIFIED ON THIS HOST | Docker socket denied to this session; user started services. MinIO passed; existing port 5432 rejected development PostgreSQL credentials. PostgreSQL 16 alternate-port startup requested, still pending |

The whole Week 1 task remains **In progress** only for that final configured
infrastructure startup verification. The code acceptance suite passes against a
separate PostgreSQL 14.24 instance and the running MinIO service. Do not treat this
as proof that this host's default Compose PostgreSQL deployment starts correctly.
Phase 1 as a whole remains in progress; Week 2 was not started.

# Verification and setup commands executed

Repeated invocations of identical commands are grouped below. Editing commands
are not reproduced; this ledger records the audit, setup, and verification commands
and their actual outcomes.

| Command | Outcome |
| --- | --- |
| `pwd`, `git status --short`, `git branch --show-current`, `git log -5 --oneline` | Initial `main`; only untracked user task document |
| `git ls-files docs` and `git log --all --oneline -- docs/CODEX_PHASE0_WEEK1.md docs/codex_phasecomplete.md docs/architecture.md` | Missing old task/architecture paths confirmed; task was subsequently saved by user |
| `rg --files` and `cat`/`sed` reads of task, handoff, roadmap, README, ADRs, backend source/tests, frontend source/tests, manifests, Makefile, Compose, CI | Baseline traced before implementation; no ingestion routes or persistence existed |
| `python3 --version`; `node --version`; `npm --version` | Python 3.10.12, Node 22.22.2, npm 10.9.7 |
| `docker --version`; `docker compose version`; `docker-compose --version` | Docker 29.1.3; `docker compose` unavailable locally; standalone Compose v5.3.1 |
| `make check` | Baseline: 13 backend + 2 frontend tests, lint/types/build pass |
| `python3 -m compileall -q apps/api/src` | Baseline compilation passes |
| `make dev-infra` | Failed: Docker socket permission denied |
| `id`; `sudo -n docker ps --format '{{.Names}}'` | No Docker group access; sudo requires a password |
| `git switch -c feat/phase0-week1` | Created working branch; no commits or pushes |
| `python3 -m pip install 'sqlalchemy>=2.0,<3' 'alembic>=1.13,<2' 'psycopg[binary]>=3.2,<4' 'boto3>=1.35,<2' 'openpyxl>=3.1.5,<4' 'defusedxml>=0.7,<1' 'python-multipart>=0.0.20,<1' 'boto3-stubs[s3]>=1.35,<2' 'types-openpyxl>=3.1,<4' 'types-defusedxml>=0.7,<1'` | Succeeded after transient DNS retries; multipart ultimately not used or added as a direct dependency |
| `python3 -m pip install -e '.[dev]'` | Passed; installed missing declared pytest-asyncio/coverage dependencies |
| `python3 -m pytest apps/api/tests/test_file_parser.py` | Initially 37 pass/1 fail: Python 3.10 CSV null-byte classification; fixed with explicit precheck |
| `python3 -m pytest apps/api/tests/test_file_parser.py apps/api/tests/test_provider_contracts.py apps/api/tests/test_health_routes.py apps/api/tests/test_settings.py apps/api/tests/test_answer_assembler.py tests` | Initially blocked by missing pytest-asyncio; resolved by dev installation |
| `EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:5432/execplus python3 -m pytest apps/api/tests/test_workspace_integration.py -x --tb=short` | Failed: host database rejected development credentials |
| `/usr/lib/postgresql/14/bin/initdb`, `pg_ctl`, `createdb` through a Python subprocess wrapper | Started an isolated temporary cluster on 127.0.0.1:55432; no existing database modified |
| `EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55432/execplus python3 -m pytest apps/api/tests/test_workspace_integration.py -x --tb=short` | Found Python 3.10 SpooledTemporaryFile/TextIOWrapper incompatibility; fixed using disk TemporaryFile |
| `EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55432/execplus python3 -m pytest -x --tb=short` | 79 passed at that stage |
| `npm install --save-dev @playwright/test@1.54.1 --workspace @execplus/web` | Passed; browser dependency and lockfile added |
| `npm audit --json` | Returned zero vulnerabilities; initial install advisory count was inconsistent with this follow-up |
| `npm run lint:web && npm run typecheck:web` | Initial Link/purity violations fixed; passes |
| `npx --yes prettier@3.6.2 --write apps/web/src/app/workspace/page.tsx apps/web/e2e/workspace.spec.ts apps/web/playwright.config.ts` | Formatted new frontend files |
| `python3 -m ruff format apps/api/src apps/api/tests tests migrations scripts` | Formatting applied; subsequent focused formatting used same tool on edited files |
| `python3 -m ruff check --fix apps/api/src apps/api/tests tests migrations scripts` | Imports fixed; remaining long strings corrected manually |
| `python3 -m mypy` | Final: 38 source files, no issues |
| `EXECPLUS_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55432/execplus python3 scripts/wait_infra.py` | PostgreSQL and MinIO accept configured development credentials |
| `EXECPLUS_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55432/execplus make migrate init-storage` | Migration and bucket initialization pass |
| `EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55432/execplus python3 scripts/check_browser.py` | Initial selectors exposed accessibility-name ambiguity; fixed accessible error/dataset names |
| `EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55432/execplus make test-browser` | **2 passed**, real API/PostgreSQL/MinIO, no mocked responses |
| `EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55432/execplus make check` | Final: **93 backend tests, 2 frontend tests**, lint/types/build pass, no skipped tests |
| `python3 -m pytest apps/api/tests/test_settings.py -o addopts='' -q` | Isolated one dependency warning: installed Starlette imports deprecated `multipart` name |
| `python3 -m compileall -q apps/api/src migrations scripts` | Pass |
| `git diff --check` | Pass |

The full check runs Ruff, ESLint, mypy, TypeScript, pytest, Node tests, and Next's
production build through the Makefile. Browser tests are a separate required
acceptance command. CI now starts Compose infrastructure, runs backend checks on
Python 3.10/3.12, and has a real-service Chromium job. Remote CI and container image
builds were not run in this session.

# Remaining work and scope boundaries

- Verify the configured Compose PostgreSQL 16 service after resolving the host
  port/credential conflict. A non-destructive alternative-port command has been
  supplied to the user. Do not reset existing database volumes.
- No production authentication, email delivery, or self-service account recovery
  is claimed. The task's supported dev/test identity flow is implemented.
- Storage crash recovery across the PostgreSQL/S3 boundary needs operational
  orphan reconciliation; synchronous failure compensation is tested. No atomic
  distributed transaction or background cleanup worker is claimed.
- Week 2 profiling, quality scores, cleaning/mapping, sample-data exploration,
  broader onboarding, and later analytics remain unimplemented by design.
- One third-party Starlette multipart deprecation warning remains; tests and
  checks pass without suppressing it beyond the repository's preexisting pytest
  `--disable-warnings` setting.
- The user-owned `docs/codex_phasecomplete.md` is preserved and remains untracked.
  Next.js generated frontend agent files during browser testing; they are retained
  with the repository's required purpose headers. The `next-env.d.ts` purpose
  header is restored after builds.

# Files changed

- `.env.example`
- `.github/workflows/ci.yml`
- `.gitignore`
- `AGENTS.md`
- `Makefile`
- `README.md`
- `ROADMAP.md`
- `alembic.ini`
- `apps/api/Dockerfile`
- `apps/api/src/execplus/application/ports.py`
- `apps/api/src/execplus/application/services/answers.py`
- `apps/api/src/execplus/application/services/health.py`
- `apps/api/src/execplus/application/services/workspaces.py`
- `apps/api/src/execplus/bootstrap.py`
- `apps/api/src/execplus/config.py`
- `apps/api/src/execplus/domain/ingestion.py`
- `apps/api/src/execplus/infrastructure/file_parser.py`
- `apps/api/src/execplus/infrastructure/identity.py`
- `apps/api/src/execplus/infrastructure/object_storage.py`
- `apps/api/src/execplus/infrastructure/persistence/__init__.py`
- `apps/api/src/execplus/infrastructure/persistence/repository.py`
- `apps/api/src/execplus/infrastructure/persistence/schema.py`
- `apps/api/src/execplus/infrastructure/readiness.py`
- `apps/api/src/execplus/main.py`
- `apps/api/src/execplus/manage.py`
- `apps/api/src/execplus/presentation/dependencies.py`
- `apps/api/src/execplus/presentation/routes/workspaces.py`
- `apps/api/tests/conftest.py`
- `apps/api/tests/test_answer_assembler.py`
- `apps/api/tests/test_file_parser.py`
- `apps/api/tests/test_health_routes.py`
- `apps/api/tests/test_provider_contracts.py`
- `apps/api/tests/test_settings.py`
- `apps/api/tests/test_workspace_integration.py`
- `apps/web/AGENTS.md`
- `apps/web/CLAUDE.md`
- `apps/web/e2e/workspace.spec.ts`
- `apps/web/package.json`
- `apps/web/playwright.config.ts`
- `apps/web/src/app/globals.css`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/workspace/page.tsx`
- `apps/web/tests/shell.test.mjs`
- `compose.yaml`
- `docs/decisions/0004-secure-ingestion.md`
- `docs/verification-week1.md`
- `docs/week1-api.md`
- `migrations/env.py`
- `migrations/versions/0001_workspace_ingestion.py`
- `package-lock.json`
- `pyproject.toml`
- `scripts/check_browser.py`
- `scripts/wait_infra.py`
- `tests/test_architecture.py`

The temporary PostgreSQL 14 cluster used for verification was stopped with
`pg_ctl -D <temporary-cluster>/data -m fast -w stop` and its task-owned temporary
directory removed after testing. Existing databases and Docker volumes were not
modified or removed. Use the documented Compose setup for subsequent local runs.
