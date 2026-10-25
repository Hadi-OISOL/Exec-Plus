> **File use case:** Explains how to enable accounting, database and BigQuery connectors.
> **What it does:** Lists each platform's setup, settings, behavior, safety rules and limits.

# Data platform connectors

Users connect a platform once, choose a source and import it as a normal upload. It then has
a profile, the data reading and replayable answers like any file. Imports are snapshots: they
do not update when the platform changes. To refresh, import again, or stage the platform's
current data into the dataset's [staged refresh](phase4-refresh-monitoring.md) with
`POST /workspaces/{id}/datasets/{id}/connectors/{platform}/refresh-candidates`
(`{source_id, options}`, the same options as a staged file). The candidate goes through the
same validation, schema-change review and activation as an uploaded refresh file; only the
dataset creator or an owner/admin may stage it, and it is audited as
`connector.refresh_staged`. Refreshes are started by a person; nothing polls a platform. A platform appears only
when its settings are present; `GET /connectors` still lists every known platform, with
`configured: false` and no form for those without settings, so the upload screen can say
"Not set up on this server". Every connector needs `EXECPLUS_TOKEN_ENCRYPTION_KEY`
(a Fernet key, see [Google integration](google-integration.md)) and `make migrate` (migration
0029 adds one table and keeps every existing record).

## Platforms

| Platform | Sign-in | Sources | Settings |
| --- | --- | --- | --- |
| QuickBooks Online | OAuth | Invoices, bills, customer and bill payments, expenses, customers, vendors, items, chart of accounts | `EXECPLUS_QUICKBOOKS_CLIENT_ID`, `..._SECRET`, `..._ENVIRONMENT` (`production` or `sandbox`) |
| Xero | OAuth with PKCE | Invoices and bills, contacts, payments, bank transactions, credit notes, items, accounts | `EXECPLUS_XERO_CLIENT_ID`, `..._SECRET`, `EXECPLUS_XERO_SCOPES` |
| Zoho Books | OAuth | Invoices, bills, payments, expenses, contacts, items, chart of accounts, orders, credit notes | `EXECPLUS_ZOHO_CLIENT_ID`, `..._SECRET`, `EXECPLUS_ZOHO_DATA_CENTER` |
| Odoo | Address, database, login, API key | Customer invoices, vendor bills, their lines, payments, contacts, products, accounts, orders | `EXECPLUS_ODOO_ENABLED=true` |
| PostgreSQL | Host, port, database, user, password, TLS | Any table or view, or one read-only SELECT | `EXECPLUS_DATABASE_CONNECTOR_ENABLED=true` |
| MySQL / MariaDB | Host, port, database, user, password, TLS | Any table or view, or one read-only SELECT | `EXECPLUS_MYSQL_CONNECTOR_ENABLED=true` |
| Microsoft SQL Server / Azure SQL | Host, port, database, user, password, TLS | Any table or view, or one read-only SELECT | `EXECPLUS_MSSQL_CONNECTOR_ENABLED=true` |
| Google BigQuery | OAuth (Google client) | Tables in the user's projects | `EXECPLUS_BIGQUERY_ENABLED=true` plus the Google client settings |

Register `{EXECPLUS_PUBLIC_API_URL}/connectors/{platform}/callback` as the redirect URI in each
OAuth app, where the platform is `quickbooks`, `xero`, `zoho_books` or `bigquery`. BigQuery also
needs the BigQuery API enabled in the Google Cloud project; it asks for read-only access and
copies tables through the table-data API, so no query runs and no query cost is incurred.

## Databases (PostgreSQL, MySQL/MariaDB, SQL Server)

All three share one connector base (`infrastructure/connectors/database.py`). Drivers:
psycopg (PostgreSQL), PyMySQL 1.2.3 (pure Python) and pymssql 2.4.5. pymssql was chosen over
pyodbc because its wheels bundle FreeTDS, so the slim API image needs no system ODBC driver.

