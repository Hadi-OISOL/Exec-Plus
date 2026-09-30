> **File use case:** Evidence ledger for the private eight-user VPS demonstration.
> **What it does:** Records the inspected deployment, passing checks, failed experiments and remaining limits.

# VPS verification — 2026-09-28

This records the initial Qwen-only deployment. The subsequent interactive workspace
and DeepSeek-primary/Qwen-helper release is recorded in
[conversational explorer verification](verification-conversational-explorer.md).
Historical measurements below are retained as evidence for that earlier deployment.

Scope: fictional-data demonstrations over restricted SSH tunnels. The user deferred
domain/public customer access. Phase 3 and all production release gates remain open.
The source is the uncommitted Phase 2/3 working tree on branch `phase2`, based on
`7d70cd7`; deployment transferred that snapshot, not a claimed GitHub release.

## Inspected and deployed

- VPS: Ubuntu 22.04, 32 logical Xeon CPU cores, 125 GiB RAM, Tesla P100 16 GiB.
- Model service: independent Ollama 0.20.0 instance, loopback 11450, eight slots,
  4096 context tokens per slot, queue 16, one loaded model, thinking disabled.
- Selected private-demo model: `qwen3:4b`, original Qwen3-4B, Q4_K_M.
  Manifest digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
  Observed loaded GPU memory was approximately 7.5 GiB with this slot configuration.
- Compared `qwen3:4b-q8_0`, manifest digest
  `6461746fd6b5a2327ba63d5cd1359af119852d82aa8c981efe948d1868a4dc20`.
  Observed loaded GPU memory was approximately 9.2 GiB; it was not selected.
- API: Python 3.12.14, two workers, loopback 18401; web: production Next.js build,
  loopback 18400. Database: PostgreSQL 16.15, dedicated loopback 18432. Dedicated
  MinIO API/console bind to 18490/18491. Ports are separate from other VPS apps.
- Eight individual application identities in an eight-seat workspace. Three
  versioned synthetic tables and six shared fictional policy documents were seeded.
- Eight independent SSH keys use a forwarding-only OS identity. All eight keys
  reached readiness through their allowed forward. Shell commands, database
  forwarding and reverse forwarding were denied. Administrator SSH policy was
  rechecked separately; the pre-existing application on 18300 still returned HTTP 200.
- Base-image digests are pinned in `deploy/vps/compose.yaml`. No model weights,
  private credentials, private keys or generated datasets are tracked by Git.

## Checks and outcomes

| Check | Result |
| --- | --- |
| Full backend suite on real VPS PostgreSQL/MinIO | 298 passed, one existing warning, no skips |
| Ruff | Passed, including deployment Python helpers |
| Mypy | Passed, 88 source files |
| Frontend ESLint / TypeScript | Passed |
| Frontend unit tests | 2 passed |
| API/web container builds | Passed |
| Initial repeated eight-user API journeys after summary fix | 24/24 passed, 168 successful requests |
| Eight distinct analytical questions, three concurrent rounds | 24/24 passed, 168 successful requests |
| Eight concurrent deployed Chromium sessions | 8/8 passed |
| Final pinned-image rollout smoke | 8/8 varied API journeys and 8/8 browser sessions passed |
| Database/object backup | Checksums passed; daily timer enabled |
| Isolated restore | Migration 0007 and all nine seeded objects verified |
| Production preflight | Remains blocked; no production gate was cleared |

The initial successful API run took 38.03 seconds across three rounds of eight users.
Per-request p95 was 6777.53 ms. Every journey checked identity, a dashboard, a model
question returning exactly 10000 from the sample data, replay, an evidence-backed
summary, document search and citation access. This is a small demo workload, not a
load guarantee for arbitrary 20 MB files or simultaneous use of other GPU applications.
Browser checks used eight separate contexts and real services, including the threaded
question path and exact citation text. No API responses were mocked.

A stronger follow-up used eight distinct questions: revenue/cost totals, maximum,
minimum, average, count and two filtered sums. All 24 journeys and 168 requests passed
in 37.85 seconds, with request p95 6736.02 ms. Source-text/citation equality was checked
explicitly in this run. Expected values come from the immutable fictional sample;
the model only proposes plans and the server executes and replays them.
After the final pinned-image rollout, the varied eight-user smoke passed again in
12.81 seconds (request p95 6759.11 ms); the eight-browser check also passed again.

The restore used a fresh temporary database and a separate MinIO instance loaded
from the snapshot. Every recovered upload and document matched its recorded SHA-256.
Temporary services/database were removed afterward. Backups remain on the same VPS;
off-site disaster recovery, retention and production restore objectives remain open.

## Model comparison and failed experiments

| Fictional evidence-selection evaluation | Passed | Median request latency |
| --- | --- | --- |
| Original Q4 prompt, initial run | 19/20 | 2003.975 ms |
| Q4 with experimental ambiguity emphasis | 17/20 | 2074.16 ms |
| Q8 with the original prompt | 16/20 | 1841.73 ms |
| Q4 original prompt restored, final confirmation | 19/20 | 2018.56 ms |

The failed prompt experiment was reverted. Final Q4 missed `q19`, “Who approves
requests?”, by returning several process-specific approvals instead of asking
which process was intended. Q8 also failed q13, q18 and q20. Retain these failures;
19/20 is not a production-quality pass or a representative accuracy claim.
The application document-search screen returns authorized source passages rather
than free-form answers from this experimental evidence-selection evaluator.

