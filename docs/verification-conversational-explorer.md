> **File use case:** Evidence ledger for the interactive conversational dashboard release.
> **What it does:** Records changes, executed checks, live model results and private-demo limitations.

# Explorer verification — 2026-09-28

The user requested an interactive dashboard, flow/column diagrams, animations and
a conversational data assistant with DeepSeek V4 Pro as primary and small models
for routing/selection. Work remains on local `phase2`, preserving teammate commit
`7d70cd7` and the pre-existing uncommitted Phase 2/3 changes. This release is deployed
to the authorized private VPS; it has not been committed, merged or pushed.

## Verified behavior

- Workspace navigation separates overview, data, preparation, documents, saved work
  and team administration. Existing data opens automatically after sign-in.
- An upload into a workspace without a selected dataset creates one from its filename.
- The overview shows a file-to-answer flow, an interactive column diagram, calculated
  cards, keyboard-focusable trend points, clickable breakdowns and profile observations.
- Chat keeps questions and responses paired, retains them while navigating the upload,
  resolves follow-ups from stored execution context and supports individual records.
- Result tables page ten returned rows at a time, expose exact matching counts and
  explicitly disclose bounded results. Case-insensitive text filters are parameterized.
- DeepSeek proposes the final structured plan. Qwen supplies advisory route/column
  selections and chooses server-generated summary evidence. Neither computes answers.
- Migration 0008 adds record/overview turn kinds and model-route storage while
  preserving older turns. Historical result-checksum encoding remains unchanged.

## Results

| Check | Result |
| --- | --- |
| Full backend suite using final API image, real PostgreSQL/MinIO | 320 passed, one existing warning, no skips, 160.77 s |
| Ruff | Passed |
| mypy | Passed, 90 source files |
| Frontend ESLint / TypeScript | Passed |
| Frontend shell tests | 2 passed |
| API and production Next.js container builds | Passed |
| Real-service Playwright journeys | 6 passed, 2.0 minutes |
| Live explorer browser checks | 6/6 passed |
| Additional live greeting and exact grouped-query checks | 2/2 passed |
| Eight independent concurrent Chromium sessions | 8/8 passed |
| Repeated eight-user API journeys | 24/24 passed across three rounds; 168 requests; p95 5650.69 ms; 36.81 s elapsed |
| Production preflight | Correctly blocked by all eight open gates |
| Installed API/source comparison | All 69 application Python files match by SHA-256 |

The full backend run was repeated after the final selection-prompt change. The
browser journeys use isolated PostgreSQL schemas and private MinIO buckets. The
optional SSH test transport runs only the disposable API beside those services;
Chromium and the development frontend run locally. Temporary API containers,
settings, test schemas, buckets and the test-specific forward are removed afterward.

Live explorer checks prove: column/chart interaction; eight Karachi records with
the composed Qwen/DeepSeek route; follow-up revenue `11502`; conversation retention;
new-conversation reset and 20-of-24 bounded pagination; mobile width and reduced motion.
Additional live API checks verify server-rendered greeting/help and revenue by city:
Karachi `11502`, Lahore `12502`, Islamabad `13502`.

Each concurrent browser signs in as a distinct demo account, verifies finance revenue
`10000` and opens the matching policy citation. This is fictional-demo evidence,
not a representative-customer quality benchmark or production load guarantee.

## Failures found and corrected

1. Original row responses exposed only total source rows. An additive matching count
   now comes from the same snapshot and is separately checked during replay.
2. New chat kinds initially violated the old database constraint. Migration 0008
   corrects that constraint and records the composed route, including dataset guidance.
3. Navigation could race a pending workspace/upload operation. Navigation is disabled
   during those transitions, and the destination is chosen after the operation.
4. A screen-reader label inherited full width and caused mobile horizontal overflow.
   Its scoped hidden style now wins; the real browser checks width and reduced motion.
5. Qwen copied a placeholder column name from the initial selection example. The
   validated fallback correctly let DeepSeek execute the requested records. Explicit
   key/type rules replaced the placeholder example; four live route probes returned
   valid hints with the intended route. Hints remain advisory and may omit columns;
   the primary always retains the complete schema.
6. The user's dedicated demo SSH forward stalled while its process remained alive.
   Only that two-port tunnel was replaced, retaining the restricted demo identity and
   adding keepalives. The replacement remains available for the user.

## Commands executed

Local checks, with several focused reruns while correcting failures:

