> **File use case:** Defines bounded external PostgreSQL snapshot imports.
> **What it does:** Records the approved connection lifecycle, exact snapshot boundaries, operation and verification.

# Approved PostgreSQL snapshots

Status: The adapter, versioned registry, atomic import/staged-refresh lifecycle and
owner Sources screen pass local acceptance. This is not yet deployed. Tests use
a separate disposable local PostgreSQL database.
No customer endpoint or credential was used. The actual application's PostgreSQL
database remains its control plane.

An operator-approved source identifies one pinned endpoint, database, secret
reference and at most twenty approved tables. Browser selections can choose only
registered fields, never a connection string, SQL or model-written query. The
adapter quotes identifiers and sends no writes to the source. It requires a
SELECT-only account without superuser, role/database creation, replication or RLS
bypass powers. Views, partitions, inherited tables and unapproved field types are
refused. The bounded first implementation supports ordinary tables, up to fifty
fields, ten thousand complete records, twenty MiB and sixty-four KiB per cell.
An exceeded limit rejects the import; it never returns a sample as a full source.

Source reads use a read-only repeatable-read transaction and a server-side cursor.
A capped count and streamed rows come from the same database snapshot. Connect,
statement and lock timeouts are explicit. Substantive queries use the remaining
shared read budget; elapsed time is checked while consuming rows and before
publication. Network failure/cleanup may extend wall time, so this is not a guaranteed
real-time deadline. These choices follow the official
[PostgreSQL transaction contract](https://www.postgresql.org/docs/18/sql-set-transaction.html)
and [Psycopg cursor documentation](https://www.psycopg.org/psycopg3/docs/advanced/cursors.html).

Private credentials are loaded from a regular, owner-only JSON file under one
operator directory. Symlinks, FIFOs, broad permissions, unexpected keys and path traversal
are refused. Secrets and host/database details are absent from snapshot output,
errors and object representations. TLS hostname/certificate verification is
required outside explicit local-test loopback fixtures; a pinned address prevents
DNS from selecting an unexpected endpoint. The application control-plane endpoint
is explicitly excluded. Production configuration must include every address alias
of that control plane; an operator must not register it as a customer source.

Integer and decimal fields retain their text values without monetary rounding.
Dates and naive timestamps retain their type; PostgreSQL timestamps with timezone
are emitted in UTC, reflecting the stored instant. Text, booleans and UUIDs are
supported. Binary floating-point columns are refused until an explicit source
normalization is chosen, avoiding an implicit binary-to-decimal meaning change.
Non-finite numbers, unsupported values and completely empty records are refused.
SQL null becomes a missing CSV cell. Empty or whitespace-only text is refused so
it cannot silently become indistinguishable from null. Existing upload checks
still apply, including spreadsheet-formula/control-character rules.

Publication binds the source connection version, selected fields,
request ID, actor/membership epoch and dataset access policy. A complete snapshot
must pass the current authority checks inside final upload/staged-refresh
publication. Initial imports require review of shared meanings; staged refreshes
retain the existing explicit schema/meaning review. Nothing auto-confirms a
meaning or auto-activates a changed source. Disconnect stops future extraction;
already retained snapshots remain governed by the normal dataset permissions.

## Owner workflow

In **Data library → Bring in database data**, choose a dataset, approved source,
table and fields. **Import snapshot** retains a new file; use **Review imported
data** to confirm its meaning. No field is automatically confirmed. With a
configured refresh feed, **Stage source refresh** retains a full replacement
candidate. **Review staged refresh** opens the existing review/activation screen.
Staging alone does not change the active feed. A feed's existing schedule still
applies to validated candidates; this screen does not create a new automatic
external polling job.

Requests have an explicit idempotency key. **Retry same attempt** checks the same
work after a lost response instead of reading again or creating duplicate files.
A failed attempt remains failed; **Start a new attempt** reads again explicitly.
At most four unfinished imports may exist per workspace. History shows up to one
hundred of the current actor's attempts; it is not shared with other members or
staff. Owner authority, membership epoch and full dataset access are rechecked
when opening retained import metadata. The files themselves keep the normal
dataset-access rules. Removing an import connection does not delete a file.

## Operator setup and recovery

Configure `EXECPLUS_SOURCE_SECRET_DIRECTORY` to a private directory readable by
the API service. The default is `/run/execplus/source-secrets`. Each reference uses
one `<reference>.json` regular file with mode `0600` and keys `username`, `password`
and optional `root_cert`. `root_cert` is a sibling regular `.crt` filename for the
source CA; it cannot be an arbitrary path. Passwords must not appear in source
registration bodies, browser fields, Git or evidence logs. Production deployment
must mount this directory explicitly; this slice adds no customer secret or
network destination to the VPS.

An active staff administrator who also owns the workspace registers configuration
through `PUT /admin/workspaces/{workspace}/sources/{source}`. It requires an
expected version, a public label, TLS hostname, pinned address, port, database,
secret reference and approved `{schema_name, table, columns}` entries. Limits
can be lowered within the supported bounds. Updates append a new configuration
version; stale forms fail. The owner catalog exposes only labels, versions,
approved table/field names and limits. It does not expose endpoints or secret
references. Registration and recovery have staff audit events; imports have
actor-private audit events.

`GET /admin/workspaces/{workspace}/source-imports/pending` exposes only identifiers,
dataset identifiers, status and creation time to an authorized operator/owner.
After at least five minutes, `POST .../source-imports/{import}/recover` can close
an interrupted attempt with the fixed `source_interrupted` reason. This does not
claim to kill a database process. Its final publication guard rejects a late
response from the old attempt; a new request ID is needed to retry.

External extraction and object writes run outside workspace locks. The short
publication transaction rechecks the connection version, actor/member/policy
epoch, retained file checksum, complete field order/count and refresh candidate.
It saves the import result together with the upload or candidate. Failed checks
roll back that publication. Cleanup deletes only objects proved not to be retained;
uncertain commits preserve possibly referenced bytes until an operator can inspect
them. They are never removed merely because a response was lost.

Migration **0023**, after integration migration 0022, adds `registered_sources`
and `source_imports`. It does not rewrite existing files or meanings. Downgrade
refuses while either new table contains retained configuration or history.

`EXECPLUS_SOURCE_ALLOW_TEST_LOOPBACK=1` is accepted only when the application
environment is exactly `test`. It lets the isolated browser runner use a disposable
local source and private temporary secret directory. Local/staging/production
startup rejects this switch, and the control-plane database stays forbidden even
in tests. This is not an operator workaround for production TLS.

This is not a QuickBooks, Xero, Zoho, Odoo, Sheets or BigQuery adapter, and not an
interactive database SQL console. Those providers retain separate authentication,
rate/cost, schema and acceptance requirements described in the
[identity and connector audit](identity-and-connectors-audit.md).
Actual checks and retained initial failures are recorded in the
[source verification ledger](verification-postgres-source-import.md).
