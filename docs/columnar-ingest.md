> **File use case:** Contract and evidence for profile-v5 typed-Parquet ingest (October 26 plan, Phase 2 items 2 and 4).
> **What it does:** Explains how new uploads become typed Parquet, how queries and receipts use it, the settings, measured cost and the limits that remain.

# Profile-v5 columnar ingest

## What changes

- **Opt-in.** `EXECPLUS_COLUMNAR_INGEST_ENABLED=true` makes every new non-sample CSV/XLSX upload
  a **profile-v5** upload. With it off (default) nothing changes. Profile v1–v4 uploads, their
  revisions and receipts keep the in-memory path byte for byte.
- **Ingest (once, per upload).** `DuckDBColumnarConverter` streams the stored file through DuckDB
  as text (`all VARCHAR`), writes a raw Parquet stage, then:
  1. validates every cell in SQL (formula-like cells, control characters, blank rows),
  2. computes exact per-column aggregates (type counts, distinct counts, placeholders, date and
     date-time ranges, decimal scale, duplicates),
  3. applies the **profile-v4 rules** to those counts (`domain/columnar.profile_from_stats`) —
     same JSON shape, `algorithm: "profile-v5"`; 40 randomized parity tests compare it with the
     in-memory `profile_for`,
  4. casts once to typed Parquet: `DECIMAL(38,s)` (scale = max(12, needed), never float),
     `BIGINT`, `DATE`, `TIMESTAMP` (v3 date-time rules, offsets converted to UTC), `BOOLEAN`,
     `VARCHAR` (stripped, empty → NULL); v4 N/A-as-missing placeholders become NULL.
  A column whose values cannot be cast is kept as text and its exact legacy error message
  (`Column "x", data row N: expected …`) is stored; queries that reference it are refused,
  exactly like the in-memory path. Nothing is rounded or skipped.
- **Storage.** Parquet goes to `…/uploads/{upload_id}/columnar-v1.parquet` next to the original.
  The root revision's `profile.columnar` holds `{format, key, sha256, size, rows, errors}`
  (no migration). The revision's `output_checksum` **is the Parquet SHA-256**, so every receipt
  already binds the source checksum and the Parquet checksum.
- **Queries.** `revision_table()` returns a `ColumnarTable` for such revisions. The executor
  downloads the Parquet into a local cache (verified by size + SHA-256, content-addressed,
  bounded by `columnar_cache_bytes`) and creates `dataset` as a view over `read_parquet`.
  SQL validation is unchanged; the connection then sets `allowed_paths` to that one file,
  `enable_external_access=false` and `lock_configuration=true`. Separate bounds apply:
  50M rows, 2 GB memory, 4 threads, 120 s, spill up to 20 GB.
- **Replay** reopens the same revision → same Parquet (checksum-verified) → same SQL → same
  result. Integration test deletes the cache before replay to force a verified re-download.
- **Row-level features** (understanding, cleaning, guidance, patterns, label matching…) still
  read the original file through the legacy parser, so they keep exact strings but work only up
  to 100,000 rows; above that they return `large_dataset_step` instead of loading millions of
  rows into Python.

## Settings

| Setting | Default |
|---|---|
| `columnar_ingest_enabled` | `false` |
| `columnar_work_directory` | system temp (ingest temp files and query spill) |
| `columnar_cache_directory` / `columnar_cache_bytes` | `$TMP/execplus-columnar-cache` / 20 GiB |
| `columnar_ingest_memory_mb` / `columnar_ingest_threads` | 2048 / 4 |
| `columnar_max_rows` | 50,000,000 |
| `columnar_query_timeout_seconds` / `_memory_mb` / `_threads` | 120 / 2048 / 4 |
| `columnar_spill_mb` | 20,480 |

## Measurements

See the "Measured" section added after the benchmark run; reproduce with
`PYTHONPATH=apps/api/src python scripts/benchmark_columnar.py --rows 1000000 10000000`
(or `EXECPLUS_RUN_BENCHMARKS=1 pytest -m benchmark`). Data is generated on the fly.

## Known limits

- Ingest runs inside the upload request (a thread, not the event loop); the Phase 1 background
  upload/jobs path should call the same `WorkspaceService.upload` from the worker.
- XLSX still uses the bounded openpyxl validator (legacy XLSX limits); swap in the
  formats-agent reader (`open_source`) for big workbooks. Only UTF-8 CSV is accepted.
- Edge differences from v4 (v5 is a new version, old files unaffected): non-ASCII digits are
  not numbers; values like `.5`, `1.`, `1_000` in numeric columns or `20240101` in date columns
  are refused at query time; DuckDB skips fully empty lines that the legacy parser rejected.
- Joins, restricted (row/column policy) views and cleaned child revisions use the legacy
  in-memory path (≤ legacy bounds). Upload size is still capped by the Phase 1 settings.
- Parquet adds storage (≈12 % of CSV size in the benchmark) and backup volume.