```bash
git status --short
git branch --show-current
git diff --check
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
python3 -m pytest apps/api/tests/test_intent.py apps/api/tests/test_conversational_explorer.py apps/api/tests/test_semantics.py apps/api/tests/test_provider_contracts.py apps/api/tests/test_bootstrap.py tests --tb=short
python3 -m pytest apps/api/tests/test_profiling.py apps/api/tests/test_conversational_explorer.py --tb=short
python3 -m pytest apps/api/tests/test_conversational_explorer.py::test_additive_match_counts_preserve_historical_result_checksums --tb=short
python3 -m pytest apps/api/tests/test_intent.py apps/api/tests/test_conversational_explorer.py apps/api/tests/test_bootstrap.py --tb=short
npm run lint --workspace @execplus/web
npm run typecheck --workspace @execplus/web
npm run test --workspace @execplus/web
python3 scripts/check_browser.py
python3 scripts/check_browser.py --grep 'upload creates'
python3 scripts/check_production_gates.py
node scripts/check_explorer_demo.mjs data/vps-private/sessions.json data/vps-private/explorer-live
node scripts/check_vps_browser.mjs data/vps-private/sessions.json data/vps-private/explorer-browser-eight.json
python3 scripts/check_demo_load.py --sessions data/vps-private/sessions.json --base-url http://localhost:18401 --rounds 3 --output data/vps-private/explorer-load-eight.json
```

`check_browser.py` received `EXECPLUS_TEST_*` credentials in memory from an ignored,
mode-0600 temporary settings file. For the remote test API it also received
`EXECPLUS_BROWSER_SSH_TARGET=administrator@173.208.151.137` and
`EXECPLUS_BROWSER_SSH_SOCKET=/tmp/oisol-execplus-vps-ssh`. No credentials were placed
in command arguments or test reports. Formatting used Ruff and Prettier 3.6.2 on
the touched source files; no frontend runtime dependency was added.

Source packaging and transfer:

```bash
git ls-files -z --cached --others --exclude-standard | tar --null -T - -czf /tmp/oisol-execplus-demo-source.tar.gz
scp -o ControlPath=/tmp/oisol-execplus-vps-ssh /tmp/oisol-execplus-demo-source.tar.gz administrator@173.208.151.137:/sdb-disk/OISOL_ExecPLUS/ops/explorer-source.tar.gz
```

On the VPS (from `/sdb-disk/OISOL_ExecPLUS/source` where applicable):

```bash
tar -xzf /sdb-disk/OISOL_ExecPLUS/ops/explorer-source.tar.gz -C /sdb-disk/OISOL_ExecPLUS/source
sudo docker tag oisol-execplus/api:demo oisol-execplus/api:pre-explorer
sudo docker tag oisol-execplus/web:demo oisol-execplus/web:pre-explorer
sudo docker compose -f deploy/vps/compose.yaml build api web
sudo bash deploy/vps/backup.sh
sudo docker compose -f deploy/vps/compose.yaml run --rm operator python -m alembic upgrade head
sudo docker compose -f deploy/vps/compose.yaml up -d api web
sudo docker compose -f deploy/vps/compose.yaml build api
sudo docker compose -f deploy/vps/compose.yaml up -d api
curl -fsS http://127.0.0.1:18401/health/ready
sudo docker run --rm --name oisol-execplus-final-explorer-tests --network host \
  --env-file /sdb-disk/OISOL_ExecPLUS/secrets/app.env \
  -v /sdb-disk/OISOL_ExecPLUS/source:/verification:ro -w /verification \
  --user root --entrypoint sh oisol-execplus/api:demo \
  -c 'pip install "pytest>=8.2,<9" "pytest-asyncio>=0.23,<1" > /tmp/install.log 2>&1 && python deploy/vps/verify.py'
```

The main API key was transferred through SSH standard input into mode-0600
`secrets/app.env`; the previous private configuration is retained as
`app.env.pre-explorer`. No data-service credentials were regenerated. The backup
before migration is `backups/20260927T222950Z`; database and object archive checksums
passed. This is the UTC name for the 2026-09-28 local-date release. It is a recovery
snapshot, not a new independent restore drill; the earlier restore evidence remains
in the initial VPS ledger. Other VPS applications and model services were not changed.

## Files changed for this slice

- Web: workspace page, dashboard/chat/activation panels, new `explore-components.tsx`,
  global styles, browser tests/config and the generated framework-type purpose header.
- Backend: model settings/bootstrap, intent parser/router, conversation models/service,
  row analytics/executor/validation/evidence, API serialization, persistence/readiness,
  the city sample and migration `0008_conversation_explorer.py`.
- Tests: new `test_conversational_explorer.py` (20 cases); city sample cases in
  profiling/import suites; updated readiness and eight-user seed expectations.
- Operations: optional `browser_transport.py`, browser runner, new live explorer
  script, adjusted eight-user browser navigation and model-neutral load-check wording.
- Documentation: `.env.example`, README, ROADMAP, AGENTS, architecture, analytics
  contract, VPS runbook, historical-ledger link and the explorer contract/ledger.

## Artifacts and remaining limits

Sanitized reports and screenshots are in ignored `data/vps-private/explorer-*`;
VPS build and final-test logs are under `ops/explorer-*.log`. Session files,
credentials, uploads and model weights remain private and outside version control.

Supported data uploads remain CSV and single-sheet XLSX; supporting documents are
TXT/Markdown. Server pagination beyond the bounded returned records, arbitrary
formats/connectors, a chat-history picker and wider query grammar are future work.
The helper's hints are best-effort and are not an authorization or correctness gate.
All eight production gates remain open, and Phase 3 remains In progress overall.
