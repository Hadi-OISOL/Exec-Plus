> **File use case:** Operating guide for the private eight-user ExecPlus demonstration.
> **What it does:** Records server layout, access, recovery, repeatable checks and expansion boundaries.

# Private VPS demo

The user authorized this deployment on 2026-09-28 for internal use and supervised
buyer/investor demonstrations with fictional data. On October 2 the user also
authorized real public datasets for product validation; the separate public-data
walkthrough below retains attribution. A domain and public customer
access are deferred. This is a private demo using expiring operator-issued sessions;
it is not a production identity deployment. Existing production gates remain open.

## What is separate on the VPS

Host: `173.208.151.137`. Inspection found Ubuntu 22.04, 32 logical CPU cores,
125 GiB RAM and a Tesla P100 with 16 GiB GPU memory. The mounted `/sdb-disk` has
over 860 GiB available after initial deployment. Other applications share this host
and GPU; they were not stopped, reconfigured or reused as ExecPlus data services.

| Location | Responsibility |
| --- | --- |
| `/sdb-disk/AIML-Models/OISOL_ExecPLUS/models` | ExecPlus model weights, isolated from other models |
| `/sdb-disk/AIML-Models/OISOL_ExecPLUS/evaluations` | Sanitized model evaluation reports |
| `/sdb-disk/OISOL_ExecPLUS/source` | Application snapshot and deployment definitions |
| `/sdb-disk/OISOL_ExecPLUS/postgres` | Dedicated PostgreSQL control-plane data |
| `/sdb-disk/OISOL_ExecPLUS/objects` | Dedicated MinIO uploads and document bytes |
| `/sdb-disk/OISOL_ExecPLUS/secrets` | Private credentials and expiring demo sessions |
| `/sdb-disk/OISOL_ExecPLUS/backups` | Private database/object recovery snapshots |
| `/sdb-disk/OISOL_ExecPLUS/ops` | Build/check logs and release artifacts |

PostgreSQL stores permissions, metadata, conversations and lineage. Uploaded files
stay in object storage; DuckDB computes results from authorized snapshots. This
does not add a live external database connector or scheduled ETL pipeline.

Compose project `oisol-execplus` owns its API, web, conversation worker, PostgreSQL
and object-store containers after the Foundation A upgrade below.
The separate `execplus-model.service` runs the existing Ollama 0.20.0 binary as a
dedicated `execplus-model` OS user. It has its own model directory, eight parallel
slots, a 16-request waiting queue, a 4096-token context per slot and one loaded
model at a time. No GPU driver or other model-service configuration was changed.

## Open the demo

Each demo user has an individual tunnel key, stored privately as
`secrets/tunnels/demo1` through `demo8` on the VPS and copied into ignored
`data/vps-private/tunnels/` during setup. Distribute only that person's key and
session token through a secure channel. With their key saved as `demo1`, run:

```bash
chmod 600 demo1
ssh -i demo1 -o IdentitiesOnly=yes -N -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -L 18400:127.0.0.1:18400 \
  -L 18401:127.0.0.1:18401 \
  execplus-demo@173.208.151.137
```

Visit `http://localhost:18400/workspace`. The original tunnel from local port
18310 to VPS port 18300 belongs to another application, not ExecPlus.
Each browser user needs their own tunnel or an approved private network path.
Keep the tunnel open. The `execplus-demo` SSH identity permits only these two
local forwards; shells, password login, database forwarding and reverse forwarding
are disabled. Each public key can be revoked separately from
`/var/lib/execplus-demo/.ssh/authorized_keys`. `deploy/vps/prepare_tunnels.sh` prepares
this configuration, checks SSH syntax before reload, and refuses to overwrite a
changed key list. Revoking a key prevents new connections; terminate any existing
SSH connection separately when immediate revocation is required. The operator's
administrator account remains separate.

Eight fictional identities, `demo1@example.test` through `demo8@example.test`,
are provisioned separately in an eight-seat workspace. The first is the owner;
the others are members. Their tokens are in `secrets/sessions.json`, mode 0600,
on the VPS. During this setup a private copy was placed in the repository's ignored
`data/vps-private/sessions.json`. Use only the relevant account's `token` value
in the sign-in field. Tokens expire after eight hours; never commit or share the
whole session file.

