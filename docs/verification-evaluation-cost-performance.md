> **File use case:** Records October 22 measured evidence for VC features 44, 45 and 50.
> **What it does:** States what was measured, the observed numbers, the commands and the limits.

# Evaluation, query cost and performance evidence — October 22

All measurements are local, on fictional fixtures, on a shared workstation whose load
average was 15–27 during the runs. They do not establish customer, provider or
production behaviour. Raw outputs were kept outside the repository.

## 44 — Provider-free AI-response evaluation

`scripts/evaluate_offline_responses.py` scores the labelled cases in
`docs/offline-response-evaluation-cases.json` (`offline-response-evaluation-v1`) and
writes a JSON report; it refuses to overwrite an earlier report. Every routed
calculation is executed in DuckDB and compared with an independent standard-library
Decimal oracle. `tests/test_offline_response_evaluation.py` pins the scores below.

| Category | Cases | Passed | Unsafe acceptances | Known failures |
| --- | --- | --- | --- | --- |
| Offline question routing | 24 | 23 (22 preferred plans) | 0 | R20 |
| Model-output validation (invented fields, injections, bounds) | 20 | 20 | 0 | — |
| Summary number grounding | 10 | 9 | 0 | S09 |
| Answer-to-execution binding | 5 | 5 | 0 | — |
| Executed answers agreeing with the oracle | 16 | 16 | — | — |

- The first run found that share questions (“Revenue share by region”) averaged the
  measure; the offline planner now totals it. R21 passed after that repair.
- R20 (“Which region has the highest revenue?”) still ranks by average when no
  aggregation word or confirmed metric definition is present. This remains a
  recorded failure, not a hidden one.
- S09 is a conservative false rejection: the guard reads `SKU-1234` as a number.
- A SQL-injection filter value is accepted only as a bound literal and matches no rows.

Command: `python3 scripts/evaluate_offline_responses.py --output <new path>`
(1.4 s on this machine). Representative customer questions, hosted-model output
quality, latency and spend are not measured here.

## 45 — Data-query concurrency cost control

The compute broker now caps simultaneous DuckDB queries per process
(`EXECPLUS_QUERY_CONCURRENT_LIMIT`, default 8) and per workspace
(`EXECPLUS_QUERY_WORKSPACE_CONCURRENT_LIMIT`, default 4), waiting at most
`EXECPLUS_QUERY_QUEUE_SECONDS` (default 15). Worst-case engine memory is therefore
bounded by 8 × 256 MiB by default. Refusals happen before the engine runs, return
HTTP 503 `query_capacity` with `Retry-After: 5`, and record a `failed` execution
receipt. Existing per-query bounds (time, memory, threads, input rows/cells, result
rows) and model-token accounting are unchanged. See `docs/compute-broker.md`.

Tests: `apps/api/tests/test_compute_broker.py` (global refusal, workspace isolation,
bounded queueing, slot release on failure and cancellation, invalid settings) and
`apps/api/tests/test_analytics_integration.py::test_query_capacity_refusal_is_a_retryable_503_with_a_failed_receipt`.

Measured overhead (2,000 calls, fake engine): median 1.0 µs direct versus 5.8 µs
through the broker, about 5 µs per query; against a real 2,000-row DuckDB query
(about 23 ms) this is below measurement noise. Slots are per process and polled,
not first-in-first-out; a refused query still counts once against the processing
allowance. Provider invoices and production concurrency sizing remain unverified.

## 50 — Query load performance

Profiling the governed query path showed most executor time is spent converting
source cells before loading DuckDB. Two changes keep results identical:
decimal range/precision constants are computed once per scale instead of per value,
and the default insert batch rises from 500 to 5,000 rows (still capped at 20,000
cells per statement).

Interleaved before/after medians (11 alternating runs each, identical result rows):

| Rows | Query | Before ms | After ms | Change |
| --- | --- | --- | --- | --- |
| 3,000 | SUM(decimal) by region | 125.56 | 112.71 | −10.2% |
| 3,000 | AVG(integer) | 57.35 | 52.61 | −8.3% |
| 20,000 | SUM(decimal) by region | 600.23 | 394.98 | −34.2% |
| 20,000 | AVG(integer) | 135.04 | 109.59 | −18.8% |

A first interleaved run showed −10.0%, −23.3%, −7.1% and −12.8% for the same four
cases; the direction is consistent, the size is not. A decimal column of 3,000
values converts in 17.8 ms versus 21.6 ms before. A new test checks the default and
small batch sizes against an independent 80-digit Decimal sum.

The end-to-end `scripts/benchmark_data_workflow.py` run passed after the change
(exact revenue 24339.000, forecast 4.1), but unchanged operations varied up to 2×
between runs under this load, so its timings support no speed claim. An earlier run
failed once with HTTP 422 on the dashboard under the same load and passed on rerun;
the benchmark now prints the response body when a request fails. A fresh in-memory
DuckDB connection per query (about 25 ms here) is retained for isolation.
Representative sustained load, latency/error thresholds and production-scale
acceptance remain open.
