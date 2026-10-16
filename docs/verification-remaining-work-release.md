> **File use case:** Records the first October 16 remaining-work release.
> **What it does:** Separates combined local coverage, actual VPS checks, retained failures and the next unreleased batch.

# Remaining-work release verification

Application **867c5a0** is activated on additive schema **0020**. It includes
portable result exports, opt-in advanced forecasts, consistent dataset row/field
policies and internal incident collection. Live API and browser acceptance pass. The checked post-release backup is
`20261016T123757Z`; database/object checksums and service restart pass.

## Local and candidate evidence

All **1,856 cases in the final application collection** have passing executions
across retained runs. This is combined coverage, not one clean full-suite run.
The final repair run passes 444 cases with 1,412 deselected in 314.64 seconds.
The coverage manifest matches final case identifiers and reruns changed services;
timestamp-dependent Excel parameter identifiers are replaced by their final
executions instead of inflating the count.

Ruff, mypy across 213 source/tool files, 55 frontend tests, types, lint and the
production web build pass. The frozen offline browser run passes 63 journeys;
three model-dependent journeys are explicitly skipped. Four final product-usage
and operations journeys and one final refresh journey pass and overlap the 63.
VPS candidate images pass restricted, non-root, read-only, network-disabled
computation checks, including actual portable files and advanced forecasts.

The [access ledger](verification-dataset-access.md) retains two real lock cycles,
their short-transaction repairs, stale historical fixtures and the obsolete
diagram-report assertion. Refresh publication now rechecks source, feed,
candidate, membership and policy after object I/O. Ingestion cleanup preserves
objects after an uncertain successful commit or unavailable metadata check.
These failures were not erased or counted as successful runs.

## Activation and live checks

Checkpoint: `pre-integration-867c5a0-20261016`. Checked pre-release backup:
`20261016T121340Z`; both data archive checksums pass. All 47 prior business-table
fingerprints and the environment-file checksum match after activation. Migration
metadata changes from 0018 to 0020; the three added policy/incident tables are
empty at activation. Readiness and the workspace return success. Existing model
providers, timers and loopback-only exposure remain unchanged.

Live checks use new fictional accounts and files. Existing user source bytes,
profiles, meanings, revisions and private memory are compared with retained
before snapshots. No policy is installed on an existing user dataset.

The export/access slice passes eight actual downloads: PDF, Excel, CSV/evidence
and PNG for a scoped dashboard and field diagram. Independent parsers inspect
the bytes, including negative/zero/null and greater-than-JavaScript-safe-integer
values. The restricted scope contains four rows and three fields, excludes the
hidden row/field/meaning and withholds full-file fingerprints. The actual hosted
record request succeeds once in 14.919 seconds; its advisory selector is invalid,
but the primary hosted planner supplies the accepted record plan. The diagram
uses the deterministic v2 tool. Seventeen private-access denials pass in this
slice. These checks do not establish representative model quality.

Both legacy and advanced forecasts retain the exact expected fictional estimates
5.1, 5.2 and 5.3. Three saved results/comparisons and six source receipts reopen;
four actual PDF/Excel downloads are independently parsed. Twenty-eight private
denials and twelve ordinary workspace-receipt controls pass. Refresh checks
exercise invalid input, schema-review staging, explicit review/activation,
idempotent retry, preserved original bytes and exact 0.50 result/replay with
automatic scheduling disabled. A separate fictional policy revocation blocks
seven profile/result/export requests. All real-user source and memory snapshots
and the original fictional scoped source remain unchanged.

Live incident inspection confirms a running collector, a recent successful poll,
no pending storage failure and no capacity limit. A temporary fictional platform
administrator can read its fixed-code status; access is denied before the grant
and after revocation. No incident status is changed. Local checks separately
exercise actual collection, deduplication, acknowledge/resolve, failure recovery,
retention and revocation; the live inspection does not claim those transitions
were rerun against operational incidents.

