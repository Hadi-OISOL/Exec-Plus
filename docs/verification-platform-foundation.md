> **File use case:** Acceptance ledger for the October 4 additive platform foundation.
> **What it does:** Records scope, commands, failures, compatibility evidence and private release limits.

# Foundation A verification — October 4, 2026

Foundation A is **Complete for local/test and the private demo**. The VPS release
and eight-user check passed. The [preimplementation audit](platform-foundation-plan.md) contains
the A–H plan published before coding. This slice implements the useful foundation
of the supplied proposal, not its advanced statistics, arbitrary Python, machine
learning or connector ambitions. Earlier uncommitted September 30 and October 2
changes remain preserved on `phase2`; nothing has been committed, pushed or merged.

## Delivered contracts and changed areas

- Domain/application: typed artifact/capability and quality projections, bounded
  compute broker, strict supported analysis plans, durable conversation job service,
  worker, cancellation and actual action events. Existing validators own calculation.
- Infrastructure/presentation: migration **0013**, transactional jobs/attempts/events,
  fenced publication, private job/artifact APIs, provider-attempt bounds, DuckDB
  input/result/thread budgets, readiness, composition and a sanitized worker CLI.
- Web: resumable chat, real action timeline, explicit cancellation, Simple/Expert
  evidence presentation and lazy source capability/quality inspection. No hidden
  model reasoning, generated percentages or fake stages. AI summaries retain their
  existing synchronous operation.
- Operations: `make jobs`, isolated browser worker, bounded private VPS worker,
  backup coordination, minimal-image check and the existing eight-user rehearsal.
- Documentation: ROADMAP, AGENTS, README, architecture, runbook, this ledger and
  [jobs](conversation-jobs.md), [compute](compute-broker.md) and
  [artifact/quality](platform-artifacts-quality.md) contracts, plus
  [ADR 0008](decisions/0008-durable-analysis-foundations.md).

New behavior is additive. Profile-v1/v2 reconstruction, source dialects, exact
decimal and wide-integer strings, historical receipts and legacy synchronous
`/ask` remain. Migration tests compare every seeded legacy table before/after
0012→0013, reopen a retained answer and create new work. New composite foreign
keys reject cross-workspace jobs and wrong turn/job relationships.

## Local acceptance evidence

| Check | Result |
| --- | --- |
| Complete backend/architecture suite with isolated PostgreSQL/MinIO | **689 passed**, 446.73 seconds |
| Reader cleanup and final CLI privacy/SIGTERM additions collected afterward | **9 passed**; 698 distinct backend tests verified in total |
| Frontend unit tests | **7 passed**, five new |
| Final real-service browser suite, including live mixed chat | **18 passed, 0 skipped**, four new lifecycle journeys |
| Ruff / mypy / compile / whitespace | Passed; mypy checks **128 files** |
| Web lint / types / production build | Passed |
| Clean API image imports and eight concurrent exact computations | Passed; network disabled, no NumPy/Pandas/PyArrow |
| Deployed browser rehearsal | **8/8 passed**, 56 replays, 18 jobs, 204 events, 32 private-access denials |
| Original profile-v1/v2 receipts after migration | **2/2 passed**, original result checksums verified |
| Deployed worker-aware backup and subsequent chat job | Passed; services restarted and a new job completed |

The 97 new backend cases comprise 19 typed-plan, 21 durable-job lifecycle, two
reader cleanup, seven CLI privacy/shutdown, 16 artifact/quality, 24 compute-broker,
six backup coordination and two migration preservation/isolation cases. Coverage
includes duplicate submissions, private-owner and tenant access, revoked access,
late publication, pre-start crash recovery, started-work interruption, cancellation,
source changes, model retries, bounds and retained legacy evidence.

The first full browser run had 16 passes and two failures: an old 20-second wait
expired during a real model-planning call, and an old global evidence selector
matched two panels. Assertions now wait for the actual terminal job and target the
intended evidence; exact numerical/citation expectations were retained. Both cases
passed individually, then all 18 passed together. The final measured average took
24,335 ms overall, including 22,208 ms planning. This is a responsiveness limitation,
not evidence of a speed improvement. Failed logs remain retained.

Review additionally caught late publication after the execution deadline, status
polling preventing safe pre-start lease recovery, uncounted provider retries, and
possible private SQL parameters in worker fatal tracebacks. These were repaired
with regression tests before release. A new script header exceeded Ruff's line
limit; it was corrected and all static checks rerun.

## Commands and reproducibility

Tests use dedicated local containers `execplus-foundation-postgres` on loopback
15433 and `execplus-foundation-minio` on 19000; fixtures and browsers create isolated
schemas/buckets. Other running applications were preserved. Private live-model
configuration comes from ignored `.env`; no credential appears in this ledger.

```bash
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus \
EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 \
python3 -m pytest

EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus \
EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 \
python3 -m pytest apps/api/tests/test_job_cli_privacy.py apps/api/tests/test_job_reader_cleanup.py -q

python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
python3 -m compileall -q apps/api/src migrations scripts deploy/vps
git diff --check
npm run lint:web
npm run typecheck:web
npm run test:web
npm run build:web

EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus \
EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 \
EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py

docker build -t execplus-foundation-api:check -f apps/api/Dockerfile .
docker run --rm --network none \
  -v /home/it-admin/OISOL/scripts/check_minimal_compute.py:/app/scripts/check_minimal_compute.py:ro \
  execplus-foundation-api:check python scripts/check_minimal_compute.py
```

