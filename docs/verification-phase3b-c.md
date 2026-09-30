> **File use case:** Records unified-conversation, catalog and offline evaluation evidence.
> **What it does:** Separates tested behavior, candidate rejection and pending human/production review.

# Phase 3B–3C verification — 2026-09-30

The prior stop was a verified **3A** checkpoint, not whole Phase 3 completion.
Work resumed on local `phase2`, preserving the teammate commit and all pre-existing
uncommitted changes. No commit, push or merge was performed.

## Gap audit and delivered behavior

The previous release had separate document search, data-only chat, no reopened
answer UI, and no durable retry claim. It also lacked a source discovery catalog
and measured Parquet/learned-retrieval candidates. Slice 3B now supports one bounded
data step plus one cited document step, explicit partial results and private history.
Migration 0010 adds request IDs and durable turn states with scoped evidence references.

Slice 3C adds current authorized metadata discovery and reproducible offline
benchmarks. Learned retrieval is rejected; Parquet is promising but not adopted
without a serving lifecycle. Existing source reads are retained, with no persistent
answer or derived-artifact cache. See [contracts](phase3-unified-conversation.md)
and [ADR 0007](decisions/0007-representation-and-judge-trials.md).

At this delivery checkpoint, Phase 3D had an offline fixed-fixture judge harness
and safety tests. Its first trial failed adoption criteria, and human label review
was pending. The later [reviewed Phase 3D assessment](verification-phase3d.md)
closed Phase 3 for the private-demo scope with the judge disabled. The measurements
below remain the earlier 3B–3C release evidence. Phase 4 has not started; all eight
production gates remain separate and open.

## Local checks

| Check | Result |
| --- | --- |
| Full backend suite | **376 passed**, one existing dependency warning, 91.03 s |
| Frontend tests | **2 passed** |
| Real PostgreSQL/MinIO browser journeys | **8 passed**, 42.8 s |
| Live combined browser answer | Exact 0.30, document citation, re-sign-in/history replay, mobile layout |
| Catalog browser interaction | Negative search, matching source, opening the dataset |
| Ruff / mypy / frontend lint / TypeScript | Passed; mypy 100 files |
| Production Next.js build | Passed |
| Parquet parity | Three table sizes passed; detailed costs in ADR 0007 |
| Search evaluation | Reference 20/21, learned candidate 18/21; rejected |
| Judge preliminary evaluation | 8/12 strict label matches, three timeouts, one misclassified defect; not adopted |

Environment: isolated PostgreSQL 16.10 and MinIO RELEASE.2025-09-07T16-13-09Z,
Python 3.10.12, Node 22.22.2. Existing applications were not reused or reconfigured.
The optional live browser case requires `EXECPLUS_BROWSER_LIVE_MODEL=1`; otherwise
CI deliberately skips it and still runs deterministic/service tests.

The final stable-ID search run used CPU only: median 0.30 ms reference / 94.33 ms
learned, maximum 0.53 / 194.47 ms, whole-process peak RSS 790,504 KiB. It made no
external inference calls. The initial and repeat runs had identical quality results;
timing differences demonstrate warm-up/host sensitivity, not additional quality evidence.

Thirty-three added backend cases since 3A include 21 unified-conversation cases,
two catalog cases and ten offline-evaluation safety/parity cases. They cover mixed
plans, exact decimals, malformed/injected evidence, missing/conflicting documents,
private history, source/definition changes, revocation between steps, concurrent
retry, failed/expired/late turn claims, and deleted/corrupt/restored citation bytes.
Judge tests reject arbitrary private input and malformed feedback, retain outages,
and prove that offline evaluation never adopts a runtime judge or changes answers.

Initial checks caught and fixed the JSON-mode prompt requirement for document
selection, a test that overlooked memory-only sign-in after refresh, the catalog
preference test's wrong HTTP method, and a restore test's wrong response-envelope
expectation. All listed final checks use the corrected source. No failing case was
removed to obtain the reported result.

## Files in this delivery

- Application: conversation contracts, document answer service, intent router,
  threads, knowledge citation timestamps, catalog, bootstrap and readiness.
- Domain/persistence: bounded mixed grammar, turn states/evidence, repository ports
  and methods, schema and migration `0010_unified_conversation.py`.
- HTTP: mixed answer serialization, private history/replay and catalog endpoints.
- Web: combined evidence, history and retry UI, catalog, workspace integration/CSS.
- Tests: `test_unified_conversation.py`, `test_catalog.py`,
  `test_phase3_evaluations.py`, fixture/readiness updates and browser coverage.
- Evaluation/operations: `evaluate_representations.py`, `evaluate_advisory_judge.py`,
  `check_unified_demo.mjs`; live-model browser flag.
- Documentation: this ledger, conversation contract, benchmark protocol, judge
  review sheet, ADR 0007, roadmap, handoff, README, architecture and VPS runbook.

The Git diff also contains earlier uncommitted Phase 2/3/VPS work. It is not all
attributable to this continuation. Generated data/results remain ignored.

