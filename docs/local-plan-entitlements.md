> **Use case:** Operate and verify local workspace capacity without billing.
> **What it does:** Defines plan scope, counting, permission boundaries, operator commands and retained limitations for requirements 14/46 and local cost controls (45).

# Local workspace allowances

Migration **0026** adds `plan_catalog`, `workspace_plans` and `plan_admissions` to the existing PostgreSQL schema. No dependency, external service, payment activation or provider configuration is added.

Native account registration and every subsequently created native workspace assign the current **Demo** catalog version in the same transaction as its workspace and owner membership. The explicit `plan.default_assigned` audit records that initialization. Legacy operator workspaces remain unassigned until an administrator deliberately assigns a plan; they keep their prior global safety limits and model ledger.

Demo, Starter, Growth and Enterprise are local capacity presets, **not subscriptions**. Each catalog update creates a new version. Assignment snapshots the selected limits and an explicit timezone-aware window of at most 366 days. Defaults last 30 days. Nothing renews automatically. Existing resources and evidence remain stored when limits decrease or a period expires; new admitted work is refused until a valid allowance exists.

## Counting and enforcement

| Allowance | What counts | Admission boundary |
| --- | --- | --- |
| Seats | Members plus pending unexpired invitations | Invitation creation/acceptance and seat-limit changes under the workspace lock |
| Datasets | Current dataset records | Explicit creation and upload/sample creation under the workspace lock |
| File bytes | Size of each original upload | Checked before parsing and again at publication; independent 20 MiB safety maximum still applies |
| Storage bytes | Sum of retained original upload sizes | Initial preflight and final publication under the workspace lock; failed publication removes its unpublished object |
| Saved studies | Current studies, not study-version history | Preflight plus final insertion under the workspace lock |
| Processing | Admitted upload-profile operations and governed query executions | Before parsing or the shared query executor; durable jobs, customer keys and embedding reuse this boundary |
| Exports | Admitted rendering operations | Authorized preparation, then admission before rendering; PDF, Excel, CSV evidence and PNG paths included |
| Forecasts | Admitted new forecast operations | Before source calculation; an explicit retry reuses its immutable forecast ID |
| Model attempts | Actual admitted provider attempts, including retries | Same transaction as existing model-usage reservation; no second token or financial ledger |

Stock limits count current resources. Period limits count immutable admissions whose timestamps fall within the active window, including admissions under a previous assignment in the same window. Assigning another tier in that same period cannot reset usage. An administrator can deliberately choose a new window; this is recorded and is not a payment event.

Started work that fails still consumes its logical operation allowance. This is not a CPU-seconds meter. Global concurrency, row, timeout, input, search and solver limits continue to bound actual work. The per-operation financial exposure ledger remains independent. It preserves unknown provider costs rather than treating them as zero.

The optional `Idempotency-Key` header is an opaque UUID. It scopes stable logical admissions to the actor and workspace. Export/forecast retries with changed inputs conflict; internal query suboperations derive separate identifiers from their source-bound query shape. Existing durable conversation operation IDs are reused when no explicit header is supplied. Retrying an unchanged logical operation does not count another admission; this does **not** promise a response cache for every upload or query. A retried upload can retain another original file and still consumes actual dataset/storage stock. Reopening a verified original query receipt performs permission/source checks and exact replay without admitting a new processing operation. Replayed evidence is available at a zero/expired processing allowance.

Consolidated exports lock all contributing workspaces in order and admit one export in each. If any source workspace refuses admission, the transaction rolls back every admission. Sharing, API keys and embed sessions grant no broader plan allowance or resource access.

## Protected controls

- `GET /plans`: authenticated catalog, without private workspace usage.
- `PUT /admin/plans/{key}`: platform administrator, exact `expected_version`, name and all limit fields.
- `GET /admin/workspaces/{workspace_id}/plan`: administrator assignment metadata only.
- `PUT /admin/workspaces/{workspace_id}/plan`: administrator, selected catalog key, expected assignment version and explicit start/end.
- `GET /workspaces/{workspace_id}/plan`: workspace owner with full dataset access; actual remaining allowances. Membership alone cannot reveal hidden-resource counts.

- `GET /workspaces/{workspace_id}/plan-usage` (October 24; separate from the legacy `/usage` seat/storage snapshot): workspace owner or admin with full dataset access, or an active platform administrator (recorded as `plan.usage_viewed`). Returns the same allowances plus a per-allowance `state` (`ok`, `near` at 80% or more, `reached`), server-written `notices` that say what still works, and `daily` exact counts for the last 30 UTC days grouped from `plan_admissions` (processing, exports, forecasts, model attempts) and `uploads`. A staff administrator who lacks full dataset access sees operation counts but not stock counts (`access_limited`). Ordinary members receive 403.
- `GET /admin/usage/workspaces?limit=` (October 24): active platform administrator only (`plan.usage_listed`). Lists every workspace with a current assignment, its exact period operation counts and limits, ranked by the highest share of any operation limit.

No migration was needed: daily history and ranking read existing `plan_admissions`, `uploads` and `workspace_plans` rows. Connector imports count through the same upload/processing admissions. The `plan_limit` refusal now names what still works.

Owners and admins see a notice on every workspace view when an allowance is near or reached. The owner opens **Usage & retention → Workspace allowances** for the full report and daily history; administrators open **Admin console → Usage by workspace** for the ranking. A platform administrator opens a workspace in **Admin console → Local workspace allowances**, selects a preset and explicitly assigns its window. Both views use protected backend responses and clear stale values when a refresh fails. The administrator UI does not process money.

For local synthetic tests, the native-account grant command requires the actual account ID and an independent operator identity check:

```sh
python -m execplus.manage grant-staff --email synthetic@example.test \
  --role admin --account-id <confirmed-account-uuid> --identity-checked
```

Do not grant a real native account staff access based on an unverified email address alone. Catalog customization is available through the documented API. All existing authentication, source-policy, private result, audit and staff boundaries remain required.

## Local model transport limits

The existing OpenAI-compatible adapter now bounds the **actual serialized UTF-8 JSON request** at 1 MiB before reservation/dispatch. It reads responses incrementally and refuses more than 2 MiB, oversized declared lengths, or compressed responses; it requests identity encoding to avoid decompression expansion. Oversized responses stop without retry, close the stream and retain unknown financial exposure for dispatched work. Request oversize creates no provider attempt.

These are memory/transport controls, **not token estimates or guarantees about provider charges**. No trusted tokenizer/context bound is available in the current adapter. Existing configured per-attempt financial reservations remain operator-declared exposure, not a proven maximum invoice. Only reported token counts and explicitly configured rates contribute to recorded estimated costs. No provider was contacted to verify real quality, cost or latency.

## Verification and limits

`apps/api/tests/test_local_plans.py` covers stock and operation races, stable retries, changed-input conflicts, period boundaries, native defaults, private summaries, safe saved replay, actual export/forecast entrypoints, and account-disable/usage lock order. `test_model_transport_limits.py` uses mocked HTTP to check UTF-8 request size, streamed/declared response bounds, compression refusal, stream closing, no retry and retained unknown exposure. Existing model-ledger/provider tests remain applicable.

`apps/web/e2e/local-plans.spec.ts` exercises actual native login, administrator assignment, upload rejection, local upgrade, successful upload and owner remaining capacity. Final commands/results, initial failures and local-only limitations are recorded in the two-phase verification documents; a written test is not itself passing evidence.

This implementation does not provide billing, organization-wide pooled subscriptions, off-server usage reconciliation, provider invoice guarantees or production-scale acceptance. It does not authorize external deployment.
