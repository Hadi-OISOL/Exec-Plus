> **File use case:** Records actual Phase 4B refresh, monitoring and deployment evidence.
> **What it does:** Separates private-demo acceptance from production and later-phase work.

# Phase 4B verification — September 30, 2026

Scope: validated staged-file refresh, explicit replacement/append/merge, freshness
and schema/meaning review, bounded exact observations, period/segment comparisons,
private KPI alerts and the operator worker. Phase 4C was not started. Existing dirty
Phase 2/3/4A work is preserved on `phase2`; this slice is not committed or pushed.

Before editing, repository instructions, roadmap, architecture, actual services,
tests, branch and status were checked. The audit is in
[phase4b-gap-audit.md](phase4b-gap-audit.md). A git-visible source archive at
`/tmp/execplus-before-phase4b.tar.gz` preserves the preceding local state.

## Results

- Initial complete `make check`: **452 backend tests**, one warning; **2 frontend
  tests**, Ruff, mypy, ESLint, TypeScript and production build passed.
- Expanded backend regression: **457 tests** passed. After the final scoped-batch
  regression and explicit runtime dependency, the final complete run passed
  **458 tests**, one warning, in 224.12 seconds. The targeted refresh suite passed
  **38 cases** before the final guards. After those guards, **46 targeted tests**
  passed in 51.80 seconds: 41 refresh/monitoring cases plus 5 foundation checks.
  The full-suite count is not a claim that its earlier run included the three
  subsequently added guard cases.
- **10/10 real-service Chromium journeys passed** with live fictional DeepSeek
  mixed chat enabled, including studies and the new refresh/alert journey (1.2 min).
- The refresh browser journey passed again with the declared multipart package
  installed: **1/1**, 15.8 seconds. This is an additional targeted check, not eleven
  distinct acceptance journeys.
- Final Ruff/mypy passed (**109 source files**); ESLint/TypeScript and the final
  production build passed. The required `next-env.d.ts` purpose header and normal
  build imports were restored after generation.
- **8/8 concurrent deployed Chromium sessions** passed at
  `2026-09-30T14:15:13.895Z`, taking 30.1–33.4 seconds per complete journey. These are
  end-to-end browser timings, not individual-query latency or a sustained-load claim.
- The deployed API passes dependency readiness and uses **migration 0012**.
  Eight critical API source files match local SHA-256 digests.
- The systemd refresh worker completed with `Result=success`, `ExecMainStatus=0`;
  its one-minute timer is enabled. It shares the maintenance lock with backups.
- `production-preflight` still rejects all **eight** production gates. The manifest
  checksum remains `8f2b92715756aab3b6c969b1001b1bc2f461176b9600cf29464342e5f24dcef9`.

The final guards reject potentially truncated segment results at a reduced query
limit, reserve monthly filter slots, and compensate partially acknowledged storage
writes for both adapter-level and unexpected failures. The rebuilt API was clean-
import checked; existing demo evidence was rechecked after this last update.

The new tests cover retained/raw and derived snapshots, exact decimals, additive
reconciliation, immutable historical replay, malformed input, schema review,
append/merge duplicates and conflicts, idempotency/concurrent activation, schedule
slots, rejected/stale definitions, keyed validation, private alert access, threshold
boundaries, cooldown/duplicate suppression, unsubscribe/read, stale/incomplete/missing
coverage, delivery transaction rollback/retry, stale claims, missing objects,
revocation before activation and between replays, activation rollback, candidate
preparation changes, monitor limits and tenant filtering before batch limits.

Failures found and fixed during verification:

1. Browser settings initially failed CORS because PUT was absent from the allowed
   methods. PUT is now allowed only for the configured existing web origin.
2. A new select needed an explicit accessible label for reliable exact targeting.
3. Adding a navigation item made the sidebar note cover Team & settings at shorter
   desktop heights. The rail now scrolls and navigation/footer cannot overlap.
4. An early targeted browser attempt overlapped local Next build output generation;
   final browser/build verification was run sequentially.
