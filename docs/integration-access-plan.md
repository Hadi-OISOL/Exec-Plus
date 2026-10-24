> **File use case:** Defines the customer integration and private embedding contracts.
> **What it does:** Explains the implemented scope, configuration, safety boundaries and observed verification separately from release status.

# Customer integration and private embedding

October 17 continuation: the local Phase 2 extension adds saved studies,
forecasts, analyses and job-status scopes, every-source key checks, a local host
example, embed-read audits and cleared integration state after a failed reload.
See [the current API contract](customer-results-api.md) and
[its evidence](verification-governed-distribution.md). The following counts and
migration notes describe the earlier foundation and are retained as history.

Status: implementation is in the working tree on additive migration **0022**, after
metering **0021**. It is not deployed. The focused backend/architecture run passes
**62 tests** in 42.688 seconds, followed by focused cancellation and operator-origin
regressions (**64 distinct backend/architecture cases**). All **55** frontend tests,
types, lint, Ruff and scoped mypy pass. The final Chromium integration journey passes
in 14.9 seconds (21.9 seconds including startup), including six responsive layouts,
readable saved measure labels and unchanged raw receipt column identities. The real
refresh-event delivery regression also passes after the separate RefreshService
lock repair. No external receiver, public exposure or new model provider is enabled.

## Read-only integration access

The owner creates a distinct, opaque API key bound only to their own issuing
account, one to twenty explicit datasets and named read-only operations. Issuing
a key for another member is refused, even when that member has broader access.
The UI creates a key for the owner and explicitly selected datasets. The database stores only
the SHA-256 hash. Each key records the issuer's membership creation epoch, expiry
(up to ninety days), revocation and last-use time. Atomic rate windows allow sixty
requests per minute per key. These operations do not invoke a language model.

The dedicated API supports:

- `GET /integration/v1/workspaces/{wid}/datasets/{did}/uploads/{uid}/profile`
- `POST /integration/v1/workspaces/{wid}/datasets/{did}/uploads/{uid}/rows`
- `POST /integration/v1/workspaces/{wid}/datasets/{did}/uploads/{uid}/query`
- `GET /integration/v1/workspaces/{wid}/boards/{board_id}`
- `GET /integration/v1/workspaces/{wid}/studies/{version_id}`
- `GET /integration/v1/workspaces/{wid}/datasets/{did}/forecasts/{forecast_id}`
- `GET /integration/v1/workspaces/{wid}/datasets/{did}/analyses/{analysis_id}`
- `GET /integration/v1/workspaces/{wid}/jobs/{job_id}`

Send the key in `Authorization: Bearer <key>`. Use the ordinary typed rows/query
request shapes. These routes call the existing governed services, preserve exact
numeric strings and receipts, and apply current row/column permissions. A key cannot
change its actor. Board reading requires the board and every pinned study to be
shared, visible to the principal and inside the key's dataset scope. Keys cannot
sign in to the workspace, upload files, manage users or open private conversations.

Key issuance, revocation and successful reads are audited. Membership removal and
re-addition cannot reactivate an old key. Access, expiry and policy epochs are checked
before work and again immediately before publication. Source reads and computation
run outside the workspace lock. Secrets appear only in the explicit creation response
and current UI; they are not stored in URLs or browser storage. Revocation stops future
reads, but cannot retract results a caller already downloaded.

Owner management endpoints are `/workspaces/{wid}/integrations/keys` (GET/POST) and
`.../keys/{key_id}` (DELETE). POST accepts `name`, `dataset_ids`, `operations`,
`expires_seconds`, and optional `user_id`, which must equal the signed-in issuer
when supplied. Operations are `profile:read`, `rows:read`,
`query:read`, `boards:read`, `studies:read`, `forecasts:read`, `analyses:read`
and `jobs:read`. No operation is inferred from a key's name.

## Signed metadata events

An explicit owner subscription watches that owner's jobs or refresh activations for
selected datasets. The first supported events are `job.succeeded`, `job.failed` and
`refresh.accepted`. Every body contains only a fixed version/type, event/resource/
dataset IDs and occurrence time. There are no questions, answers, filenames,
definitions, receiver response bodies or raw error messages. Refresh occurrence time
comes from the actual activation audit event.

Delivery is disabled by default. Enabling requires BOTH protected operator settings:

- `EXECPLUS_WEBHOOK_MASTER_SECRET`: at least 32 bytes; generate a high-entropy value
  locally and keep it in the protected environment file.
- `EXECPLUS_WEBHOOK_DESTINATIONS`: a JSON object mapping exact approved HTTPS origins
  to fixed public IP addresses, for example `{"https://receiver.example":"<public-ip>"}`.

There is no runtime DNS lookup and no user-supplied address override. TLS still verifies
the approved hostname. The direct HTTP transport ignores proxy environment variables,
does not follow redirects, limits response reading and closes the active connection
at a five-second wall deadline. Loopback HTTP destinations require the explicit
`EXECPLUS_INTEGRATION_ALLOW_LOOPBACK=true` setting, which is rejected outside local/test.
No local test request goes to an external receiver.

Per-subscription/version signing secrets derive from the protected master through
HMAC-SHA256. The secret is shown once as hex and can be replaced explicitly. Decode
that hex to bytes when verifying. Each request contains:

- `X-ExecPlus-Event-ID`: stable opaque event ID, unchanged across retries.
- `X-ExecPlus-Signature`: `t=<unix-seconds>,v1=<hex-hmac-sha256>` over the exact bytes
  `<unix-seconds>.<body>`.

