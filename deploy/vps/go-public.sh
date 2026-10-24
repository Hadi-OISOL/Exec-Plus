#!/usr/bin/env bash
# Use case: Owner-run switch that makes Syntelio reachable at a public HTTPS address on the VPS.
# What it does: Checked backup, saved app.env, public settings, web rebuild, Caddy start, service
# recreation and an HTTPS readiness wait. Rerun after changing SYNTELIO_PUBLIC_HOST to move hosts.
# Usage: sudo bash go-public.sh [--dry-run] [--enable-firewall]

set -euo pipefail
umask 077
root=/sdb-disk/OISOL_ExecPLUS
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
secrets="$root/secrets"
public_env="$secrets/public.env"
app_env="$secrets/app.env"
state="$secrets/public-state"
lock=/run/lock/execplus-maintenance.lock
web_image=oisol-execplus/web:demo
dry_run=0
enable_firewall=0
for argument in "$@"; do
  case "$argument" in
    --dry-run) dry_run=1 ;;
    --enable-firewall) enable_firewall=1 ;;
    *) echo "Unknown option: $argument" >&2; exit 2 ;;
  esac
done

run() {
  printf '+ %s\n' "$*"
  if ((dry_run == 0)); then "$@"; fi
}

env_value() {
  awk -v key="$1" 'index($0, key "=") == 1 { value = substr($0, length(key) + 2) } END { print value }' "$2"
}

set_key() {
  local file="$1" key="$2" value="$3" temporary
  printf '+ set %s in %s\n' "$key" "$file"
  ((dry_run)) && return 0
  temporary="$(mktemp "$file.XXXXXX")"
  KEY="$key" VALUE="$value" awk '
    index($0, ENVIRON["KEY"] "=") == 1 { if (!done) print ENVIRON["KEY"] "=" ENVIRON["VALUE"]; done = 1; next }
    { print }
    END { if (!done) print ENVIRON["KEY"] "=" ENVIRON["VALUE"] }
  ' "$file" > "$temporary"
  chmod --reference="$file" "$temporary"
  chown --reference="$file" "$temporary"
  mv "$temporary" "$file"
}

test "$(id -u)" -eq 0 || { echo "Run with sudo." >&2; exit 1; }
test -f "$public_env" || { echo "Missing $public_env (copy public.env.example and fill it in)." >&2; exit 1; }
test -f "$app_env" || { echo "Missing $app_env." >&2; exit 1; }
for file in compose.yaml compose.public.yaml Caddyfile backup.sh; do
  test -f "$here/$file" || { echo "Missing $here/$file." >&2; exit 1; }
done

host="$(env_value SYNTELIO_PUBLIC_HOST "$public_env")"
email="$(env_value SYNTELIO_ACME_EMAIL "$public_env")"
registration="$(env_value SYNTELIO_LOCAL_REGISTRATION_ENABLED "$public_env")"
host_pattern='^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$'
[[ "$host" =~ $host_pattern ]] || { echo "SYNTELIO_PUBLIC_HOST must be a lowercase hostname, e.g. syntelio.1-2-3-4.sslip.io." >&2; exit 1; }
[[ "$email" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ && "$email" != *@example.com ]] || { echo "Set SYNTELIO_ACME_EMAIL to a real mailbox." >&2; exit 1; }
[[ -z "$registration" || "$registration" == true || "$registration" == false ]] || { echo "SYNTELIO_LOCAL_REGISTRATION_ENABLED must be empty, true or false." >&2; exit 1; }

addresses="$(getent ahostsv4 "$host" | awk '{ print $1 }' | sort -u)"
local_addresses="$(ip -4 -o addr show scope global | awk '{ split($4, part, "/"); print part[1] }')"
if [[ -z "$addresses" ]] || ! grep -qxF -f <(printf '%s\n' "$local_addresses") <<< "$addresses"; then
  echo "$host does not resolve to this server (${addresses:-no address}). Fix DNS first." >&2
  exit 1
fi
caddy_running="$(docker ps -q --filter label=com.docker.compose.project=oisol-execplus --filter label=com.docker.compose.service=caddy)"
if [[ -z "$caddy_running" ]] && ss -H -ltn '( sport = :80 or sport = :443 )' | grep -q .; then
  echo "Ports 80 or 443 are already used by another program on this server:" >&2
  ss -H -ltnp '( sport = :80 or sport = :443 )' >&2
  exit 1
fi

compose=(docker compose -f "$here/compose.yaml" -f "$here/compose.public.yaml" --env-file "$public_env")
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
url="https://$host"
echo "Target address: $url"
((dry_run)) && echo "Dry run: nothing below is executed."

run bash "$here/backup.sh"

if ((dry_run == 0)); then
  exec 9>"$lock"
  flock -x 9
fi

run cp -p "$app_env" "$app_env.pre-public-$stamp"
if [[ ! -f "$state" ]]; then
  run docker tag "$web_image" "oisol-execplus/web:pre-public-$stamp"
  printf '+ record rollback state in %s\n' "$state"
  if ((dry_run == 0)); then
    {
      echo "STAMP=$stamp"
      echo "API_IMAGE=$(docker image inspect --format '{{.Id}}' oisol-execplus/api:demo)"
      echo "UFW_RULES=0"
    } > "$state"
  fi
fi

run mkdir -p "$root/caddy/data" "$root/caddy/config"
run install -m 0644 "$here/Caddyfile" "$root/caddy/Caddyfile"

set_key "$app_env" EXECPLUS_WEB_ORIGIN "$url"
set_key "$app_env" EXECPLUS_PUBLIC_API_URL "$url/api"
set_key "$app_env" EXECPLUS_SESSION_COOKIE_SECURE true
set_key "$app_env" EXECPLUS_TRUSTED_PROXIES '["127.0.0.1"]'
set_key "$app_env" EXECPLUS_CONNECTOR_ALLOW_PRIVATE_HOSTS false
if [[ -n "$registration" ]]; then
  set_key "$app_env" EXECPLUS_LOCAL_REGISTRATION_ENABLED "$registration"
fi

run "${compose[@]}" build web
run "${compose[@]}" up -d --no-build --no-deps --force-recreate api jobs web
run "${compose[@]}" up -d --no-build --no-deps --force-recreate caddy

if command -v ufw >/dev/null; then
  if ((enable_firewall)); then
    run ufw allow OpenSSH
    run ufw allow 80/tcp
    run ufw allow 443/tcp
    run ufw --force enable
    ((dry_run)) || sed -i 's/^UFW_RULES=.*/UFW_RULES=1/' "$state"
  elif ufw status | grep -q '^Status: active'; then
    run ufw allow 80/tcp
    run ufw allow 443/tcp
    ((dry_run)) || sed -i 's/^UFW_RULES=.*/UFW_RULES=1/' "$state"
  else
    echo "Note: the ufw firewall is off. See docs/public-access.md before using --enable-firewall."
  fi
fi

if ((dry_run)); then
  echo "Dry run finished. Would wait for $url/api/health/ready."
  exit 0
fi

echo "Waiting for the certificate and the services (up to 5 minutes)..."
for _ in $(seq 60); do
  if curl -fsS --max-time 10 -o /dev/null "$url/api/health/ready" \
    && curl -fsS --max-time 10 -o /dev/null "$url/workspace"; then
    echo "Syntelio is public at: $url/workspace"
    exit 0
  fi
  sleep 5
done
echo "HTTPS did not become ready. Check: docker logs oisol-execplus-caddy-1 --tail 50" >&2
echo "Undo with: sudo bash $here/go-private.sh" >&2
exit 1