5. A clean VPS runtime lacked `python-multipart`, although the local environment
   had it transitively. `pyproject.toml` now explicitly requires `>=0.0.32,<0.1`;
   [the maintained package](https://pypi.org/project/python-multipart/) was checked,
   installed locally, rebuilt remotely and import-tested in the clean container.
   The API was unavailable during that repair; final readiness and live checks pass.
6. Manual dataset processing originally filtered after the worker batch limit.
   Repository filtering now applies before the limit; a 102-job foreign backlog
   regression proves it cannot starve the selected dataset's work.

## Reproduction commands and retained evidence

Only ExecPlus-owned disposable containers were used. Existing Sync-IO services were
left alone. The actual command surface used was:

```bash
git status --short --branch
git diff --check
docker ps --format '{{.Names}} {{.Ports}}'
docker run -d --rm --name execplus-phase4b-postgres -p 127.0.0.1:15433:5432 \
  -e POSTGRES_USER=execplus -e POSTGRES_PASSWORD=execplus -e POSTGRES_DB=execplus postgres:16-alpine
docker run -d --rm --name execplus-phase4b-minio -p 127.0.0.1:19000:9000 \
  -e MINIO_ROOT_USER=execplus -e MINIO_ROOT_PASSWORD=change-me minio/minio:latest server /data
export EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus
export EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000
python3 -m pytest apps/api/tests/test_studies.py -x -q
python3 -m pytest apps/api/tests/test_refresh.py -x -q --tb=short
python3 -m pytest apps/api/tests/test_refresh.py -q --tb=short
python3 -m pytest apps/api/tests/test_refresh.py tests --tb=short
make check
python3 -m pytest -q --tb=short
python3 -m pip install 'python-multipart>=0.0.32,<0.1'
python3 -c 'import execplus.main; print("API import passed with explicit upload parser")'
python3 -m pytest --tb=short
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
npm run lint:web
npm run typecheck:web
npm run build:web
python3 scripts/check_browser.py --grep 'refresh retains'
EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py
bash -n deploy/vps/backup.sh
node --check scripts/check_refresh_demo.mjs
python3 scripts/check_production_gates.py
sha256sum docs/production-readiness.json
```

Ruff format/import fixes and the cached Prettier CLI formatted only touched Python
and web/script files. The tests ran in disposable schemas/buckets cleaned by their
fixtures. Failure logs and final results are retained locally in `/tmp/phase4b-*.log`;
private browser report/screenshot and source parity records are under ignored
`data/vps-private/`. No generated dataset, token or private key was added to git.

VPS operations used the existing SSH control socket at
`/tmp/execplus-phase3-ssh` and target `administrator@173.208.151.137`. The source
bundle contains git-visible source only, excluding ignored secrets and datasets.
Commands executed from `/sdb-disk/OISOL_ExecPLUS/source` included:

```bash
sudo docker tag oisol-execplus/api:demo oisol-execplus/api:pre-phase4b
sudo docker tag oisol-execplus/web:demo oisol-execplus/web:pre-phase4b
sudo docker compose -f deploy/vps/compose.yaml build api web
sudo bash deploy/vps/backup.sh
sudo docker compose -f deploy/vps/compose.yaml run --rm -T operator python -m alembic upgrade head
sudo docker compose -f deploy/vps/compose.yaml up -d api web
sudo install -m 644 deploy/vps/execplus-refresh.service deploy/vps/execplus-refresh.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now execplus-refresh.timer
sudo systemctl stop execplus-refresh.timer
sudo docker compose -f deploy/vps/compose.yaml build api
sudo docker compose -f deploy/vps/compose.yaml run --rm -T operator \
  python -c 'import execplus.main; print("API import passed")'
sudo docker compose -f deploy/vps/compose.yaml up -d api
sudo systemctl start execplus-refresh.timer
sudo docker compose -f deploy/vps/compose.yaml exec -T postgres \
  psql -U execplus -d execplus -Atc 'select version_num from alembic_version'
curl -fsS http://127.0.0.1:18401/health/ready
sudo docker compose -f deploy/vps/compose.yaml run --rm -T operator \
  python scripts/provision_demo.py --confirm-fictional-demo --output /run/execplus-demo/sessions.json
sudo systemctl show execplus-refresh.service -p Result -p ExecMainStatus -p ActiveState
sudo journalctl -u execplus-refresh.service -n 8 --no-pager -o cat
```

The expired private session set was renewed and copied securely to the ignored
local session file. Then, locally:

```bash
node scripts/check_refresh_demo.mjs data/vps-private/sessions.json data/vps-private/phase4b-eight-browsers.json
```

Backup **20260930T141138Z** passed database/object archive checksums. Previous source
is `releases/pre-phase4b-source`; old images use `pre-phase4b`. Do not discard new
user metadata in a blind downgrade. Corrected API build and worker evidence are
under `ops/phase4b-*.log` and the release evidence directory.

## Files and remaining boundaries

New domain/service/routes: `domain/refresh.py`, `application/services/refresh.py`,
`application/services/monitoring.py`, `presentation/routes/refresh.py`. New migration:
`0012_refresh_monitoring.py`. New coverage: `test_refresh.py`, the real browser
refresh journey, and `scripts/check_refresh_demo.mjs`. Persistence ports/schema,
composition, readiness, fixture setup, historical analytics context, active-source
selection/catalog, CLI, explicit runtime dependency and web navigation were updated.
The new `refresh-panel.tsx`, CSS, worker units and backup lock complete the workflow.
This ledger, contract, audit, roadmap, README, architecture and AGENTS handoff describe it.

4B is scoped to staged files, declared coverage and private in-app notifications.
There is no automatic desktop sync, live source connector, causal inference,
calibrated anomaly detector or new email delivery. Forecasts (4C), exports (4D),
connectors (4E), all Phase 5 production evidence and frozen Phase 6 work remain.


The final evidence archive is checksummed under `ops/phase4b-evidence/`. A final
read-only API rehearsal checks the eight existing fictional workspaces, current
0.50 totals, 0.20 deltas, original 0.30 receipts and delivered/read notifications;
it creates no additional demo workspaces. The disposable `execplus-phase4b-postgres`
and `execplus-phase4b-minio` containers are stopped after verification.
