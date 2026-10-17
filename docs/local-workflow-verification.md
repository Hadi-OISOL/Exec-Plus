> **File use case:** Local synthetic workflow, recovery, evaluation and performance runbook.
> **What it does:** Gives repeatable commands that preserve original evidence and keep external acceptance separate.

# Local workflow verification

These tools use the existing Python environment, PostgreSQL/MinIO test stack and application services. No dependency, provider, paid service or credential integration was added. They never use the VPS, existing backups, customer files or saved browser sessions. Run commands from the repository root after installing its normal development dependencies.

## Explicit fictional inputs

```bash
.venv/bin/python scripts/create_synthetic_workflow_kit.py --output data/synthetic-workflow-v1
```

This writes nine CSVs, an integrity/meaning manifest and a short walkthrough; it does **not** import anything. The generated companies, employees, amounts, exchange rates and outcomes are fictional. Unchanged files can be regenerated; edited files and symbolic links are refused before writing further files.

- Finance: 120 complete generated days; revenue **12,714 USD**, cost **7,557 USD**.
- Sales: 240 order lines; **720 items**, revenue **2,340 USD**, cost **1,188 USD**. Unit price is not additive.
- Inventory: thirty days of two SKU snapshots. Only the final date totals **329 items**; adding stock snapshots across dates is misleading.
- HR: 24 fictional employees; monthly salary total **30,900 USD/month**, **21 full-time equivalents**. This snapshot establishes no hiring, turnover, fairness or causal conclusions.
- Company A/B: distinct USD/EUR ledgers with explicit fictional conversion assumptions. Use separate company workspaces and deliberate consolidation grants. No exchange rate, elimination or source access is guessed.
- Dirty data: missing values, an exact duplicate, whitespace, invalid numeric/date text. Review and preview transformations before applying; nothing is silently cleaned.
- Precision/null fixture: exact independent Decimal arithmetic retains the **0.000000000000000001** residual. Engines that cannot retain that scale must refuse or disclose their limit; this fixture does not promise arbitrary precision in every query method.
- Formula fixture: expected upload rejection. It is intentionally unsafe CSV text, not a valid demonstration upload.

The generator's oracles use independent standard-library Decimal arithmetic with precision 80. `numeric_parse_complete` describes parsing only; it is not permission to aggregate a field. Meaning, units and sharing still require normal application confirmation.

## Synthetic recovery rehearsal

```bash
PYTHONPATH=apps/api/src .venv/bin/python scripts/rehearse_local_recovery.py \
  --output data/verification/local-recovery-NEW-RUN
```

The two normal development images must already be cached: `pgvector/pgvector:pg16` and `minio/minio:RELEASE.2023-03-13T19-46-17Z`. The runner uses `--pull=never`; it does not install images. It creates its own labelled temporary containers/network with loopback-only ephemeral ports and bounded temporary storage. Source and restore databases/buckets are newly generated; existing names are rejected even if empty. Cleanup removes only resources created by this invocation.

The runner clears inherited application/provider configuration, explicitly disables models/email/vector/webhooks, migrates a fresh source, registers a fictional native account with its local Demo plan, and uploads fictional finance/sales/HR data through authorized API routes. It retains private onboarding progress, an explicitly configured staff alert policy and real local HTTP metrics. It confirms the declared meanings and checks independently known totals. It then creates a custom PostgreSQL dump and bounded object archive, with code/schema/image identity, table fingerprints and SHA-256 metadata.

Before restoring, it validates dump/object sizes and checksums, rejects archive links, traversal, duplicate/extra/missing entries and never extracts paths onto the filesystem. It restores only the new target, without `--clean`. The existing recovery verifier runs under database read-only settings, checks source/revision integrity and replays representative exact receipts. Source, restored and post-verification fingerprints must agree. The report retains failure type and elapsed time even if a stage fails. A new output directory is required for every attempt.

This proves a local synthetic procedure only. Off-server custody, retention policy, production restores and formal recovery time/data-loss objectives remain unverified. The report's elapsed time includes temporary setup and is not a production RTO.

## Fixed offline evaluation

The existing `scripts/check_analysis_evaluation.py` accepts `docs/two-phase-evaluation-cases.json`: **40 named cases / 112 exact checks**, including all 32 earlier cases. It uses deterministic/scripted model responses and records actual pass, failure, skip, missing-node and duplicate-node results. New dimensions count distinct checks for numerical correctness, source citation binding, unsupported-output rejection, access control and replay consistency. They are regression counts, not representative model-accuracy percentages.

Use dedicated disposable local PostgreSQL/MinIO test services and the repository's usual `EXECPLUS_TEST_*` variables. Disable model, email and vector routes explicitly; never source deployment configuration. Then run:

```bash
PYTHONPATH=apps/api/src .venv/bin/python scripts/check_analysis_evaluation.py \
  --manifest docs/two-phase-evaluation-cases.json \
  --output data/verification/two-phase-evaluation-NEW-RUN
```

The output must be ignored by Git and new. Every selected check must pass; skips never become passes. Unsupported-claim fixtures cover specific numerical, structural and tool claims. They do not establish universal detection of unsupported prose or representative live-model quality, spending, speed or customer-data behavior.

## Repeatable local benchmark

```bash
PYTHONPATH=apps/api/src .venv/bin/python scripts/benchmark_data_workflow.py \
  --fixtures data/verification/workflow-benchmark-inputs \
  --output data/verification/workflow-benchmark-NEW-RUN.json
```

This uses new cached-image temporary containers, fresh synthetic schemas/buckets and the existing API integration helpers. No endpoint or credential argument is accepted. It measures CSV/XLSX validation and reading, PDF/XLSX/CSV rendering, ingestion/profiling, profile read, query, dashboard, forecast, and saved-study exports. Each operation runs four times: first after imports, then three warm calls. It checks exact source cells, revenue **24,339.000** and the known forecast first estimate **4.1**. Input XLSX bytes are retained across runs, including the archive metadata; their hashes must match for comparisons.

Reports retain the full timing samples, warm median, derived **serial** operations/second, process high-water RSS, fixture hashes, source hashes, versions and failures. High-water RSS includes imports/prior operations and excludes containers; it is not per-operation peak memory. There is no operating-system cache flush or concurrent-load claim. Pause other verification jobs when collecting comparisons, and state remaining host contention. Report every slower operation too.

The October 17 immutable pre-change run at `d4db038` is retained in `data/verification/2026-10-17/two-phase/baseline/before.json` with its original runner and identical inputs. The initial profile identified redundant XLSX loading/row traversal. The combined parser collects only request-local rows during mandatory validation; archive security checks, values, source checksums, permission scope and old parser-port fallback remain intact. No shared value cache was introduced.

Tracked evidence: [original 37 regression report](regression-original-37.md), [Phase 1 verification](verification-codex-phase1.md), [Phase 2 verification](verification-codex-phase2.md). An implementation or run command is not a passing verification result; consult those ledgers for actual executions and remaining gates.
