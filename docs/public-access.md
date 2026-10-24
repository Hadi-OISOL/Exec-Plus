# Public HTTPS access for Syntelio

> **File use case:** Owner runbook for opening the VPS deployment on a public HTTPS address.
> **What it does:** Explains the setup, the exact commands, checks, domain change, rollback and the
> limits that still apply.

## What this does

Today Syntelio is reachable only through an SSH tunnel (`http://localhost:18400`). After this change
anyone with the link can open it at one HTTPS address, 24/7, with no tunnel:

- **One address for everything.** `https://<host>/` is the website; `https://<host>/api/...` is the
  API. Using one hostname keeps the sign-in cookie first-party, so browsers keep you signed in.
- **Caddy** is a small web server that runs in a container in front of the app. It gets a free
  certificate from Let's Encrypt and renews it automatically, redirects `http://` to `https://`,
  removes `/api` before passing a request to the API, limits request size to 25 MiB, adds security
  headers and logs requests **without query strings** (so sign-in codes are never logged).
- **API, website, database and storage stay private.** They still listen only on `127.0.0.1`. Only
  Caddy listens on the internet, on ports 80 and 443.
- **Free hostname now:** `syntelio.173-208-151-137.sslip.io`. sslip.io is a free DNS service that
  turns the IP in the name into an address; nothing to buy or configure. A real domain later is a
  one-line change (see below).

Files involved (all in `deploy/vps/`):

| File | Purpose |
| --- | --- |
| `public.env.example` | The settings you fill in; copied to `/sdb-disk/OISOL_ExecPLUS/secrets/public.env`. |
| `Caddyfile` | Caddy's routing, headers, size limit and log filtering. |
| `compose.public.yaml` | Adds the Caddy container and builds the website for the public API address. |
| `go-public.sh` | Turns public access on (or moves to a new hostname). Has `--dry-run`. |
| `go-private.sh` | Turns it off again and returns to tunnel-only access. Has `--dry-run`. |

## What `go-public.sh` does, in order

1. Checks you are root, `public.env` is filled in correctly, the hostname resolves to this server
   and nothing else already uses ports 80/443. It stops here, changing nothing, if any check fails.
2. Takes a checked backup with the existing `backup.sh` (database + files, checksums verified).
3. Takes the maintenance lock, so the backup timer and refresh worker cannot run at the same time.
4. Saves `app.env` as `app.env.pre-public-<time>`, tags the current website image as
   `oisol-execplus/web:pre-public-<time>` and records this in `secrets/public-state` (only on the
   first run, so the undo always returns to the original private setup).
5. Changes these lines in `app.env` (everything else, including secrets, is untouched):

   | Setting | New value | Why |
   | --- | --- | --- |
   | `EXECPLUS_WEB_ORIGIN` | `https://<host>` | Only the public site may call the API with cookies. |
   | `EXECPLUS_PUBLIC_API_URL` | `https://<host>/api` | Google sign-in sends people back here. |
   | `EXECPLUS_SESSION_COOKIE_SECURE` | `true` | The sign-in cookie is only sent over HTTPS. |
   | `EXECPLUS_TRUSTED_PROXIES` | `["127.0.0.1"]` | Sign-in rate limits use the real visitor IP that Caddy reports. |
   | `EXECPLUS_CONNECTOR_ALLOW_PRIVATE_HOSTS` | `false` | Connectors cannot be pointed at addresses inside the server. |
   | `EXECPLUS_LOCAL_REGISTRATION_ENABLED` | your choice | Only if you set it in `public.env`. |

6. Rebuilds the website image with the public API address built in.
7. Recreates the API, jobs and website containers, then starts Caddy.
8. If the ufw firewall is already on, opens ports 80 and 443 in it.
9. Waits up to 5 minutes for `https://<host>/api/health/ready` and `https://<host>/workspace`, then
   prints the address.

## Before you start

- SSH access to the VPS as `administrator` with sudo.
- The new scripts on the VPS. They are part of the source after the next release. Until then, copy
  the five files from `deploy/vps/` of this branch into `/sdb-disk/OISOL_ExecPLUS/source/deploy/vps/`
  (they do not change anything by being there):

  ```bash
  scp deploy/vps/{public.env.example,Caddyfile,compose.public.yaml,go-public.sh,go-private.sh} \
      administrator@173.208.151.137:/tmp/
  ssh administrator@173.208.151.137
  sudo cp /tmp/{public.env.example,Caddyfile,compose.public.yaml,go-public.sh,go-private.sh} \
      /sdb-disk/OISOL_ExecPLUS/source/deploy/vps/
  ```

