> **File use case:** Retains measured evidence for the bounded next-batch fixed evaluation and five-minute local workload.
> **What it does:** Reports exact checks, errors, timing, resources, source preservation and the limits of this internal evidence.

# Next-batch evaluation evidence — October 16

The declared [local evaluation](next-batch-local-evaluation.md) passed its final
fixed selection and sustained workload. This is local fictional evidence; no
production gate or representative quality claim changes.

## Fixed evaluation

The final manifest contains **32 named cases / 89 exact tests**. All **89 passed**,
with zero failures, errors, skips, missing nodes, unexpected nodes or duplicate
results. Pytest elapsed time was **84.83 seconds**. The original eighteen cases
remain included; additional checks cover exact source snapshots and staged
activation, import publication races/idempotency, usage limits/unknown costs,
issuer-bound keys, private embeds, signed webhook retries, consolidation
privacy/atomic limits, seasonal/drift evidence and source scenarios.

The initial selection ran **86 passing tests**, but the evaluation correctly
failed because one manifest entry named a parameterized usage test without its
`[True]` / `[False]` suffixes. The final manifest pins both variants and adds the
final source activation, issuer authority and consolidation quota regressions.
No application test failed in that initial evaluation; its manifest failure is
retained rather than counted as a passing evaluation.

Ignored evidence:

- `data/verification/2026-10-16/remaining-work/fixed-next-batch/`: initial log,
  JUnit and failed manifest-accounting report.
- `data/verification/2026-10-16/remaining-work/fixed-next-batch-final/`: final
  manifest hash, 89-node JUnit/log and complete 32-case report.

## Five-minute measured interval

The measured interval ran **12:50:59–12:55:59 UTC**, lasting **300.003 seconds**.
All eight fictional owners completed **30 cycles each**. Their sixteen company
workspaces are independent; this is not shared-workspace contention evidence.
Local operator grants only permit provisioning their approved fictional sources.
Other agents paused local browser, build and backend-test jobs for this interval.
OS background load remained present and is recorded.

| Measure | Observed result |
| --- | --- |
| Sustained HTTP requests | **1,400**, including 280 expected private/scope denials |
| Instrumented requests across setup, warmup, probes and sustained work | **1,896**; this excludes uninstrumented fixture-helper setup requests |
| Expected HTTP 404 denials across those phases | **336** |
| Unexpected HTTP statuses / failed exact or privacy checks | **0 / 0** |
| Sustained executions per feature group | **40**; calendar group executes both methods |
| Source preservation | All **48** original files and saved meanings match before/after; external database rows unchanged |
| Operation source drift | **None** across recorded hashes |
| Process CPU during measured interval | **55.446 seconds** |
| Current process RSS before → after | **306.109 → 306.176 MiB** |
| Lifetime peak process RSS | **322.340 MiB**, below declared 1 GiB bound |

Each sustained group preserves its declared result: total **820**, exact decimal
import bytes, unknown unpriced cost, fixed seasonal dates/reference values,
exact drift distance, scenario remaining **37.6**, and consolidated Cash **200** /
Equity **−200** / Internal **0**. Saved results reopen exactly. Repeated imports
with the same request ID return the same import. All original bytes and meanings
are checked twice, producing 96 file checks and 96 meaning checks; this does not
mean 96 distinct sources.

Selected operation latency, from the sustained interval only:

| Operation | Calls | Median ms | p95 ms | Maximum ms |
| --- | ---: | ---: | ---: | ---: |
| Exact query | 240 | 240.627 | 308.610 | 352.836 |
| Query replay | 240 | 217.025 | 291.772 | 342.254 |
| Fresh PostgreSQL import | 40 | 249.193 | 345.862 | 395.272 |
| Same import request retry | 40 | 212.664 | 334.262 | 396.835 |
| Scoped integration query | 40 | 128.435 | 220.010 | 244.129 |
| Owner usage summary | 40 | 199.084 | 319.238 | 359.392 |
| Synthetic usage service lifecycle | 40 | 28.373 | 48.185 | 50.276 |
| Seasonal analysis | 40 | 474.716 | **582.186** | 593.239 |
| Distribution drift | 40 | 259.927 | 349.425 | 360.974 |
| Source scenario | 40 | 406.329 | 489.898 | 521.176 |
| Consolidation | 40 | 388.177 | 526.739 | 548.531 |
| Consolidation replay | 40 | 368.254 | 462.301 | 485.948 |

All operation p95 values, including those omitted from the compact table, meet
the declared **5,000 ms** local threshold. The usage lifecycle row is a direct
service operation, not an HTTP request or a provider inference. Its reported
token counts are fictional and no prices are configured, so cost stays unknown.

Identical common probes ran three rounds before and after the interval:

| Operation | Before p95 ms | After p95 ms |
| --- | ---: | ---: |
| Exact query | 404.293 | 424.607 |
| Query replay | 441.912 | 247.612 |
| Private consolidation denial | 49.651 | 154.322 |

Common probe wall time was 2.200 seconds before / 1.600 seconds after, with 72
requests in each. The mixed changes do not establish a speedup or degradation.
They compare one build around this particular short paced workload.

The full report includes twenty-second CPU/current-RSS/peak-RSS samples,
per-operation counts/latency/error data, exact-check counters, source hashes and
all seven passing acceptance gates. Process resources exclude PostgreSQL/MinIO
and provider processes. API latency excludes a browser and external network.
Cleanup completed for the isolated schema/bucket and the separate SELECT-only
source fixture. No customer or VPS data participated.

## Harness checks and retained limitations

- The ten-second smoke passed every functional/resource check but intentionally
  failed the source-freeze gate: the runner was formatted and a consolidation
  fixture changed while it ran. `sustained-local/smoke-1.{log,json}` retains this
  evidence. It is not counted as the five-minute pass.
- The historical workload mode still completed **144 common + 64 newer-method
  requests**, zero errors. Its elapsed times were obtained alongside other tests
  and are not used as performance evidence here.
- Initial static checks found import ordering/line-length issues and direct test
  fixture imports unavailable to mypy. The runner now loads fixed project-local
  fixture modules explicitly; final Ruff, mypy and compilation checks pass.
- After the measured run, only argument validation was adjusted to allow the
  historical `--source another-checkout --output current-project/data/...` usage.
  Output must still be new, ignored and inside the runner project. The actual
  measured runner is archived as `sustained-local/measured-runner.py`; its SHA-256
  matches the report. No operation, fixture or threshold changed after measurement.
- Final report: `data/verification/2026-10-16/remaining-work/sustained-local/final.json`.
  This is an observed five-minute paced run, not a long-duration soak, maximum
  capacity proof, real model latency/quality evaluation or production acceptance.
- CP-SAT was changing when this workload was declared and remains excluded.
  External identity/email/payment, customer connectors and representative privacy,
  security, retrieval/model and recovery gates remain governed by their separate
  requirements. No production status is promoted by these results.
