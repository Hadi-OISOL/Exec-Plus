> **File use case:** Defines the opt-in row and column permission contract.
> **What it does:** Records the implementation boundary, protected surfaces and required evidence for feature 64.

# Dataset access policies

Status: Implemented locally; combined verification and private-demo release are
pending. No policy has been created on a real user dataset. This work is not
deployed and does not change the production acceptance gates.

An owner can explicitly enable a versioned policy on one dataset. Existing datasets
without an enabled policy retain their current workspace permissions. Once enabled,
only named workspace members receive access. A grant allows either all columns or
an explicit set, and either all rows or rows matching every bounded typed condition.
Missing grants deny access. Workspace owner/admin and staff roles do not bypass a
data grant. Owner-only policy management is a separate, audited capability.

Policy updates append a revision using optimistic concurrency. They do not modify
source files, business definitions or old result receipts. A policy revision is part
of each new answer's source authorization. Current access is checked before reading,
before publication and when reopening or exporting a saved answer. A changed policy
requires a fresh result; the previous immutable evidence remains stored.
This includes disabling a previously enabled policy. Every policy-backed receipt
is bound to its originating actor, including full-data grants; sharing never
widens a receipt's audience. Another member must create their own authorized
result. Removing and re-adding a member does not reactivate their earlier grant.

| Surface | Explicit full-data grant | Restricted rows or columns |
| --- | --- | --- |
| Dataset and upload discovery | Existing metadata after authorization | Allowed datasets only; visible counts, no original size or hidden schema |
| Profile and field meaning | Existing profile/definitions | Profile recomputed from authorized cells; visible field definitions only; no shared dataset description/history |
| Calculations, records, KPIs and dashboard | Existing governed execution | Projected snapshot before planning/execution; inaccessible fields cannot be queried or filtered |
| Agent reading, diagrams and patterns | Existing source checks | Only projected metadata/data; no unstructured shared notes |
| Forecasts, scenarios and decisions | Existing eligibility/limits | Same methods over authorized snapshot; exact access scope retained in evidence |
| Saved answers, private conversations and jobs | Existing ownership plus current policy | Current matching policy/audience required; old broader results are unavailable |
| Answer drills and exports | Existing eligibility plus final policy check | Only authorized saved evidence; no original-file bypass |
| Raw artifact lineage and historical preparation recipes | Existing authorized artifact access | Denied; the current projected profile and result receipts remain available |
| Original file download | Allowed by existing roles and grant | Denied; use an authorized result export |
| Shared documents/citations | Existing document privacy plus grant | Denied because prose cannot be safely row/column projected |
| Upload, cleaning, shared-meaning changes and refresh administration | Existing mutation role plus full-data grant | Denied with a clear capability message |
| Multi-source joins | Existing validated join plus full-data access to both sources | Denied until a separately verified scoped join contract exists |
| Shared saved configurations/studies/boards | Every referenced source must be authorized | Only matching scoped evidence; otherwise unavailable without exposing names or counts |

The server must apply typed row conditions before dropping hidden columns. Invalid,
missing or incompatible condition values do not match. A source schema change that
makes a grant invalid denies access instead of silently widening its scope. The
policy accepts no SQL, script, model-generated expression or arbitrary predicate.
Conditions are ANDed, with equality, inequality and ordered comparisons for the
field's validated numeric, date, boolean or text type. Missing cells never satisfy
a condition, including inequality. Decimal comparisons preserve supplied precision.

Restricted JSON and PDF/Excel/CSV/PNG outputs omit original-file and original
revision fingerprints. Those unsalted hashes could otherwise reveal hidden values
in a small guessed source. Source identifiers, definition versions, access revision
and hashes of authorized results remain available. Full fingerprints stay in private
execution receipts for integrity checks and exact replay. No-policy and explicit
full-data outputs retain their existing provenance. The public withholding marker
states that fingerprints were withheld; it never invents replacement evidence.

The owner-only management catalog lists dataset identifiers and names even when
the owner has no data grant. The policy editor exposes source field names/types and
current member identities solely to define or repair grants; this is an explicit
management metadata boundary, not access to rows, profiles or calculations. Normal
data discovery still conceals denied datasets. An owner can recover from a policy
that excludes them without modifying the underlying source.

Personal preferences remain actor-private. They cannot grant data access, restore
revoked source evidence or change the governed population. Old explanation prose is
not reused after a policy change. Workspace operational aggregates must not reveal
hidden dataset names, schema, counts or source contents.
Staff workspace lists withhold upload/storage totals when the actor lacks full
access to any protected source. Workspace aggregate usage/audit and source refresh
administration require full access. Restricted studies omit preparation recipes
and use the projected definition; old broader histories and shared boards remain
unavailable rather than leaking titles or version counts.

The disabled-model browser environment cannot plan conversational record requests.
The same durable record request fails before execution in both unrestricted and
restricted scopes when models are disabled. Typed-planner integration checks cover
successful durable rows, exact scope, private source evidence and reopening; the
offline permission journey uses deterministic diagrams plus direct governed rows.
This is an existing offline capability boundary, not a successful live-model test.

Acceptance requires independent row/column fixtures, old unrestricted compatibility,
owner/admin non-bypass, all endpoint and enumeration paths, source/history/download
denials, policy changes during queries/models/jobs/exports, unchanged old evidence,
membership removal, malformed predicates, cross-workspace attempts and migration
preservation. Installation or unit success alone is not release acceptance.