- **Rotate the DeepSeek key and the Google client secret first.** Both were shared in chat. Put the
  new values in `/sdb-disk/OISOL_ExecPLUS/secrets/app.env` (`EXECPLUS_LLM_API_KEY`,
  `EXECPLUS_GOOGLE_CLIENT_SECRET`).
- Decide whether strangers may sign up (see "Sign-up" below).
- Ports 80 and 443 must be reachable from the internet. On 2026-10-24 nothing on the server used
  them and ufw was off; if the hosting provider has its own firewall panel, open TCP 80 and 443 there.

## Step by step

All commands run on the VPS.

```bash
cd /sdb-disk/OISOL_ExecPLUS/source/deploy/vps

# 1. Fill in your settings (hostname, your email, sign-up choice).
sudo install -m 600 public.env.example /sdb-disk/OISOL_ExecPLUS/secrets/public.env
sudo nano /sdb-disk/OISOL_ExecPLUS/secrets/public.env

# 2. See exactly what will happen. Changes nothing.
sudo bash go-public.sh --dry-run

# 3. Go public. Takes about 5-10 minutes (backup + website build).
sudo bash go-public.sh
```

It ends with `Syntelio is public at: https://syntelio.173-208-151-137.sslip.io/workspace`.

### Google sign-in

Google is enabled on the VPS, so add the new addresses to the OAuth client in Google Cloud Console
(APIs & Services > Credentials > the OAuth 2.0 client):

- Authorized JavaScript origin: `https://<host>`
- Authorized redirect URIs: `https://<host>/api/auth/google/callback` and
  `https://<host>/api/integrations/google/callback`

You can keep the old `localhost:18401` entries until you no longer need the tunnel. Google may
refuse sslip.io addresses or show an "unverified app" screen; if it refuses them, Google sign-in waits
for the real domain while email/password accounts keep working.

## How to check it works

From any computer:

```bash
H=https://syntelio.173-208-151-137.sslip.io
curl -sS $H/api/health/ready                         # {"status":"ready",...}
curl -sS -o /dev/null -w '%{http_code}\n' $H/workspace # 200
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' http://syntelio.173-208-151-137.sslip.io/  # 308 https://...
curl -sSI $H/workspace | grep -i strict-transport      # HSTS header present
```

In a browser (ideally a private window and once on a phone using mobile data):

1. Open `https://<host>/workspace`; the padlock shows a valid certificate.
2. Create an account, then reload the page: you stay signed in.
3. Upload a small CSV and ask a question; an answer appears.
4. Sign out, sign in again. If Google is set up, try the Google sign-in button.
5. Disable the test account afterwards (account settings, "disable account").

On the VPS: `docker logs oisol-execplus-caddy-1 --tail 50` shows certificate and request logs.

## Moving to a real domain later

1. At your domain registrar, add a DNS `A` record, e.g. `app.example.com` → `173.208.151.137`.
   Wait until `getent hosts app.example.com` on the VPS shows that IP.
2. Change one line in `/sdb-disk/OISOL_ExecPLUS/secrets/public.env`:
   `SYNTELIO_PUBLIC_HOST=app.example.com`
3. Add the new origin and two redirect URIs to the Google OAuth client (same pattern as above).
4. Run `sudo bash go-public.sh` again. It rebuilds the website for the new address, updates
   `app.env`, restarts Caddy (which fetches a certificate for the new name) and keeps the original
   private settings for the undo script.

People signed in on the old address need to sign in again on the new one.

## Rolling back

```bash
cd /sdb-disk/OISOL_ExecPLUS/source/deploy/vps
sudo bash go-private.sh --dry-run
sudo bash go-private.sh
```

This stops and removes Caddy, sets the six public-access lines in `app.env` back to their original
values (other edits made since, such as rotated keys, are kept), puts back the tunnel website image
(or rebuilds it if a newer release was installed meanwhile), recreates the API, jobs and website and
removes the 80/443 firewall rules if `go-public.sh` added them. Access is then through the SSH tunnel
again. The certificates stay in `/sdb-disk/OISOL_ExecPLUS/caddy/` for a quick return.

The data is not touched by either script. The backup taken in step 2 is there if anything else goes
wrong (`docs/vps-demo-runbook.md`, "Backups and restoration").

## Firewall (ufw)

ufw is **off** on this server. Docker publishes container ports by editing iptables directly, so
ufw does **not** protect ports published by Docker. Syntelio's own containers bind to `127.0.0.1`, so
they stay private either way. Other apps on this server matter:

