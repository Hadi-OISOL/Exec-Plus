> **File use case:** Declares repeatable local failure checks and sustained workload bounds for the next independent feature batch.
> **What it does:** Fixes inputs, expected behavior, acceptance thresholds and exclusions before reporting measured results.

# Next-batch local evaluation

Final measured evidence is in [the verification ledger](verification-next-batch-evaluation.md).

This is an internal functional and five-minute workload check. It does not clear a
representative-corpus, model-quality, security, provider-privacy, recovery or
production-performance gate. No customer data, VPS database or hosted model is used.

## Fixed failure cases

`next-batch-evaluation-cases.json` retains the original eighteen named cases and
adds source imports, model accounting, scoped keys/embedding/webhooks,
consolidation, chronological anomalies/drift and source-derived scenarios. Every
check names an existing exact pytest node. The existing runner deduplicates nodes,
rejects missing or unexpected results and retains failures/skips. This is a curated
regression set, not a new independent application test suite or representative AI
benchmark. Scripted model checks remain explicitly scripted.

```sh
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@127.0.0.1:5432/execplus \
  .venv/bin/python scripts/check_analysis_evaluation.py \
  --manifest docs/next-batch-evaluation-cases.json \
  --output data/verification/2026-10-16/remaining-work/fixed-next-batch-repeat
```

## Declared sustained workload

The existing `measure_analysis_workload.py` gains an opt-in `--next-batch` mode;
its earlier short comparison mode remains available. A disposable PostgreSQL
schema and MinIO bucket contain eight fictional owners, each with two company
workspaces. A separate disposable PostgreSQL database and SELECT-only role supply
two exact decimal rows. Credentials exist only in a temporary mode-0600 local
file. Setup uses the existing fictional consolidation and source fixture builders;
the report records their hashes and the relevant operation modules' hashes.

Each user starts a cycle every ten seconds for **300 seconds**, without overlapping
its own cycles. Users run concurrently. Each cycle calculates the exact total
**820**, replays that result and attempts another owner's private consolidation
(404 required). It also rotates through these six groups:

| Group | Measured behavior | Exact or privacy check |
| --- | --- | --- |
| PostgreSQL import | Fresh snapshot, same-request retry and retained content | Two exact decimal rows; retry returns the same import |
| Usage | Synthetic reserve/start/settle plus owner summary | Known fictional token counts; no configured price, so cost stays unknown |
| Scoped API | Issuer-bound key query and another-dataset request | Total 820; out-of-scope dataset returns 404 |
| Calendar methods | Seasonal and drift creation/reopening | Fixed flagged dates, observed/reference values, exact distance and full saved replay |
| Source scenario | Declared row-level scenario creation/reopening | Revenue 80, declared alternative remaining 37.6, unchanged saved result |
| Consolidation | Declared mappings/rates/eliminations and reopening | Cash 200, equity −200, internal balance zero, unchanged saved layers |

All six groups warm up before measurement. Identical three-round common probes
run immediately before and after sustained work. Original file bytes and saved
meanings are checked before and after, as are the external fixture rows. The
common probes compare one build around sustained work; they do **not** establish
an old/new version speedup. Repeated processing writes only new private fictional
results/imports/accounting records. Cleanup removes the isolated schema, bucket,
source database, SELECT-only role and temporary secret directory.

Declared local acceptance thresholds, chosen before the five-minute run:

- All eight users complete the requested duration and at least thirty cycles.
- Zero unexpected HTTP statuses, failed exact checks, private disclosure or source
  changes. Expected 404 denials are counted separately, not hidden as errors.
- Per-operation sustained p95 at most **5,000 ms**.
- API/test process peak RSS at most **1 GiB**.
- Relevant operation source hashes remain unchanged throughout the run.

The report records operation counts, median/p95/max latency, failures, explicit
check counts, before/after CPU/current RSS/peak RSS and twenty-second resource
samples. Linux peak RSS is lifetime high-water RSS, not current memory. Resource
figures exclude PostgreSQL/object-storage/provider processes. ASGI TestClient
excludes browser and public-network latency. This is paced activity across separate
workspaces, not constant eight-request concurrency or shared-workspace contention.
The interval is sustained for the declared five minutes, not a long-duration soak.

```sh
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@127.0.0.1:5432/execplus \
  .venv/bin/python scripts/measure_analysis_workload.py \
  --next-batch --duration-seconds 300 \
  --output data/verification/2026-10-16/remaining-work/sustained-local/repeat.json
```

A ten-second smoke validates the harness first and is never counted as the
five-minute result. Initial harness failures and revised runs remain in ignored
evidence. The measured run is scheduled after other local browser/backend/build
checks finish; OS background activity can still affect timing.

## Exclusions

CP-SAT was still changing when this fixed workload was declared and is excluded.
No claim covers hosted model quality/latency, real provider billing, payment/email
delivery, customer source readiness, webhook/embed throughput, arbitrary SQL,
public network exposure or representative production acceptance. Their separate
functional evidence does not become sustained workload evidence by association.
