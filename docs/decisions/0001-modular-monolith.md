> **File use case:** Architecture decision record for the initial application shape.
> **What it does:** Records why Syntelio starts as a modular monolith and when services may be extracted.

# ADR 0001: Begin with a modular monolith

- Status: Accepted
- Date: 2026-09-02

## Context

The alpha requires ingestion, analytics, conversations, and auditing, but the workload and organizational boundaries have not yet been measured.

## Decision

Use a web application and a Python modular monolith with explicit domain, application, presentation, and infrastructure boundaries. Run asynchronous work in a separate process only when Phase 1 introduces jobs. Share application code, not transport or vendor objects.

## Consequences

Local development, refactoring, transactions, and testing remain straightforward. Module contracts make later extraction possible. Independent deployment and scaling are deferred until telemetry identifies a bottleneck or ownership boundary.

