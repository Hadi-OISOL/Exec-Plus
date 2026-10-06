> **File use case:** Records evidence for the October 6 forecasting priorities.
> **What it does:** Separates implemented private-demo behavior, measured checks and remaining limitations.

# Phase 4C and priority audit history — October 6, 2026

**Status:** Complete for the approved local/test and private-demo scope. Phase 4C
and the priority audit-history view are verified and deployed; Phase 4 as a whole
remains In progress because exports and connectors remain unfinished.

## Delivered scope

VC items 34–36 add basic daily/monthly forecasting, chronological backtest error
measurement, a naive benchmark and saved actual-versus-forecast comparisons.
Item 37 reuses existing scheduled staged-file refresh; a new integration case
activates a scheduled replacement and compares its actuals with an unchanged forecast.
Item 38 adds deterministic commentary on actual period changes, estimates, ranges
and observed errors. Item 39 brings the searchable, permission-filtered audit
history forward from 4D. Exports and connectors remain separate work.

Upload-first exploration now offers descriptive, basic predictive and all-supported
analysis choices. Prescriptive analysis is labelled planned and unavailable. A new
fictional 90-day forecasting sample is additive; all original sample versions remain
unchanged. Forecasting requires confirmed meaning, units and explicit complete-period
coverage. It does not silently turn inferred metadata into approved business meaning.

See [the gap audit](phase4c-gap-audit.md), [forecast contracts and model trial](phase4-forecasting.md)
and [audit visibility contract](audit-history.md).

## Automated evidence

- The final full backend/architecture suite passes **816 cases**, including 118
  new cases, in 399.33 seconds. The runner reports one warning with warnings hidden
  by the repository's existing pytest configuration.
- 39 new numerical-method cases cover temporal leakage, exact actuals, zero/negative
  data, seasonal eligibility, missing periods, uncertainty and partial comparisons.
- 17 forecast integration cases use real PostgreSQL/MinIO, including exact daily
  sums, weighted monthly averages, immutable reopening, scoped ownership, changed
  meaning, invalid coverage, tampered results and scheduled refresh.
- 36 additional hardening cases cover malformed calendar evidence, receipt/source/
  method/filter substitution, off-loop reads, cancellation cleanup, source tampering,
  revocation and definition changes before actual-source computation.
- Eight persistence/migration cases and sixteen audit-history cases verify tenant
  constraints, retained 0013 data, private visibility, current sharing, bounded
  pagination and literal search handling. Two sample coverage cases are additive.
- All 20 real-service browser journeys pass, including existing live mixed chat and
  two new forecasting journeys. Forecast creation, later comparison, original replay,
  audit searches, insufficiency and layouts at 320/390/1280 pixels are covered.
- Nine frontend tests, Ruff, mypy over 136 source files, TypeScript, ESLint and the
  production web build pass. The generated Next.js purpose header is restored.
- The clean non-root API image passes imports and eight concurrent exact/calendar
  forecasting journeys: 32 distinct query IDs, eight forecasts and pending comparisons,
  with no NumPy, pandas, PyArrow or network access.

The first full backend run had 815 passes and one obsolete assertion expecting four
demo samples. The new fifth sample explains the failure; the corrected provisioning
suite passes 6/6. The final full run passes 816/816 and is retained separately. Earlier browser selector
failures and the discovered mobile navigation overflow are retained; the corrected
two-journey run and full twenty-journey run pass.

## Model exploration

Seven identical chronological synthetic fixtures compare the runtime baselines,
fixed ARIMA(1,1,0)/(0,1,1) candidates and Prophet in an isolated optional environment.
Prophet improves the noisy-trend fixture; simple methods exactly reproduce several
clean trend/seasonal examples. Abrupt changes remain difficult. ARIMA convergence
failures and the initial Prophet/CmdStanPy compatibility failure are retained.
These trials do not establish universal superiority or customer forecast quality.
No scientific dependency, model endpoint, credential or runtime judge changed.

## Private VPS release

Baseline branch `phase2`, commit `9c2445d`, was clean before this work. A remote
source comparison found only an obsolete “Phase 3 · In progress” landing badge and
its test, absent from that local baseline. The current local landing page replaces
that stale deployment; the old source is preserved in the checkpoint.

