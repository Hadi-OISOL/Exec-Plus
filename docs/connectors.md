> **File use case:** Explains how to enable accounting, database and BigQuery connectors.
> **What it does:** Lists each platform's setup, settings, behavior, safety rules and limits.

# Data platform connectors

Users connect a platform once, choose a source and import it as a normal upload. It then has
a profile, the data reading and replayable answers like any file. Imports are snapshots: they
do not update when the platform changes, so import again to refresh. A platform appears only
when its settings are present. Every connector needs `EXECPLUS_TOKEN_ENCRYPTION_KEY`
(a Fernet key, see [Google integration](google-integration.md)) and `make migrate` (migration
0019 adds one table and keeps every existing record).

## Platforms

| Platform | Sign-in | Sources | Settings |
| --- | --- | --- | --- |
| QuickBooks Online | OAuth | Invoices, bills, customer and bill payments, expenses, customers, vendors, items, chart of accounts | `EXECPLUS_QUICKBOOKS_CLIENT_ID`, `..._SECRET`, `..._ENVIRONMENT` (`production` or `sandbox`) |
| Xero | OAuth with PKCE | Invoices and bills, contacts, payments, bank transactions, credit notes, items, accounts | `EXECPLUS_XERO_CLIENT_ID`, `..._SECRET`, `EXECPLUS_XERO_SCOPES` |
| Zoho Books | OAuth | Invoices, bills, payments, expenses, contacts, items, chart of accounts, orders, credit notes | `EXECPLUS_ZOHO_CLIENT_ID`, `..._SECRET`, `EXECPLUS_ZOHO_DATA_CENTER` |
| Odoo | Address, database, login, API key | Customer invoices, vendor bills, their lines, payments, contacts, products, accounts, orders | `EXECPLUS_ODOO_ENABLED=true` |
| PostgreSQL | Host, port, database, user, password | Any table or view | `EXECPLUS_DATABASE_CONNECTOR_ENABLED=true` |
| Google BigQuery | OAuth (Google client) | Tables in the user's projects | `EXECPLUS_BIGQUERY_ENABLED=true` plus the Google client settings |

Register `{EXECPLUS_PUBLIC_API_URL}/connectors/{platform}/callback` as the redirect URI in each
OAuth app, where the platform is `quickbooks`, `xero`, `zoho_books` or `bigquery`. BigQuery also
needs the BigQuery API enabled in the Google Cloud project; it asks for read-only access and
copies tables through the table-data API, so no query runs and no query cost is incurred.

## Behavior

- A user's connections are private to them. Disconnecting revokes OAuth tokens at the platform
  and deletes the stored record. A revoked or expired grant asks the user to reconnect.
- OAuth platforms use the first organisation or company the user granted.
- Records are flattened into columns (`Customer_name`), lists of objects become a count column
  and Xero dates become ISO dates. Binary columns are skipped.
- Limits: 100,000 rows per import by default (`EXECPLUS_CONNECTOR_MAX_ROWS`, at most 200,000),
  500 columns, 2,000,000 cells and 20 MiB. Platform quotas also apply; Xero allows about sixty
  calls a minute, so a very large import can be slowed or refused.
- Imports are audited as `connector.imported`, visible only to the person who ran them.

## Safety

- OAuth refresh tokens, Odoo API keys and database passwords are stored sealed with
  authenticated encryption and never logged or returned by any endpoint.
- Database sessions are forced read-only and time-limited; writes are refused by the server.
  Table names are checked against the database's own list, never spliced into SQL.
  Use a dedicated read-only database user anyway.
- Hosts on private networks (loopback, private ranges, link-local) are blocked outside local and
  test environments, and https is required for Odoo. The check resolves the name once, so it
  reduces but cannot remove DNS-rebinding risk. Set `EXECPLUS_CONNECTOR_ALLOW_PRIVATE_HOSTS`
  only for a trusted deployment. Do not point the database connector at ExecPlus's own database.

## Verification status

The PostgreSQL connector is tested against a real PostgreSQL server, including the read-only
guarantee. The other platforms are tested against mock servers shaped like each platform's
documented API. None has been run against the real platform, and endpoint, scope and field names
should be confirmed with real credentials before relying on them. Xero in particular is moving
to granular scopes, so adjust `EXECPLUS_XERO_SCOPES` if Xero rejects the defaults. Odoo uses
the JSON-RPC endpoint, which Odoo is replacing in version 19 with a newer API. Not included:
MySQL, SQL Server or other databases, live queries, scheduled refresh and report-style data
such as profit and loss.
