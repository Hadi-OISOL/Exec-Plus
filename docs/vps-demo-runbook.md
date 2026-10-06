> **File use case:** Operating guide for the private eight-user ExecPlus demonstration.
> **What it does:** Records server layout, access, recovery, repeatable checks and expansion boundaries.

# Private VPS demo

The user authorized this deployment on 2026-09-28 for internal use and supervised
buyer/investor demonstrations with fictional data. On October 2 the user also
authorized real public datasets for product validation; the separate public-data
walkthrough below retains attribution. A domain and public customer
access are deferred. This is a private demo using expiring operator-issued sessions;
it is not a production identity deployment. Existing production gates remain open.

The October 6 deployment runs migration **0015**, retaining private basic forecasts,
later-actual comparisons, grounded commentary and authorized audit history, and
adding the verified internal operations/support slice. The subsequent analytics
interface release changes only the web image. The
[Phase 4C section](#phase-4c-and-audit-history--october-6) below gives the current
walkthrough and rollback boundary. Historical release sections retain their original
migration/checkpoint details.

The analytics interface opens at the same `/workspace` address: **Overview** starts
questions, **Ask ExecPlus** continues the conversation, **Search data** opens the
authorized catalog and dashboard, and the two library views browse saved answers
and study dashboards. Hard-refresh an already-open tab after the web release.
See [interface usage](analytics-interface.md) and
[its verification ledger](verification-interface-redesign.md).

The prior web image is `oisol-execplus/web:pre-interface-20261006`; prior source is
`releases/pre-interface-20261006/source`. Only web was recreated under the maintenance
lock. API/jobs images and containers, migration 0015, secrets, model settings and
loopback ports are unchanged. A web rollback can retag that preserved image and
run `docker compose -f deploy/vps/compose.yaml up -d --no-deps web` from the source
directory. Restore the matching frontend source before a subsequent rebuild;
do not downgrade database metadata for this presentation-only release.

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
answers and permission-aware citations. Basic forecasts now add explicitly labelled
estimates with retained evaluation evidence. Do not describe the demo as independently
validated customer accuracy, advanced predictive modelling or unrestricted autonomous
analysis.

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
checks and their limits. That release left Phase 4C–4E open; the October 6 forecasting
extension below advances 4C. All eight production gates remain blocked.

The final eight-user browser rehearsal passed 56 receipt replays, 18 jobs and 32
private job-access denials. Backup **20261004T113138Z** then verified the new writer
stop/start sequence, followed by a successful fresh chat job. The initial local
tunnel stall is retained in the ledger; direct VPS readiness stayed healthy. These
checks do not replace sustained-load or off-server recovery acceptance.

## Phase 4C and audit history — October 6

The private API, web and conversation worker now run with migration **0014**.
It adds private forecast/comparison records to the existing database. Migration
preserved row counts and aggregate hashes for all **38 existing data tables**,
including **2,909 query executions**. Four original Oct4 receipts, two profile-v1
and two profile-v2, reproduced their independently checked typed result checksums.
Existing conversation jobs, old receipts and source reconstruction remain supported.

Refresh the browser after deployment. To try the new workflow:

1. In **Data library → Try a fictional example**, choose **Try forecasting sample**.
   It contains ninety fictional daily revenue/order records from January 1 through
   March 30, 2024. It is separate from the unchanged older samples.
2. Open **Forecasts**, or select **Predictive · basic forecasts** under **Analysis
   focus**. Use **Review data meanings** to confirm the date column, row meaning
   and metric units; revenue in this fictional sample is PKR.
3. Select `date`, `revenue`, SUM and daily periods. Declare complete coverage from
   January 1 through March 30, 2024 and choose a short horizon. Coverage confirmation
   is the user's assertion; observed dates alone do not prove completeness.
4. Create the forecast. Inspect observed history, saved estimates, heuristic ranges,
   separate validation/test windows and the last-value benchmark. Dates are relative
   to the source window: an old window produces dates that may also be historical
   today. Chart positions are approximate; tables preserve server numeric strings.
5. For later actuals, upload or activate a checked staged refresh in the same dataset.
   Preserve the original meaning and units, select that source, reopen the saved
   forecast and declare complete actual coverage. **Compare actual data** saves a
   separate comparison. Unobserved periods stay pending; no automatic retraining or
   rewrite occurs.
6. Open **Audit history** to search actions/type/identifiers or filter dates. Each
   account sees its own private activity plus currently permitted shared events.
   Owners/admins cannot browse another person's private forecast or conversation
   events through this screen.

The runtime compares last-value, recent-mean and linear-trend baselines, with an
optional declared seasonal baseline when enough training cycles exist. MAE and RMSE
measure error in the metric's unit. WAPE and MAPE are error percentages, not an
accuracy guarantee; MAPE is unavailable with any zero actual, and WAPE with all-zero
actuals. A separate test window and last-value benchmark disclose weak results.
Ranges are heuristic and have no calibrated coverage probability. Grounded commentary
reports measured changes and errors without claiming their causes. Forecasting makes
no DeepSeek/Qwen calls. ARIMA and Prophet remain isolated research candidates; read
[the forecast contract and comparison](phase4-forecasting.md) before making claims.

**Descriptive** and **All supported · explore and forecast** keep existing exploration available.
Prescriptive analysis is visibly planned and cannot execute. Scheduled refresh still
consumes deliberately staged files; it is not a live connector. Phase 4D exports,
Phase 4E connectors, frozen Phase 6 advanced methods and all eight production gates
remain outside this release. See [audit visibility](audit-history.md) and
[the release ledger](verification-phase4c.md) for exact acceptance evidence.

The preceding source is retained at `releases/pre-phase4c-20261006/source`, API/web
images use tag `pre-phase4c-20261006`, and checksummed pre-release backup
**20261006T063824Z** preserves the prior database/object pair. Keep the new 0014
forecast/comparison metadata before any rollback. Restoring the old backup over
current data loses new saved work; an older image does not provide forecast access.
Preserve 0013 jobs/turn relationships and profile-v2 compatibility as well. Continue
using the maintenance lock, and stop both API and jobs before object storage during
backups. No listening port, model setting or production gate changed.

Phase 4C is complete for the approved local/test and private-demo scope. Local
release checks passed **816 backend/architecture cases**, **20 real-service browser
journeys** and **nine frontend tests**, plus static checks and clean-image computation.
All **eight deployed browsers** created private forecasts, saved actual comparisons
after the owner activated a staged refresh, and verified that originals were unchanged. The
rehearsal also passed sixteen saved-result reopenings, forty-eight exact receipt
replays, sixteen cross-user access denials, sixteen private-audit checks and eight
audit searches, with desktop and 390/320-pixel layouts.

The live run finished in 55.048 seconds. This is a short functional rehearsal, not a
sustained-load or speed benchmark. The initial attempt stopped at a test selector
before creating forecasts; its failure is retained separately from the successful
rerun. Refresh completed successfully and both refresh/backup timers are active.
Post-release backup **20261006T065810Z** stopped API/jobs before object storage,
verified the database dump and object-archive checksums, then restarted storage,
API and jobs with healthy API readiness. Evidence remains private under
`data/vps-private/phase4c/`; no production gate is cleared by these checks.

## October 6 operations release

The bounded operations slice uses migration **0015** for separate internal staff
access, private support requests, immutable ticket events and privileged access
audit. Read [the operations contract](operations-console-support.md) and
[verification ledger](verification-operations.md) for release acceptance and limits.

Staff grants are operator-managed and separate from workspace ownership. Grant an
existing account only after deciding who will handle intentionally shared support
requests and operational metadata:

```bash
cd /sdb-disk/OISOL_ExecPLUS/source
sudo docker compose -f deploy/vps/compose.yaml run --rm -T operator \
  python -m execplus.manage grant-staff --email staff@example.test --role admin
sudo docker compose -f deploy/vps/compose.yaml run --rm -T operator \
  python -m execplus.manage revoke-staff --email staff@example.test
```

An internal `support` grant can handle requests without the admin directory or
product-report privileges. Neither grant gives access to ordinary private customer
analyses or sources. Reopen the workspace after a grant to refresh the navigation.

- **Support:** create a request and follow its replies/status. Requests are private
  to their requester and explicit support staff; no source file is attached.
- **Admin console:** inspect workspace metadata or handle the support queue. Assign,
  prioritize, escalate and resolve requests; reload after an edit conflict.
- **Usage & retention:** workspace owners/admins see aggregate deliberate product
  activity, feature use and completed-week return cohorts. Incomplete weeks are
  unavailable rather than zero. Admins can open the same report through the console.

The prior source is preserved in `releases/pre-operations-20261006/source` and
API/web images use `pre-operations-20261006`. Pre-release backup
**20261006T080234Z** has verified database/object checksums. Preserve all new 0015
staff/ticket/event/audit rows, 0014 forecasts and previous jobs/profile versions
before any rollback. Restoring an older backup over new work would lose it.
Previous images expect migration 0014 and cannot simply pass readiness on 0015.
Prefer a forward fix; any rollback needs an explicit compatibility/data-preservation
plan before changing the schema or replacing the live database.

This slice does not configure billing, real outbound support email, public identity,
external help desks or production support/privacy procedures. Model endpoints,
network exposure and all eight production gates remain unchanged.

Operations acceptance passes **869 backend/architecture cases**, **24 real-service
browser journeys** and **nine frontend tests**, plus static checks and clean-image
computation. Migration 0015 preserved all forty old data tables. Eight deployed
users passed their support lifecycle, saved-history and aggregate-report checks,
with 36 protected-access denials and successful authorized controls. Existing
receipts and forecasts also replay/reopen unchanged. This is functional private-demo
evidence, not sustained load or production acceptance.

Only the existing first demo account has the internal admin grant; the other seven
remain ordinary users. After refreshing, it sees **Admin console** in navigation.
All workspace members see **Support** and managers see **Usage & retention**.
Post-release backup **20261006T082942Z** passed database/object checksum verification
and restarted storage/API/jobs with healthy readiness. Both maintenance-coordinated
timers remain active. The release, its verification artifacts and checkpoints are
recorded in [the operations ledger](verification-operations.md).
