> **File use case:** Records the Week 1 authentication, tenancy, and ingestion decisions.
> **What it does:** Defines the supported local flow, transaction policy, and parser/storage boundaries.

# ADR 0004: Secure local activation and retained uploads

- Status: Accepted
- Date: 2026-09-07

## Identity and authorization

Select an operator-provisioned opaque-session provider for the supported local/test
flow. The `IdentityProvider` port resolves an eight-hour bearer token to a persisted
user. Tokens contain 256 bits of randomness, are stored only as SHA-256 hashes, and
are revoked at sign-out. The browser keeps its token only in component memory.
Provisioning is a CLI operation, not an unauthenticated HTTP endpoint. An operator
is responsible for establishing the user's email identity. The provider refuses
to start outside local/test. A production identity provider, verified email,
self-service registration, password recovery, and SSO remain future decisions.
This is the explicitly supported development authentication flow, not production
identity readiness.

A workspace is the Week 1 organization/team boundary. Owner, admin, and member
roles control its resources. All members can read memberships and create, rename,
and upload datasets. Managers can list/revoke invitations, inspect audit events,
and invite members. Only owners can invite admins or change seat limits. Owners
cannot be removed; only owners can remove admins. Separate organization billing
and multi-workspace administration are later roadmap work.

## Seats and invitations

Memberships plus unexpired pending invitations occupy seats. The limit is 3–50
inclusive. Invitations last seven days; only an authenticated identity with the
matching normalized email can accept. Invitation links are copied manually; the
application does not send email. Expired/revoked invitations release their seats.
Expired pending records retain their historical status and expiration timestamp;
the UI displays them as expired. Acceptance is single-use and replaces a seat
reservation with a membership. Removing a member releases a seat immediately.

All membership, invitation, limit, and resource mutations lock the workspace row
within a PostgreSQL transaction before checking authorization and capacity.
Concurrent seat operations serialize on that row. Resource reads use explicit
workspace predicates; composite foreign keys prevent uploads from referring to
a dataset in another workspace. Application checks enforce isolation; PostgreSQL
row-level security remains future defense in depth, not an implemented claim.

## Persistence, originals, and audit

SQLAlchemy Core implements the repository port; Alembic owns immutable schema
migrations. Dataset, upload, and audit creation occurs in a transaction. Object
storage receives the validated original under
`workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/original`.
The adapter verifies this derivation on every operation. Clients never receive
storage keys or presigned URLs; downloads pass through authorization and checksum
verification and use attachment disposition and no-sniff headers.

Original uploads are immutable and retained. New uploads create new records;
there is no customer-facing delete or overwrite operation in Week 1. Adapter
deletion supports compensation: failures after an attempted object write roll
back SQL and try to remove the object. Cleanup failures log only workspace/upload
identifiers for operational reconciliation. A process crash or ambiguous network
failure between S3 and PostgreSQL is not a distributed transaction: an operator
must reconcile orphaned objects. Durable background reconciliation and lifecycle
retention policies remain later operational hardening.

Audit events store only action, actor, workspace, resource identifiers, and time.
They contain no flexible client-supplied metadata, filenames, tokens, or row data.
CLI provisioning is outside a workspace; workspace creation records its initial
owner membership and creation events atomically.

## Parsing and HTTP contracts

Raw request bodies stream to temporary disk files, with an enforced ceiling of
20 MiB (20,971,520 bytes), independent of Content-Length. No multipart buffering
or LLM is involved. Validation precedes object or upload-record persistence.
CSV supports UTF-8/BOM, commas, quoted fields, and embedded newlines, with a single
nonempty unique header row and consistent row width. XLSX supports exactly one
worksheet, no merged cells, formulas, macros, external relationships, embedded
objects, unsafe XML entities, or oversized/highly compressed archive contents.
Workbook dimensions are recomputed rather than trusted.

Both formats require at least one data row and reject entirely empty rows.
Missing individual values are retained for later quality validation. The structural
ceiling is 100,000 rows including the header, 1,000 columns, and 1,000,000 cells.
Archive ceilings: 512 entries, 100 MiB total expanded size, 30 MiB per entry,
and a maximum 200:1 compression ratio. These conservative bounds trade acceptance
of unusually sparse/compressible spreadsheets for bounded validation work.

Names are normalized using NFKC and trimming; paths, controls, ambiguous hidden
names, and encoded path separators are rejected. Filenames never determine keys.
Formula-like text beginning with `=`, `+`, `@`, or nonnumeric `-` is rejected,
including CSV headers. This conservative values-only policy also prevents unsafe
future spreadsheet previews/exports from accidentally reusing accepted formulas.
There is no row preview, cleaning, quality score, semantic tagging, profiling, or
conversational analytics in Week 1. Counts describe structure only.
