> **File use case:** Records the first additive platform-foundation decisions.
> **What it does:** Explains reuse of existing artifacts, PostgreSQL jobs and governed compute with visible activity.

# ADR 0008: Extend existing evidence with durable conversation execution

Date: 2026-10-04. Scope: local/test and the private demo. Acceptance evidence is in
[the release ledger](../verification-platform-foundation.md); production approval
and the remaining proposal slices are separate.

## Context

ExecPlus already retains source revisions, definitions, query receipts, document
passages and study versions. Its conversation endpoint originally waited for the
entire answer in one HTTP request. A richer analysis platform needs typed outputs,
bounded work, cancellation and understandable progress while keeping those existing
permissions and exact-result contracts. The preimplementation
[audit](../platform-foundation-plan.md) defines the dependency order.

## Decision

Expose typed artifact/capability and quality projections over the existing owning
aggregates. Each traversal reauthorizes its references. Descriptors identify
metadata availability; source-byte integrity and exact replay remain separate
checks. Do not duplicate existing resources in a generic artifact table or advertise
future statistical/ML operations as currently supported capabilities.

Use PostgreSQL-backed conversation jobs with bounded attempts, leases, workspace
concurrency, ordered events and transactional terminal publication. A job reuses
one existing private turn and request identifier. Retry only safe pre-start claims;
started work interrupted by a lost lease fails conservatively. Exclude stale
attempts from publishing. Preserve synchronous `/ask` and historical answer replay.
This first workflow does not migrate every worker or promise exactly-once execution.

Keep the existing QueryExecutor port. The application compute broker selects only
operator-registered engines and validates scope/bounds before dispatch. DuckDB is
the sole runtime engine; it retains strict conversion, isolated connections and
exact decimals. Container limits and cooperative query deadlines do not constitute
an arbitrary-code sandbox. Future engines must independently satisfy the contract.

Store a strict server-derived plan describing supported execution and immutable
sources. It is not a model-authorized general DAG executor. Publish real action
codes at execution boundaries, without prompt contents, hidden reasoning or source
values. Simple/Expert are views of the same evidence. Neither view grants permission
or runs calculations merely because it was selected.

## Alternatives and consequences

An in-process background task would lose durable state across API restarts and
cannot coordinate multiple API workers. A separate queue platform would add an
unnecessary service for this bounded workload. Reusing the existing PostgreSQL
control plane provides transactions and claim fencing with less operational scope.
General ingestion/statistical workflows can later use proven shared primitives,
but do not inherit conversational budgets or retry safety automatically.

A unified artifact table would duplicate established versions and access rules.
Projections keep those sources authoritative and expose an extension boundary;
they do not add derived-object retention, rebuild, vector or export lifecycles.

The browser can reconnect and request cancellation, but cleanup can outlast the
execution deadline. Operators must run `make jobs` locally or the Compose worker
on the VPS. Backups stop API and conversation writers before storage; refresh keeps
its maintenance lock. Worker fatal logs contain a categorical outcome, not bound
SQL parameters or exception traces. New 0013 metadata must survive future rollbacks.

Parser/disclosure policies, new methods, process-isolated execution, experiments,
connectors and production operational reviews remain separately gated work. These
interfaces alone provide no evidence of better model quality or sustained capacity.
