> **File use case:** Simple startup guide for ExecPlus developers and demo users.
> **What it does:** Gives step-by-step commands for opening the private VPS demo or running the project locally.

# Start ExecPlus

Choose **A** to use the existing VPS demo. Choose **B** to run a separate copy on your computer.

**October 17 version boundary:** the accepted local work and the private VPS
release **4fff22633f0c5f44** use schema **0029**. Starting the demo does not deploy
this checkout. See [private release evidence](verification-codex-private-release.md).
Use section B and the [local walkthrough](two-phase-local-walkthrough.md) for a
separate fictional-data demonstration without touching the VPS.

## A. Open the VPS demo

### 1. Open a terminal in the project

```bash
cd /home/hadiabbasisdev/Desktop/OISOL
```

On another computer, use the folder where you saved the project and your assigned SSH key.

### 2. Start your private connection

This example uses the existing `demo1` key. Other users should use their own assigned key.

```bash
chmod 600 data/vps-private/tunnels/demo1
ssh -i data/vps-private/tunnels/demo1 \
  -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -N \
  -L 18400:127.0.0.1:18400 \
  -L 18401:127.0.0.1:18401 \
  execplus-demo@173.208.151.137
```

A blank terminal is normal. Leave it open while using the demo. The application runs on the VPS; you do not need to run the local commands below.

### 3. Open the app and sign in

Open **http://localhost:18400/workspace**.

Use `localhost` exactly. Opening `http://127.0.0.1:18400` instead can show
**Failed to fetch** at sign-in because the VPS API permits the `localhost` web
origin. The SSH forwards still bind to loopback; this does not require public access.

Open `data/vps-private/sessions.json` privately in your editor. Copy only your account's `token` value, without quotation marks, into **Session token**, then click **Sign in**. Do not share the file or paste tokens into chat.

If the page still shows the old interface, press **Ctrl + Shift + R**; on macOS, **Cmd + Shift + R**. Refreshing requires signing in again.

### 4. If your token has expired

Tokens last eight hours. An operator can issue one new token on the VPS:

```bash
ssh administrator@173.208.151.137
cd /sdb-disk/OISOL_ExecPLUS/source
sudo docker compose -f deploy/vps/compose.yaml run --rm -T operator \
  python -m execplus.manage provision-user --email demo1@example.test
```

Use your assigned account's email. Copy the printed token directly into the app. This command does not update your computer's `sessions.json` automatically. The restricted `execplus-demo` account cannot run these operator commands.

**If the tunnel says “Address already in use”:** first try the app URL; your earlier tunnel may still be open. If it is not working, close your earlier tunnel with **Ctrl + C**, then run step 2 again. Do not stop an unrelated service using that port.

### 5. Operator: start or restart all app services

From your computer, connect once:

```bash
ssh administrator@173.208.151.137
```

Now run these inside the VPS terminal:

```bash
cd /sdb-disk/OISOL_ExecPLUS/source
sudo flock /run/lock/execplus-maintenance.lock bash -c '
  systemctl start execplus-model.service execplus-refresh.timer execplus-backup.timer &&
  docker compose -f deploy/vps/compose.yaml stop api web jobs &&
  docker compose -f deploy/vps/compose.yaml up -d postgres storage api web jobs
'
curl --retry 10 --retry-delay 2 --retry-connrefused -fsS \
  http://127.0.0.1:18401/health/ready
sudo docker compose -f deploy/vps/compose.yaml ps
```

`status: ready` and running API/web/jobs mean startup completed. This keeps the
existing database/files and deployed images. The maintenance lock coordinates with
backups/refresh. Current requests may be interrupted by an explicit restart.
Do not run the SSH login again once you are already inside the VPS.

Back on your own computer, open the connection from step 2 and visit the URL in
step 3. To run the tunnel in the background instead, add `-f` to that SSH command.
If the old tunnel still works, keep using it. Detailed server maintenance is in the
[VPS runbook](vps-demo-runbook.md).

## B. Run on your own computer

These commands are for Linux/macOS. You need **Python 3.10+**, **Node.js 22**, **npm**, **make**, and running **Docker with Compose**. A local installation has its own users and data; VPS tokens do not sign you into it.

### 1. Set up once

Open the project folder; replace this path on another computer:

```bash
cd /home/hadiabbasisdev/Desktop/OISOL
python3 -m venv .venv
source .venv/bin/activate
test -f .env || cp .env.example .env
test -f apps/web/.env.local || cp apps/web/.env.example apps/web/.env.local
make install
```

The copy commands keep any existing settings. Run `make install` again after pulling dependency changes. It installs the backend package so `execplus` can be imported.

### 2. Start the database and file storage

In the same terminal:

First check that `.env` points to your separate local database and storage.
Never run these migrations against a VPS database.

```bash
make dev-infra COMPOSE="docker compose"
make migrate
make init-storage
```

Run `make migrate` after pulling changes. This checkout requires migration **0029**;
the private release also uses **0029**, with separate release evidence.
Check the local migration with `python3 -m alembic current`.
The new tables include local accounts, resumable setup, allowances and internal
request metrics, alongside the earlier integration/import/worksheet support.
External connectors remain unused in this walkthrough. Existing data is retained;
do not downgrade across retained saved work.

If Docker needs sudo on Linux, use this instead of the first command:

```bash
make dev-infra COMPOSE="sudo docker compose"
```

If your installation uses `docker-compose`, substitute that for `docker compose`. Do not run the whole `make` command with sudo: Python needs your active virtual environment.