The initial live summary workload passed only 1/8 full journeys: Qwen often copied
the input evidence map rather than returning its ID list. Summary requests now use
short temporary aliases with an explicit output shape. The server validates every
alias and maps selections back to the original immutable query IDs. It still renders
all claims/numbers from executed evidence. Four added unit cases verify valid mapping,
ordering and refusal of unknown/duplicate aliases; existing grounding tests still pass.

The first browser harness expected fixed decimal display for an integer result and
used an insufficient assertion timeout under parallel startup. The harness was corrected
to accept the exact integer or equivalent trailing-zero representation; all eight
sessions then passed. Application numerical validation was not weakened.

Docker Hub initially failed due VPS network routing. The build uses the reachable
ECR mirror of Docker Official Images, with inspected digests. A model-service startup
error caused by a read-only default home was fixed by assigning the dedicated service
user its own model-directory home. Other model runtimes were not changed.

Local PostgreSQL on port 55433 was stopped, so the initial new integration test could
not connect. Running the full suite across the SSH database tunnel was interrupted
because network round trips dominated test time. The full suite then passed in a
disposable container beside the VPS services, using isolated schemas/buckets and
private credentials. It did not run against or reset the demo workspace.

## Reproduction commands

Run static checks from the local repository:

```bash
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
npm run lint:web
npm run typecheck:web
npm run test:web
node --check scripts/check_vps_browser.mjs
bash -n deploy/vps/backup.sh deploy/vps/prepare_tunnels.sh
git diff --check
```

The deployment snapshot was made with `git ls-files -z --cached --others
--exclude-standard | tar --null -T - -czf /tmp/oisol-execplus-demo-source.tar.gz`,
copied by SCP, and extracted into the dedicated `source` directory. `.env`, private
keys, generated data and local dependency directories were excluded by Git rules.
No password was put in that archive, a repository file or a shell command argument.

On the VPS, from `/sdb-disk/OISOL_ExecPLUS/source`:

```bash
python3 deploy/vps/initialize.py
sudo docker compose -f deploy/vps/compose.yaml config --quiet
sudo docker compose -f deploy/vps/compose.yaml build
sudo docker compose -f deploy/vps/compose.yaml up -d postgres storage
sudo docker compose -f deploy/vps/compose.yaml run --rm operator python scripts/wait_infra.py
sudo docker compose -f deploy/vps/compose.yaml run --rm operator python -m alembic upgrade head
sudo docker compose -f deploy/vps/compose.yaml run --rm operator python -m execplus.manage init-storage
sudo docker compose -f deploy/vps/compose.yaml up -d api web
sudo docker compose -f deploy/vps/compose.yaml run --rm operator \
  python scripts/provision_demo.py --confirm-fictional-demo --output /run/execplus-demo/sessions.json
sudo bash deploy/vps/prepare_tunnels.sh
sudo bash deploy/vps/backup.sh
```

The systemd units in `deploy/vps/` were installed under `/etc/systemd/system/`,
followed by `systemctl daemon-reload`, enabling `execplus-model.service` and
`execplus-backup.timer`. See the [runbook](vps-demo-runbook.md) for prerequisites.

Backend suite runner (temporary container, real isolated PostgreSQL schemas and buckets):

```bash
sudo docker run --rm --network host \
  --env-file /sdb-disk/OISOL_ExecPLUS/secrets/app.env \
  -v /sdb-disk/OISOL_ExecPLUS/source:/verification:ro -w /verification \
  --user root --entrypoint sh oisol-execplus/api:demo \
  -c 'pip install "pytest>=8.2,<9" "pytest-asyncio>=0.23,<1" && python deploy/vps/verify.py'
```

Model evaluation used the operator's additional SSH forward from local 18450 to
VPS 11450. For Q8, substitute `qwen3:4b-q8_0` in both model settings:

```bash
EXECPLUS_LLM_MODE=local \
EXECPLUS_LLM_BASE_URL=http://127.0.0.1:18450/v1 \
EXECPLUS_LLM_API_KEY= \
EXECPLUS_LLM_SMALL_MODEL=qwen3:4b \
EXECPLUS_LLM_LARGE_MODEL=qwen3:4b \
EXECPLUS_LLM_REASONING_EFFORT=none \
EXECPLUS_LLM_JSON_MODE=true \
python3 scripts/evaluate_demo_model.py --output data/phase3-demo-v1/qwen-vps-q4-final.json

python3 scripts/check_demo_load.py --sessions data/vps-private/sessions.json \
  --rounds 3 --output data/phase3-demo-v1/vps-load-varied.json
node scripts/check_vps_browser.mjs data/vps-private/sessions.json \
  data/phase3-demo-v1/vps-browser-v2.json
```

Generated evidence stays ignored under `data/phase3-demo-v1/` and is copied to the
VPS model `evaluations` folder. Backend/build logs are under the VPS `ops` folder.
Never put the private `data/vps-private` files into a verification report or archive.

## Remaining limits

Known model ambiguity failure; only fictional data evaluated; 4096-token model
context; shared GPU; short burst tests rather than sustained customer-load evidence;
operator-issued eight-hour sessions; domain/HTTPS and public identity not configured;
email delivery disabled; reference retrieval still uses deterministic hashed vectors;
same-disk backups only; no billing/subscription rollout. The existing
[production ledger](production-readiness.json) remains authoritative before customer launch.