- **Browse:** schemas, then tables and views, each table with an approximate row count from the
  database's statistics (`pg_class.reltuples`, `information_schema.tables.table_rows`,
  `sys.partitions`). Views show no count. Counts are estimates; MySQL's can be far off.
- **Preview:** `POST /connectors/{platform}/preview` with `{source_id}` returns the first 20 rows
  as exact strings.
- **Custom SELECT:** a `source_id` of `query/<url-encoded SQL>` imports the result of one
  SELECT (at most 10,000 characters). It is parsed in the database's own dialect and refused
  unless it is exactly one SELECT/UNION with no comments, no writes (also inside CTEs), no
  `SELECT ... INTO`, no row locks and none of the functions that sleep, read files, change
  settings or reach other servers (for example `pg_*`, `set_config`, `SLEEP`, `LOAD_FILE`,
  `OPENROWSET`, `xp_*`). It then runs wrapped as `SELECT * FROM (<query>) AS syntelio_query`
  with a row limit, so a second statement cannot run even if the parser were fooled. On SQL
  Server, a query with `WITH` or with `ORDER BY` but no `TOP`/`OFFSET` is therefore rejected
  by the server. Refusals return `connector_query_refused` (422).
- **Import:** rows are read in batches of 2,000 from a streaming cursor and written to a temporary
  file, then handed to the normal upload path as the same CSV artefact as before
  (byte-identical for PostgreSQL; JSON columns are flattened the same way). The 300,000-row
  test tables stay under a 32 MiB Python allocation peak. Limits: `EXECPLUS_DATABASE_CONNECTOR_MAX_ROWS`
  (default 1,000,000; one extra row is probed and a larger source is refused, never cut short),
  the upload size limit (`EXECPLUS_MAX_UPLOAD_BYTES`) and 500 columns. A single row above
  20 MiB is refused for tables before its values reach the application. Binary columns are left
  out of table imports; a custom query that returns binary values is refused. Today the
  upload parser still caps a file at 100,000 rows and 20 MiB, so larger imports are refused
  there until the Parquet upload work raises those limits.
- **Staged refresh:** the same `refresh-candidates` route works for tables and custom queries.
- **TLS:** the form offers *Required* (encrypted, certificate not checked), *Required, with a
  verified certificate* (PostgreSQL `verify-full` against system CAs; MySQL with the system CA
  store; not offered for SQL Server because FreeTDS does not verify) and *Off*. *Off* is only
  offered and accepted where private hosts are allowed (local/test or
  `EXECPLUS_CONNECTOR_ALLOW_PRIVATE_HOSTS`). Leaving it empty keeps the previous default:
  PostgreSQL `prefer` locally and `require` elsewhere; MySQL tries TLS and, outside trusted
  deployments, refuses a server that does not encrypt (`connector_tls_unavailable`).
- **Read-only sessions:** PostgreSQL uses `default_transaction_read_only=on` and a 30 s statement
  timeout. MySQL/MariaDB run `SET SESSION TRANSACTION READ ONLY` on connect plus a 120 s
  statement limit (`max_execution_time` / `max_statement_time`). SQL Server has no read-only
  session, so every session runs inside a transaction that is always rolled back, and
  connecting refuses logins that are `sysadmin`, `db_owner`, `db_datawriter`, `db_ddladmin` or
  hold database-wide INSERT/UPDATE/DELETE/ALTER/CREATE TABLE (`connector_not_read_only`, 403).
  Object-level grants are not detected there; the rollback still undoes them.

### Least-privilege accounts

```sql
-- PostgreSQL
CREATE ROLE syntelio_reader LOGIN PASSWORD '...';
GRANT USAGE ON SCHEMA sales TO syntelio_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA sales TO syntelio_reader;
-- MySQL / MariaDB
CREATE USER 'syntelio_reader'@'%' IDENTIFIED BY '...';
GRANT SELECT, SHOW VIEW ON shop.* TO 'syntelio_reader'@'%';
-- SQL Server (inside the database)
CREATE LOGIN syntelio_reader WITH PASSWORD = '...';
CREATE USER syntelio_reader FOR LOGIN syntelio_reader;
ALTER ROLE db_datareader ADD MEMBER syntelio_reader;
```

