OBJECTIVE

Bring ExecPlus to a genuinely verified state for:

Phase 0 — Engineering Foundation
Phase 1 Week 1 — Secure Workspace & Ingestion Foundation

Do NOT start Phase 1 Week 2.

The authoritative product roadmap is ROADMAP.md.

The roadmap currently marks Phase 0 as Complete and Phase 1 as Planned, but treat the Phase 0 "Complete" label as a claim that must be independently verified against the actual implementation and tests.

Your job is to:

inspect first
identify what is actually implemented
identify gaps
implement missing work
add/strengthen tests
run the required checks
leave the repository in a clean, working state

Do not simply update ROADMAP.md to say something is complete unless the implementation and acceptance evidence actually exist.

1. READ THESE FIRST

Before changing code, read:

AGENTS.md
ROADMAP.md
README.md
Makefile
.env.example
compose.yaml
pyproject.toml
package.json
all existing architecture/ADR documentation under docs/
existing backend source under apps/api/src
existing backend tests under apps/api/tests
existing frontend source/tests
CI workflows under .github/workflows

Understand the current architecture before implementing anything.

Existing intended architecture:

apps/web -> apps/api -> application services -> domain

with infrastructure adapters behind domain/application ports.

Preserve this architecture.

2. FIRST: PERFORM A REAL GAP AUDIT

Before implementing, inspect the repository and create an internal checklist classified as:

IMPLEMENTED
PARTIALLY IMPLEMENTED
MISSING
IMPLEMENTED BUT NOT PROVEN BY TESTS
BROKEN

Do this for every Phase 0 exit criterion and every Phase 1 Week 1 deliverable.

Do NOT assume that a file existing means the feature is implemented.

Do NOT assume that a TODO/interface/stub means the feature is complete.

Trace important features from API route -> application service -> domain -> infrastructure -> persistence where applicable.

3. PHASE 0 EXIT CRITERIA

Verify all four Phase 0 exit criteria from ROADMAP.md.

A. Python modules compile

Run the repository's appropriate compile/check commands.

Fix any compilation/import issues.

B. Baseline tests pass

Run the existing backend and frontend tests.

Fix failures caused by the current repository.

Do not weaken tests just to make them pass.

C. Frontend type + lint checks pass

Run the existing frontend lint and typecheck commands.

Fix genuine issues.

D. No runtime dependency directly points at a vector DB vendor

Inspect:

Python dependencies
Node dependencies
imports
infrastructure adapters
configuration

The application should depend on provider-neutral retrieval/embedding ports rather than directly coupling domain/application code to a vector DB vendor.

If the existing implementation already satisfies this, preserve it and add an architecture test if necessary.

4. PHASE 0 IMPLEMENTATION HARDENING

Verify that these claimed foundation pieces actually work:

product invariants and system boundaries
modular monolith API
domain-first dependency rules
replaceable LLM port
replaceable embedding/retrieval/vector-store port
local/hosted model routing through validated configuration
PostgreSQL infrastructure
S3-compatible/MinIO infrastructure
health endpoint
readiness endpoint
project-status UI
backend architecture tests
CI
lint
type checking
environment template
developer commands

Only modify these if something is missing, broken, unsafe, or insufficiently tested.

Add tests where implementation exists but the roadmap exit criterion is not actually demonstrated.

5. THEN IMPLEMENT PHASE 1 WEEK 1

Implement ONLY Week 1.

Week 1 deliverables:

Authentication, organizations, memberships & invitations
Workspace-isolated dataset metadata, uploads, object storage & audit events
CSV/Excel upload wizard with 20MB and unsafe-format validation
Parser fixtures for valid/malformed/oversized/multi-sheet/merged inputs
Seat limits 3–50 + tenant-isolation tests

Implement these in dependency order.

6. WORK PACKAGE 1 — AUTHENTICATION / ORGANIZATIONS / MEMBERSHIPS

Build a clean foundation for:

users
organizations/workspaces
memberships
roles
invitations
authentication/session identity
workspace-scoped authorization

Use the existing architectural style.

Do not introduce a huge auth framework unless the repository already uses one.

For local/dev operation, provide a deterministic way for tests to create authenticated identities.

At minimum support the concepts:

User

id
email
display name if appropriate
timestamps

Workspace/Organization

id
name
timestamps

Membership

user_id
workspace_id
role
timestamps

Invitation

id
workspace_id
email
role
status
expiration
inviter
timestamps

Use UUIDs or the repository's existing ID convention consistently.

Define sensible roles, e.g. owner/admin/member, only if compatible with the roadmap.

Enforce workspace membership at the application/API boundary.

A user must NEVER be able to access another workspace's resources merely by changing an ID in a request.

7. WORK PACKAGE 2 — WORKSPACE-ISOLATED DATASET / UPLOAD / AUDIT FOUNDATION

Implement persistence for:

datasets
dataset versions/uploads where appropriate
object-storage metadata
audit events

Every tenant-owned resource must have an explicit workspace/organization scope.

Dataset metadata should include enough information to support later profiling and analytics without prematurely implementing Week 2 profiling.

