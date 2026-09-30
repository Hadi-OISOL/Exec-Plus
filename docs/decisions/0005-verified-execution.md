> **File use case:** Records execution-boundary hardening decisions.
> **What it does:** Explains exact arithmetic, query validation and reproducible answer receipts.

# ADR 0005: Bound execution and replayable evidence

Status: Accepted for local/test analytics, 2026-09-17.

Keep semantic planning in the domain and parse its SQL again in the DuckDB adapter
using SQLGlot. Permit only the supported SELECT grammar, declared tables and bound
filter values. Disable external file/network access and automatic extension loading.
This prevents a forged internal plan from escaping the same boundary used by HTTP.

Use DECIMAL(38,12), exact SUM/COUNT for AVG, and explicit half-even rounding to twelve
places. DuckDB floating-point division cannot supply the exact computation contract;
see [DuckDB numeric types](https://duckdb.org/docs/current/sql/data_types/numeric).
Return exact decimal strings over JSON. Reject unsupported scale or malformed types.

Store immutable source references, bound parameters and result checksums alongside
query executions. Replay reconstructs those revisions and verifies results. Keep
aggregate evidence in access-controlled lineage, with identifiers-only general audit.
Allow models to select server-rendered evidence statements, never free-form numerical
claims. The statement selection and route are recorded with the execution.

Security configuration follows [DuckDB's execution guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview)
and [extension guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/securing_extensions).
SQL parsing uses [SQLGlot's AST API](https://sqlglot.com/).