Receivers must use constant-time comparison, reject timestamps outside a five-minute
window and remember processed event IDs. A valid signature alone does not prevent
replaying a recent message. Changing a signing secret affects subsequent attempts;
an already dispatched request cannot be withdrawn.

The database outbox deduplicates subscription/type/resource identities. A ten-second
worker poll collects at most 200 events and makes at most ten attempts per pass.
Claims use `SKIP LOCKED`, thirty-second leases and unique lease IDs; stale workers
cannot overwrite a newer attempt. Successful 2xx responses finish delivery. Network
failures, 408, 429 and 5xx retry after 10/30/120/600/3600 seconds, up to six total
attempts. Redirects and other 4xx responses stop. This is **at-least-once**, not exactly
once: a receiver may process a message before the sender loses its acknowledgement.

Every attempt rechecks current membership epoch, subscription, event ownership and
dataset scope. Job evidence also must still match its policy scope. Revoked access
cancels delivery before transport. There is no workspace lock across HTTP work.
Database operations have bounded statement/lock deadlines; cancellation drains a
started attempt before engine disposal. The outbox retains thirty days and at most
5,000 records globally. A full queue is shown in owner settings; collection resumes
when capacity returns. Events older than the retention window are not redelivered.

Owner endpoints under `/workspaces/{wid}/integrations/webhooks` support list/create,
`/{id}` revoke, `/{id}/rotate`, and `/{id}/deliveries` (last 100 attempts). Owners cannot
subscribe to another member's private job activity. The UI shows configuration state,
last worker failure, queue capacity and delivery status without exposing signing keys
on reopening.

## Private embedded boards

The owner explicitly creates a view of a shared board whose pinned study versions are
also shared. A grant binds the owner, membership epoch, board version and exact host
origin. Its opaque bootstrap secret works once within five minutes; exchange creates
a separate fifteen-minute view session. Both secrets are hashed in the database.
Neither is in a URL, localStorage or sessionStorage. The owner UI shows a one-use HTML
snippet for the approved host; a host's authenticated server may instead call the same
creation endpoint and transfer the result to its authorized page. Production host
login remains the host application's responsibility.

`POST /workspaces/{wid}/integrations/embeds` takes `board_id` and `host_origin`.
GET lists current owner grants; DELETE `.../embeds/{id}` revokes. The frame URL is
`/embed/{grant_id}` and contains only the grant ID. The frame announces
`{type:"execplus:ready",grantId}` to its exact parent origin. The approved parent sends
`{type:"execplus:open",grantId,secret}` to the exact Syntelio origin. The frame checks
both `event.origin` and `event.source === window.parent` before exchanging the token.
It never executes received HTML, SQL, chart options or arbitrary script.

The HTTP response uses `Content-Security-Policy: frame-ancestors <approved-origin>`.
The Next.js proxy looks up only the grant's host descriptor using the fixed server
`EXECPLUS_INTERNAL_API_URL`, never a request-provided URL. VPS host networking uses
`http://127.0.0.1:18401`; local tests use their configured API origin. Proxy metadata is
not authorization: the API separately checks every exchange and read. Missing,
expired or revoked descriptors deny framing. Responses are no-store with no-referrer.

Every board read checks expiry/revocation, current membership, board version, board
sharing, every study's sharing and current source permissions before and after replay.
Changing the board requires a new grant. The view uses the same real ECharts charts,
exact tables, coverage and recorded calculation evidence as the application. It has
no editing or workspace navigation. Expiry clears the displayed data; a failed manual
access refresh also clears it. An already displayed/downloaded result cannot be
remotely erased from a host's memory.

## Evidence and boundaries

The passing backend runs includes actual scoped query/profile/rows and exact shared
board reads, owner-only controls, ordinary-session rejection, membership replacement,
policy/revocation races, single-use exchange, host mismatch, session expiry, migration
preservation and nonempty downgrade refusal. Real loopback HTTP checks cover signatures,
metadata-only content, retry identity, rotation, stale leases, six-attempt exhaustion,
redirect refusal, pinned-address rejection, bounded sockets and cancellation drain.

Initial failures were four test callbacks using synchronous TestClient on its event
loop; the corrected callbacks run on a worker thread. A later aggregate command used
an absent architecture-test directory and collected no tests; the corrected explicit
file run supplies the 62 passes. These attempts remain in ignored verification logs.
The first browser attempt created and revoked a real key and generated an embed, then
failed because its intercepted synthetic public HTTPS page could not access loopback:
Chromium reported `ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS`. A real local TLS host,
ephemeral fixture certificate and context-only certificate bypass model the approved
HTTPS site without relaxing application origin/CSP rules. The corrected journey
passes strict parent-source exchange, actual wrong-host CSP denial, exact large/
negative/missing values, private evidence, key/session revocation and six responsive
layouts. A duplicate React sibling key was repaired, and integration controls now
mount only inside Team so leaving the view destroys its one-time secrets. A frontend
lint finding was corrected by separating asynchronous settings reads from state
application; failed post-save reloads now say the action completed.
Final screenshots were recaptured after resetting the iframe's scroll position;
this was a verification-helper adjustment, not an application failure. They show
the full dashboard heading and the same readable Manrope typography at 1440, 390
and 320 pixels. The approved-host fixture still uses a real local TLS server.

No live, representative security, cross-browser or sustained-load acceptance is
claimed. Release status will be recorded separately.
Customer domain/TLS, real host authentication and an explicitly approved destination
remain operator/customer inputs. No external account is needed for the implemented
local receiver path.

Primary references checked for these contracts:
[MDN frame-ancestors](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors),
[MDN postMessage](https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage),
[GitHub webhook signature verification](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
and [Python HMAC](https://docs.python.org/3/library/hmac.html).
