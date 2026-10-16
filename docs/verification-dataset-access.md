> **File use case:** Records verification of opt-in dataset row and field permissions.
> **What it does:** Separates scoped execution, browser behavior, retained failures and pending deployment checks.

# Dataset access verification

Status: focused implementation checks pass locally. The combined frozen suite,
candidate image checks and private VPS release are still pending. No policy has
been applied to an existing user dataset.

The policy and migration run passes **47 tests**. A broader compatibility run
passes 180 of 181 cases; its remaining assertion had collected the earlier 0019
head while incident migration 0020 was being integrated. The corrected readiness
roundtrip passes separately. These runs overlap and are not added together as
distinct coverage. Source mypy passes 167 files; final combined static checks
remain part of the release gate.

Cases cover exact projected calculations and records, recomputed profiles,
field definitions, diagrams, durable jobs, old receipts, source changes,
membership removal and re-addition, malformed typed conditions, owner/admin
non-bypass and optimistic policy updates. Existing 0018 data is preserved through
the additive migrations; destructive downgrade refuses retained policies.
Restricted public responses withhold original raw-file and revision hashes while
private replay receipts retain them. Four independent export checks inspect real
PDF, Excel, CSV and PNG contents for hidden rows, meanings and fingerprints.

The actual browser journey passes in **10.2 seconds** (14.7 seconds including
startup). It saves an explicit two-field, North-only member grant, checks that
editing alone does not save, retains the draft after a simulated 503, retries,
and independently verifies the two exact authorized records. The restricted
member sees Home, the access notice and a two-field diagram without being asked
to edit shared definitions. The owner cannot read the excluded data but can
manage the policy, recover a 409 edit conflict and disable the policy to restore
ordinary workspace access. All three 1440/390/320 layouts pass without horizontal
overflow or browser errors. Screenshot inspection prompted a later display-only
cleanup of repeated member names; its final browser recheck is pending.

Retained earlier failures distinguish application defects from test setup:

- An empty member display name rendered an unhelpful label. The management API
  now falls back to the member's existing email, and the browser passes.
- Conversational record requests failed with the test model disabled. Four real
  worker checks reproduce this in both unrestricted and restricted scopes, then
  succeed in both using the same typed test planner. The restricted answer has
  exactly the permitted rows and fields and reopens correctly. The offline
  browser uses the available deterministic diagram route and direct governed
  records; this is not a claim of hosted-model acceptance.
- The first diagram journey reached the restricted result, then timed out after
  reloading the owner page because the test omitted signing in again. Session
  tokens intentionally remain in memory. The corrected fixture signs in and
  completes owner recovery; the failed execution remains recorded.

Evidence is retained in ignored
`data/verification/2026-10-16/dataset-access/` and
`data/verification/2026-10-16/conversation-harness/access-browser-*.log`.
The [contract](dataset-access-policies.md) lists full-data-only operations and
the separate owner management metadata boundary. These checks do not establish
regulated-customer acceptance or clear production security/privacy gates.
