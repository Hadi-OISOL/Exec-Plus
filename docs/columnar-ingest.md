> **File use case:** Contract and evidence for profile-v5 typed-Parquet ingest (October 26 plan, Phase 2 items 2 and 4).
> **What it does:** Explains how new uploads become typed Parquet, how queries and receipts use it, the settings, measured cost and the limits that remain.

# Profile-v5 columnar ingest

## What changes

- **Opt-in.** `EXECPLUS_COLUMNAR_INGEST_ENABLED=true` makes every new non-sample CSV/XLSX upload
  a **profile-v5** upload. With it off (default) nothing changes. Profile v1–v4 uploads, their
  revisions and receipts keep the in-memory path byte for byte.
- **Ingest (once, per upload).** `DuckDBColumnarConverter` opens the stored file with the shared
  format readers (`infrastructure/readers.open_source`, first table, every column VARCHAR, on
  `hardened_connection`), so every reader format is accepted: CSV/TSV/TXT, Excel, ODS, JSON/NDJSON,
  Parquet, SQLite, SPSS/Stata/SAS, XML and ZIP/GZ/BZ2/XZ archives of them. The upload records the
  stored format as `r:<suffix>` (e.g. `r:csv.gz`; migration **0033** widens `uploads.format` to
  16 characters). It writes a raw text Parquet stage, then:
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
- **Row-level features** (understanding, cleaning, guidance, patterns, label matching…) read the
  original file again through the same reader (`StructuredFileParser` routes `r:` formats), so
  they see exactly the strings the Parquet was built from, but only up to 100,000 rows; above
  that they return `large_dataset_step` instead of loading millions of rows into Python.
- **Chunked uploads.** `UploadSessionService.process` calls `WorkspaceService.upload` on the
  assembled temp file, so big files are converted in the worker after `complete`.

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

October 25, local machine (8 cores, 14 GiB RAM, NVMe), DuckDB 1.5.6, ingest and queries
each in a fresh process, ingest 2 GB / 4 threads, queries 2 GB / 4 threads. Synthetic CSV with
8 columns (2 identifiers, region, date, product, 2-decimal amount incl. negatives, integer,
note). Query times are on a warm local Parquet file (no object-store download), 3 runs.
Every answer equalled exact integer-cent arithmetic computed while generating the file.

| Rows | CSV | Parquet | Ingest | Ingest peak RSS | Query peak RSS | SUM | AVG | Group by region | Top-10 customers (100k groups) | Monthly trend |
|---|---|---|---|---|---|---|---|---|---|---|
| 1,000,000 | 104 MB | 12.5 MB | 6.7 s | 540 MiB | 175 MiB | 0.04 s | 0.04 s | 0.05 s | 0.13 s | 0.07 s (0.31 first) |
| 10,000,000 | 1.05 GB | 125 MB | 61.4 s | 2,063 MiB | 408 MiB | 0.16 s | 0.18 s | 0.20 s | 0.80 s | 0.37 s (0.62 first) |

Ingest phases at 1M rows: text stage ≈0.8 s, validation + profile aggregates ≈4 s, duplicate
count 0.3 s, typed staging ≈1 s, final Parquet 0.3 s. DuckDB's VARCHAR → `DECIMAL(38,s)` cast was
~250× slower than `DECIMAL(18,s)`, so values are cast narrow-then-widened when they fit.
The legacy path cannot load these sizes at all (200,000-row / 2,000,000-cell bound).

Reproduce with
`PYTHONPATH=apps/api/src python scripts/benchmark_columnar.py --rows 1000000 10000000`
(or `EXECPLUS_RUN_BENCHMARKS=1 pytest -m benchmark`). Data is generated on the fly.

## Known limits

- Small files (below the session inline threshold) still convert inside the request thread.
- Multi-sheet/multi-table files use the first table; a table picker is not built yet.
- Reader behaviour is inherited: the Excel extension returns numbers as text with 16
  significant digits (`12345678901234568` arrives as `1.234567890123457e+16` and is stored as
  `12345678901234570`); a malformed CSV whose rows have different widths can be sniffed as a
  single text column instead of being refused (legacy CSV refused it).
- Edge differences from v4 (v5 is a new version, old files unaffected): non-ASCII digits are
  not numbers; values like `.5`, `1.`, `1_000` in numeric columns or `20240101` in date columns
  are refused at query time; DuckDB skips fully empty lines that the legacy parser rejected.
- Joins, restricted (row/column policy) views and cleaned child revisions use the legacy
  in-memory path (≤ legacy bounds). Upload size is still capped by the Phase 1 settings.
- Parquet adds storage (≈12 % of CSV size in the benchmark) and backup volume.