Renew all eight sessions on the VPS:

```bash
cd /sdb-disk/OISOL_ExecPLUS/source
sudo docker compose -f deploy/vps/compose.yaml run --rm operator \
  python scripts/provision_demo.py --confirm-fictional-demo \
  --output /run/execplus-demo/sessions.json
```

The command preserves the workspace and seeded data, writes new private tokens,
and revokes the tokens in the previous saved session file. Securely retrieve renewed
tokens when needed; the local session file does not update automatically. To create one session
for an existing demo account and display it to the operator, use:

```bash
sudo docker compose -f deploy/vps/compose.yaml run --rm operator \
  python -m execplus.manage provision-user --email demo1@example.test
```

This individual command does not revoke previously issued sessions; they still
expire normally. Additional real team identities can be provisioned and invited,
with the seat limit changed deliberately by the workspace owner.

## Suggested investor walkthrough

1. Sign in and choose the fictional investor-demo workspace.
2. Select **City sales sample v1**, or open **Data library** and choose **Try cities sample**.
3. Open the column map, focus chart points and click a breakdown to inspect records.
4. In **Ask ExecPlus**, ask “Show all records of Karachi,” then “Their total revenue?”
   The fictional result is eight matching records and exact revenue of 11502.00.
5. Generate an AI summary. Qwen selects evidence; the server supplies every number.
6. Open answer evidence or a card's **Evidence & save** controls to save/share it.
   Shared items are available under **Saved work** to authorized workspace members.
7. Select **Finance sample v1**, open **Documents**, search “Who approves standard
   refunds?” and open a verified citation. These six policy documents belong to the
   finance dataset, not the city dataset.

The new navigation and conversational contracts are documented in
[the explorer guide](conversational-explorer.md). Existing uploads and prior
conversations survive migration 0008. Refresh open browser tabs after deployment.

The September 30 update adds **Overview → Data understanding**, using migration
0009. The fictional **Fictional definition walkthrough** workspace demonstrates
confirmed paid-only metrics, saved meanings and exact historical replay. Read
[the walkthrough and limits](phase3-data-understanding.md) and
[verification](verification-phase3a.md). The earlier shared samples retain their
profile-only inferred flow until someone deliberately saves a definition.
Private goals now prioritize supported study suggestions in the separate Phase 4A
**Studies & dashboards** view; the original Overview retains its existing behavior. Slice 3B adds unified document/data
questions and private history; the release evidence below distinguishes deployment
from the earlier 3A checkpoint.

The preceding application source is retained at `releases/pre-phase3a-source`,
with images tagged `pre-phase3a`. Backup `20260930T053553Z` precedes migration 0009.
Restore the application and a compatible schema deliberately when rolling back;
do not casually downgrade away newly saved definitions. The deployment keeps
the same loopback-only ports and private session identity.

The useful distinction is verifiable calculation, preserved source files, traceable
answers and permission-aware citations. Do not describe this as independently
validated customer accuracy, forecasting, or unrestricted autonomous analysis.

## Service operations

All application ports bind to loopback. The Qwen3-4B helper stays on the VPS;
DeepSeek V4 Pro handles primary planning over HTTPS. Planning sends schema names,
the question and structured prior context, without uploading row bodies to DeepSeek.
Qwen suggests routes/columns and selects server-generated evidence. DeepSeek retains
the full schema and can correct advisory hints. The helper's invalid/unavailable
responses fall back to primary planning; calculations still execute locally.

The primary uses the existing `EXECPLUS_LLM_*` hosted settings in private `app.env`.
The helper uses `EXECPLUS_LLM_SELECTION_BASE_URL=http://127.0.0.1:11450/v1`,
`EXECPLUS_LLM_SELECTION_MODEL=qwen3:4b`, and a separate optional selection API key.
See [explorer verification](verification-conversational-explorer.md) for this release.

| Port | Service |
| --- | --- |
| 18400 | Production-built Next.js frontend, accessed through SSH |
| 18401 | API, two workers |
| 18432 | Dedicated PostgreSQL 16 |
| 18490 / 18491 | Dedicated MinIO API / operator console |
| 11450 | Isolated Qwen model API; do not expose publicly |

