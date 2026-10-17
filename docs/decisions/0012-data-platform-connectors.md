> **File use case:** Records the data platform connector architecture decision.
> **What it does:** Explains the shared connector framework, credential handling and safety limits.

# ADR 0012: Snapshot connectors for accounting systems, databases and BigQuery

Status: Incoming connector design revised during the October 17 branch integration.
Local candidate only; live provider acceptance and production gates remain open.

## Decisions

- **One framework.** A connector implements a small protocol: browse sources and fetch records.
  OAuth platforms add the authorization, code exchange, refresh and revoke steps; credential
  platforms add a validation step. A single service handles connecting, browsing and importing,
  so secrets, permissions, audit and errors behave identically everywhere.
- **Snapshots.** A source is copied into a normal CSV upload and flows through the existing
  profile, meaning, receipt and refresh paths. ExecPlus never queries a platform live, which
  keeps answers replayable from retained bytes.
- **Credentials.** All secrets are sealed with the existing token vault in one table, one row per
  user and platform. Rotated tokens and cleanup use version-conditional writes so stale
  requests cannot replace a newer connection. One-use server OAuth attempts bind the
  initiating session, browser cookie and connection version; a protected cookie exchange
  returns an application session into memory. Secrets retain exact whitespace.
- **Databases.** Only PostgreSQL is supported because its driver is already a dependency. Sessions
  are read-only and time-limited at the server, and tables are chosen from the database's own catalog.
- **BigQuery.** Tables are copied through the table-data API with read-only consent, avoiding SQL
  generation, a new validator and query cost. Views and live queries are out of scope.
- **Network policy.** User-supplied hosts must be public outside local and test environments.

## Consequences

- Adding a platform means one adapter and one registration; no service, route or table changes.
- Snapshots go stale until re-imported. Oversized sources and ambiguous flattened
  column names are refused. Transport, cumulative records, cells and CSV bytes are bounded.
- Upload publication rechecks the session and connection generation and commits the
  provider audit atomically. UI reload failure after a saved import cannot repeat the write.
- Only the PostgreSQL adapter is verified against a real server; the rest await real credentials.
- Live warehouse queries, more databases and scheduled refresh remain separate decisions.
