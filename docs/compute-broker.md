> **File use case:** Defines the compatible analytical compute boundary.
> **What it does:** Records engine registration, enforceable budgets and historical-result compatibility.

# Bounded compute broker

Bootstrap registers the existing DuckDB executor under `duckdb` and passes a
`ComputeBroker` implementing the existing `QueryExecutor` protocol to analytics
and joins. Studies, discovery, monitoring and replay use these same services.
This is one local engine, not an implemented remote-compute service.

Registration belongs to the operator-controlled composition root. No HTTP/model
field can select an endpoint, install a package, run Python, change engine limits
or bypass validated SQL. Supported operations are `snapshot_query` and
`declared_join`. An unsupported capability or unregistered engine is rejected
before execution. Future adapters require their own capability and isolation tests.

The broker verifies workspace/dataset scope, combined input bounds, result identity,
result shape and row budget. DuckDB independently enforces input/fetch limits,
configured threads and memory, and its existing cooperative timeout/interruption.
Temporary disk spilling is disabled (`max_temp_directory_size=0B`); external access,
automatic extensions and unsigned extensions remain disabled. Query values remain
bound parameters. Current exact decimals, averages, wide integers, projection,
declared-join cardinality guards and result checksum serialization are unchanged.

| Setting | Default | Supported maximum |
| --- | --- | --- |
| `EXECPLUS_QUERY_TIMEOUT_SECONDS` | 15 | 300 seconds, finite |
| `EXECPLUS_QUERY_MEMORY_LIMIT_MB` | 256 | 16384 MiB |
| `EXECPLUS_QUERY_THREADS` | 1 | 8 |
| `EXECPLUS_QUERY_INPUT_ROWS` | 200000 | 200000 combined rows |
| `EXECPLUS_QUERY_INPUT_CELLS` | 2000000 | 2000000 combined cells |
| `EXECPLUS_QUERY_RESULT_ROWS` | 100000 | 100000 returned rows |

The existing `EXECPLUS_QUERY_ROW_LIMIT` remains the planner's limit and does not
override a stricter execution budget. File intake keeps its separate existing
20 MiB/row/cell limits. Per-engine memory is not an OS-level process RSS guarantee;
parsing and strict Python conversion also consume memory. Containers retain their
own limits, and process-isolated parsing/sandbox execution is future work. An
adapter must stop and clean up on cancellation before returning control; declaring
capabilities does not establish that behavior without tests.