### 3. Keep the local demonstration offline

The commands below explicitly disable models, vectors and email for this local
run. They leave existing settings files unchanged. Use fictional uploads and
samples; no provider key, email account, connector or billing setup is needed.
Keep webhook destinations unconfigured. These steps demonstrate deterministic
tools and their evidence; open-ended model conversation is a separate capability.

### 4. Start the API — terminal 1

```bash
cd /home/hadiabbasisdev/Desktop/OISOL
source .venv/bin/activate
EXECPLUS_LLM_MODE=disabled EXECPLUS_VECTOR_MODE=disabled \
  EXECPLUS_EMAIL_MODE=disabled EXECPLUS_WEBHOOK_MASTER_SECRET= \
  EXECPLUS_WEBHOOK_DESTINATIONS='{}' \
  python3 -m uvicorn execplus.main:app --app-dir apps/api/src \
    --reload --no-access-log --no-proxy-headers --host 127.0.0.1 --port 8000
```

### 5. Start the chat worker — terminal 2

```bash
cd /home/hadiabbasisdev/Desktop/OISOL
source .venv/bin/activate
EXECPLUS_LLM_MODE=disabled EXECPLUS_VECTOR_MODE=disabled \
  EXECPLUS_EMAIL_MODE=disabled EXECPLUS_WEBHOOK_MASTER_SECRET= \
  EXECPLUS_WEBHOOK_DESTINATIONS='{}' make jobs
```

Keep this running: it processes chat questions. Without it, queued requests cannot finish.

### 6. Start the website — terminal 3

```bash
cd /home/hadiabbasisdev/Desktop/OISOL
npm --workspace @execplus/web run dev -- --hostname 127.0.0.1 --port 3000
```

Keep all three terminals open. Replace the checkout path in each terminal on
another computer. The API and web commands bind only to this computer. Preserve
`--no-proxy-headers`: direct-peer account rate limits must not trust arbitrary
forwarded headers.

### 7. Open and use the app

Open **http://localhost:3000/workspace**. Choose **New account**, enter a fictional
local identifier such as `learner@example.test`, your display name, a password of
15–128 characters twice and a workspace name, then submit **Create local account**.
Use **Sign in with
password** to enter. Registration creates a private owned workspace and a local
Demo allowance; it does not verify the mailbox or activate a paid subscription.

An operator may still create a separate demo-token account:

```bash
python3 -m execplus.manage provision-user --email operator-demo@example.test
```

Copy that printed token privately into **Session token → Sign in**. This command
refuses an existing password account; use its password or the authorized recovery
procedure in [local accounts](local-accounts-onboarding.md). Tokens are never a
password-recovery shortcut.

1. Follow **Your setup guide**, or pause it and resume later.
2. Open **Data library** and upload a CSV/XLSX or choose **Explore retail demo**.
3. Review quality, meanings and units in **Prepare data** before confirming them.
4. Follow the [two-phase local walkthrough](two-phase-local-walkthrough.md) for
   exact calculations, saved results, exports and advanced tools.

API readiness: **http://localhost:8000/health/ready**. API documentation: **http://localhost:8000/docs**.

### 8. Know what this offline run proves

Guided calculations, quality checks, cleaning, forecasts, explicit scenarios,
decision tools and protected downloads run locally. The model is disabled, so
an arbitrary conversational question may need a supported guided action or show
an explicit unavailable response. Do not treat that as a measured hosted-model
result. No provider setup is required for either local implementation phase.

The [Phase 1](verification-codex-phase1.md) and
[Phase 2](verification-codex-phase2.md) records separate passed checks, retained
failures and open gates. Local HTTP, synthetic data and a successful build do not
establish public deployment or representative customer acceptance.

### 9. Start again another day

Activate `.venv`, run `make dev-infra COMPOSE="docker compose"`, then use the API,
worker and website commands above. Sign in again with your local password;
browser reload does not retain a session. There is no need to recreate `.env` or
the virtual environment each time. Operator-token accounts can request a fresh
token through the same local provisioning command.

To stop locally, press **Ctrl + C** in each app terminal, then run:

```bash
make down COMPOSE="docker compose"
```

This preserves database/storage volumes. Do not add `-v` if you want to keep your data.

## Quick fixes

| Problem | What to do |
| --- | --- |
| `No module named execplus` | From the project root, run `source .venv/bin/activate`, then `make install`. Use that environment for every Python command. |
| Port `5432` is occupied | In root `.env`, set `EXECPLUS_POSTGRES_PORT=55433` and `EXECPLUS_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus` **before** running `make dev-infra`. Use a free port and update both settings together; these credentials are the local Compose defaults. |
| Chat stays queued | Check that `make jobs` is running with the same configuration as the API. |
| Token rejected | For a password account, sign in with its password. For an operator account, issue a fresh token on that same installation; local and VPS tokens are separate. |
| New account is unavailable | Check the local `EXECPLUS_LOCAL_REGISTRATION_ENABLED` setting. Do not use token provisioning to replace an existing native account. |
| New work hits an allowance | Open **Usage & retention → Workspace allowances**. A local platform administrator can assign a valid internal allowance; saved evidence remains retained. This is not a payment flow. |
| Sign-in does nothing through a LAN address | Configure the browser API address, CORS origin and allowed dev host as shown in [LAN setup](week1-api.md#access-through-a-network-address), then restart API/web. |
| Port `3000` or `8000` is occupied | Check whether your earlier ExecPlus process is still running. Reuse or stop that process before starting another copy. |
