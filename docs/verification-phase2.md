> **File use case:** Audits the teammate's Phase 2 branch against roadmap acceptance.
> **What it does:** Records inherited implementation, concrete gaps, fixes and test evidence.

# Phase 2 audit — 2026-09-17

Fetched `origin/phase2` at `7d70cd7` and checked out a local tracking branch from a
clean `main` at `2eb8b4b`. The teammate's commit is preserved. No merge to main or
remote rewrite has occurred.

Existing scope includes structured aggregate queries, DuckDB execution, KPI and
dashboard definitions, intent routing, summaries, joins, saved items and threads.
ROADMAP.md, AGENTS.md and the setup guide still described Phase 2 as not started.

Initial code findings requiring verification/hardening:

- Decimal columns are converted to DOUBLE and invalid booleans become false.
- Execution does not independently bind the plan to the workspace; SQL validation
  is a keyword scan and external access is not disabled.
- Query timeout interrupts but leaves a connection and worker ownership unresolved.
- Stored lineage lacks immutable upload/revision references, bound parameters,
  execution outcome and returned-result evidence; failures are not recorded.
- KPI matching silently takes the first competing column.
- Profile-v1 semantic tags were changed without a version transition.
- Thread-turn lookups omit workspace_id; thread access omits owner enforcement.
- Saved-item payloads are untyped; saved-analysis replay and share-link UI are absent.
- Summary validation accepts number words and scale suffixes without verifying them.
- No Phase 2 browser acceptance journey or current API/operational documentation.

Phase 3 is authorized by the current user request. Its provider/corpus evaluations
require actual model endpoints and an approved representative corpus; synthetic
fixtures alone must not be presented as completing those gates.

## Resolution and acceptance

The findings above were corrected rather than accepted as roadmap checkmarks.
Phase 2 is verified for supported local/test operation on 2026-09-17:

| Acceptance | Evidence |
| --- | --- |
| Golden numerical answers | Aggregate, filtered, grouped, joined and KPI integration suites; Decimal 0.1+0.2, exact AVG, large-integer JSON and bound numeric-string regressions |
| Read-only and tenant isolation | AST/external-access attack cases, executor scope checks, workspace integration and join authorization |
| Ambiguous/unsupported never execute | Intent-router suites and a competing-revenue regression that forbids even a model call |
| Reconstructable numbers | Typed receipts, immutable revisions/checksums, replay before/after cleaning, scoped replay refusal |
| Dashboard and drill-down | API golden tests plus browser filter/drill-down/replay journey |
| Summary grounding | Executed statement selection; arbitrary prose, number words, exponents and invented evidence IDs rejected |
| Deterministic KPI recommendations | Governed library/template fixtures; competing mappings are omitted pending clarification |
| Shared analyses remain authorized | Saved-item ownership/tenant suites, report recipient tests, authenticated share-link browser journey |

The initial timeout regression and missing infrastructure were resolved. Later
browser checks caught an incorrect test assumption (the amount KPI is AVG, not
SUM) and a real mobile overflow in the hidden accessible trend table. The assertion
now checks its defined AVG, and the accessible table has a correctly bounded wrapper.

Verification commands from the repository root:

```bash
git fetch origin
git switch --track origin/phase2
python3 -m pip install -e '.[dev]'
python3 -m pip install 'sqlglot>=27,<28'
python3 scripts/wait_infra.py
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus make check
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus make test-browser
python3 -m compileall -q apps/api/src
make migrate
git diff --check
```

The full check passes: Ruff, mypy (79 source files), frontend ESLint/TypeScript,
286 backend tests, 2 frontend tests and the production Next.js build. Five real-service
Chromium tests pass. Tests migrate disposable PostgreSQL schemas and use private
MinIO buckets; no SQLite substitutes or skipped integration tests. The local database
was migrated to 0007 and PostgreSQL/object-store readiness returned healthy.

The remaining limitations are explicit contracts: single-table aggregates and declared
unique-right-key joins, bounded DECIMAL scale, no composite KPI expressions, local/test
opaque-session identity, and configured-model dependence for natural-language input.
Live provider comparisons belong to Phase 3. Historical pre-receipt answers cannot
be retroactively proven. No merge, push, real email or hosted document transmission
was performed by this verification run.
