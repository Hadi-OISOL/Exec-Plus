> **File use case:** Evidence for the separately authorized October 17 private VPS release.
> **What it does:** Records exact source/images, preservation, live fictional checks and backup results.

# Two-phase private release

Release **4fff22633f0c5f44** is active on schema **0029**. Local acceptance was
checkpointed as **00be9da**, preserving connector merge **142a7dd** and its two
parents. This is a private demonstration release, not production acceptance.
No push, public exposure, live connector/provider call or customer-data analysis
forms part of its verification.

## Exact artifacts and preservation

The immutable archive contains 973 explicitly listed source files, with SHA256
`a2976be4928b5c104cc64710aebb177a407f5732589825ca9280e8f09edc7ee7`.
The API/jobs image is
`sha256:ab3d84bf90407d88f659d288f3212c8d58cf44d79942e245f20c5a5560d44914`;
the web image is
`sha256:4d348afd1d22195e1c19884f806928e722801a153eb42f864e14bdc1679475df`.
Runtime, migration and dependency bytes match the accepted checkpoint. The later
documentation, browser-only timing-test correction and preserved generated
`next-env.d.ts` differ explicitly; the original candidate manifest is retained.
The final report document was added after the archive and is separately recorded.

Activation used one maintenance lock, stopped writers/storage, and made checked
pre-release backup **20261017T161322Z**. Database/object archive checksums,
archive readability and backup metadata checks passed before migration. The old
source and actual running image IDs were retained independently of mutable tags.
Migration **0020 → 0029** preserved all **50 original table projections**, added
exactly **27 empty tables**, and preserved all **167 original stored files**
(3,932,332 bytes). Original configuration hashes matched before writer restart.
No data restore or downgrade occurred. API/jobs/web returned on the checked
images; readiness, website, original service set and model/timer state passed.

The root activation gate references the accepted backend reconciliation,
107-pass/3-skip browser reconciliation, frontend/static/build evidence and
restricted image checks. Those checks exercise local methods with network
disabled, read-only filesystems, non-root users and bounded memory/CPU.

## Live verification

The final Phase 1 API journey passes five groups in **64.479 seconds**: native
accounts/private Demo allowances, saved setup, safe cleaning, exact query/dashboard/
study results, deterministic protected exports and password/session lifecycle.
The Phase 2 API journey passes twelve groups in **140.485 seconds**: exact two-source
contributions/PVM, constrained scenarios, rolling and multivariate flags, six
bounded capacity solves with baseline-only approval, explicit-FX company reports,
scoped keys, embed sessions, quota accounting and unchanged eight fictional files.
Each successful run disables both generated accounts and verifies revocation.
The final native browser journey passes five groups and nine 1440/390/320 layouts
in **40.652 seconds**, with no page errors, rejected requests or overflow. Actual
signup/login/logout, private guide persistence, Demo allowance reads, account
controls and explicit account disabling pass; login and sessions are revoked.
The verifier answers three provider-status reads locally as disabled; it does not
exercise Google or other external providers. All 45 dispatched API requests are
bounded to the newly generated account and its own empty workspace.
Root inspected desktop/mobile captures. Checked post-release backup
**20261017T162930Z** passes database/object SHA256, `pg_restore --list` and object
archive listing. After backup, the same API/jobs/web container IDs and images
remain running with zero restarts; readiness and web return200, all five services,
six loopback listeners, model/timers and configuration hashes pass. No restore
occurred; these integrity checks do not establish a production recovery objective.
Only freshly generated identities and their own fixtures participate.

The first Phase 1 live run stopped with `RemoteProtocolError` while reopening
its newly created study. Both generated accounts were disabled and their sessions
revoked. The API/jobs/web had zero restarts, no OOM, and no logged exception;
readiness still passed. The exact network cause is unproven. Explicit rechecks
use fresh HTTP connections across the existing SSH forward, without automatic
write retries or application changes. The initial failure remains retained.

The second run timed out on the fictional onboarding update while the old SSH
forward failed, and its two API cleanup requests could not connect. At the same
time, server-local readiness returned200 in0.016772 seconds, while forwarded
readiness received no bytes in8.003178 seconds. There was no active/waiting database
request, restart or OOM. The restricted demo tunnel was re-established using its
existing key, with only127.0.0.1:18400/18401 retained. Replacement health passed;
the underlying network/SSH cause is not established. A rejected out-of-range
staging-port argument made no connection; the valid temporary port was removed.
The two exact generated identities were independently checked against the retained
run IDs, creation window, synthetic name/email shape and sole owned workspace;
the existing operator recovery and disable services then revoked every session.
No other account or credential was changed. Both failed runs remain retained.

The first native browser attempt stopped in the registration form: its guard
rejected a production web request and the registration transport failed. The
helper could not confirm cleanup through login. A separate read-only lookup of
that exact randomly generated synthetic email confirms **zero account rows**;
there is no orphaned account. The failed browser evidence remains separate from
the passing local rehearsal. Safe request diagnostics and the production public
page allowlist were corrected before the passing explicit browser recheck. The
repair passes 34 local guard/cleanup cases and an actual Playwright loopback
transport selfcheck. Fresh connections have zero automatic retries; rejected
requests record only a local pathname and errors use fixed safe codes. The first
unrecorded web path remains unproven; public homepage prefetch was a plausible
cause. The application did not change for this verifier repair.

An initial report-transfer wrapper expected the Phase 1-only cleanup summary key
on the Phase 2 report. It was corrected to the shared two-entry `account_cleanup`
contract; the already transferred Phase 1 bytes were verified unchanged. Both
successful report files and the staged post-backup checker are hash-verified.

## Operator evidence and limits

Private evidence is retained under
`data/verification/2026-10-17/two-phase/phase2-live-4fff22633f0c5f44/` and
`phase2-release-candidate/`. The VPS operational ledger is
`/sdb-disk/OISOL_ExecPLUS/ops/phase2-20261017-4fff22633f0c5f44/`;
the preserved source checkpoint is
`/sdb-disk/OISOL_ExecPLUS/releases/pre-phase2-20261017-4fff22633f0c5f44/`.
Keep forward repair after schema activation; do not restore an older database
over subsequently saved work.

Read [local acceptance](verification-codex-phase2.md),
[the per-requirement report](codex-two-phase-final-report.md) and
[the local walkthrough](two-phase-local-walkthrough.md). All eight production
gates remain open. Live synthetic success cannot establish representative model
quality, external provider readiness, public HTTPS/security, recovery objectives
or customer-scale performance.