- Prior source: `/sdb-disk/OISOL_ExecPLUS/releases/pre-phase4c-20261006/source`.
- Prior API/web tags: `pre-phase4c-20261006`.
- Pre-release checked database/object backup: `20261006T063824Z`.
- Candidate built separately under `releases/phase4c-candidate-20261006` and passed
  the clean-image computation check before activation.
- Migration **0014** adds private forecast/comparison tables and source-identity
  constraints. All **38 existing data tables**, including **2,909 query executions**,
  retained their row counts and aggregate hashes; only the migration version changed.
- API, web and jobs are running with dependency-aware readiness. The maintenance
  lock excludes the refresh worker during migration. The initial SSH migration
  wrapper consumed remaining script input after Alembic; remaining fingerprint/start
  steps were resumed with explicit closed stdin, then verified successfully.
- Four original live receipts pass independent typed-checksum comparison: two
  profile-v1 and two profile-v2 results. No historical source was replaced.
- Eight sessions were renewed into ignored `data/vps-private/sessions.json`; do not
  publish them. Existing loopback ports and model configuration remain unchanged.
- The first deployed eight-user harness timed out on an exact label selector for a
  rendered select control; it submitted no forecasts. The corrected combobox-role
  selectors passed a focused form-fill check. Both failed and corrected reports are
  retained, rather than rewriting the initial result.
- The refresh service reports `Result=success`, `ExecMainStatus=0`; refresh and
  backup timers remain active.
- The fresh deployed rehearsal passes **8/8** users: eight forecasts, eight saved
  actual comparisons after staged refresh, eight unchanged originals, sixteen saved
  result reopens and **48 exact receipt replays**. Sixteen cross-user 404 denials,
  sixteen private-audit absence probes and eight audit UI searches pass. Layouts
  at 1440/390/320 pixels pass for every user; 24 private screenshots are retained.
  The run took 55.048 seconds in total and is a short functional rehearsal, not a
  sustained-load or forecast-speed benchmark. Its refreshed snapshot was manually
  activated; the scheduled activation path is covered by the integration test.
- Post-release backup **`20261006T065810Z`** stopped API/jobs before storage,
  verified both database and object-archive checksums and restarted the writers
  after storage/API health checks. This is an on-server private-demo backup;
  it does not close the off-server recovery or production restore gates.

Private evidence is retained under `data/vps-private/phase4c/`; numerical model
trials are under `data/forecast-evaluation/`; local browser screenshots and failed
attempts are under `data/phase4c/`. None is committed as customer data or credentials.

## Commands

```bash
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus \
EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 -m pytest
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus \
EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 \
EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py
npm run lint:web
npm run typecheck:web
npm run test:web
npm run build:web
python3 scripts/check_production_gates.py
node --check scripts/check_forecasts_vps.mjs
node scripts/check_forecasts_vps.mjs data/vps-private/sessions.json \
  data/vps-private/phase4c/eight-forecasts-20261006-final.json
git diff --check
```

On the private VPS, Compose commands use `deploy/vps/compose.yaml`: `build api web`,
`stop api jobs`, `run --rm -T operator python -m alembic upgrade head`, then
`up -d api web jobs`. The clean-image command is
`docker run --rm --network none oisol-execplus/api:demo python scripts/check_minimal_compute.py`.
Backups use `sudo bash deploy/vps/backup.sh`; sessions use the existing
`scripts/provision_demo.py --confirm-fictional-demo --output /run/execplus-demo/sessions.json`.
Deployment logs retain complete command outcomes without publishing secrets.

## Boundaries

Forecasts are estimates from explicitly declared complete history. Their ranges are
heuristic and have no guaranteed coverage. Single chronological holdouts and short
eight-user checks are not representative-customer quality or sustained-load evidence.
Forecast creation/comparison is explicit in the Forecasts view; it does not schedule
automatic retraining or enable arbitrary predictive/prescriptive chat execution.
Refresh consumes deliberately staged files; external connectors remain 4E.

The production preflight deliberately exits 1 with all eight gates blocked. Phase 5
must still establish representative quality, security, privacy, recovery, identity,
delivery and operational acceptance. Phase 4D exports, 4E connectors and frozen
Phase 6 advanced/prescriptive methods are not implemented by this release.
