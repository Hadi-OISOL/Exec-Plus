> **File use case:** Tracks combined acceptance for the remaining independent tools.
> **What it does:** Separates verified local behavior, deployment evidence and actual external dependencies.

# Independent tools release verification

Candidate application **b817068** (runtime sources unchanged from **6818176**) targets additive migration **0024**. It is not
yet activated; the live private demo remains **867c5a0 / 0020**. The full backend
and browser regression runs were interrupted and are being resumed. This ledger must be updated from
their actual results before describing the candidate as delivered.

## Implemented contracts

- [Usage accounting](usage-metering.md): actor/workspace-bound provider attempts,
  explicit versioned prices and allowances, concurrent reservations, unknown-cost
  handling, reconciliation and owner summaries. No prices or paid plans are invented.
- [Scoped integration access](integration-access-plan.md): issuer-only keys,
  revocation, exact source scope, one-use host-bound dashboard embedding and signed
  bounded webhook delivery. Customer destinations and signing configuration remain
  external setup; the private demo is not made public.
- [Approved PostgreSQL snapshots](postgres-source-import.md): operator-selected
  tables/fields, SELECT-only credentials, bounded complete snapshots, idempotent
  import, schema review and explicit refresh activation. Customer endpoints and
  credentials remain external setup. Local fixtures use a separate real database.
- [Source-derived scenarios](source-derived-scenarios.md),
  [seasonal anomalies](seasonal-anomaly-method.md),
  [distribution drift](distribution-drift-method.md) and
  [larger allocations](large-allocation-method.md): declared deterministic methods,
  explicit assumptions, preserved exact source values and private immutable results.
  The solver distinguishes proven optimal, feasible, infeasible and unknown outcomes.
- [Company consolidation](company-consolidation.md): explicit account mappings,
  periods, conversion rates and balanced intercompany eliminations with exact layers,
  private saved worksheets and protected exports. This is not automatic accounting
  judgment or a claim of accounting-standard certification.

## Local evidence

Ruff, mypy across **262 files**, **59 frontend tests**, types, lint and the production
web build pass. Targeted method, service, privacy, migration and browser evidence
is retained in each linked contract's verification ledger. Independent source review
found no additional blocker in the bounded solver's lifecycle, exact scaling,
outcome handling or source/private-result checks.

The fixed evaluation passes **89 exact tests across 32 named cases**, with no
skips or missing results. The declared local eight-user workload passes **300.003
seconds / 1,400 sustained requests**, including 280 expected private/scope denials,
with zero unexpected statuses or failed exact/privacy checks. All 48 original
files and meanings remain unchanged. The highest operation p95 is 582.186 ms;
peak process RSS is 322.340 MiB. This is a paced fictional local workload, not
representative customer, shared-workspace contention, hosted-model or production
acceptance. See [the complete evidence](verification-next-batch-evaluation.md).

## Retained defects and operational preparation

An independent review reproduced an owner issuing an integration key for another,
more broadly authorized member. Keys now bind only to their issuer, with current
scope checks. Another review reproduced two disjoint-company worksheet creations
exceeding the same person's fifty-run limit. A narrow organization/person
transaction lock makes that limit atomic. Both initial failing regressions and
their passing repairs remain recorded.

The additive release procedure checks all prior business-table fingerprints and
configuration. Automatic rollback requires both twelve empty new tables and
unchanged prior business tables: new calendar/scenario/allocation results use
existing tables and must also prevent rollback to code that cannot reopen them.
No saved work is overwritten from a backup. Private activation and live checks
remain pending.

Upstream license files retain their original whitespace; the ordinary diff check
excludes only that attributed license directory. A first candidate-build command
lost its administrative SSH control connection before staging/building; the fresh
authenticated connection is used for the retry. A browser-runner help invocation
without its required test database environment stopped before any test ran.
These attempts are not successful verification executions. The first candidate
image builds, but the historical core-compute check rejects the newly declared
pandas dependency. The check now permits only the pinned pandas/OR-Tools pair
and still refuses undeclared PyArrow; its Ruff/mypy checks pass. The 6818176 image
separately passes 22 actual analytics/solver/license checks as UID10001 with no
network, read-only filesystem, 1 GiB/one CPU/64-process limits, plus the older
advanced forecast and all four portable formats. The final candidate build and core/pattern/depth/domain checks pass with the
repaired operator check. Its 22 new analytics/solver/license checks and portable
forecast/export checks also pass; application/UI/migration files are unchanged.
One long browser journey reaches saved-answer reopening but exceeds its total
120-second test budget while waiting to click a resolved button. The failure is
retained and a focused recheck is pending. The shared workstation is under memory
pressure; this observation does not by itself prove the timeout cause.

Private evidence: `data/verification/2026-10-16/remaining-work/combined-nextbatch/`
and the per-feature directories. Tokens, source files, browser profiles, generated
reports and downloaded backups remain ignored. All eight production gates remain
blocked.

## Interrupted verification and migration rehearsal

The interrupted full backend log contains 963 passing progress dots, but no final
summary or XML; it is not a completed suite. The interrupted browser run records
42 passes, one model skip and the retained 120-second timeout, with thirty of
seventy-four journeys unreported. Fresh complete runs retain these earlier logs.

The isolated pre-activation migration rehearsal passes in 39 seconds against the
checked `20261016T123757Z` backup. Migration 0020 to 0024 preserves all fifty prior
business tables and creates twelve empty tables. Verification checks 93 uploads,
95 revisions, 27 documents/passages, twenty exact receipt replays and one current
permission denial. The temporary network has no published ports or live data
volumes. Cleanup removes its containers, network and objects; live application
container identities/start times and configuration remain unchanged. This is
pre-activation evidence, not a deployment or a post-release restore.
