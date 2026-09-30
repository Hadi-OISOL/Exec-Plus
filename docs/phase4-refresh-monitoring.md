> **File use case:** Defines the supported Phase 4B refresh and monitoring behavior.
> **What it does:** Documents activation, explicit update modes, evidence and private alert delivery.

# Refresh and monitoring

Open **Refresh & alerts** for a dataset whose current business meaning is confirmed.
The dataset creator and workspace owners/admins can configure refresh, stage and
review files, activate a snapshot, and manage up to six shared active monitors.
Current members may inspect observations and subscribe to their own private alerts.
Organization membership alone grants no access.

## File refresh contract

A refresh feed records its active upload, immutable revision, confirmed meaning,
source timestamp, optional complete-coverage dates, freshness limit, configuration
version and schedule. Saving settings deliberately rebases the selected source;
optimistic version checks prevent lost updates. Editing preparation or meaning
outside refresh makes the feed need review before further activation. Historical
receipts keep their original definitions.

Schedules consume deliberately **staged CSV or single-sheet XLSX files**. There is
no desktop-file polling or live connector in 4B. The worker checks enabled feeds
at their due time. Without a candidate it records `waiting_for_file` and does not
advance source freshness. With a validated candidate it checks access again and
activates it. The next regular slot follows successful activation; an interrupted
activation claim becomes due again after five minutes. Schema-review candidates
are never automatically approved. Phase 4E connectors will use this contract.

Each candidate has an idempotency UUID and content/options fingerprint. Repeating
identical input returns the same candidate; reusing the UUID for different input
conflicts. Up to twenty unresolved candidates are allowed. Two candidates staged
against one version cannot silently overwrite each other: activation of the first
makes the second conflict. The original source remains usable on validation,
storage, transaction or activation failure. Failed attempts and review decisions
are visible; expected failure codes omit source values and internal diagnostics.

- **Replace:** the uploaded file is the whole new snapshot. Every row is preserved;
  omission intentionally removes it from the new snapshot, while the old file remains.
- **Append without keys:** explicitly keep all rows, including duplicates.
- **Keyed append:** reject existing keys, or ignore exact rows with an existing key.
  A changed row with an existing key is rejected; choose merge to update it.
- **Merge:** upsert by one to four declared keys. Matching keys update, new keys
  append, and absent keys remain. There is no inferred deletion.
- Keyed modes reject missing keys and duplicate keys in the active snapshot.
  Incoming repeated keys are rejected, except identical rows under `ignore_exact`.
  Conflicting repeated keys always fail. Keys are trimmed, case-sensitive strings;
  leading zeros remain significant. No model guesses a matching key.

Append/merge requires the same ordered columns. Its raw delta and derived complete
CSV snapshot are both retained, with base/input/output identifiers and exact counts.
Files and derived snapshots are limited to 20 MiB. Empty candidates and typed
conflicts/invalid dates are rejected. A replacement with changed column names or
inferred types requires explicit meaning review. Declared relationships require
review and reconfirmation after refresh; they are not silently carried forward.
Activation atomically adds the confirmed meaning, changes the feed head, records
an audit event and enqueues observations. The catalog and default upload selection
use the feed head, not an unreviewed staged file.

## Observations and comparisons

Monitors use a confirmed numeric measure, explicit unit, governed aggregation and
filters, relevance 1–5, and an optional segment for additive SUM contributions.
Methods are immutable: disable an old monitor and create a new one to change its
question. Definition changes invalidate existing monitor methods until reviewed
through a new monitor. Current members see shared monitoring methods and results;
private goals are never copied into them.

Every activation/configuration version enqueues at most one job per active monitor.
A job captures its immutable source/meaning and uses validated read-only queries
for the metric, selected sample count, nonmissing count and optional segment totals.
At most 1,000 segments are supported. Reaching the configured query row limit
also fails conservatively rather than presenting a possibly truncated breakdown. Jobs have
durable claim IDs, a ten-minute recovery lease, three attempts and per-source
uniqueness. Overlapping workers cannot complete another worker's claimed result.