Suggested conceptual fields:

Dataset:

id
workspace_id
name
description if useful
created_by
created_at
updated_at

Upload:

id
workspace_id
dataset_id
original filename
content type
size
storage key
upload status
checksum if practical
created_by
timestamps

AuditEvent:

id
workspace_id
actor/user
action
resource type
resource id
metadata
timestamp

DO NOT store raw uploaded row values inside audit events.

Audit metadata must not leak secrets or sensitive payloads.

8. OBJECT STORAGE

Use the existing S3-compatible/MinIO infrastructure.

Create a provider-neutral object-storage port if one does not already exist.

The domain/application layer must NOT directly depend on boto3/minio SDK implementation details.

Infrastructure should provide the adapter.

Support:

storing an upload
retrieving metadata
deleting/retaining according to the existing lifecycle design
deterministic object keys scoped to workspace/dataset/upload

Object keys must prevent accidental cross-tenant collisions.

Do not expose arbitrary object-storage paths directly to clients.

9. WORK PACKAGE 3 — UPLOAD VALIDATION

Implement upload validation for:

CSV
Excel single-sheet files

Maximum file size:

20 MB

Reject:

files larger than 20 MB
unsupported file extensions/content types
unsafe file types
Excel workbooks containing multiple sheets
Excel files containing merged cells
malformed CSV
malformed Excel
suspicious/path-traversal filenames
unsupported structures

Do not trust the filename alone.

Validate actual file content/type as reasonably as the current stack permits.

Normalize filenames.

Never use the user-supplied filename directly as a storage path.

Important:

CSV must be treated safely.

Prevent spreadsheet formula injection concerns where relevant to future export/preview behavior.

Do not silently accept malformed files.

Return deterministic, user-understandable validation errors.

10. PARSER DESIGN

Create a clean parser boundary.

The application should not directly contain pandas/openpyxl/etc. implementation details if a provider/parser abstraction is appropriate.

The parser should be able to determine:

format
sheet count where applicable
merged-cell presence
row/column dimensions
parse success/failure

Do NOT implement full deterministic profiling yet.

Week 2 will handle profiling.

The parser should instead produce enough validated structural information for the upload pipeline.

11. REQUIRED PARSER FIXTURES

Create deterministic fixtures/tests for:

Valid
valid CSV
valid single-sheet Excel
Invalid
malformed CSV
malformed Excel
oversized file
unsupported file type
multi-sheet Excel
Excel with merged cells
unsafe filename/path traversal attempt

Tests must assert both:

rejection/acceptance
useful deterministic error classification

Do not create giant binary fixtures unnecessarily.

Generate fixtures programmatically where appropriate.

12. WORK PACKAGE 4 — UPLOAD API / WIZARD

Implement the backend API required for a guided upload flow.

The frontend wizard should be able to:

select/create workspace if applicable
select dataset/create dataset
choose CSV or Excel file
upload
see validation state
see successful upload state
see actionable rejection reason

Do not implement Week 2 profiling UI yet.

The successful upload response should expose metadata useful to the UI without exposing raw business data unnecessarily.

13. WORK PACKAGE 5 — SEAT LIMITS

Implement configurable workspace seat limits.

Allowed limits:

3 through 50 inclusive.

The limit must be workspace-specific/configurable.

Reject invalid values:

less than 3
greater than 50

Enforce the limit when adding/inviting members according to the product model.

Think carefully about race conditions if multiple invitations/membership creations happen concurrently.

The system must not allow the workspace to exceed its configured seat limit.

Tests must cover:

minimum = 3
maximum = 50
invalid <3
invalid >50
seat limit reached
adding/inviting when full
membership removal freeing a seat if appropriate
invitation semantics according to the chosen model
14. TENANT ISOLATION — THIS IS CRITICAL

Add explicit cross-workspace tests.

Create at least:

Workspace A

User A
Dataset A
Upload A
Audit events A

Workspace B

User B
Dataset B
Upload B
Audit events B

Then prove:

User A cannot read Dataset B
User A cannot read Upload B
User A cannot modify Dataset B
User A cannot access Workspace B membership data
User A cannot retrieve Workspace B object-storage content
User A cannot access Workspace B audit events
User B cannot access A's resources

Do not rely only on frontend hiding.

The authorization must be enforced server-side.

Add regression tests for IDOR-style attacks where a valid resource ID from another workspace is manually supplied.

15. SECURITY REQUIREMENTS

Throughout implementation:

never trust workspace_id supplied by the client without authorization verification
derive authorization from authenticated identity + membership
never expose raw storage keys unnecessarily
never log secrets
never place file contents in audit logs
sanitize filenames
prevent path traversal
validate upload size before expensive processing when possible
avoid loading huge files fully into memory when the stack allows streaming/size checks
do not bypass existing architectural boundaries
do not introduce direct vendor dependencies into domain/application layers
16. DATABASE / MIGRATION DISCIPLINE

If PostgreSQL persistence is not yet implemented for these concepts:

