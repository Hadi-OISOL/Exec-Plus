> **File use case:** Records the anomaly and recommendation architecture decision.
> **What it does:** Keeps domain methods extensible while preserving verified execution and private human review.

# ADR 0010: Bounded evidence-backed decision analysis

Status: Accepted for the user-authorized October 10 private-demo extension; release
verification is recorded separately.

Existing profiles, thresholds and forecasts do not implement statistical anomaly
detection or a constrained recommendation engine. Extend the modular monolith with
versioned, server-owned domain methods and a separate private analysis aggregate.
Reuse retained sources, confirmed meaning, query executor, typed receipts and audit;
do not overload historical study/forecast records or give language models arithmetic.

Initial methods are weighted snapshot MAD/IQR candidate detection and bounded
integer allocation under one budget. Eligibility and assumptions belong to each
method. There is no universal detector or generic optimizer that can justify every
business intervention from observational data. Later methods must add independent
evaluations, explicit capability contracts and reconstructable versioned evidence.

Each immutable run binds source, meaning, method, request and calculated result.
Reopening replays and recomputes the full contract. Private reviews append under an
optimistic sequence; approvals require current feasible evidence. Workspace/staff
management does not bypass owner privacy. An approval never executes an external
action. Ordinary answer-sharing/summary paths cannot publish or mutate these receipts.

Use standard-library Decimal and bounded methods before introducing optional
scientific solvers. Computation is off-thread inside bounded HTTP operations; future
durable scheduling and refresh/alert integration require their own lifecycle checks.
Migration 0016 is additive. Preserve existing exact decimals/profile versions and
old query/study/forecast behavior. Broad Phase 6 and production gates remain frozen.
