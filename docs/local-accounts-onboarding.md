> **File use case:** Defines local password accounts and resumable setup without external identity services.
> **What it does:** Records the identity boundary, account lifecycle, private guide state, operator recovery and verification requirements.

# Local accounts and guided setup

**Implementation status:** Implemented for the October 17 local-only two-phase
task in additive migration `0025`, with synthetic integration/security checks.
See [the verification record](verification-local-accounts-onboarding.md) for exact
runs and remaining acceptance checks. This does not authorize production
deployment or access to existing customer data.

## Identity boundary

An email address is a local account identifier. Registration does **not** establish
ownership of that mailbox, a company identity or a domain. There is no SMTP,
OAuth, payment service, email verification or email password-reset endpoint.
The existing operator-issued, expiring bearer sessions remain supported.
An existing operator account cannot acquire a password through public signup.

Registration creates a new user, password credential, owned workspace and explicit
price-free Demo allowance in one transaction. Later workspaces created by native
accounts receive the configured default plan. These are internal allowances, not
paid subscriptions. Existing operator workspaces retain their prior assignment.
The registration response is identical when the identifier is
unavailable; it never replaces an existing credential or membership. A separate
login verifies the password and creates a random opaque session. Session tokens
are hashed in the database and held only in browser memory, not local storage,
cookies, URLs or saved onboarding state. Reloading requires signing in again.

