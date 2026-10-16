> **File use case:** Defines and records recovery of the current private demo.
> **What it does:** Explains isolated restoration, encrypted copy verification, safeguards and remaining production inputs.

# Current-version recovery rehearsal — October 16

The checked post-release backup `20261016T105008Z` restores successfully with
application **b3a1fb1**, recovery helpers **64240dd** and schema **0018**. The
isolated verification takes **22 seconds** for this particular backup; this is a
measured rehearsal, not an agreed recovery-time objective.

The restored snapshot contains 86 uploads, 88 prepared revisions, 27 documents
and 27 document passages. All original object checksums, revision reconstruction
checks and passage boundaries/checksums pass. Twenty executed receipts replay
exactly across sum, analysis, rows, average, maximum, minimum and count. There are
4,332 eligible executed receipts; this is a bounded replay sample, not a claim
that every receipt was executed again. All 47 application-table fingerprints are
unchanged by verification; migration metadata independently reports 0018.

## October 16 schema 0020 follow-up

Application `867c5a0` and checked post-release backup `20261016T123757Z` pass
an isolated restore in 24 seconds: 93 uploads, 95 revisions, 27 documents/passages,
twenty exact query replays and one verified permission denial. Twenty-one receipt
candidates are inspected within the 100-candidate cap. All table fingerprints stay
unchanged during verification; the temporary internal network exposes no ports
and mounts no live volumes. Evidence: `ops/restore-f78eb10177ce/verification.json`.

The same backup also passes an encrypted off-VPS copy check: 4,169,320 bytes,
in-memory decryption and matching database/object/manifest hashes, with no
plaintext files created. Directory permissions remain 0700; ciphertext/key are
0600. The helper now sets umask077 before creating ciphertext; the enclosing
0700 directory already restricted access while the first transfer was active.
Independent custody, automated retention and restore from that encrypted copy
remain outside this rehearsal.

Operator helpers `096b740` and `ee3a058` distinguish revoked access from damaged
evidence and keep PostgreSQL read-only during replay. An initial rehearsal failed
when a final permission check requested a write lock. Only the isolated snapshot
repository now suppresses that lock; current access/source checks still execute,
and production locking is unchanged. Fifteen local checks include real read-only
PostgreSQL replay, revoked receipts and corrupted authorized evidence. Static
checks pass. A direct invocation of the non-executable script also failed; the
successful operator command invokes it with Bash. Both attempts remain recorded.


## Isolation and reproducibility

`deploy/vps/restore-drill.sh <backup timestamp> <candidate commit> <schema>` checks
the immutable backup manifest, validates archive paths/types/size, creates an
internal Docker network and separate temporary PostgreSQL/object-store containers,
and restores into a uniquely named database. It publishes no ports and mounts no
live data volumes. The database uses temporary storage; object files are copied
into the rehearsal directory. Cleanup targets only the created container/network
IDs and temporary object directory, retaining the verification report.

The candidate application image runs with dropped capabilities, a read-only root,
bounded memory/CPU and a temporary working directory. The checked operator source
`scripts/verify_recovery_snapshot.py` is mounted read-only. It derives isolated
hosts from a strict generated label, disables model use, enables database
read-only transactions, verifies every retained object/revision/passage and compares
table fingerprints before and after replay. It does not connect to live services.

The first attempts failed because the temporary storage hostname contained
underscores; the object store returned HTTP 400. The corrected DNS alias passes.
Twelve local checks also pass after the repair, including traversal/symlink
refusal, unsafe target rejection and source/revision corruption detection. Earlier
failures and temporary diagnostic logs are retained privately.

## Encrypted copy outside the VPS

The same database dump, object archive and checksum manifest were streamed
directly into an AES256 encrypted archive on the operator workstation. Its size
is 4,133,086 bytes. Verification decrypted the stream in memory, checked all three
members and matched both data archives to the checked VPS manifest. No plaintext
backup files were created on the workstation. The ignored private directory is
mode 0700; archive and local passphrase file are mode 0600. The first transfer was
interrupted after administrative connection checks timed out; its incomplete
ciphertext remains clearly labelled and is not counted as a valid backup.

This proves a current-version isolated restore and an independently located,
integrity-checked encrypted copy. It does not claim a restore initiated from that
encrypted copy, automatic external retention or independent key custody. The
archive and local key are on the same operator machine; production requires an
approved destination, separate key custody, retention and agreed recovery-point
and recovery-time objectives. Feature 42 remains Partial and the production
recovery gate stays blocked.

Evidence is retained under
`data/verification/2026-10-16/conversation-harness/` and the VPS directory
`ops/restore-6047da13ebde/`. Private copies remain in ignored
`data/vps-private/recovery/`; never publish that directory or its contents.