Snapshot comparisons use the preceding captured source version, not whatever is
current when a slow worker finishes. Monthly comparisons use the last two complete
calendar months before the declared source date, with start-inclusive/end-exclusive
query bounds. They need operator-declared complete coverage spanning both months.
Monthly monitors allow at most eighteen explicit filters, reserving two slots for
the period bounds. Coverage is not inferred from the last record: dates and missing source rows cannot
prove completeness. Current partial months are excluded. Inventory snapshots need
an explicit single-date equality filter; summing inventory over months is refused.

Observations retain method version `monitor-v1`, filters, original definition,
preparation, source timestamp, declared coverage, periods, profile quality and
query receipt IDs. Opening evidence reexecutes retained authorized sources and
verifies their checksums. Missing objects cannot be replaced by cached findings.
Current permission is checked before each replay and again before returning data.
Decimal results stay strings. Zero baselines have no percentage change.

Ranking is lexicographic: declared relevance, absolute relative change, then profile
quality. An undefined percentage ranks with zero magnitude; absolute values with
different units are not compared. The UI shows stale sources, missing data, small
samples, absent baselines, incomplete periods, superseded snapshots and changed
current definitions. Profile quality is descriptive, not a correctness guarantee.

SUM drivers are the difference between executed segment totals. New/disappeared
segments contribute zero on their absent side; the ten largest absolute
contributions plus an exact remainder reconcile to the total delta. AVG and other
nonadditive measures do not claim additive drivers. No output calls a changed total
an anomaly or an arithmetic contribution a cause. Hypotheses remain unverified;
causal methods and calibrated anomaly detection are outside 4B.

## Private alerts

A member subscribes themselves to an enabled monitor using an exact finite decimal
threshold (`gt`, `gte`, `lt`, `lte`) and a 1–10,080 minute cooldown. At most five active
rules per member/monitor are permitted; an identical subscription is idempotent.
Rules apply to future observation jobs. They test the current metric value, not its
change or percentage. A breached new source can notify again after the cooldown.

Delivery is a private **in-app inbox**, with no external email sent. Rule access,
monitor state, current source/definition, source freshness and period/value coverage
are checked immediately before delivery. Delivery, cooldown update and observation
completion are one transaction. The `(rule, observation)` uniqueness constraint
prevents duplicate notifications after retries. States include `delivered`,
`not_triggered`, `suppressed_cooldown`, `blocked_stale`, `blocked_coverage`,
`blocked_definition`, `superseded`, `unauthorized` and `cancelled`. Read timestamps
are separate. Disabled/revoked subscriptions cannot deliver; prior outcomes retain
authorized replay links. Subscription, unsubscribe, read and outcome events are audited.

## API and worker

Dataset root: `/workspaces/{workspace_id}/datasets/{dataset_id}`.

| Operation | Contract |
|---|---|
| GET /refresh | Head, freshness, meaning state, candidate history, editor capability |
| PUT /refresh | Confirmed upload/revision/meaning IDs, expected version, source dates, intervals, enabled |
| POST /refresh/candidates | Multipart `file` and JSON `options`: request UUID, expected version, mode, keys, duplicate rule, source dates |
| POST /workspaces/{w}/refresh-candidates/{id}/review | Explicit `definition`, or `reject: true` |
| POST /workspaces/{w}/refresh-candidates/{id}/activate | Validate retained source again and atomically activate |
| GET/POST /monitors | Shared methods and the caller's private rules/outcomes; create a method |
| DELETE /workspaces/{w}/monitors/{id} | Disable a shared method (editor only) |
| POST /observations/process | Process this dataset's pending jobs (editor only) |
| GET /observations | Latest observation per active monitor, ranked with replayed findings |
| GET /workspaces/{w}/observations/{id} | Historical replay, findings and original query evidence |
| POST /workspaces/{w}/monitors/{id}/alerts | Self-subscribe with operator, threshold and cooldown |
| DELETE /workspaces/{w}/alerts/{id} | Self-unsubscribe |
| POST /workspaces/{w}/alert-events/{id}/read | Mark an owned delivered notification read |

The operator runs `python3 -m execplus.manage process-refreshes`. It processes up to
100 due feeds and 100 pending/recoverable jobs per invocation, logging counts rather
than data. The VPS one-minute systemd timer serializes its worker with backups using
`/run/lock/execplus-maintenance.lock`. The API remains private on existing ports.
Migration 0012 adds tenant-constrained control-plane tables; existing files and
receipts are preserved. No Phase 4C forecasts or Phase 4E source connectors are implied.
