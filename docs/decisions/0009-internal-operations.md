> **File use case:** Records the permission boundary for internal operations.
> **What it does:** Separates staff metadata/support authority from customer data permissions.

# ADR 0009: Explicit staff grants and operational projections

**Status:** Accepted for the authorized private-demo operations slice, October 6, 2026.

## Context

The VC priorities require an admin console and support workflow spanning customers.
Existing workspace owner/admin roles are customer roles. Reusing them for global
administration would silently broaden authority over other workspaces and private
conversations. Ordinary feedback is intentionally limited and cannot track a support
conversation or resolution. Existing usage records can support reporting, but naive
audit-action counts also count automatic worker activity as human retention.

## Decision

Add persistent staff grants managed only by the operator CLI, with distinct `admin`
and `support` roles. Privileged requests check and lock the current grant, audit
their metadata-only operation and release the lock with their transaction. Revocation
applies to later requests. No grant changes the workspace membership checks on
existing source, document, query, forecast or conversation APIs.

Internal admin routes are explicitly audited global operational projections. Global
workspace discovery returns bounded customer/resource metadata; detail and support
resource lookups retain an explicit workspace ID. Support queues span only the
purpose-specific requests users intentionally submitted. Ticket text is accessible
to its requester and active staff, not automatically to another customer manager.
There is no impersonation, arbitrary query execution, attachment/log ingestion or
external delivery. Grants, support events and privileged audit are retained in 0015.

Product reports reuse SQL aggregates over existing records. A versioned allowlist
of deliberate product actions establishes observed activity/cohorts. Automatic query
and worker events remain available for operational counts but do not independently
establish retention. Historical cohort membership and current workspace membership
are separate denominators. Incomplete weeks remain unavailable.

## Consequences

Operators can troubleshoot workflow state without acquiring silent source-data
access. Staff grants remain a powerful support-text/metadata privilege and must be
reviewed separately before public customer use. API responses cannot undo data
already returned before revocation. Support text needs production retention/privacy
policy; staff audit is operational history rather than tamper-evident compliance
storage. Billing, identity/security reviews, incident processes and off-server
recovery remain outside this private-demo acceptance.

Aggregation substantially reduces application-side event materialization in measured
fixtures. It is not a universal performance claim: history still requires database
work, and representative alpha budgets/load tests remain required. Legacy API response
shapes and original analytical evidence stay compatible. See
[contracts](../operations-console-support.md) and [verification](../verification-operations.md).