Prefer a replica or a reporting copy for large imports.

### SQLite

SQLite files have no server to connect to, so they come in as ordinary file uploads (the
upload format readers handle `.sqlite`/`.db`); there is no SQLite connector form.

## Behavior

- A user's connections are private to them. Disconnecting invalidates the local connection
  and pending handoffs before attempting remote revocation. A revoked or expired grant
  asks the user to reconnect. Version checks prevent stale refreshes from replacing a
  newer connection; browser/session-bound one-use attempts protect OAuth callbacks.
- OAuth platforms use the first organisation or company the user granted.
- Records are flattened into columns (`Customer_name`), lists of objects become a count column
  and Xero dates become ISO dates. Binary columns are skipped. Ambiguous flattened
  or generated column names are refused instead of overwriting source fields.
- Limits: 100,000 rows per import by default (`EXECPLUS_CONNECTOR_MAX_ROWS`, at most 200,000),
  500 columns, 2,000,000 cells and 20 MiB. Platform quotas also apply; Xero allows about sixty
  calls a minute, so a very large import can be slowed or refused.
  Imports probe one extra row and refuse sources above the row limit; a partial source
  must not silently become a complete-looking upload. HTTP responses are streamed with a
  20 MiB cap and identity encoding; compressed responses are refused. Cumulative page
  records and generated CSV have separate byte budgets. PostgreSQL uses a streamed
  cursor and refuses oversized rows before returning their values to the application.
- Imports are audited as `connector.imported`, visible only to the person who ran them.
  The audit and upload publication share one transaction. Failed UI reload after a saved
  import offers a read-only retry, rather than resubmitting the import.

## Safety

- OAuth refresh tokens, Odoo API keys and database passwords are stored sealed with
  authenticated encryption and never logged or returned by any endpoint.
- Secret values retain their exact whitespace; only nonsecret form fields are trimmed.
- Database sessions are forced read-only (rolled back on SQL Server) and time-limited.
  Table names are checked against the database's own list, never spliced into SQL; custom
  queries pass the SELECT checker above.
  Use a dedicated read-only database user anyway.
- Hosts on private networks (loopback, private ranges, link-local) are blocked outside local and
  test environments, and https is required for Odoo. The check resolves the name once, so it
  reduces but cannot remove DNS-rebinding risk. Set `EXECPLUS_CONNECTOR_ALLOW_PRIVATE_HOSTS`
  only for a trusted deployment. Do not point the database connector at Syntelio's own database.

## Verification status

MySQL 8.4, MariaDB 11.4 and SQL Server 2022 (Developer edition container) are tested against
real servers: connect, wrong password, TLS, listing with counts, previews, exact DECIMAL(18,4)
copies, allowed and refused custom queries, read-only enforcement with an account that could
write, private-host and TLS rules, a 300,000-row batched export with bounded memory, and an
API journey (sealed password, import, custom-query import, staged refresh, tenant isolation).
The PostgreSQL connector is tested against a real PostgreSQL server, including the read-only
guarantee and an end-to-end API journey with a least-privilege role (sealed password, browse,
import, re-import as a refresh, tenant isolation). Offline tests record every mock-platform
request and prove reads only (GET, or Odoo `fields_get`/`search_read`), read-only scopes where
the platform offers them (QuickBooks has only its full accounting scope), settings gating and
the error mapping; malformed platform replies become `connector_unexpected_response` (502). The other platforms are tested against mock servers shaped like each platform's
documented API. None has been run against the real platform, and endpoint, scope and field names
should be confirmed with real credentials before relying on them. Xero in particular is moving
to granular scopes, so adjust `EXECPLUS_XERO_SCOPES` if Xero rejects the defaults. Odoo uses
the JSON-RPC endpoint, which Odoo is replacing in version 19 with a newer API. Not included:
Oracle and other databases, live (non-snapshot) queries, unattended scheduled platform polling and report-style data
such as profit and loss.