Password hashing uses Python's standard-library scrypt with an independent
random salt, `N=131072`, `r=8`, `p=1`, and a constant-time digest comparison.
Each process admits at most two simultaneous password computations and rejects
additional attempts immediately with a retryable error. Unknown-user login follows
the same hashing path. New passwords contain 15–128 characters, at most 512 UTF-8
bytes. Passwords are never trimmed or silently truncated; explicit length bounds
reject unreasonable input before hashing.
This follows the [OWASP scrypt guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
using [Python hashlib](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt).
It adds no package or external service. This is a reviewed implementation choice,
not an independent security certification.

Login, registration and sensitive credential changes use committed, atomic rate
windows keyed by a hash of the operation and normalized identifier or direct peer.
Local Makefile, image-default and browser-test launches use `--no-proxy-headers`,
so client-supplied forwarding headers do not replace the peer address. Existing
VPS deployment commands are unchanged; their proxy/header policy still requires
separate review before native accounts are exposed there. Limits apply before expensive
hashing and failed attempts consume the allowance. Application errors omit
passwords, token values and submitted account identifiers. Generic authentication
responses follow [OWASP authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

Registration permits five attempts per identifier and twenty per direct peer per
hour. Login permits ten per identifier and sixty per peer per fifteen minutes.
Password change and disable each permit five per account and sixty per peer per
fifteen minutes. These are fixed windows, with possible bursts across a boundary;
they are not a claim of distributed abuse protection or trusted proxy deployment.

Browser requests to account mutation routes must use the configured web origin
when an Origin header is present. JSON is required. Authentication uses an
explicit Authorization bearer header and does not use ambient cookies; a foreign
site cannot automatically attach the account's credentials. Non-browser clients
may omit Origin and must still provide the applicable password or bearer session.
This does not establish safe public HTTP transport; public HTTPS and deployment
review remain separate gates.

## Account lifecycle and access

- Login issues an eight-hour session, retaining at most eight current native
  sessions. Logout revokes that session immediately.
- Password change requires the current password, revokes all existing sessions,
  and returns one replacement session. Concurrent changes cannot reuse an old
  credential after another change commits.
- Account disable requires the current password. It revokes account sessions and
  dependent keys/embed grants and denies subsequent workspace access, worker
  publication and other authenticated output. Stored evidence and membership
  history remain intact; disabling one account does not revoke another account.
- Recovery is a local operator action against an explicit account UUID after
  separately checking that the requester controls that account. An interactive
  password prompt prevents passwords from entering shell history or command-line
  arguments. An explicit acknowledgement records the fixed redacted audit reason
  `operator_checked_account_control`; reset revokes all sessions, keys and embed
  grants. A supplied email address alone is never sufficient identity proof.

Additive HTTP contracts (all credential requests are bounded JSON):

| Endpoint | Authority and outcome |
| --- | --- |
| `GET /auth/options` | Public local registration availability; no account lookup |
| `POST /auth/register` | Generic `202`; creates only an entirely new account/workspace |
| `POST /auth/login` | Password proof; returns the existing bearer-session format |
| `GET /auth/account` | Current actor's local-account status and identifier only |
| `GET /auth/account/events` | Current actor's bounded, redacted account events |
| `POST /auth/password` | Current password; rotate password and revoke old credentials |
| `POST /auth/disable` | Current password and explicit confirmation; disable own account |
| `POST /workspaces/{workspace}/invitations/{invitation}/identity-approval` | Authorized manager explicitly approves the intended account UUID |
| `GET /workspaces/{workspace}/onboarding-progress` | Current member's private guide state |
| `PUT /workspaces/{workspace}/onboarding-progress` | Expected-version update to that actor's guide state |

The existing `GET /auth/me`, `POST /auth/logout`, workspace, organization,
invitation and analytical routes retain their contracts. Password change and
operator recovery revoke that actor's scoped keys/embed credentials as well as
sessions. The interface must disclose this before submitting the change.
Operator token provisioning refuses existing native accounts instead of bypassing
their passwords. Raw credential request bodies are capped at 8 KiB before parsing,
including streams without a trustworthy Content-Length.
The same pre-parsing guard covers local administrative plan catalog/assignment and
incident-threshold updates. It does not alter existing raw file-upload limits.

## Invitations without mailbox verification

Existing email-only invitations must not let a self-registered claimant obtain
someone else's workspace. A workspace owner or authorized manager explicitly
approves the intended native account UUID after checking the recipient through
their established local channel. The approval is bound to the invitation and
account. Acceptance still checks pending state, expiry, matching identifier,
workspace role and available seats. Approval does not verify the mailbox.
Operator-provisioned users retain the existing invitation behavior.

Organization grouping continues to use the existing OrganizationService. Owning
an organization never grants access to an independently permissioned workspace.

## Private resumable guide

Setup is a small optional guide linking existing application screens:

1. Create an account and workspace.
2. Upload a supported file or choose an explicitly fictional sample.
3. Inspect profile and quality checks.
4. Review column meanings and preview safe cleaning where needed.
5. Build a first supported analysis and inspect its evidence.
6. Save an analysis/dashboard through existing controls.
7. Explore eligible recommendations and their stated assumptions.
8. Invite a teammate through the explicit account-approval flow.

Guide progress belongs to the actor and workspace, with membership checked on
every read/write. A version check prevents competing updates from silently
overwriting one another. Resume, skip and finish-guide state persists. A skipped
step is shown as skipped, never as an operation that was performed. Related
activity comes only from that actor's audit actions in the workspace. It does not
prove a person reviewed every result or that every advanced method is eligible.
Finishing the guide does
not confirm shared meanings, apply cleaning, approve a recommendation or invent
an analysis. Private goals/notes remain in their existing private services.
The old aggregate onboarding endpoint stays compatible.

## Local operator commands

Apply migrations through the current repository head before starting the API.
Open `/workspace`, choose **New account**, submit **Create local account**, then
use **Sign in with password**.
The existing **Session token / Sign in** controls remain available for operator
accounts. `EXECPLUS_LOCAL_REGISTRATION_ENABLED=false` disables new public signup;
existing native password login remains available.

An authorized local operator may recover an account only after independently
checking account control. Run in an interactive terminal with the exact UUID
shown in that user's Account security panel:

```bash
python3 -m execplus.manage recover-local-account --account-id <account-uuid> --identity-checked
```

The command privately prompts twice for the new password. A disabled account stays
disabled unless the operator deliberately adds `--reenable`. Do not supply a
password in a command, file, environment variable or chat. The flag acknowledges
the operator's real check; it does not perform identity verification itself.
If the terminal cannot hide input, recovery fails before an echoing fallback can
read the password.

Granting native staff authority also requires the exact intended UUID:

```bash
python3 -m execplus.manage grant-staff --email person@example.test --role admin --account-id <account-uuid> --identity-checked
```

Email-only native grants are refused. Existing operator-account grant behavior
remains compatible. Revocation remains possible for disabled accounts.

## Transaction and retention boundaries

Credential rotation, disable and recovery lock the actor's existing workspaces in
UUID order, then their account, then revoke only their credentials. Workspace
services lock their workspace before the shared active-account check. Native
account disable serializes with credential creation/revocation and blocks later
customer API, embed and worker publication.

Staff operations perform a nonlocking early denial check, eagerly finish their
bounded action, then lock and revalidate the active account and staff grant before
commit. No staff result streams before that final guard. Concurrent revocation
rolls back the action. Staff-only operations do not acquire workspace locks after
locking an account. These orders prevent a staff/account inversion.

Migration `0025` adds account credentials, redacted events, ephemeral rate windows,
explicit invitation approvals and actor/workspace-private guide progress. Guide
progress cascades on membership removal. Downgrade refuses retained accounts,
history, approvals or guide state. At later schema heads, retained plan evidence
may stop downgrade earlier; operators must not delete evidence to force rollback.

The verification record includes real PostgreSQL upgrade/downgrade checks,
password hashing and bounds, duplicate/concurrent signup, session lifecycle,
disabled keys/embeds/jobs, throttling, request guards, invitation/staff identity
checks, private guide conflicts and concurrent revocations. Numerical
source/dashboard/export checks belong to the shared Phase 1 acceptance gate.

Production identity exposure, verified-email recovery, public HTTPS, independent
penetration/privacy review and representative customer acceptance remain open.