```bash
cd /sdb-disk/OISOL_ExecPLUS/source
sudo docker compose -f deploy/vps/compose.yaml ps
systemctl status execplus-model.service
curl -fsS http://127.0.0.1:18401/health/ready
sudo docker compose -f deploy/vps/compose.yaml up -d
```

For a fresh deployment, first create the project root on the mounted disk and run
`python3 deploy/vps/initialize.py` as the administrator. It generates private,
random credentials and refuses to replace a partial secret set or adopt existing
data without its original credentials. The model service needs its dedicated OS
user/home directory and the inspected Ollama binary path from the unit definition.
Review port availability before repeating this deployment on another server.

Then build images, start `postgres storage`, run the operator commands
`python scripts/wait_infra.py`, `python -m alembic upgrade head`, and
`python -m execplus.manage init-storage` before starting `api web jobs`.
Use `sudo docker compose -f deploy/vps/compose.yaml run --rm operator` as the prefix
for each operator command. Base images are pinned by digest. ECR's Docker Official
Images mirror was used because Docker Hub was unreachable from this VPS.

The web API URL is a build argument. A future domain requires rebuilding the web
image for its HTTPS API address and updating `EXECPLUS_WEB_ORIGIN`; changing only
runtime environment variables cannot replace an already-built browser URL.

## Backups and restoration

`execplus-backup.timer` runs daily at 03:00 UTC (08:00 Pakistan time). It briefly
stops the ExecPlus API and conversation worker before the object store, captures a
PostgreSQL dump and MinIO files, verifies SHA-256 checksums, and restarts only the
services previously running, including on failure. The maintenance lock also
excludes the scheduled refresh worker. Do not run another writer outside this
coordination during a backup.
Run manually with `sudo bash deploy/vps/backup.sh`. Completed snapshots contain
`database.dump`, `objects.tar.gz`, and `SHA256SUMS`; partial snapshots lack a complete
verified set. Protect the credentials separately. Backups currently remain on the
same disk and have no automatic deletion policy; monitor disk usage.

An isolated restore was checked using a separate `execplus_restore_` database and
a temporary MinIO container bound to `127.0.0.1:19490`. The script
`scripts/check_restored_demo.py --database <restore_database>` validates restored
upload/document checksums against restored metadata. Never restore over the live
database or object directory as a test. The first drill recovered migration 0007
and all nine seeded source objects. Same-host recovery is not off-site disaster recovery.

## Expansion and before-public-launch list

- [ ] Domain, HTTPS, production sign-in and individually accountable team access.
- [ ] Approved customer-like documents, human answer review and explicit quality targets.
- [ ] Resolve measured model weaknesses and test longer inputs plus sustained mixed traffic.
- [ ] Learned embeddings/vector selection, isolation and deletion benchmarks.
- [ ] Off-server encrypted backups, retention, monitoring, recovery objectives and drills.
- [ ] Real email provider and scheduled-report delivery rehearsal.
- [ ] Provider privacy terms, key rotation, supported OS/runtime updates and security review.
- [ ] Rate limits, quotas, spending/resource alerts and support ownership.

Database, storage and model endpoints are configuration values behind independent
services, so each can move to another host without moving the application domain
logic. Start by measuring queue time, GPU memory and API latency. Add a dedicated
model GPU/host when the shared P100 becomes the constraint; scale API workers and
move PostgreSQL/object storage independently as usage grows. A four-billion-parameter
model or eight parallel slots alone does not prove capacity for every workload.

See [VPS verification](verification-vps-demo.md), the existing
[production readiness ledger](production-readiness.json), and
[Phase 3 demo gates](phase3-demo-and-production-gates.md). This deployment does not
mark any open production gate passed. Phase 4A is now deployed as documented below.

## Unified conversation release (2026-09-30)

The preceding release deployed migration **0010**, with unified document/data questions, checked
citations, private history and Data library catalog search. The **Fictional unified
walkthrough** workspace demonstrates total revenue 0.30 together with the fictional
refund approver. Ask both in one question, open its citation, then reopen the saved
answer from Private conversation history. Refreshing the page still requires sign-in.

