> **File use case:** Owner-approved three-phase plan for the October 26 data-intake work on Syntelio.
> **What it does:** Lists what each phase delivers, the facts found on October 25, and how each phase is verified and released.

# Data intake plan — October 26

Owner goal: accept every common data file, much larger files, and live database connections.

## Facts found on October 25

- Google Sheets import builds a filename from the sheet/tab title; titles containing `/`, `\`, `:`
  or `%` fail `validate_filename` (`infrastructure/file_parser.py`) with "Use a plain filename
  without paths or control characters."
- Size is capped at 20 MiB in three places: `max_upload_bytes` and `google_import_max_bytes`
  (`config.py`, both hard-capped `le=20 MiB`) and Caddy `SYNTELIO_MAX_REQUEST_BYTES` (25 MiB).
  Query limits also bound large files: 200,000 input rows, 2,000,000 cells, 256 MB DuckDB memory.
- Only `.csv` and `.xlsx` are accepted (`file_parser.py`).
- Existing database connector: read-only PostgreSQL (tested end to end); BigQuery mock-only.

## Phase 1 — Fix imports and lift size limits

- Google Sheets: build a safe filename from the title (replace unsafe characters) instead of
  refusing; keep the strict check for user-typed upload names.
- Raise limits to a configurable ceiling (target 200 MiB upload / import), streamed to object
  storage without loading the whole file in memory; matching Caddy limit and timeouts.
- Raise query bounds proportionally (rows/cells/memory) with measured timings on large
  synthetic files; keep exact numbers and refuse honestly above the new ceiling.
- Progress bar for big uploads; clear message when a file is over the limit.

## Phase 2 — Every common data file format

- Add: `.xls` (old Excel), `.xlsm`, `.ods`, `.tsv`/`.txt` delimited, `.json` / `.jsonl`,
  `.parquet`, `.xml` (table-shaped), `.sav`/`.dta` (SPSS/Stata) if a small pinned reader exists,
  `.sqlite`/`.db` (pick a table), and `.zip`/`.gz` containing one of these.
- Multi-sheet/table files ask which sheet/table to import (Excel already has tab choice in Sheets).
- New uploads get the next profile version; old files replay unchanged.
- Each format: a real sample file test, exact-number check against pandas, malicious-file checks
  (zip bombs, formula injection, oversized nesting).

## Phase 3 — Database connections

- Add read-only connectors for MySQL/MariaDB, Microsoft SQL Server, and SQLite file upload;
  harden PostgreSQL; table/view picker with row-count preview; optional custom read-only SELECT
  validated by the existing SQL safety checker.
- Credentials encrypted at rest (existing pattern), private-host rules, row limits, and staged
  refresh like other connectors.
- Each connector tested against a real local database container.

## Release

Each phase: agents in worktrees → merge → full backend + browser suites → checked backup →
release with the 2026-10-25 kit (copy, bump date; add migration handling only if a phase adds
one) → live check on https://syntelio.173-208-151-137.sslip.io.