The initial local image preceded the final CLI-only privacy repair; the release
image includes that repair and repeated clean-image checks successfully. The first
staged VPS check failed because a restrictive extraction umask left root-owned
application files unreadable by the non-root runtime. The API Dockerfile now makes
packaged application files readable/traversable; the corrected image passes imports
and eight isolated exact computations. The failure log is retained, and activation
used the corrected image. `next-env.d.ts`'s
purpose header and production type references were restored after Next's build.
Logs/screenshots are ignored private artifacts under `data/foundation-20261004/`
and `data/vps-private/`. They are not datasets or credentials to commit.

## Private deployment checkpoint

Before replacing source, the existing release was preserved at
`releases/pre-foundation-20261004/source`, with API/web image tags
`pre-foundation-20261004`. Backup **20261004T111433Z** verified checksums for the
PostgreSQL dump and object archive. Configuration checksums are private beside the
checkpoint. The API and worker share image
`sha256:565c842cda3a9965d7fba2c9c920f54c5ca17c93ae53ef04c96fb8e243954915`;
the web image is
`sha256:4b591ab1d8c476d4f120892cf4031a9c1f1a690f3ff69e7d339fceeaa5f4e03e`.
The corrected source archive's SHA-256 is
`e3dfbd5a61433e4c227cfe92abb99b53f9f78c303e371c1f29d131dc843ef39d`;
acceptance documentation was updated afterward without changing executable code.

Migration 0013 is now running with healthy API, web and conversation-worker
containers. An aggregate row hash and row-count comparison preserved all **35
legacy tables**, including **2,497 query receipts and 85 conversation turns**.
The comparison ran with application writers stopped and refresh excluded by the
maintenance lock. All three private environment-file checksums are unchanged.

The first deployed browser run timed out before sign-in for all eight users. It
created no jobs or model calls. The restricted local SSH tunnel stalled while
direct VPS readiness remained healthy and containers had zero restarts. The owned
tunnel was reconnected; a new readiness request succeeded. That failed report is
retained as `vps-eight-users.json`. An original-receipt request also timed out over
that tunnel; both profile-v1 and profile-v2 replays passed after reconnection.

The fresh **8/8** rehearsal is `vps-eight-users-final.json`. Each account replayed
all seven discovery receipts; all eight balance totals matched **6,431,836**.
Across the journeys, **18 jobs succeeded**, **204 ordered allowlisted events** were
checked and **32 attempts** by another account to read status/events/results or
cancel a job correctly returned 404. Ten turns used the live model. Filtered record
and aggregate follow-ups, retail quality guidance and desktop/320/390 layouts passed.
The eight total jobs overlapped, including waiting time; completion took
**12.072–27.777 seconds** from server creation to completion. This does not imply
eight simultaneous executions. Separate queue/planning durations were not collected
by this deployed checker and must not be inferred. Full journeys took 59.620–91.717
seconds. The run is a functional rehearsal, not a sustained-load benchmark.

Independent read-only release checks matched **172/172 executable/config files**
and **98/98 API modules** in both the image source and installed package to local
files. Startup logs had zero error indicators, API/jobs had no unexpected restarts,
and all six existing ExecPlus listeners remained loopback-only. The new worker
opened no port. The changed-file check found no known credentials, private keys or
unintended generated/data artifacts. Existing model/private environment checksums
were unchanged.

After the browser run, the updated backup stopped API/jobs before storage, verified
dump/object checksums and restarted the services. Backup **20261004T113138Z** is the
first checked 0013 checkpoint. A fresh conversation job then completed and its
answer resolved successfully. This verifies writer coordination and restart, not
an off-server restore drill. All eight production gates still block release.

Exact final private browser and operational commands:

```bash
umask 077
set -o noclobber
node scripts/check_data_partner_vps.mjs \
  data/vps-private/sessions.json data/vps-private/partner/targets.json \
  data/foundation-20261004/vps-eight-users-final.json \
  > data/foundation-20261004/vps-eight-users-final.stdout.log 2>&1

# On the VPS; these private scripts retain the exact archive/build/migration commands.
bash /sdb-disk/OISOL_ExecPLUS/ops/foundation-build-final.sh
sudo -n bash /sdb-disk/OISOL_ExecPLUS/ops/foundation-activate.sh
sudo -n bash /sdb-disk/OISOL_ExecPLUS/source/deploy/vps/backup.sh
curl -fsS http://127.0.0.1:18401/health/ready

# In the repository; expected exit 1, all eight gates blocked.
python3 scripts/check_production_gates.py
```

Operational logs are `ops/foundation-api-final-build.log`,
`foundation-web-final-build.log`, `foundation-minimal-final.log`,
`foundation-migration.log`, `foundation-activation.log` and
`foundation-worker-backup.log`. Initial packaging and tunnel failures remain
separate artifacts. Sessions were renewed privately and still expire after eight
hours. No model configuration, network exposure, other application or production
gate was changed.

## Remaining limits

Conversation jobs are the first durable workflow; ingestion, discovery, reports,
refresh and AI summaries have not all migrated to this queue. Claims are fenced;
safe pre-start interruptions may retry, while started work fails conservatively.
This is not exactly-once physical execution. Cancellation waits for cooperative
reader/query cleanup and is not a process-kill guarantee. The compute budget is
not an OS-level RSS bound, billing quota or full sandbox.

Artifacts are authorized metadata projections, not byte-integrity proof. Quality
heuristics are labelled suggestions, not confirmed business errors. No new input
format, statistics method, arbitrary plan execution, sandbox, ML, vector provider,
connector or remote engine is enabled. Preparation B–Integration F retain their
dependency and evaluation gates. Phase 4C–4E remain Planned; Phase 6 remains Frozen.
All eight production gates must remain blocked. A short eight-user rehearsal
cannot establish sustained capacity, customer accuracy or production readiness.
