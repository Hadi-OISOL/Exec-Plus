> **File use case:** Records the connector identity and session security contract.
> **What it does:** Defines OAuth, self-service account, lifecycle, migration and verification boundaries.

# Connector identity and session boundaries

This local candidate hardens optional provider connections. Verification uses fake
providers, fictional accounts, disposable PostgreSQL schemas and test object storage.
It does not establish provider setup, customer acceptance or production readiness.

## Browser consent and return

- Start creates a server-side attempt with a random state, a hash of an HttpOnly
  browser-binding cookie, a ten-minute expiry and sealed PKCE/nonce material.
  Authenticated connections also record the exact initiating session hash and the
  existing connection version. Existing atomic authentication throttles bound starts
  by account/browser and direct network peer; forwarded addresses are not trusted.
- Callback claims that attempt once before provider I/O. Completion rechecks the
  account, original session, attempt status and connection version in one transaction.
  Disconnect invalidates pending and completed connection handoffs before remote revoke.
  No provider request runs while these database transaction locks are held.
- The return URL contains only `?oauth=complete` or a fixed failure marker. A separate
  HttpOnly, sixty-second handoff cookie is exchanged by an exact-origin JSON POST to
  `/auth/oauth/exchange`. Both handoff and browser binding must match. The handoff is
  consumed once; successful connect returns a fresh application session and revokes
  only its initiating session. Provider denial can safely restore that still-active
  session with a bounded error. Revoked, disabled or expired sessions cannot resume.
- Application bearer tokens never appear in the OAuth URL or browser storage. They
  are returned only by the protected exchange and held in application memory. Cookies
  use `SameSite=Lax`, path `/`, and `Secure` for a configured HTTPS API. Local HTTP
  verification uses the same hostname for web and API, with separate ports. Production
  cross-site cookies/HTTPS/domain configuration remain deployment acceptance work.
- Credential and exchange JSON use the existing streamed 8 KiB body limit before
  parsing. Field-count/character bounds are additional limits; a schema-valid Unicode
  payload can still exceed the overall byte limit and be rejected.

## Identity, permissions and connection races

Google sign-in creates an explicitly classified self-service principal keyed by the
verified provider subject. The code verifies issuer, audience/authorized party, nonce,
expiry and verified email on tokens returned by the configured server token exchange.
It never accepts an arbitrary client-supplied ID token. Existing native or operator
accounts are never associated merely because their email matches. Reusing an existing
subject retains the same account ID, including when provider email changes.

New self-service workspaces receive the existing Demo allowance assignment. This is
an internal plan, not payment or billing activation. Exact-account approval is still
required for invitations and staff grants. Native password change/recovery remains
password-only. The account screen identifies Google access separately from operator
access and offers no unsupported password recovery. No general email verification
status is claimed. External account disable state is enforced by bearer authentication,
retained service calls, API keys, embeds and queued jobs; this slice does not add a
customer-facing external-account disable/recovery flow.

Every stored connection has an opaque version. Refresh-token rotation and failure
cleanup use conditional updates/deletes; stale requests cannot replace or remove a
newer connection. Credential validation also creates a fenced operation, so disconnect
or logout during validation prevents saving credentials, including first connection.
Provider reads recheck the current session/version before returning. File imports
repeat that check inside the existing upload publication transaction after parsing and
object storage. The provider-import audit commits in that same transaction. An audit
failure therefore publishes no upload and cleans up its newly written object; a later
retry does not duplicate a secretly committed upload.

## Schema and retained work

Migration 0028 follows existing 0027. It adds Google connection versions, provider
identities and OAuth attempts, and changes the invitation approval user reference to
`users.id` so an explicitly approved provider identity is representable. Migration 0029
adds versioned generic connections. Existing approval rows and business data remain.
Downgrade refuses retained identities/connections/attempts and unsupported approval
references rather than discarding them. Operator retention/removal is deliberate.
Expired OAuth attempts are cleaned during later allowed starts; active records remain
bounded by the existing atomic authentication rate windows.

## Verification

The retained initial runs passed 56 compatibility cases and 25 new security cases.
Subsequent review found missing shared self-service guards and a late upload-publication
race; both were repaired before a 221-case gate passed in 311.17 seconds. A further
review found a separate post-publication audit transaction; both provider tests
reproduced a committed upload despite the returned error. That audit now shares the
publication transaction. The final focused run passes all 94 cases in 121.49 seconds,
including both audit rollback/retry regressions; initial failures remain in the evidence.
Ruff passes for all changed Python files, and the configured mypy gate passes all
311 source files. The two formatting-only blank lines added after the final test run
were checked to leave the parsed Python syntax trees unchanged. See the machine reports under ignored
`data/verification/2026-10-17/connector-merge/` for final counts and source hashes.
Overlapping focused runs are not additional distinct tests.
The browser return tests mock provider responses; SQL/cookie/state tests exercise the
actual local backend. No real OAuth consent, provider delivery or live credentials
were used in either suite.
