> **File use case:** Records the September 30 wide-spreadsheet query repair.
> **What it does:** Explains the reproduced failure, exact numerical contract, regression checks and private deployment evidence.

# Wide spreadsheet query repair

The reported total and dashboard both returned HTTP 422 on the deployed API.
The authorized upload had 216 rows and 163 columns. Profiling reported no type
conflicts, but seven cells in four unrelated numeric columns required 13–27
fractional places. Loading every column as DECIMAL(38,12) blocked a valid total.
Conversation handling then replaced that actionable failure with a generic retry
message. No uploaded values or credentials are recorded in this document or tests.

The query adapter now selects an exact per-column scale of at least twelve and
at most thirty-eight, retaining the existing total precision bound. It projects
only SQL-referenced columns, including WHERE, GROUP BY and join dependencies.
Sample counts preserve all source rows even without a referenced column; unknown
source columns remain rejected. Invalid referenced values fail with the column,
one-based data-row position and expected format/range. No value is silently dropped,
rounded or turned into a binary float during loading. AVG retains its documented
twelve-place half-even output contract.

Profile-v1, source bytes, full-source checksums, ordinary decimal formatting,
tenant checks, join cardinality guards, receipts and model composition are unchanged.
The repair adds no migration and does not advance any phase or production gate.

## Verification

- All 160 numeric-column totals in the reported upload match independent Python
  Decimal sums at precision 80. Source content was inspected only through the
  authorized private session and retained temporarily in ignored, restricted files.
- Focused query/refresh/study run: 88 passed, one warning, 80.22 seconds.
- Ruff, formatting checks and mypy (109 source files) pass.
- Final full suite: **485 passed**, one warning, 225.24 seconds. This includes
  **24 new regression cases** (23 precision/scope cases and one mixed-answer case).
- Live API: five affected/requested totals match independent Decimal sums, all
  five replay exactly, and both source/revision checksums are unchanged. A
  pre-repair monitoring observation still replays as `0.300000000000`.
- Deployed Chromium: dashboard HTTP 200, the exact reported question returns a
  complete answer with a visible Verified badge, and replay matches the answer.
  Passed at **2026-09-30T14:54:56.748Z**. The dataset has multiple uploads; this
  check explicitly selected the reported upload rather than the newest default.
- Running container digests match all four changed API files. Dependency readiness
  passes for PostgreSQL and object storage. The production manifest is unchanged.

Synthetic regression coverage includes decimal scales 13/27/38, exponent notation,
trailing zeros, negatives, exact JSON/replay, tiny numeric filters, unused conflicts,
referenced metric/filter/group/record failures, invalid precision/range/non-finite
values, high-precision joins, empty/full sample counts, unavailable columns,
actionable chat history and document/data partial answers.

An intermediate full-suite run exposed 25 study/monitor failures because their
column-free COUNT(?) plans need a cardinality-preserving relation. That repair
and explicit empty/nonempty-count regressions were added before live activation.

## Commands

```bash
docker run -d --rm --name execplus-queryfix-postgres -p 127.0.0.1:15433:5432 \
  -e POSTGRES_USER=execplus -e POSTGRES_PASSWORD=execplus -e POSTGRES_DB=execplus postgres:16-alpine
docker run -d --rm --name execplus-queryfix-minio -p 127.0.0.1:19000:9000 \
  -e MINIO_ROOT_USER=execplus -e MINIO_ROOT_PASSWORD=change-me minio/minio:latest server /data
export EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus
export EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000
python3 -m pytest apps/api/tests/test_query_precision.py apps/api/tests/test_refresh.py apps/api/tests/test_studies.py --tb=short
python3 -m pytest --tb=short
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m ruff format --check apps/api/src/execplus/infrastructure/query/duckdb_executor.py apps/api/tests/test_query_precision.py apps/api/tests/test_unified_conversation.py
python3 -m mypy
git diff --check
python3 data/vps-private/query-fix-api.py
node data/vps-private/query-fix-browser.mjs
docker stop execplus-queryfix-postgres execplus-queryfix-minio
```

Only ExecPlus-owned disposable containers are used; unrelated local services are
untouched. The patch is based on committed `phase2` baseline `c9560af`; deployed
source digests were compared with that baseline before updating the four API files.
Rollback source is `releases/pre-queryfix-20260930/` on the VPS, with API image
`oisol-execplus/api:pre-queryfix-20260930`. Code-only build logs are under
`ops/queryfix-build-final.log`; runtime imports passed in a clean operator container.
The API was activated under `/run/lock/execplus-maintenance.lock` using
`docker compose -f deploy/vps/compose.yaml up -d --no-deps api`. The existing web,
model, database and storage containers were preserved. No migration was needed.
Private sanitized reports are `data/vps-private/query-fix-api-result.json` and
`data/vps-private/query-fix-browser-result.json`; full regression output is retained
as `data/vps-private/query-fix-pytest.log`. Diagnostic copies of source rows were
removed after verification. One-off private diagnostic scripts require the original
authorized session and temporary inputs; synthetic tests are the durable reproduction.

Refresh the browser, select the intended upload, start a new conversation and retry.
Failed historical turns remain historical failures; they are not rewritten as successes.

The administrator SSH master disconnected during the final optional documentation
sync. The local app tunnel was restored with the assigned restricted demo key and
keepalive settings; final API readiness and workspace HTTP 200 both pass. Repair
documentation/tests are maintained in the local checkout; that optional VPS copy
did not complete. The four deployed API files had already passed digest verification.
