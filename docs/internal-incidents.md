> **File use case:** Defines self-contained internal service-error monitoring.
> **What it does:** Records redacted collection, administrator review, retention and verified operational boundaries.

# Internal service alerts

## October 17 local extension — implemented; full gate pending

The current local-only task extends this collector; it does not activate a live
release. Migration **0027** adds bounded request aggregates and
versioned in-app alert policies. The historical evidence below remains historical
until the new implementation has its own passing checks.

- Every API response carries a server-generated `X-Request-ID`. Incoming IDs
  are not trusted or echoed. A server failure uses that same opaque identifier
  for its fixed-code occurrence; durable workers retain their existing job IDs.
- Fixed operation categories distinguish ingestion, exports, analysis, queue
  submission and other requests. Classification uses registered route metadata,
  never a saved raw path. Health probes and administrator polling do not dilute
  product-request error rates. Rejected requests are counted separately from
  server failures; an expected permission denial is not an application crash.
- Collection flushes bounded minute aggregates in the existing short database
  transaction. A stable batch identifier prevents duplicate counts if a commit
  succeeds but its acknowledgement is interrupted. Pending data stays in memory
  only within a fixed bound; overflow, outages and crash-loss limitations remain
  explicit. No request body, uploaded value, email, token, SQL or traceback is
  included in aggregate records or structured application error messages.
- Active staff administrators can inspect request counts, rejection/failure
  counts, mean/maximum time to response headers and a clearly stated observation window.
  This is not streaming-download duration or background-job duration.
  Rates use actual recorded denominators. Empty or insufficient observations
  cannot become a healthy-service claim. Process collector health and shared
  database observations are shown separately.
- An administrator may configure a category's minimum sample, failure-count and
  failure-rate thresholds with optimistic version checks and audit history.
  The in-app alert reports its threshold, observation window and current state;
  it does not send email, page an external system, repair a job or claim complete
  uptime monitoring. Existing incident acknowledgement/resolution remains an
  independent human-review action.

The final focused incident/architecture run passes **50 tests** in **23.59 seconds**:
26 new metric/correlation cases, nineteen existing incident cases and five
architecture cases. This covers duplicate/concurrent collection, actual commit
acknowledgement loss, retention, storage outages, bounded pending memory, exact
denominators, threshold boundaries, stale policy edits, staff revocation and
private metadata exclusion. Full regression and actual browser verification are
still pending; this is not a deployment claim.

Request observations retain two days of minute aggregates and at most 50,000
batch keys. Each process has at most 256 pending minute/category buckets plus
one immutable batch of at most 256 buckets awaiting acknowledgement. At capacity,
that batch retries while ordinary incidents can still collect; later overflow is
counted. A retry older than the deduplication horizon is discarded, never counted
again. The displayed dropped-or-expired count describes this process, not a
complete global loss measurement. Process crashes may lose pending observations.
Default thresholds are disabled. A rule compares exact integer ratios over the
last 1–60 completed minutes, requires its minimum request and failure counts,
and uses a failure threshold in hundredths of one percent. Empty windows report
insufficient evidence when enabled. Rates shown to two decimals are display
rounding; the numerator and denominator remain available.

`PUT /admin/incidents/thresholds/{category}` records explicit versioned settings.
`GET /admin/incidents/{incident_id}/references` exposes at most fifty retained
opaque request/job references to the same active platform administrator role.
Older rows lacking the new category cannot be retroactively correlated. Accepted
jobs emit only their opaque job ID and server-generated request ID in structured
application logs. Unhandled HTTP exceptions return a generic 500 with that ID;
raw exception text is not logged by this boundary. Streaming failures after
headers are outside these header-outcome counts.

The first focused run caught a false conflict from an INSERT rowcount assumption;
RETURNING now checks actual persisted policy writes. That initial failure and a
fixture-property mistake are retained in the Phase 1 verification ledger.

## Historical private-demo behavior (prior to this local change)

The staff administrator console includes **Service alerts**. It lists fixed categories
for HTTP server errors, failed or expired analysis jobs, failed refresh activation and
failed scheduled reports. An administrator can acknowledge or resolve an incident.
Acknowledgement keeps counting new occurrences; a new occurrence reopens a resolved
incident. These actions do not repair or retry failed work.

Access requires an active platform **admin** grant. A workspace owner, workspace admin,
support staff member or revoked platform administrator cannot read or change incidents.
Every successful or denied administrator action is recorded in the existing staff audit.
Updates use an expected version so a stale page cannot overwrite a new occurrence.

## Final private-demo release

Application `867c5a0` is deployed on schema `0020`. Combined final backend coverage,
restricted images, live API/browser acceptance, preserved data/configuration and
checked pre/post backups are recorded in the
[release ledger](verification-remaining-work-release.md). Earlier pending-deployment
statements below describe their historical checkpoints. Production acceptance
remains separate; no production gate is cleared.


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

### October 17 shutdown recheck

Metrics-only pending observations and stable retry batches now receive one bounded
collection attempt at graceful shutdown. All 28 metric checks pass, including both
shutdown states. Abrupt process loss and a failed final storage attempt can still
lose pending observations; collection health continues to expose that limitation.