Document evidence selection now sends authorized candidate passages to hosted
DeepSeek, in addition to primary planning; only fictional demo data is approved.
Source quotes are displayed separately from computed figures. Qwen still supplies
advisory selection, and no judge or learned search candidate is enabled.

Backup `20260930T095357Z` precedes migration 0010. Rollback images use tag
`pre-phase3bc`, and source is at `releases/pre-phase3bc-source`. Preserve newly
created turns before any rollback; do not casually downgrade away their evidence.
See [release verification](verification-phase3b-c.md) and
[conversation contracts](phase3-unified-conversation.md). The subsequent
[human-reviewed judge assessment](verification-phase3d.md) completed Phase 3's
private-demo scope with a do-not-adopt decision. That assessment left the application on 0010;
no runtime judge was added or service restarted for the assessment. All production
gates remain open in Phase 5.


## Phase 4A release — September 30

The 4A release deployed **0011** (superseded by 4B below). Refresh the browser and open **Studies & dashboards**.
Confirm meanings and units under **Overview → Data understanding**, run a suggested
study, create a dashboard, and pin its result. Saved versions reopen their original
source/definition receipts; reruns create a new version. Shared dashboards require
explicitly shared studies. **Clear all pins** also repairs a dashboard whose
source studies have become unavailable. Organization/department grouping is under
**Team & settings** and never grants access to another workspace.

Eight simultaneous browsers passed exact study calculation, pin persistence,
version rerun/reopening and mobile layout. Each demo account now owns a separate
**Fictional study walkthrough N** workspace for inspection. These use two fictional
receipts totaling exactly 0.30 PKR and no model calls. Existing shared seed data and
private sessions are preserved. See [the contract](phase4-studies.md) and
[release verification](verification-phase4a.md).

Backup `20260930T131523Z` contains the verified pre-4A database/object pair. Previous
images are tagged `pre-phase4a` and source is `releases/pre-phase4a-source`. New study
metadata must be retained before any rollback; do not blindly downgrade 0011 after
users have saved work. Deployment/build logs are under `ops/phase4a-*.log`. The
model service, other VPS applications, network exposure and production gates are unchanged.

## Phase 4B release — September 30

The 4B release introduced **0012**. Open **Refresh & alerts** for a confirmed dataset.
Use the source date/coverage controls, stage a replacement or explicit append/merge,
review schema changes, then activate. Choose up to six measures to watch; observations
and private in-app notifications retain replayable evidence. The eight demo accounts
have separate **Fictional refresh walkthrough N** workspaces showing an exact
0.30 → 0.50 PKR update and a delivered/read alert. No email was sent.

`execplus-refresh.timer` runs the operator worker about once per minute. Due times
and enabled flags in PostgreSQL control staged-file activation. A file needing
review is never silently activated. Open the refresh screen's **Reload refresh
status** to see later scheduled work. The timer uses the same maintenance lock as
`backup.sh`; do not bypass that lock when running an operator worker during backups.

```bash
sudo systemctl status execplus-refresh.timer
sudo journalctl -u execplus-refresh.service --no-pager -n 20
sudo flock --nonblock --conflict-exit-code 75 /run/lock/execplus-maintenance.lock \
  docker compose -f deploy/vps/compose.yaml run --rm -T operator \
  python -m execplus.manage process-refreshes
```

Backup **20260930T141138Z**, image tags **pre-phase4b**, and
`releases/pre-phase4b-source` preserve the 0011 release. Keep new candidate,
observation and alert metadata before any rollback; do not downgrade casually.
Build/start/migration records are under `ops/phase4b-*.log`. The first API start
exposed a missing multipart runtime dependency. It was explicitly declared,
rebuilt, import-checked in a clean operator container and verified before final
acceptance. `phase4b-api-package-fix.log` records the corrected build.

Short-lived sessions were renewed into the private local session file because the
previous set had expired. Existing seeded data, study workspaces, model service,
other VPS applications, ports and network exposure are unchanged. See
[contracts](phase4-refresh-monitoring.md) and [verification](verification-phase4b.md).

## Upload-first data partner — October 2

