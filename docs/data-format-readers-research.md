> **File use case:** Research input for Phase 2.1 and Phase 3.1 of the October 26 big-data intake plan (`docs/plan-data-intake-20261026.md`).
> **What it does:** Picks a pinned, offline, open-source reader for every upload format, records licences, sizes, memory behaviour, exact-decimal handling and security notes, and proposes a compact "dataset brief" and auto-dashboard approach that keeps the rule "the LLM never computes numbers".

# Data format readers and LLM dataset briefs — research (October 25, 2026)

## 1. Summary

- **DuckDB is already installed (1.5.6) and can be the single ingest engine.** It reads CSV/TSV
  (+ `.gz`/`.zst`), JSON/NDJSON, Parquet natively, and XLSX/XLSM, SQLite and Avro through
  official extensions that we pre-bundle in the image. It writes typed Parquet with `COPY … (FORMAT
  parquet)`, so **pyarrow is not needed** for the core path.
- **Only two new runtime packages are needed for the full required list:**
  `python-calamine` (XLS, ODS, XLSB) and `pyreadstat` (SPSS, Stata, SAS). XML uses the already
  installed `defusedxml` streaming parser; archives and encodings use the standard library and the
  already installed `charset-normalizer`.
- **Exactness rule:** DuckDB's automatic type sniffing turns `0.10` into `DOUBLE`. Every text-based
  reader must read **all columns as text first**, then Syntelio decides each column's type
  (integer / `DECIMAL(38,s)` with the existing per-column scale rule / date / timestamp / boolean / text)
  with DuckDB aggregate checks, then casts once while writing Parquet. Verified locally (§4).
- **Offline rule:** DuckDB defaults to `autoinstall_known_extensions = true`, i.e. it will download
  extensions from the internet on first use. The ingest connection must set
  `autoinstall_known_extensions=false`, point `extension_directory` at a read-only bundled folder,
  and `LOAD` only the allow-listed extensions.

## 2. What is installed today

Checked with `.venv/bin/python` and `pyproject.toml` on October 25:

| Package | Installed | In `pyproject.toml` | Use for intake |
|---|---|---|---|
| duckdb | 1.5.6 | `>=1.5.0,<2` | Core engine (CSV, JSON, Parquet, Parquet writer, profiling) |
| openpyxl | 3.1.5 | yes | Current XLSX path; keep for old profile versions and small files |
| defusedxml | 0.7.1 | yes | Safe streaming XML (`defusedxml.ElementTree.iterparse`) |
| charset-normalizer | 3.5.2 | transitive (httpx/requests) | Encoding detection — declare it explicitly |
| pandas | 2.3.3 | yes | Fallback readers (`read_stata`, `read_sas` with chunks) |
| numpy / scipy | 2.2.6 / 1.15.3 | yes | Not needed for intake |
| pypdf | 6.20.1 | dev only | Not a table reader |
| pyarrow, python-calamine, pyreadstat, lxml, xlrd, fastavro, pdfplumber, odfpy | not installed | — | See recommendations |

Note: **DuckDB 2.0.0 was released on PyPI on October 21, 2026**; the project pins `<2`. Stay on
**1.5.6** for this work. Extensions are built per DuckDB version (`extension_directory/v1.5.6/linux_amd64/`),
so a DuckDB upgrade must re-bundle them in the same change.

## 3. Reader per format

Versions are current stable on PyPI on October 25, 2026 (fetched from the PyPI JSON API).
Wheel sizes are the CPython 3.12 manylinux x86_64 wheel.