- `learnanysong-api` publishes port **8009** on all addresses through Docker; ufw cannot close it.
- `nvidia_gpu_expo` listens on port **9835** directly; turning ufw on would block it from outside.

If you want the firewall on (only SSH, 80 and 443 allowed for normal programs), check with the owners
of those apps first, then run `sudo bash go-public.sh --enable-firewall`. It allows OpenSSH **before**
enabling ufw, so your SSH session is not cut off. Caddy also offers HTTP/3, which uses UDP 443; with
ufw on, browsers simply fall back to normal HTTPS unless you also run `sudo ufw allow 443/udp`.

## Sign-up

Right now anyone who finds the address can create an account, and every account gets a workspace and
can spend hosted-model (DeepSeek) usage. Options:

- Keep it open for a demo period, and watch the admin usage report.
- Set `SYNTELIO_LOCAL_REGISTRATION_ENABLED=false` in `public.env` and rerun `go-public.sh`: existing
  accounts keep working; new people can no longer create accounts by themselves.

Sign-up and sign-in rate limits now count each visitor's own IP (Caddy passes it to the API). Before,
all tunnel users shared one limit because they all arrived from `127.0.0.1`.

## Future releases (important)

The website image has the API address built in. The release kit in
`data/verification/<date>-claude-release/build.sh` currently builds the website with
`--build-arg NEXT_PUBLIC_API_URL=http://localhost:18401`. While Syntelio is public, change that line to
`--build-arg NEXT_PUBLIC_API_URL=https://<host>/api` (the value of `SYNTELIO_PUBLIC_HOST`), or the
next release will break the public website (it would call the tunnel address). Releases leave Caddy
running and `app.env` unchanged. Adding these five files to the release source also makes the
scripts available without the manual copy above.

## What is still NOT production-ready

Public access makes the private demo reachable; it does not make it a production service.

- **All 8 production gates in `docs/production-readiness.json` are still open:** representative
  corpus, retrieval quality, vector provider, backup/restore drills, model comparison, provider
  privacy (customer data goes to DeepSeek), report delivery and identity/security review.
- **Accounts:** the server still runs `EXECPLUS_ENVIRONMENT=local`, because the email/password
  sign-in only runs in local/test mode. There is no email verification, and password recovery is an
  operator reset code. Treat it as a demo for invited people.
- **Secrets:** rotate the DeepSeek key and the Google client secret (shared in chat earlier).
- **Backups stay on the same server.** A disk or server failure loses both the app and its backups.
  Copy backups off the server (`docs/recovery-rehearsal.md`).
- **No monitoring or uptime alerts.** Add an external uptime check on `https://<host>/api/health/ready`.
- **Sign-up is open** unless you turn it off (see above). Public signups can use paid model tokens.
- **sslip.io** is a free third-party service; if it is down, the address does not resolve. A real
  domain removes that dependency.
- **Shared host:** other applications on this VPS are unaffected by Caddy, but a problem in one of
  them (CPU, memory, disk) can still slow Syntelio.
- Anything already listening on `127.0.0.1` (including SSH tunnel users) can claim any visitor IP to
  the sign-in rate limiter, because the API trusts `X-Forwarded-For` from `127.0.0.1`. Only trusted
  operators have tunnels today.

## What was verified before handing over (2026-10-24)

- **Local rehearsal** with the same Caddyfile and pinned Caddy image, the production website image
  built with `NEXT_PUBLIC_API_URL=https://syntelio.localhost:36443/api`, the API (`--no-proxy-headers`,
  the five public settings) and a jobs worker, using Caddy's own test certificate (`tls internal`):
  sign-up in Chrome, reload keeps the session, cookie is HttpOnly + Secure + SameSite=Lax on the one
  host and no token in browser storage, CSV upload, chat question answered, no page errors. Also:
  `http://` redirects (308) to `https://`, foreign-origin sign-in is refused (403), cookie requests
  without the app header are refused (401), a 28 MB upload is refused with 413 (with and without a
  declared size), a spoofed `X-Forwarded-For` is replaced by the real client IP, `/api` is removed
  before the API sees the path, and access logs drop query strings and cookies.
- `caddy validate` and `caddy fmt` pass; `docker compose config` merges `compose.public.yaml` as
  intended; shellcheck 0.10.0 passes for both scripts; `apps/api/tests/test_public_access_scripts.py`
  rehearses dry run, go-public → go-private round trip, rebuild-on-newer-release and refusals.
- **Not verified:** a real Let's Encrypt certificate for the sslip.io name, reachability of ports
  80/443 through the provider's network, Google sign-in on the new address, and the scripts on the
  VPS itself (only read-only inspection was done there).