Refresh the browser at `http://localhost:18400/workspace`. A new account starts at
**Data library**: upload a supported CSV/XLSX directly, with workspace and dataset
setup supplied automatically. Existing users can select **Public banking and retail
walkthrough**, shared with all eight demo identities. These files are attributed
public UCI data, separate from the fictional samples and existing private uploads.

1. Select the bank dataset. Its original publisher CSV contains 4,521 rows. The
   overview calculates numerical ranges/averages, shows category counts and offers
   questions relevant to that file. Open **How this was calculated** for receipts.
2. Ask “Are there any data quality issues?” or “Help me understand my data.”
3. Ask “What is the total balance?” (6,431,836), “Show all records where job equals
   retired” (230 matching records), then “What is their total balance?” (533,414).
   These are the uploaded sample's results, not claims about all bank customers.
4. Select the retail dataset. Its first 10,000 original rows deliberately retain
   missing customer IDs and negative quantities. Ask about those issues; do not
   describe negative values as errors without knowing the source convention.
5. Business definitions, preparation, studies and refresh remain available through
   their controls. Optional setup no longer precedes the first useful reading.

Sources and subset limits are recorded in [the contract](data-partner-reset.md).
The release checkpoint is `releases/pre-partner-20261002/source`, images tagged
`pre-partner-20261002`, and checksummed backup `20261002T035155Z`. Schema remains
0012. New ordinary uploads use profile-v2; old profiles and receipts retain v1.
The preceding application cannot read new v2 revisions, so a rollback must preserve
new data and account for that compatibility boundary. Do not downgrade the database.

Build/import/activation logs are `ops/partner-*.log`; the corrected API build uses
`partner-concurrency-*`. Private sessions were renewed into the ignored local
session file and still expire after eight hours. Models, network bindings, other
VPS applications and production gates are unchanged. See the
[verification ledger](verification-data-partner.md) for final acceptance and retained
failed rehearsals; a healthy endpoint alone does not establish eight-user behavior.

## Foundation A — October 4

Migration **0013** adds durable private chat jobs. API, web and the new `jobs`
container use the same private endpoints. The worker has four slots, with at most
two active jobs per workspace, 2 GiB container memory and four CPUs; it adds no
listening port. Its default execution/publication deadline is 100 seconds, with
cooperative cancellation and reader/query cleanup. It is not a process sandbox.

Refresh the browser and sign in with the renewed token for your account from the
ignored local `data/vps-private/sessions.json`. Select a file and ask a question.
**Current activity** shows recorded actions from that request. **Cancel request**
asks the worker to stop and reports the actual outcome. Returning to **Private
conversation history** reconnects a running job or offers **Load saved answer**.
**Expert** expands evidence and activity without recalculating. **Source capabilities
& recorded quality** distinguishes observed checks from suggested interpretations.

`make jobs` is needed for local development. On the VPS Compose starts the worker;
do not launch an additional uncoordinated worker around backups or migrations.
Jobs/events remain owner-private, including from other workspace members. The
worker CLI prints categorical failures rather than exception tracebacks or private
parameters. Reports, refresh and AI summaries retain their existing execution paths.

The preceding source is at `releases/pre-foundation-20261004/source`, with API/web
images tagged `pre-foundation-20261004` and checksummed backup **20261004T111433Z**.
Migration preserved aggregate hashes/counts for all 35 legacy tables. Preserve new
0013 jobs/turn relationships before any rollback; do not blindly downgrade or
restore the preceding backup over newly saved work. Profile-v2 compatibility still
applies. Build, migration and activation logs use `ops/foundation-*`.

Model settings, private environment files, other applications and existing network
bindings are unchanged. See [job contracts](conversation-jobs.md) and
[the acceptance ledger](verification-platform-foundation.md) for the final release
checks and their limits. Phase 4C–4E and the eight production gates remain open.

The final eight-user browser rehearsal passed 56 receipt replays, 18 jobs and 32
private job-access denials. Backup **20261004T113138Z** then verified the new writer
stop/start sequence, followed by a successful fresh chat job. The initial local
tunnel stall is retained in the ledger; direct VPS readiness stayed healthy. These
checks do not replace sustained-load or off-server recovery acceptance.
