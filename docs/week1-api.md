> **File use case:** Documents the supported Week 1 HTTP and local setup contracts.
> **What it does:** Explains authentication, role checks, raw uploads, errors, and verification commands.

# Local activation

Run `make install`, `make dev-infra`, `make migrate`, and `make init-storage`.
Use `.env.example` for local configuration. PostgreSQL migrations must precede API
readiness. `init-storage` creates the configured bucket if absent, without granting
public access. PostgreSQL and MinIO host ports bind to loopback in Compose.

If port 5432 is occupied, select a free port with
`EXECPLUS_POSTGRES_PORT=55433 make dev-infra`, and set
`EXECPLUS_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus`
in the local environment. Do not replace credentials or reset an existing server
or volume to resolve a port conflict.

Provision a local session (its only output is the secret token):

```bash
python3 -m execplus.manage provision-user --email owner@example.test
```

Start `make api` and `make web`, then open `/workspace` and enter that token.
Provision a second user's email the same way to exercise invitations. Owners copy
invitation links from the team panel; the matching user signs in and accepts the
link. Tokens expire after eight hours; sign-out revokes the current token. Reloading
the page clears the browser's in-memory session. Do not share or commit tokens.
This provider is supported only in `local` and `test` environments.

# Access through a network address

Next.js loads frontend environment files from `apps/web`, while the API loads
`.env` from the repository root. For browser access through a network address,
configure both explicitly. For example, for `http://192.168.0.120:3000`:

Root `.env`:

```dotenv
EXECPLUS_WEB_ORIGIN=http://192.168.0.120:3000
```

`apps/web/.env.local` (copy `apps/web/.env.example` if needed):

```dotenv
NEXT_PUBLIC_API_URL=http://192.168.0.120:8000
EXECPLUS_WEB_DEV_HOSTS=192.168.0.120
```

Use your server's actual address. `EXECPLUS_WEB_DEV_HOSTS` accepts comma-separated
hostnames without schemes or ports and permits Next.js development connections
for those hosts only. The API origin must include its scheme and frontend port.
Restart `make api` and `make web` after configuration changes, then hard-refresh
the browser. A rejected development connection can leave the rendered sign-in
form without working event handlers; an API origin mismatch prevents authentication.

# HTTP contract

Except health endpoints, requests require `Authorization: Bearer <session-token>`.
UUID path parameters are validated. Unauthorized tenant resources return a generic
404; missing/invalid sessions return 401. Insufficient workspace roles return 403.

| Method and path | Behavior |
| --- | --- |
| GET `/auth/me` | Current identity |
| POST `/auth/logout` | Revoke current session; 204 |
| GET/POST `/workspaces` | List memberships' workspaces / create workspace and owner; 201 |
| PATCH `/workspaces/{w}/seats` | Owner changes `seat_limit`; 204 |
| GET `/workspaces/{w}/members` | Members, roles, and email addresses visible within the workspace |
| DELETE `/workspaces/{w}/members/{user}` | Authorized membership removal; 204 |
| GET/POST `/workspaces/{w}/invitations` | Manager list / create `{email, role}` invitation; 201 |
| DELETE `/workspaces/{w}/invitations/{i}` | Revoke pending invitation; 204 |
| POST `/workspaces/{w}/invitations/{i}/accept` | Matching identity accepts unexpired invitation |
| GET/POST `/workspaces/{w}/datasets` | List / create dataset with `{name}`; 201 |
| GET/PATCH `/workspaces/{w}/datasets/{d}` | Read / rename dataset with `{name}` |
| GET `/workspaces/{w}/datasets/{d}/uploads` | Retained upload metadata |
| POST `/workspaces/{w}/datasets/{d}/uploads?filename=...` | Raw file body; 201 after validation and storage |
| GET `/workspaces/{w}/datasets/{d}/uploads/{u}` | Upload metadata, excluding storage key |
| GET `/workspaces/{w}/datasets/{d}/uploads/{u}/content` | Authorized original attachment with integrity check |
| GET `/workspaces/{w}/audit-events` | Manager-only audit history |
| GET `/health/live` | Process liveness |
| GET `/health/ready` | Migrated PostgreSQL and configured bucket checks; 503 on failure |

Workspace creation accepts `{name, seat_limit}`; omitted limit defaults to 3.
Invitation roles are `admin` or `member`. The owner role is created only with the
workspace. See ADR 0004 for capacity and role rules.

Upload bodies are raw bytes, not multipart form data. Use `text/csv` (also
`application/csv` or `text/plain`) for CSV and
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` for XLSX.
Responses include filename, format, checksum, byte size, row and column counts,
upload/dataset/workspace IDs, creator, timestamp, and `stored` status. Row counts
exclude the header. No raw rows or storage paths appear in metadata.

Errors have `{error: {code, message}}`. Parser rejections use 422, size violations
use 413, invitation/capacity conflicts use 409, and infrastructure failures use
503. Stable parser codes include `file_too_large`, `unsafe_filename`,
`unsupported_format`, `content_mismatch`, `empty_file`, `empty_table`,
`invalid_header`, `malformed_csv`, `malformed_excel`, `multiple_sheets`,
`merged_cells`, `unsafe_formula`, `unsafe_content`, `unsafe_workbook`, and
`unsupported_structure`. The UI displays the actionable message.

Only the configured `EXECPLUS_WEB_ORIGIN` may use browser CORS. API development
and container commands disable generic access logs so filename query parameters
are not logged. Operational cleanup messages contain identifiers only.

# Verification

```bash
make check
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:5432/execplus make test-integration
npx playwright install chromium --with-deps
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:5432/execplus make test-browser
```

Run the Playwright installation from `apps/web`. Integration fixtures apply real
migrations in isolated temporary schemas and use separate private MinIO buckets;
they clean up their own resources. `EXECPLUS_TEST_OBJECT_STORE_ENDPOINT` overrides
the test MinIO endpoint. Test credentials are the Compose development defaults.

`make check` includes integration tests when `EXECPLUS_TEST_DATABASE_URL` is set.
Without it, pytest explicitly skips those cases; that is insufficient evidence to
claim Week 1 completion. Browser tests use a disposable schema/bucket and launch
separate API/web processes on ports 8001/3001. They exercise actual services,
including local sign-in, invitations, CSV upload, rejection, and workspace changes.
