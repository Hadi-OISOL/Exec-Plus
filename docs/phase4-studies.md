> **File use case:** Defines Phase 4A's adaptive studies and collaboration contract.
> **What it does:** Documents permissions, supported methods, evidence, UI and operational limits.

# Adaptive studies and department dashboards

Open **Studies & dashboards** after selecting an upload. Confirm **Overview →
Data understanding** first. Suggestions use confirmed column roles, units and
domain, with deterministic matching against words in your private goal. Sales,
finance, inventory and operations prioritize their relevant measure tags; research
prioritizes descriptive distributions and missingness. No model generates browser
code or calculates study values. Existing Overview dashboards retain their earlier
profile-based behavior for uploads without saved meanings.

Each suggestion names its reason and supported component. **Run & save study**
creates a private immutable version. **Dismiss** applies only to your account and
the current definition version; **Restore dismissed suggestions** reverses it.
Correct roles, units/domain or your private goal through **Review meaning or change
my goal**. Goal text is never copied into studies, dashboards or shared catalog data.

The descriptive builder supports:

- Confirmed numeric measures with sum, average, count, minimum or maximum, subject
  to confirmed aggregations, required filters, missing-value and unit rules.
- Category distributions, optionally compared by one other category. Ordinal
  responses require an explicit order covering all observed categories; ordinal
  codes and identifiers cannot be summed. Missing responses remain visible.
- Missingness by column and optional group, with executed sample, present and
  missing counts. Metric studies carry the same coverage counts and filters.

At most 1,000 groups are supported. Larger results fail explicitly without a saved
partial study. Empty selections show insufficient data. Groups below five records
carry a small-sample warning; this is not anonymization or statistical inference.
Charts are approximate visual encodings with exact values in accessible paginated
tables. Date views show observed points, not interpolated values or forecasts.
Inventory snapshots across dates require an explicit date grouping/filter.

## Reproducibility and sharing

A study has at most 50 immutable versions. Each retains the question, normalized
method, method version (`descriptive-v1`), execution receipt IDs, upload/revision
and understanding IDs, source upload time, immutable preparation recipe/version,
confirmed definitions and limitations. Result values are reconstructed from the
retained source through the existing receipt verifier. Missing/corrupt originals
fail explicitly; saved metadata does not substitute for source bytes.

**Open version** uses original evidence even after later corrections. **Rerun on
selected snapshot** creates a new version of that study, using its saved method
and the selected snapshot's confirmed meaning. The original remains intact. The
snapshot must be another upload of the same dataset, or a new preparation revision
of its upload. Confirm changed meaning before rerunning. This does not implement
scheduled refresh (4B).

**Compare study versions** reopens both originals. Numeric differences use exact
decimal arithmetic over executed values when methods and definitions are identical.
Changed meaning disables numerical deltas and displays both evidence sets with a
limitation. Missing groups are not silently treated as zero. Differences are not
presented as causal explanations.

Only the study owner can share/unshare or rerun it. Workspace members, including
admins, cannot read another member's private study. Sharing explicitly exposes its
question, methods and all versions. Every replay reauthorizes membership, dataset
and study visibility before returning evidence, including a final check after query
execution. Audit rows retain action/actor/resource IDs, never row values or goal text.

## Dashboards and departments

Create a named dashboard and pin up to **six distinct saved result versions**.
The service and PostgreSQL enforce the limit. Updates require the current board
version; concurrent edits conflict instead of overwriting. Only its owner edits a
dashboard. A workspace-shared dashboard can include only explicitly shared studies.
Opening it replays and reauthorizes every pin. Revoked/private/unavailable pins
produce an error rather than returning stale cached values; the owner can remove
them. Sharing a board does not implicitly share a private study.

Under **Team & settings → Organization & departments**, an owner can create an
organization and attach a workspace they also own. One workspace represents one
department and belongs to at most one organization. Existing owner/admin/member
roles, seat limits and invitation flows continue to govern that workspace. An
organization is a grouping, not an access grant: department listings expose only
workspaces the actor already belongs to. Even an organization owner must be a
workspace member to access its data. Existing standalone workspaces are preserved.
Organization ownership transfer, cross-department data federation and billing
entitlements are outside this slice.

## API and persistence

All endpoints require an opaque session and workspace authorization where applicable.
Let `W=/workspaces/{workspace_id}` and
`S=W/datasets/{dataset_id}/uploads/{upload_id}`.

| Method and path | Contract |
| --- | --- |
| `GET S/adaptive-views` | Confirmed state, source/definition IDs, supported suggestions and private dismissals; otherwise `needs_review` |
| `POST S/adaptive-views/dismissals` | Current `understanding_id` and up to 12 known suggestion IDs; an empty list restores them |
| `POST S/studies` | `name`, `question`, `method`, expected `revision_id` and `understanding_id`; creates a private study/version |
| `GET W/datasets/{dataset_id}/studies` | Visible study metadata and immutable version references across this dataset's uploads |
| `GET W/study-versions/{version_id}` | Replayed executed results, coverage, display component, definitions and lineage |
| `POST W/studies/{study_id}/rerun` | `upload_id`, latest `parent_id`, expected `revision_id` and `understanding_id`; new immutable version |
| `PATCH W/studies/{study_id}` | Owner-only `{shared: boolean}` |
| `GET W/study-comparison?before=UUID&after=UUID` | Two authorized versions of the same study with compatible exact differences |
| `GET/POST W/study-boards` | Visible boards / create `{name, shared, pins, expected_version: 0}` |
| `GET/PATCH W/study-boards/{id}` | Replay all pins / owner update with `name`, `shared`, up to six version-ID `pins`, `expected_version` |
| `GET/POST /organizations` | Accessible groups / create `{name}` |
| `POST W/department` | Dual-owner attach/rename `{organization_id, name}`; moving to another organization is refused |

Study methods accept `kind` (`metric`, `distribution`, `missingness`), `column`,
`aggregation` (required for metrics; counts otherwise), up to one `group_by`, up
to 20 parameter-bound `filters` and up to 30 explicit category values in `order`.
API filters use the existing supported operators. No arbitrary SQL, JavaScript,
HTML, connection strings or component names are accepted as executable input.

Migration **0011** adds organization/department records, studies/versions, boards
and private dismissals. Historical 0001–0010 data and receipts remain unchanged.
Readiness requires 0011. Preserve a database/object backup and previous images
before deployment; downgrading deletes new study metadata and is not a routine
rollback after users have saved new work.

4B refresh/alerts, 4C basic forecasts, 4D exports and 4E live connectors remain
separate roadmap work. The rejected Phase 3 judge remains disabled and the eight
production gates remain blocked.
