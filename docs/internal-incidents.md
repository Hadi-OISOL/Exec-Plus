> **File use case:** Defines self-contained internal service-error monitoring.
> **What it does:** Records redacted collection, administrator review, retention and verified operational boundaries.

# Internal service alerts

The staff administrator console includes **Service alerts**. It lists fixed categories
for HTTP server errors, failed or expired analysis jobs, failed refresh activation and
failed scheduled reports. An administrator can acknowledge or resolve an incident.
Acknowledgement keeps counting new occurrences; a new occurrence reopens a resolved
incident. These actions do not repair or retry failed work.

Access requires an active platform **admin** grant. A workspace owner, workspace admin,
support staff member or revoked platform administrator cannot read or change incidents.
Every successful or denied administrator action is recorded in the existing staff audit.
Updates use an expected version so a stale page cannot overwrite a new occurrence.

## Collection and privacy

The API process queues HTTP responses with status 500 or higher and unhandled request
failures without waiting for database work. The queue holds 256 entries. It records a
fixed category, an opaque generated occurrence ID and a time; it accepts no request
path, query string, headers, body, error message, stack trace, SQL, token or customer data.

An asynchronous collector polls about every thirty seconds. Durable job, refresh-audit
and report-delivery records provide only occurrence IDs, times and fixed status/code
fields. The collector never selects their private plans, questions, result values or
source evidence. Unrecognized job failure codes become a fixed generic job category.
Persistent occurrence keys prevent the same durable failure from being counted again
after a restart or simultaneous collection by another API process.

All stored incident descriptions come from the fixed code registry. Public incident
records contain component, category, severity, status, exact count and timestamps.
They do not expose the underlying job or source IDs. The two additive tables in
migration **0020** preserve existing records; downgrade refuses while incident evidence
remains. No worker code or external monitoring provider is required.

## Bounds and recovery

The collector keeps thirty days of occurrence keys, with a 100,000-key maximum, and
removes resolved incidents whose last occurrence is older than thirty days. Active
categories remain visible. A full key store produces a capacity alert. Uncollected
durable failures remain at their source; request events beyond that bound may be lost.
The bounded request queue also emits a count of entries dropped by overflow.

SQL collection has a five-second deadline after obtaining a connection. Each statement
uses its remaining deadline and database locks have a one-second timeout. Collection
uses bulk key insertion and grouped counter updates. Connection acquisition retains
the application's three-second connection timeout and thirty-second pool wait limit.
Cancellation waits for the active SQL worker to finish; shutdown stops polling and
drains an active operation before disposing the database engine.

If storage is unavailable, pending request events remain queued and the collector logs
only the fixed message `incident_collector_unavailable`. Successful storage recovery
records a recovery incident. The console shows collection time, pending failures and
capacity state. When it cannot load that status, it shows a failure rather than claiming
the service is healthy. Counts from separate collection processes share durable storage,
while queue and collector-health details describe the serving process.

A process crash can lose its pending in-memory request errors. Durable failures remain
available for the thirty-day polling window. These tests do not prove arbitrary
network-packet-loss behavior, an external uptime guarantee or complete request tracing.
There is no external paging, email notification or automatically scheduled remediation.

## Observed checks

The focused suite passes **25 tests** in 8.321 seconds: nineteen incident cases, the
real migration/readiness roundtrip and five architecture checks. It verifies the
fixed-data contract, queue overflow, storage recovery, staff denial/revocation/audit,
optimistic state transitions, durable failure polling, concurrent deduplication,
retention/capacity bounds, middleware privacy and non-destructive downgrade.

A real held PostgreSQL advisory lock times out near one second. Cancelling collection
waits for that SQL attempt to end before returning; queued events remain retryable.
A real closed-port connection failure recovers against the working database. A
500-occurrence batch is stored completely within the collection budget. These are
bounded functional checks, not sustained-load acceptance. Mypy checks seven affected
source files; frontend types and lint pass.

The real browser journey passes in 32.4 seconds (38.7 seconds including the runner).
It waits for an actual durable refresh-failure record to be collected, acknowledges
and resolves it through the API, filters the resolved record, then revokes staff
access and checks that privileged cards disappear. The 1440, 390 and 320 pixel
layouts have no horizontal overflow, action targets are at least 44 pixels high,
and no page errors occurred. The accompanying access-policy journey also passes
in 13.2 seconds. Screenshots were inspected at desktop and narrow mobile widths.

The initial incident browser attempt failed with HTTP 422 because the acknowledgement
request omitted its JSON content type. The request now sends that header explicitly;
the regression checks both the actual request header and successful response before
checking the saved review state. The failed run remains in the evidence directory.
These checks describe local/test behavior; deployed acceptance is still pending.
Local logs remain under ignored
`data/verification/2026-10-16/remaining-work/`.