| Format | Recommended reader | Pin | Licence | Size / native deps | Streaming & memory (500 MB) | Exact decimals | Fallback |
|---|---|---|---|---|---|---|---|
| CSV / TSV / TXT (any delimiter, BOM) | DuckDB `read_csv(all_varchar=true)` + `sniff_csv` | duckdb 1.5.6 (installed) | MIT | none new | Streams, parallel, spills to `temp_directory`; bounded by `memory_limit` | Text in → Syntelio casts to `DECIMAL(38,s)` | stdlib `csv` (existing) |
| CSV in other encodings (cp1252, Shift-JIS, GB18030 …) | `charset-normalizer` on first 1–4 MB → stdlib incremental decoder transcodes to a UTF-8 temp file → DuckDB | 3.5.2 (installed) | MIT | 0.3 MB | Constant memory (chunked transcoding) | n/a | Ask user to pick encoding |
| `.csv.gz` / `.zst` | DuckDB native | — | — | — | Streams | as CSV | stdlib `gzip` |
| XLSX / XLSM | DuckDB **excel** extension `read_xlsx(all_varchar=true, sheet=…)` | bundled for 1.5.6 (12 MB) | MIT | 12 MB extension file | **Streams: ~110 MB peak RSS for both 15 MB and 50 MB files** (§4) | `all_varchar` returns the stored cell text (`0.11`), dates as Excel serials | openpyxl read-only (63 MB but ~12k rows/s) |
| XLS (BIFF, ≤65,536 rows) | `python-calamine` | 0.9.0 | MIT | 0.9 MB, Rust (no system libs) | Loads the whole sheet; fine because XLS is small by design | Numbers arrive as float → `Decimal(repr(x))` (shortest round-trip = Excel's stored value) | xlrd 2.0.2 (BSD, XLS only) |
| XLSB, ODS | `python-calamine` | 0.9.0 | MIT | as above | **Loads whole sheet: 255 MB for 300k rows, 820 MB for 1M rows** (§4). Cap these at ~50 MB file size or ~1M cells per worker | as XLS | odfpy 1.4.1 (2020, unmaintained-looking, slow) — avoid |
| JSON / JSONL / NDJSON | DuckDB `read_json(format='newline_delimited' or 'array', columns={…})` | — | — | none | Streams NDJSON; `maximum_object_size` caps one object | Sniffs `DOUBLE`; Syntelio must pass explicit `columns=` with `DECIMAL`/`VARCHAR` after a text pre-scan | stdlib `json` for small files |
| Nested JSON | DuckDB `unnest(col, recursive := true)` for structs; lists → separate child table or JSON text | — | — | — | — | — | — |
| Parquet | DuckDB `read_parquet` | — | — | none | Streams row groups | Keeps source types; source `FLOAT/DOUBLE` stays double and is **flagged "source stored as floating point"** | — |
| XML (table-shaped) | `defusedxml.ElementTree.iterparse` (stdlib expat underneath) | 0.7.1 (installed) | PSF | none new | Constant memory if each record element is cleared after use | Text in → same caster | lxml 6.1.3 (5.2 MB) only if speed matters; must be ≥6.1 (CVE-2026-41066) or pass `resolve_entities=False` |
| SPSS `.sav/.zsav/.por`, Stata `.dta`, SAS `.sas7bdat/.xpt` | `pyreadstat.read_file_in_chunks(…, chunksize=100_000, output_format="dict")` | 1.3.7 (Oct 21, 2026) | Apache-2.0 (bundles MIT ReadStat) | 2.9 MB, C (bundled) | Chunked, bounded | These formats store IEEE doubles natively; convert with shortest repr, keep integer-typed Stata columns as integers. Value labels and variable labels go into the brief | `pandas.read_stata(iterator=True)`, `pandas.read_sas(chunksize=…)` (no new dependency, no SPSS) |
| SQLite `.sqlite/.db` | DuckDB **sqlite** extension `sqlite_scan(file, table)` with `SET sqlite_all_varchar=true` | bundled (34 MB) | MIT | 34 MB extension | Streams | Text in → caster (SQLite has dynamic typing: `'abc'` inside a NUMERIC column fails without `all_varchar`, verified) | stdlib `sqlite3` with `?mode=ro&immutable=1` URI |
| ZIP | stdlib `zipfile` | — | — | none | Stream each member to a temp file with byte counter | — | — |
| GZ / BZ2 / XZ | stdlib `gzip`, `bz2`, `lzma` | — | — | none | Streaming decompress with byte counter | — | — |
| Avro (optional) | DuckDB **avro** extension `read_avro` | bundled (12 MB) | MIT | 12 MB | Streams | Avro `decimal` logical type maps to DECIMAL | fastavro 1.13.1 (MIT, 3.6 MB) |
| Feather / Arrow IPC, ORC (optional) | `pyarrow` (`pyarrow.ipc`, `pyarrow.orc`) | 26.0.0 | Apache-2.0 | **54 MB wheel** | Record-batch streaming → hand to DuckDB | Arrow `decimal128` preserved | Defer until a user needs it |
| Google Sheets export | Existing Google import already downloads CSV/XLSX → normal path | — | — | — | — | — | — |
| HTML tables (optional) | `pandas.read_html` needs lxml or bs4+html5lib | — | — | adds lxml | Whole document in memory | text → caster | Defer; low value |
| PDF tables (optional) | `pdfplumber` 0.11.10 (MIT, pdfminer.six) for text PDFs; camelot-py 2.0.0 (MIT) needs Ghostscript/OpenCV for lattice mode | — | — | pure Python / heavy system deps | Page by page | Text → caster | **Not reliable**: scanned PDFs need OCR, merged cells and multi-page tables break. Offer only as "extract, then show for review before import", never silent |

### Notes per reader

- **DuckDB excel extension** (`read_xlsx`): reads `.xlsx` (and `.xlsm`, verified: the macro part
  is simply ignored, nothing executes); **does not read `.xls`**. Typed mode infers types from the
  *first data row only* and maps most numbers to `DOUBLE`, so always use `all_varchar=true` and,
  separately, a typed `DESCRIBE` to learn which columns Excel formats as DATE/TIMESTAMP
  (convert serials with `DATE '1899-12-30' + serial`). Formula cells return the cached value saved
  by Excel; files written by tools that do not store cached values give empty cells — report that.
  Docs: https://duckdb.org/docs/2.0/core_extensions/excel.html
- **python-calamine** exposes `CalamineSheet.iter_rows()` and `to_python(nrows=…)`, but the Rust
  library parses the whole worksheet range first, so memory grows with the sheet. Integers come back
  as floats (`0.0`). Pandas ≥2.2 can use it as `engine="calamine"`.
  https://github.com/dimastbk/python-calamine, https://pypi.org/project/python-calamine/
- **pyreadstat**: "Pyreadstat is not a validated package" (README). Dates outside Python's range
  raise `OverflowError` → use `disable_datetime_conversion=True` and convert in DuckDB. Some
  `.xpt`/`.por`/`.sav` files do not report a row count. https://github.com/Roche/pyreadstat
- **charset-normalizer** guessed `cp1250` for a tiny Latin-1 file in our test — on short samples
  it can be wrong. Use a large sample (1–4 MB), prefer UTF-8 when it decodes cleanly, map
  `latin-1/cp1250/cp1252` ambiguity to `cp1252`, and let the user override in the preview.
- **DuckDB `encodings` extension** handles cp1252 etc. inside `read_csv`, but the extension file is
  **336 MB** — not worth bundling; Python transcoding is smaller.

## 4. Local measurements (October 25, scratch environment, not the repo venv)

| Test | Result |
|---|---|
| `read_csv` default on `0.10`, `12345678901234567.25` | Column typed `DOUBLE` (would lose exactness) |
| `read_csv(all_varchar=true)` then `SUM(TRY_CAST(amount AS DECIMAL(38,2)))` | `12345678901234567.55` exact |
| `read_json` default on `{"b": 1.10}` | `DOUBLE`; with `columns={'a':'STRUCT(b DECIMAL(38,2), c BIGINT[])'}` exact `1.10` |
| `COPY … TO 'x.parquet' (FORMAT parquet, COMPRESSION zstd)` | `DECIMAL(38,2)` and `DATE` preserved on read-back |
| `read_csv(encoding='latin-1')` / `'utf-16'` | Work natively; `cp1252` needs the 336 MB extension |
| `read_csv('x.zip')` | Not supported (fails); `.gz` works |
| XLSX 300k rows × 10 cols (15 MB) → Parquet via `read_xlsx(all_varchar)` | 2.6 s, **114 MB peak RSS** (56 MB baseline), 2 threads |
| XLSX 1M rows × 10 cols (50 MB) → Parquet via `read_xlsx(all_varchar)` | 12.6 s, **110 MB peak RSS** → streams |
| python-calamine `iter_rows` on the same files | 1.9 s / 255 MB; 10.7 s / **820 MB** → whole sheet in memory |
| openpyxl read-only on the 300k-row file | 25.6 s / 63 MB |
| `sqlite_scan` with `'abc'` stored in a NUMERIC column | Error; works with `SET sqlite_all_varchar=true` |

A 500 MB XLSX is roughly 10M rows; extrapolating the 50 MB result gives about 2–3 minutes in the
jobs worker with flat memory. This is an extrapolation, not a measurement.

## 5. Security checklist for the ingest worker

| Threat | Applies to | Control |
|---|---|---|
| Zip bomb / huge expansion | ZIP, GZ/BZ2/XZ, **and XLSX/XLSM/XLSB/ODS (they are ZIPs)** | Before any reader: open with stdlib `zipfile`, check member count (e.g. ≤1,000), total declared uncompressed size (e.g. ≤ 5× quota-remaining and ≤ 4 GB), per-member ratio (e.g. ≤ 200:1); decompress with a hard byte counter (declared sizes can lie). Nesting depth ≤ 2. Reject absolute paths, `..`, symlinks |
| XXE, billion laughs, DTD fetches | XML; also XLSX internals | `defusedxml` (forbids DTDs/entities). If lxml is ever added: ≥6.1.0 because `iterparse` resolved external entities by default before 6.1 (CVE-2026-41066). openpyxl already uses defusedxml when installed |
| Macros | XLSM, XLS | No reader executes VBA; never write the VBA part to Parquet; record "workbook contains macros (ignored)" |
| Formula injection | Exports, not imports | Today `file_parser.py` rejects formula-like cells (`unsafe_formula`). For large files, rejecting a 10M-row upload because one note starts with `=` is harsh. Proposed (needs owner decision): keep text as data in Parquet; read cached values for real formulas; keep the existing export neutralisation in `exports/portable.py`. Old profile versions keep today's behaviour |
| Native parser memory bugs | pyreadstat/ReadStat (OSS-Fuzz heap overflows in the SAS parser, e.g. OSV-2020-333, and a 2026 report on `sas7bdat_parse_all_pages_pass2`), calamine, DuckDB extensions | Run readers in the separate jobs container as non-root, with no network, memory/CPU limits and a wall-clock timeout per file; pin versions; a crash fails only that ingest job |
| DuckDB reading other files / network | All DuckDB readers | Ingest connection: `autoinstall_known_extensions=false`, `autoload_known_extensions=false`, `allow_community_extensions=false`, `allowed_directories=[job temp dir, bundled extension dir]`, `memory_limit`, `threads`, `temp_directory`, `max_temp_directory_size`, then `SET lock_configuration=true`. The query executor keeps `enable_external_access=false`. DuckDB says these settings are not a complete sandbox; keep the container isolation. https://duckdb.org/docs/2.0/operations_manual/securing_duckdb/overview.html |
| SQLite tricks | `.sqlite/.db` | Open read-only/immutable; list tables from `sqlite_master` only; ignore views/triggers; no `ATTACH` from user text |
| Encoding confusion / NUL bytes | CSV | Keep today's NUL-byte and markup checks; reject files that fail strict decoding after the chosen encoding |
| Untrusted file names | All | Keep `validate_filename`; sanitize Google Sheets titles (plan item) |

## 6. Integration approach

One reader port, one output:

```text
upload (object storage) → jobs worker
  → unpack guard (zip/gz/bz2/xz, bomb limits) → detect format by magic bytes + extension
  → reader returns a DuckDB relation of TEXT columns (+ per-column hints: excel date format,
    stata int type, SPSS labels, source float flag)
  → type decision: one DuckDB aggregate pass per table (all-integer? max digits/scale? valid date?
    boolean set?) using the existing per-column DECIMAL(38,s) scale rule
  → COPY (SELECT CAST(...) ...) TO staging.parquet (FORMAT parquet, COMPRESSION zstd,
    ROW_GROUP_SIZE ~122,880) → upload Parquet + checksum → new profile version (v5)
```

- Readers that are Python generators (calamine, pyreadstat, XML iterparse) write text rows into a
  temporary DuckDB table in batches (`executemany`/appender of 50k rows) or a temporary CSV, then
  join the same path. No pyarrow needed. If pyarrow is added later (Feather/ORC), its
  `RecordBatchReader` can be queried by DuckDB directly with no copy.
- Multi-sheet/multi-table files (XLSX sheets, SQLite tables, ZIP members, XML repeating elements)
  first return a **listing** (name, approximate rows/columns) so the user picks, as the plan requires.
- Source receipts keep the original file checksum and the Parquet checksum; old CSV/XLSX uploads
  and profile v1–v4 replay unchanged.

## 7. How open-source projects make big tables understandable to LLMs

| Project | What the model sees | How charts/dashboards are chosen | Fit for Syntelio |
|---|---|---|---|
| **LIDA** (Microsoft, MIT, 0.0.14, last release Feb 2024) | Per column: `dtype` (number/string/category/date/boolean), `std/min/max`, `num_unique_values`, 3 random `samples`, empty `semantic_type` and `description` that the LLM fills in; plus dataset name/description | "Goal explorer" asks the LLM for N goals `{index, question, visualization, rationale}` that must name exact fields; then the LLM **writes plotting code** that is executed | Copy the summary shape and the goal JSON. Do **not** copy code generation/execution |
| **Data Formulator** (Microsoft Research, MIT, 0.7.0, May 2026) | Agents load data into a local engine and see schema + samples; charts via the "Flint" semantic chart spec | Agent recommends charts as compact specs, user refines; agents also generate data transforms (code) | Compact declarative chart spec is the right idea; Syntelio already has ECharts templates |
| **PandasAI** (MIT, 3.0.0) | DataFrame head/schema; LLM writes pandas code that runs | Generated code makes charts | Opposite of our rule. CVE-2024-12366 (CVSS 9.8): prompt injection → arbitrary code execution |
| **Vanna** (MIT, 2.0.2) | DDL, documentation and past question→SQL pairs retrieved by RAG; user-aware tools | LLM writes SQL; runs it; charts from results | Retrieval of schema/docs is useful; Syntelio already validates SQL plans |
| **ydata-profiling** (MIT, 4.18.4) | Not LLM-oriented: full HTML profile (types, missing, histograms, correlations, alerts like "high cardinality", "constant", "skewed") | n/a | Copy its **alert vocabulary**, not the library (pandas-in-memory, heavy deps) |
| **DuckDB `SUMMARIZE`** | `column_name, column_type, min, max, approx_unique, avg, std, q25, q50, q75, count, null_percentage` in one pass | n/a | Use as the cheap first pass on Parquet; replace approximate figures with exact ones where shown to users |
| Voyager / CompassQL / Draco (UW, academic) | — | **Rule-based** chart enumeration from field types (quantitative/temporal/nominal) with ranking by perceptual rules | Best match: the server enumerates valid charts, the model only chooses/ranks |

Common pattern: the model never sees raw rows at scale — it sees a **typed schema + a few stats +
3–5 sample values + semantic hints**, and outputs a **plan/goal list referencing exact field names**.
The weak point in all of them is that the model or its generated code computes the answers; Syntelio
keeps the plan-only rule.

### Recommended compact "dataset brief" (server-built, exact, ≤ ~2–4k tokens)

```json
{
  "brief_version": 1,
  "dataset": {"name": "sales_2026.xlsx#Orders", "rows": "8412339", "columns": 14,
              "grain": "one row per order line (confirmed|inferred)", "source_checksum": "…",
              "date_coverage": {"column": "order_date", "min": "2024-01-01", "max": "2026-09-30",
                                "complete_months": 32, "gaps": []}},
  "columns": [
    {"name": "amount", "type": "decimal(38,2)", "role": "measure", "unit": "PKR (confirmed)",
     "aggregation": "sum", "nulls": "0.4%", "min": "0.10", "max": "98234.50", "sum": "…",
     "distinct": "~51k", "flags": ["skewed", "has_negatives"]},
    {"name": "region", "type": "text", "role": "dimension", "distinct": "7",
     "top": [["North", "31.2%"], ["South", "22.0%"], ["…", "…"]], "flags": []},
    {"name": "order_date", "type": "date", "role": "time", "grain_detected": "day"}
  ],
  "quality": [{"code": "duplicate_rows", "count": "112"}, {"code": "mixed_types", "column": "qty"}],
  "relationships_hint": [{"a": "region", "b": "store", "kind": "hierarchy (each store in one region)"}],
  "labels": {"gender": {"1": "Male", "2": "Female"}},
  "samples": {"rows": 3, "values_redacted_for": ["customer_email"]},
  "analyst_findings": ["finding ids from the six deterministic analysts"],
  "user_goal": "private goal text if set"
}
```

Rules: every number is computed by DuckDB on the Parquet and carried as an exact string; columns
beyond a cap (e.g. 60) are listed by name+type only and the model can request detail through a tool;
samples are few and PII-flagged columns are redacted; the brief is cached per Parquet checksum and
stored with the profile version so reopened answers replay.

### Recommended auto-dashboard approach

1. **Server enumerates candidate tiles** from roles (CompassQL-style rules), e.g.:
   KPI per confirmed measure (sum/avg as configured); time series for measure × time column
   (grain chosen from detected coverage); top-N bar for measure × each low/medium-cardinality
   dimension; share/stacked bar for two dimensions; distribution for a skewed measure; scatter for
   two related measures; map only with confirmed geo roles; table of the six analysts' verified findings.
   Each candidate is already a governed query plan with an id.
2. **Model ranks and picks** 6–9 candidate ids using the brief and the user's goal, writing a short
   title and one-line "why" per tile (LIDA's `{question, visualization, rationale}` but referencing
   candidate ids, not free code). Unknown ids are rejected by validation; with no model, a deterministic
   score (coverage, cardinality fit, finding strength, goal keyword match) picks.
3. **Server executes** each picked plan, stores receipts, renders with the existing ECharts kit and
   six-pin dashboard model; the user can edit/pin/share. Different data → different candidates →
   different dashboard, with no model arithmetic.

## 8. Prioritized implementation list

1. **Ingest core + CSV/TSV/TXT (+ .gz)** on DuckDB 1.5.6 with text-first typing, encoding
   detection/transcoding, Parquet writer, hardened ingest connection and bundled-extension folder.
   Highest volume format; no new dependencies.
2. **XLSX/XLSM** via bundled DuckDB `excel` extension (streams; verified). Keep openpyxl for old
   profile versions and as fallback.
3. **Archive guard (ZIP/GZ/BZ2/XZ)** with stdlib — also used as the bomb check for XLSX/ODS.
4. **JSON/JSONL/NDJSON** via DuckDB with explicit column types and the flatten rule
   (structs → `parent.child` columns; arrays → child table or JSON text; depth cap).
5. **Parquet** input via DuckDB (re-written to the canonical typed Parquet; float columns flagged).
6. **SQLite** via bundled `sqlite` extension (also reused by Phase 3 database connections).
7. **XLS/ODS/XLSB** via `python-calamine` 0.9.0 with a size cap (whole-sheet memory).
8. **SPSS/Stata/SAS** via `pyreadstat` 1.3.7 in chunks, with labels into the brief.
9. **Table-shaped XML** via `defusedxml` iterparse with a record-element picker.
10. **Dataset brief v1 + candidate-tile auto-dashboard** (Phase 3).
11. Optional, on demand: Avro (bundled DuckDB `avro`), Feather/ORC (pyarrow 26, 54 MB), HTML,
    PDF tables (pdfplumber, review-before-import only).

Dependencies to add: `python-calamine==0.9.0`, `pyreadstat==1.3.7`, and declare
`charset-normalizer>=3.4,<4` explicitly. Image additions: `excel`, `sqlite_scanner` (and later
`avro`) extension files for DuckDB 1.5.6 linux_amd64 (~12 + 34 + 12 MB), installed at build time.

## 9. Risks

- **Offline extensions:** if the bundled extension folder or version mismatches DuckDB, `LOAD` fails;
  if autoinstall is left on, the worker silently reaches the internet. Test with network disabled.
- **DuckDB 2.0 is out**; staying on 1.5.x is safe now but extensions must be re-bundled on upgrade.
- **Type decisions on 10M rows** need one extra full scan; text-first doubles the temp disk use
  during ingest (spill dir sizing on the VPS).
- **Excel dates/formats:** `all_varchar` gives serials for dates; date detection relies on the typed
  pass (first data row). Columns with mixed formats need the "mixed types" quality flag.
- **Floats at the source** (SPSS/Stata/SAS/Parquet DOUBLE/XLS numbers) are not decimal in the file;
  shortest-repr conversion reproduces what the source shows but cannot recover precision that the
  source never stored. Say so in the brief.
- **Calamine and pyreadstat memory/robustness**: whole-sheet loading and historical OSS-Fuzz
  overflows in ReadStat; isolate per-job with limits.
- **Formula policy change** for big uploads needs an owner decision (§5).
- **PDF/HTML** extraction quality is poor and should never be presented as exact without review.
- Measurements in §4 were short local runs on synthetic data, not a 500 MB live test.

## Sources

- PyPI JSON API for versions/licences/sizes: https://pypi.org/project/duckdb/,
  https://pypi.org/project/python-calamine/, https://pypi.org/project/pyreadstat/,
  https://pypi.org/project/pyarrow/, https://pypi.org/project/lxml/, https://pypi.org/project/fastavro/,
  https://pypi.org/project/charset-normalizer/, https://pypi.org/project/pdfplumber/,
  https://pypi.org/project/camelot-py/, https://pypi.org/project/xlrd/, https://pypi.org/project/odfpy/
- DuckDB Excel extension: https://duckdb.org/docs/2.0/core_extensions/excel.html
- DuckDB securing guide: https://duckdb.org/docs/2.0/operations_manual/securing_duckdb/overview.html ;
  https://simonwillison.net/2026/Jan/16/duckdb-security/
- python-calamine: https://github.com/dimastbk/python-calamine
- pyreadstat: https://github.com/Roche/pyreadstat ; ReadStat fuzz findings:
  https://osv.dev/vulnerability/OSV-2020-300 , https://db.gcve.eu/vuln/osv-2020-333 ,
  https://vulert.com/vuln-db/heap-buffer-overflow-in-sas7bdat-parse-all-pages-pass2
- lxml XXE in iterparse: https://osv.dev/vulnerability/CVE-2026-41066 , https://lxml.de/changes-5.0.0.html
- PandasAI CVE-2024-12366: https://kb.cert.org/vuls/id/148244
- LIDA: https://github.com/microsoft/lida (`lida/components/summarizer.py`, `goal.py`)
- Data Formulator: https://github.com/microsoft/data-formulator
- PandasAI: https://github.com/sinaptik-ai/pandas-ai ; Vanna: https://github.com/vanna-ai/vanna
- ydata-profiling: https://github.com/ydataai/ydata-profiling
- Draco / CompassQL (rule-based chart recommendation): https://github.com/cmudig/draco2 ,
  https://github.com/vega/compassql
