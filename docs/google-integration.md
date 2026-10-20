> **File use case:** Explains how to enable Google sign-in and Google Sheets import.
> **What it does:** Lists the Google Cloud setup, settings, endpoints, security behavior and limits.

# Google sign-in and Google Sheets

Users can sign in with Google and import a sheet they choose. In local and test environments
the existing local session adapter serves Google sign-in too, so `provision-user` keeps working;
staging and production use the production-capable adapter. Nothing changes unless
`EXECPLUS_GOOGLE_CLIENT_ID` is set; the development token sign-in keeps working beside it.

## Google Cloud setup

1. Create a project and enable the **Google Sheets API** and the **Google Picker API**.
2. Configure the OAuth consent screen. While the app is in Testing, only listed test users
   (up to 100) can sign in and refresh tokens expire after seven days. `drive.file` and the
   sign-in scopes are non-sensitive; broader scopes would need Google verification.
3. Create an OAuth client of type **Web application** with these redirect URIs, using your
   public API address:
   `{EXECPLUS_PUBLIC_API_URL}/auth/google/callback` and
   `{EXECPLUS_PUBLIC_API_URL}/integrations/google/callback`.
4. Create a browser API key for the picker, restricted to your web address, and note the
   project number (the picker's app id).

## Settings

| Setting | Purpose |
| --- | --- |
| `EXECPLUS_GOOGLE_CLIENT_ID`, `EXECPLUS_GOOGLE_CLIENT_SECRET` | The OAuth client. Both are required together. |
| `EXECPLUS_TOKEN_ENCRYPTION_KEY` | A Fernet key sealing refresh tokens and sign-in state. |
| `EXECPLUS_PUBLIC_API_URL` | The address Google redirects back to. Use https outside local. |
| `EXECPLUS_GOOGLE_PICKER_API_KEY`, `EXECPLUS_GOOGLE_APP_ID` | Public picker values returned to the browser. |
| `EXECPLUS_WEB_ORIGIN` | Where the browser returns after Google. |

Create the key with
`python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
and keep it in the ignored `.env`. Changing it invalidates stored connections. Run
the normal reviewed migration procedure first. Migration 0028 follows 0027 and adds
versioned Google connections, external identities and one-use OAuth attempts while
preserving existing records. Generic connectors follow in 0029. Live activation stays
with the release owner; these branches are local candidates until explicitly released.

## Flow

1. **Continue with Google** starts `GET /auth/google/start`, which sets a short-lived
   HttpOnly cookie and redirects to Google asking only for `openid email profile`.
2. Google returns to `GET /auth/google/callback`. A verified Google subject identifies
   the self-service account. Existing password/operator accounts are never linked by
   email alone. The callback consumes a browser-bound server attempt and redirects to
   `?oauth=complete`; an exact-origin, one-use cookie exchange returns the session into
   application memory. No application bearer appears in the URL or browser storage.
   New self-service workspaces receive the existing Demo allowances.
3. In Data library, **Connect Google** asks once for `drive.file`. The user must use the
   Google account that matches their ExecPlus email.
4. **Choose a Google Sheet** opens Google's picker, using the user's own short-lived token.
   If the sheet has several tabs the user picks one, then it is imported as a CSV upload.

## Endpoints

Public: `GET /auth/google/config`, `GET /auth/google/start`, `GET /auth/google/callback`,
`GET /integrations/google/callback`. Signed-in: `POST /integrations/google/connect`,
`GET /integrations/google/status`, `DELETE /integrations/google`,
`GET /integrations/google/picker-token`, `GET /integrations/google/spreadsheets/{id}`,
`POST /workspaces/{workspace_id}/datasets/{dataset_id}/google-sheets/import`.
`POST /auth/oauth/exchange` is shared with other OAuth connectors and requires its
browser/handoff cookies and exact web origin. Google-specific routes other than
config return 404 when Google is not configured.

## Behavior and limits

- Numbers import as raw values and date cells as the text shown in the sheet. Formulas
  import their current result. Hidden tabs are not offered.
- Limits: 20 MiB, 200,000 rows, 500 columns, 2,000,000 cells, one tab per import. A header
  row and at least one data row are required; blank or repeated headers are renamed.
- The import is a snapshot. It has a profile, the data reading and replayable answers like
  any upload, but it does not update when the sheet changes. Import again to refresh.
- Google applies its own quotas, roughly sixty reads per minute per user.
- Errors are explained without exposing Google's replies: expired connection, a sheet that
  was not picked, a sheet that is too large and Google being unavailable.
- Refresh tokens are encrypted at rest and never appear in logs; imports are audited as
  `google_sheets.imported`, visible only to the person who ran them.

The connection attempt also binds the initiating live application session and connection
version. Disconnect/replacement and account/session revocation are rechecked after
provider calls and at import publication. The import audit shares the upload transaction.
See [identity and session boundaries](connector-identity-security.md) for the complete
contract and synthetic verification limits. A saved import followed by a failed UI
refresh is reported as saved, with a read-only reload instead of repeating the import.
