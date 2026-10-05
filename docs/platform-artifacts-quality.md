> **File use case:** Documents artifact, capability, lineage and quality metadata for platform foundations.
> **What it does:** Specifies additive APIs and their limits without replacing immutable source records.

# Artifact and quality descriptions

The artifact service projects existing uploads, revisions, profiles, documents,
business definitions, query receipts and study versions. It adds no artifact table,
source copy, model call or calculation. Existing IDs remain authoritative. A snapshot,
profile and quality report use their immutable revision ID with distinct artifact kinds.

Every reference includes workspace, dataset, kind, ID and an upload ID when required.
Each descriptor identifies its checksum scope, method version, creator, timestamp,
access scope, supported capabilities and source references. Physical storage keys,
source rows, private goals, private questions and query filter values are excluded.

`availability: metadata_only` is deliberate: opening these descriptions does not
read source bytes or replay a query. A stored checksum does not prove an object is
still available or intact. The existing source and replay endpoints retain those
checks. Opening artifact metadata never adds a Verified badge.

## APIs

With `SOURCE = /workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}`:

- `GET SOURCE/artifacts` returns the retained upload and, when profiled, the current
  snapshot, profile and quality report descriptors.
- `GET SOURCE/quality` returns `quality-v1`; optional `revision_id` selects an exact
  historical revision. An upload with no retained profile returns an explicit 404.
- `GET /workspaces/{workspace_id}/datasets/{dataset_id}/artifacts/{kind}/{id}` opens
  one description. Snapshot, profile and quality kinds require `upload_id` as a query
  parameter. Definition references optionally accept their matching upload ID.
- Add `/lineage` to the individual artifact URL for a graph with source-to-derived
  edges. Traversal is limited to 32 nodes and depth eight. `truncated: true` reports
  incomplete traversal; returned edges reference returned nodes by their `key`.
  Cycles fail explicitly.

Kinds are `raw_asset`, `dataset_snapshot`, `profile`, `quality_report`, `document`,
`definition`, `query_result` and `study_version`. No unsupported format or future ML
artifact is advertised. The catalog preserves its previous fields and adds
`asset_kinds`, `capabilities` and `artifact_refs` for accessible current sources.

Workspace membership and resource scope are checked before every projection and
lineage traversal. Documents and studies retain their owner/shared checks, including
after unsharing or revocation. Query projections retain the existing workspace-level
receipt visibility and expose no private conversation text. Source IDs and retained
metadata checksums must match; another workspace's sources cannot become graph nodes.

## Capabilities

Tabular snapshots describe the existing inspect/profile/query/transform/visualize/join
operations. Each remains subject to retained source availability, current access,
confirmed meanings where required and operation-specific validation. Documents
advertise inspect/text-search, never SQL, transformation, training or statistics.
Query artifacts advertise replay only for supported successful receipts with source
references and a result checksum. Legacy and failed executions remain inspectable
metadata. Study replay/visualization requires replayable recorded queries.

## Versioned quality

`quality-v1` binds the exact revision reference, source/output checksums, profile
algorithm and metadata checksum, thresholds and findings into a deterministic checksum.
It reads the stored profile without rewriting profile-v1, profile-v2, recipes or heads.
It does not replace the existing profile score.

Findings distinguish measured **observations** (missing cells, duplicate rows,
distinct nonempty values and constant columns) from **heuristics** (inferred type/date
conflicts, suspected identifiers and high cardinality). High cardinality means at
least 90% distinct among at least ten nonempty values; those thresholds are recorded.
Missing/distinct counts use the original profile's whitespace semantics; duplicate
rows use its original row-comparison semantics. Counts include denominators and
optional column names, with no source-cell contents.

No heuristic confirms a business meaning, classifies PII or authorizes a calculation.
`confirmed_rules` is empty in this version. Assertions, range/category rules, drift,
outliers and time-series gaps remain future quality-engine work. Business accuracy
and representative production validation cannot be inferred from this report.