create proper database models/tables
create migrations
add indexes for workspace-scoped access
add foreign keys
add uniqueness constraints where appropriate
add timestamps
make workspace ownership explicit

Indexes should support common workspace-scoped lookups.

Do not use an in-memory dictionary as the production implementation if PostgreSQL is already the intended infrastructure.

Tests may use an isolated test database or the repository's existing test strategy.

Follow existing migration tooling rather than introducing another one.

17. FRONTEND

Implement the minimum polished UI needed for Week 1.

Do not build the full product yet.

The user should be able to understand:

current workspace
membership/invitation state where appropriate
upload dataset
validation errors
upload success
basic dataset/upload list

The UI must not pretend profiling exists if Week 2 has not been implemented.

Follow the existing frontend architecture and styling.

18. API DESIGN

Keep endpoints RESTful and workspace-aware.

Use the existing project's conventions.

Possible conceptual routes:

/auth/...
/workspaces/...
/workspaces/{workspace_id}/members/...
/workspaces/{workspace_id}/invitations/...
/workspaces/{workspace_id}/datasets/...
/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/...

Do not blindly use these exact routes if the existing project has a better established convention.

Document the resulting API behavior.

19. TESTING REQUIREMENTS

Add tests at multiple levels where appropriate:

Unit
filename validation
file-size validation
format detection
CSV validation
Excel validation
merged-cell detection
multi-sheet detection
seat-limit rules
authorization rules
Integration/API
authenticated workspace creation
membership creation
invitations
dataset creation
upload
audit event creation
object storage integration
unauthorized access
Security
cross-tenant access
IDOR
invalid workspace IDs
invalid dataset IDs
object-storage isolation
Parser fixtures

All required valid/malformed/oversized/multi-sheet/merged cases.

Do not remove existing tests.

Do not weaken assertions.

20. ACCEPTANCE CRITERIA

Do not declare Week 1 complete until all of the following are demonstrably true:

Authentication / workspace
user can authenticate in the project's supported dev/test flow
workspace can be created
membership can be created
invitation can be created/accepted according to the implemented flow
workspace roles are enforced
Tenant isolation
cross-workspace API access fails
cross-workspace dataset access fails
cross-workspace upload access fails
cross-workspace audit access fails
cross-workspace object access fails
Uploads
valid CSV accepted
valid single-sheet Excel accepted




20MB rejected

malformed CSV rejected
malformed Excel rejected
multi-sheet Excel rejected
merged-cell Excel rejected
unsupported/unsafe formats rejected
unsafe filenames rejected/sanitized
Storage
upload metadata is persisted
object is stored in MinIO/S3-compatible storage
storage keys are workspace-safe
raw file is not exposed through arbitrary paths
Seats
3–50 accepted
values outside range rejected
workspace cannot exceed configured seat limit
Audit
important workspace/dataset/upload/membership actions generate audit events
audit events are workspace scoped
audit events do not contain raw uploaded rows/secrets
Phase 0
Python compile check passes
backend tests pass
frontend tests pass
frontend lint passes
frontend typecheck passes
build passes
architecture tests pass
vector DB vendor neutrality remains intact
21. COMMANDS

Use the repository's existing Makefile commands where possible.

Run:

make check

Also run focused tests during implementation.

If make check fails:

determine whether the failure is caused by your changes
fix the implementation/test/configuration
rerun
do not simply suppress the failure

Also verify infrastructure startup using the repository's documented commands.

22. ROADMAP UPDATE

Only after implementation and tests genuinely satisfy the acceptance criteria:

Update ROADMAP.md so that status reflects reality.

Do not mark:

Phase 1 Week 2
Phase 2
Phase 3

as complete or in progress.

Only update Phase 0/Week 1 status if the actual evidence supports it.

Add concise verification evidence where the roadmap format supports it.

23. GIT DISCIPLINE

Before changing anything:

inspect git status
inspect current branch
do not overwrite unrelated user changes
do not reset/discard existing work
do not force-push
do not modify unrelated files unnecessarily

At the end:

show changed files
show tests/checks executed
show failures if any
explain what remains incomplete

Do not create a giant unrelated refactor.

Keep commits logically organized if committing is requested.

24. IMPORTANT IMPLEMENTATION RULE

DO NOT STOP AFTER THE FIRST FEATURE.

Work through the entire dependency chain:

Phase 0 verification/hardening
→ authentication
→ workspace/membership model
→ authorization
→ dataset/upload persistence
→ object storage
→ upload validation
→ parser
→ parser fixtures
→ seat limits
→ tenant isolation tests
→ upload UI
→ audit events
→ complete verification

However, if the existing architecture requires a different dependency order, use the technically correct order and explain it.

25. FINAL REPORT

At the end, report exactly:

Phase 0
implemented
already existed
fixed
tests proving it
Week 1

For each deliverable:

status
files changed
implementation summary
tests proving it
Verification

List the exact commands run and their results.

Remaining gaps

Anything not completed must be explicitly listed.

Do NOT claim success if tests are failing.

Most importantly:

Do not merely make the roadmap look complete.

Make the repository actually satisfy the roadmap.