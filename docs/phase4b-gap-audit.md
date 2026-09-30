> **File use case:** Records the Phase 4B audit before implementation.
> **What it does:** Separates verified foundations from missing refresh and monitoring behavior.

# Phase 4B audit — September 30, 2026

The user authorized 4B after the verified 0011 private-demo release. Work remains
on `phase2`; existing Phase 2/3/4A changes are preserved. The git-visible source
was archived locally before this slice. Phase 4C is outside this implementation.

Verified foundations: retained CSV/single-sheet XLSX uploads, immutable profile-v1
revisions, confirmed versioned meanings, exact read-only DuckDB queries, replayable
receipts, studies, workspace row locks and delivery-time report authorization.

Missing before implementation:

- No dataset refresh head, staged-file schedule or validated activation transaction.
- No explicit append/merge or keyed duplicate policy. Uploading another file alone
  does not implement refresh, schema review or meaning carry-forward.
- No durable monitoring jobs, period completeness contract or ranked observation history.
- No KPI subscriptions, cooldowns, in-app delivery state or duplicate suppression.
- Existing variance compares scalar receipts but does not reconcile segment drivers.
- No refresh UI, worker command, timer, integration tests or deployment evidence.

Implementation boundary: schedules consume files deliberately staged in ExecPlus.
They cannot fetch a user's desktop file. Phase 4E connectors will use the same
candidate contract. Replacements preserve originals; append and merge retain both
the input delta and derived full snapshot. Invalid or unreviewed candidates never
replace the active head. Period coverage is explicitly declared, not inferred from
the last observed date. Alerts use a private in-app inbox; no external email is
authorized by this feature. Descriptive drivers are arithmetic contributions, not
causal conclusions or calibrated anomaly detection.

Required evidence: real PostgreSQL/MinIO tests for activation rollback, duplicates,
schema/definition drift, scheduling, stale/incomplete sources, exact comparisons,
replay, permissions and delivery retries; browser coverage; static analysis and a
production build; a backup and private VPS verification before claiming deployment.
All eight production gates remain open.
