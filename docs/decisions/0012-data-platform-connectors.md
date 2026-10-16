> **File use case:** Records the data platform connector architecture decision.
> **What it does:** Explains the shared connector framework, credential handling and safety limits.

# ADR 0012: Snapshot connectors for accounting systems, databases and BigQuery

Status: Accepted for the user-requested October 15 private-demo extension. Broader connectors were
frozen in Phase 6; this slice was explicitly requested and does not clear any production gate.

## Decisions

- **One framework.** A connector implements a small protocol: browse sources and fetch records.
  OAuth platforms add the authorization, code exchange, refresh and revoke steps; credential
  platforms add a validation step. A single service handles connecting, browsing and importing,
  so secrets, permissions, audit and errors behave identically everywhere.
- **Snapshots.** A source is copied into a normal CSV upload and flows through the existing
  profile, meaning, receipt and refresh paths. ExecPlus never queries a platform live, which
  keeps answers replayable from retained bytes.
- **Credentials.** All secrets are sealed with the existing token vault in one table, one row per
  user and platform. A rotated refresh token is saved immediately. OAuth state is sealed and
  time-limited and names the initiating user, so no cross-origin cookie is needed.
- **Databases.** Only PostgreSQL is supported because its driver is already a dependency. Sessions
  are read-only and time-limited at the server, and tables are chosen from the database's own catalog.
- **BigQuery.** Tables are copied through the table-data API with read-only consent, avoiding SQL
  generation, a new validator and query cost. Views and live queries are out of scope.
- **Network policy.** User-supplied hosts must be public outside local and test environments.

## Consequences

- Adding a platform means one adapter and one registration; no service, route or table changes.
- Snapshots go stale until re-imported, and large sources are capped.
- Only the PostgreSQL adapter is verified against a real server; the rest await real credentials.
- Live warehouse queries, more databases and scheduled refresh remain separate decisions.