## Exact verification commands

```bash
git status --short
git branch --show-current
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 make check
EXECPLUS_BROWSER_LIVE_MODEL=1 EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 scripts/check_browser.py
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
python3 -m pytest apps/api/tests/test_phase3_evaluations.py --tb=short
python3 scripts/evaluate_representations.py --output data/phase3-evaluation/storage.json
USE_TF=0 TRANSFORMERS_NO_TF=1 CUDA_VISIBLE_DEVICES='' TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 python3 scripts/evaluate_representations.py --encoder /home/it-admin/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/c9745ed1d9f207416be6d2e6f8de32d1f16199bf --reranker /home/it-admin/.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L-6-v2/snapshots/c5ee24cb16019beea0893ab7796b1df96625c6b8 --output data/phase3-evaluation/search.json
python3 scripts/evaluate_advisory_judge.py
node --check scripts/check_unified_demo.mjs
```

`make check` runs Ruff, frontend lint, mypy, TypeScript, pytest, frontend tests and
the production build. Judge raw cases were retained; summary counting was corrected
to distinguish an undetected defect from a wrong issue label, without another model
request. The initial timing/response failures remain in the saved report.

## Private VPS release

API/web builds succeeded and the private VPS now runs migration **0010** with healthy
PostgreSQL/object-store readiness. All **5/5** deployed unified checks passed:
fictional source creation, live mixed answer/citation, private history reopening,
retry reusing the same turn/execution, and catalog/mobile navigation.

Backup `20260930T095357Z` verified both database and object checksums before migration.
Previous images are tagged `pre-phase3bc`; previous source is retained at
`/sdb-disk/OISOL_ExecPLUS/releases/pre-phase3bc-source`. The existing eight sessions
were still valid and were not unnecessarily rotated. No network exposure or model
selection changed. DeepSeek remains primary; Qwen remains advisory.

The new fictional walkthrough workspace contains only generated two-row receipts
and a generated refund policy. Reports are ignored at
`data/vps-private/phase3bc-live.json`; the deployment source bundle excludes ignored
data, tokens, keys and model files. All **8/8 concurrent deployed browser sessions** passed sign-in, a live numerical
question and citation access; report: `data/vps-private/phase3bc-eight-users.json`.
This is a bounded functional concurrency check, not a new sustained load benchmark.

Commands executed (SSH control socket was authenticated through a hidden prompt):

```bash
scp -o ControlPath=/tmp/execplus-phase3-ssh /tmp/execplus-phase3bc-source.tar.gz administrator@173.208.151.137:/sdb-disk/OISOL_ExecPLUS/ops/phase3bc-source.tar.gz
node scripts/check_unified_demo.mjs data/vps-private/sessions.json data/vps-private/phase3bc-live.json
node scripts/check_vps_browser.mjs data/vps-private/sessions.json data/vps-private/phase3bc-eight-users.json
```

Inside `/sdb-disk/OISOL_ExecPLUS` on the VPS, after verifying free disk, prior
container identities and availability of the rollback destination:

```bash
cp -a source releases/pre-phase3bc-source
sudo -n docker tag oisol-execplus/api:demo oisol-execplus/api:pre-phase3bc
sudo -n docker tag oisol-execplus/web:demo oisol-execplus/web:pre-phase3bc
tar -xzf ops/phase3bc-source.tar.gz -C source
cd source
sudo -n docker compose -f deploy/vps/compose.yaml build api web
sudo -n bash deploy/vps/backup.sh
sudo -n docker compose -f deploy/vps/compose.yaml stop api
sudo -n docker compose -f deploy/vps/compose.yaml run --rm operator python -m alembic upgrade head
sudo -n docker compose -f deploy/vps/compose.yaml up -d api web
sudo -n docker compose -f deploy/vps/compose.yaml run --rm operator python -m alembic current
curl -fsS http://127.0.0.1:18401/health/ready
```

The complete checks also executed `python3 -m compileall -q apps/api/src migrations
scripts`, `git diff --check`, and `make production-preflight` (expected failure:
all eight gates blocked). The production manifest SHA-256 remains
`8f2b92715756aab3b6c969b1001b1bc2f461176b9600cf29464342e5f24dcef9`.

## Remaining gaps

- The human-label review and final judge assessment were subsequently completed;
  see [Phase 3D verification](verification-phase3d.md). The judge was rejected.
- Production representative evaluation, vector/provider selection, privacy, recovery,
  identity/security and delivery reviews remain blocked in the unchanged manifest.
- Parquet serving/lifecycle and persistent caches are not adopted. The benchmark is
  not a concurrent VPS performance result. Learned retrieval needs a better measured
  candidate before adoption; semantic similarity does not replace exact calculations.
- Supported conversations remain bounded to one selected dataset, one supported data
  question and one document search. No arbitrary joins, generated UI, new file formats,
  connectors, autonomous studies or Phase 4 work is implied.
