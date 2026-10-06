> **File use case:** Simple startup guide for ExecPlus developers and demo users.
> **What it does:** Gives step-by-step commands for opening the private VPS demo or running the project locally.

# Start ExecPlus

Choose **A** to use the existing VPS demo. Choose **B** to run a separate copy on your computer.

## A. Open the VPS demo

### 1. Open a terminal in the project

```bash
cd /home/it-admin/OISOL
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

Server maintenance/startup commands are in the [VPS runbook](vps-demo-runbook.md).

## B. Run on your own computer

These commands are for Linux/macOS. You need **Python 3.10+**, **Node.js 22**, **npm**, **make**, and running **Docker with Compose**. A local installation has its own users and data; VPS tokens do not sign you into it.

### 1. Set up once

Open the project folder; replace this path on another computer:

```bash
cd /home/it-admin/OISOL
python3 -m venv .venv
source .venv/bin/activate
test -f .env || cp .env.example .env
test -f apps/web/.env.local || cp apps/web/.env.example apps/web/.env.local
make install
```

The copy commands keep any existing settings. Run `make install` again after pulling dependency changes. It installs the backend package so `execplus` can be imported.

### 2. Start the database and file storage

In the same terminal:

```bash
make dev-infra COMPOSE="docker compose"
make migrate
make init-storage
```

Run `make migrate` after pulling changes; the current application requires migration **0015**. Existing data is retained.

If Docker needs sudo on Linux, use this instead of the first command:

```bash
make dev-infra COMPOSE="sudo docker compose"
```

If your installation uses `docker-compose`, substitute that for `docker compose`. Do not run the whole `make` command with sudo: Python needs your active virtual environment.

### 3. Get a local sign-in token

```bash
python3 -m execplus.manage provision-user --email owner@example.test
```

Copy the printed token privately. Run this command again when it expires.

### 4. Start the API — terminal 1

```bash
cd /home/it-admin/OISOL
source .venv/bin/activate
make api
```

### 5. Start the chat worker — terminal 2

```bash
cd /home/it-admin/OISOL
source .venv/bin/activate
make jobs
```

Keep this running: it processes chat questions. Without it, queued requests cannot finish.

### 6. Start the website — terminal 3

```bash
cd /home/it-admin/OISOL
make web
```

Keep all three terminals open.

### 7. Open and use the app

Open **http://localhost:3000/workspace** and sign in with the local token from step 3.

1. Open **Data library** and upload a CSV/XLSX or choose a fictional sample.
2. Use **Overview** for starting insights and questions.
3. Open **Ask ExecPlus** for chat, or **Search data** for the dashboard.
4. Browse **Saved work**, **Studies & dashboards**, **Forecasts** and **Support** as needed.

API readiness: **http://localhost:8000/health/ready**. API documentation: **http://localhost:8000/docs**.

### 8. Enable AI chat if this is a fresh installation

The example configuration has models disabled. Basic dashboards and forecasts can run without a model; full natural-language planning needs one.

In the root `.env`, set these values and add your own approved key locally:

```dotenv
EXECPLUS_LLM_MODE=hosted
EXECPLUS_LLM_BASE_URL=https://api.deepseek.com
EXECPLUS_LLM_SMALL_MODEL=deepseek-v4-pro
EXECPLUS_LLM_LARGE_MODEL=deepseek-v4-pro
```

Put the key in `EXECPLUS_LLM_API_KEY`, then restart **both `make api` and `make jobs`**. Keep existing working model settings if already configured. The VPS demo already has its model configuration.

### 9. Start again another day

Activate `.venv`, run `make dev-infra COMPOSE="docker compose"`, then start the API, worker and website in their three terminals. Get a new token if needed. There is no need to recreate `.env` or the virtual environment each time.

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
| Token rejected | Generate a fresh token for the same deployment and account; local and VPS tokens are separate. |
| Sign-in does nothing through a LAN address | Configure the browser API address, CORS origin and allowed dev host as shown in [LAN setup](week1-api.md#access-through-a-network-address), then restart API/web. |
| Port `3000` or `8000` is occupied | Check whether your earlier ExecPlus process is still running. Reuse or stop that process before starting another copy. |
