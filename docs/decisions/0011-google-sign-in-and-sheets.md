> **File use case:** Records the Google sign-in and Google Sheets import architecture decision.
> **What it does:** Explains the identity adapter, token storage and snapshot import choices and their limits.

# ADR 0011: Google sign-in and snapshot import from Google Sheets

Status: Accepted for the user-requested October 15 private-demo integration. It does not
clear any production gate.

The only identity adapter refused to run outside local/test, and Google Sheets was the
first planned connector (Phase 4E). Add Google as the sign-in method and as a source,
without changing how sessions, permissions, uploads, profiles, receipts or refresh work.

## Decisions

- **Identity.** Google OpenID Connect (authorization code with PKCE) proves the caller's
  verified email. ExecPlus then issues its normal opaque, expiring session, so every route,
  permission and audit rule is unchanged. A production-capable `DatabaseSessionIdentity`
  now backs sessions; `LocalSessionIdentity` keeps its local/test restriction.
- **Claims.** Issuer, audience, expiry, nonce and `email_verified` are checked. The ID token
  comes straight from Google's token endpoint over TLS, so its signature is not re-verified
  (OpenID Connect Core 3.1.3.7); non-local environments must use https endpoints.
- **Access to sheets.** A separate, user-initiated consent requests only `drive.file`, a
  non-sensitive scope that reaches only files the user opens with Google's picker. Nothing
  broader is requested, and sign-in never requests it.
- **Tokens.** Refresh tokens are sealed with authenticated encryption
  (`EXECPLUS_TOKEN_ENCRYPTION_KEY`), stored one row per user and never logged. Disconnecting
  revokes the token at Google and deletes the row. A revoked grant removes the row and asks
  the user to reconnect.
- **State.** Sign-in binds a sealed, ten-minute state to the browser with an HttpOnly cookie.
  The connect flow carries the sealed state in OAuth `state`, which names the initiating user,
  so no cookie is needed across origins.
- **Import.** A chosen tab is copied into a normal CSV upload (raw numbers, formatted dates)
  and follows the existing profile, meaning, receipt and refresh paths. Answers still replay
  from retained bytes; ExecPlus never queries Google live.

## Consequences

- Any user with a verified Google account can sign in. Public exposure still needs the
  deferred Phase 5 reviews, and Google verification is needed beyond the Testing-mode user
  cap or when broader scopes are added.
- Sheets are snapshots. They go stale until re-imported; scheduled refresh from Google is
  future work. Limits: 20 MiB, 200,000 rows, 500 columns, 2,000,000 cells, one tab per import.
- BigQuery, Gmail and live warehouse queries are separate decisions and remain Phase 6.