Retained live harness failures include a formula-like CSV fixture correctly
refused at ingestion; an expected-404 assertion where the documented response is
403; and a table assertion selecting report metadata instead of the result table.
An additional assertion incorrectly expected unscoped forecast source-query
receipts to be private. Forecast/comparison records and exports are private;
ordinary source-query receipts retain existing workspace sharing. Scoped policy
receipts remain actor-bound. The corrected check verifies both private denials
and ordinary authorized controls. Resuming the forecast fixture also initially
asked for a new forecast on its superseded upload; the current-source guard
correctly refused. The corrected resume reopens the retained original request
and results. Existing hosted jobs and uploads are reused
after harness corrections; no model retry is hidden.

Two live browser attempts stop before sign-in completes. The first waits for page
load; the second renders the sign-in form but has six pending JavaScript chunks.
There are no page errors or intercepted mutations. Independent curl checks confirm
that transfers also stall through the existing local SSH forward, while the VPS
serves a sampled chunk in four milliseconds. A fresh default tunnel remains slow.
A fresh connection with compression and IPQoS disabled completes the sampled
619,309-byte transfer in 2.503 seconds. It also takes a different observed public
network path, so this does not establish compression as the cause. The old flow
had heavy retransmission while the server was mostly idle. Only this user's
restricted local forward was replaced; application containers and network
configuration were unchanged. The final real-browser journey passes in 24.499
seconds: nine layouts at 1440/390/320, four independently parsed explicit downloads,
exact saved reopening, zero page errors, zero automatic downloads and unchanged
sources. Both initial failures remain recorded.

A supplemental 17.331-second check resolves a misleading element screenshot:
its tall result was clipped by the conversation scroll area. The actual chart
and exact field inspector are fully reachable and visible at 1440/390/320 after
normal scrolling, and selecting Measures renders the permitted amount field.
Screenshots were inspected. Two initial strict-label selectors and one stalled
admin SSH marker check are retained as supplemental harness failures. No app
change was needed for this capture issue.

## Recovery and remaining work

Operator helpers **096b740 / ee3a058** distinguish revoked receipt access from corrupted
restored data. It verifies that revoked/policy-changed receipts still deny replay,
then samples permitted receipts under the unchanged 100-candidate bound. It
continues to fail corrupted authorized evidence. Fifteen local recovery checks,
Ruff and the helper's mypy check pass. The tested helper is hash-verified on the
VPS without replacing application containers. The first 0020 restore exposes a
read-only SELECT FOR UPDATE conflict. The helper now suppresses only workspace
write locks in the isolated, exclusive restored snapshot while retaining database
read-only mode, all access checks and corruption detection. A real PostgreSQL
regression confirms successful replay and unchanged table fingerprints. One
operator retry invoked a non-executable script directly; invoking it with Bash
corrects that command. The corrected isolated rehearsal passes in 24 seconds on 0020: all 93 uploads,
95 revisions, 27 documents/passages, twenty exact receipt replays and one revoked
receipt denial. Twenty-one candidates are checked within the 100-candidate bound.
Temporary containers use an internal network with no published ports or live
volumes; original application services remain running. The same checked backup
also has a 4,169,320-byte encrypted copy outside the VPS. In-memory decryption
checks both archive hashes and the manifest without creating plaintext files.
This is not independent key custody, automatic retention, or a restore initiated
from that encrypted copy. Evidence is retained at
`ops/restore-f78eb10177ce/verification.json`.

The next working-tree batch remains unreleased: usage metering, scoped
integrations/embedding, approved PostgreSQL imports, source-derived scenarios,
calendar anomalies/drift and consolidation. Its local evidence does not describe
the current VPS. All eight production gates remain blocked; neither public
access nor production acceptance follows from this release.

Private evidence: `data/verification/2026-10-16/remaining-work/`, including the
`combined-867c5a0` run ledger and retained live fixture directory.
