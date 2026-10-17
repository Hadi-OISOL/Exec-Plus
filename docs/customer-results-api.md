> **File use case:** Documents scoped customer result access and local embedding.
> **What it does:** Maps explicit permissions to existing verified services and records external gates.

# Governed result access

Workspace owners can issue an expiring `epk_` key for their **own current access**,
one to twenty datasets and explicitly selected read operations. These are separate
from account sessions. The secret is returned once; persistence stores its hash.
The existing maximum lifetime is ninety days and admission is sixty requests per
minute per key, atomically enforced. Revocation, disabled accounts, membership
changes and dataset policy changes invalidate access. A key never gains another
person's private studies, forecasts, analyses or questions because its owner has
a workspace role. Private result ownership remains unchanged.

All routes below start with `/integration/v1/workspaces/{workspace_id}`. Existing
exact calculations, file checks, replay and access services produce the responses.
The API does not invoke a new model or create a parallel calculation implementation.

| Operation | Route | Returned scope |
| --- | --- | --- |
| `profile:read` | `GET /datasets/{dataset_id}/uploads/{upload_id}/profile` | Authorized file structure/profile |
| `rows:read` | `POST /datasets/{dataset_id}/uploads/{upload_id}/rows` | Bounded permitted rows, using existing request filters |
| `query:read` | `POST /datasets/{dataset_id}/uploads/{upload_id}/query` | Existing exact metric query and evidence |
| `boards:read` | `GET /boards/{board_id}` | Shared dashboard whose studies are also shared |
| `studies:read` | `GET /studies/{version_id}` | Accessible immutable saved version with replayed evidence |
| `forecasts:read` | `GET /datasets/{dataset_id}/forecasts/{forecast_id}` | Issuer's saved forecast, verified through existing replay |
| `analyses:read` | `GET /datasets/{dataset_id}/analyses/{analysis_id}` | Issuer's saved scenario/anomaly/decision result and reviews |
| `jobs:read` | `GET /jobs/{job_id}` | Issuer's bounded request status, without prompts, replies or raw payloads |

Send `Authorization: Bearer <scoped key>`. OpenAPI `/openapi.json` describes
`ScopedIntegrationKey` bearer authentication on all eight routes. Regular account
tokens are not scoped API keys; API keys cannot use ordinary account routes,
submit jobs, approve recommendations or download ordinary protected exports.
Creating/revoking keys remains on owner-authenticated `/workspaces/{id}/integrations/keys`.

Saved studies and dashboards require **every evidence source** to be present in the
key's dataset scope, including both sides of contribution studies. Primary-file
scope alone is insufficient. Before reading and before delivery, the core services
check source access and private ownership. The final locked key transaction also
rechecks study visibility and dashboard sharing/pin identity, so a revocation after
the inner read discards the result. The integration wrapper rechecks the key,
membership epoch and every permitted dataset's policy epoch after computation;
revocation during a read discards its response. Successful reads append a redacted
audit event. Existing job status recovery may record expired work, as on the ordinary
status route; this does not authorize job submission or cancellation.

In Team & settings, the owner can select the main dataset and additional sources,
then choose operations in plain language. If the integration lists cannot reload,
the UI clears prior keys, grants, host addresses, selections, delivery metadata and
new secrets. It reports when the preceding action already succeeded; **Reload
integrations** reads again without resubmitting that action. A secret hidden after
a failed refresh cannot be recovered: revoke the key and create a new one if needed.

# Local private embedded dashboards

Embedding uses the existing owner-issued, tenant-bound grant, exact host origin and
saved dashboard version. The approved parent transfers a one-use `epb_` bootstrap
to its expected frame after a source/origin/grant-checked message. It must be used
within five minutes. The frame exchanges it for a separate in-memory `eps_` session
lasting at most fifteen minutes; broad account/API credentials never enter the host.

Every read rechecks shared dashboard/studies, all source permissions, membership,
expiry and revocation before and after replay. Successful reads now record
`integration.embed_read` with IDs only. The frame restricts `frame-ancestors` to the
approved origin, clears displayed data on expiry or a failed refresh, and exposes
no ordinary account/export authority. Already displayed authorized content cannot
be remotely erased until the frame checks again; the owner can revoke further reads.

The runnable [local host example](../examples/local-embed-host/README.md) accepts
only local frame URLs and one-use secrets. Its standalone form uses no storage,
fetch calls or credentials in URLs, and its sandbox excludes downloads. It can be
served on loopback with Python; the application requires an explicit local/test
loopback setting for HTTP local origins. No third-party account is required.

Signed webhook/outbox behavior continues under the existing contract. This change
does not enable outbound delivery or add a provider. Real HTTPS hosting, deployment
domain allowlisting, outside delivery and independent security review remain open.
See [verification evidence](verification-governed-distribution.md).
