#!/usr/bin/env bash
# Use case: Owner-run undo of go-public.sh, returning Syntelio to tunnel-only access.
# What it does: Stops Caddy, restores only the public-access lines of app.env from the first saved copy
# (later edits such as rotated keys are kept), restores a localhost website image and closes 80/443.
# Usage: sudo bash go-private.sh [--dry-run]

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
keys=(
  EXECPLUS_WEB_ORIGIN
  EXECPLUS_PUBLIC_API_URL
  EXECPLUS_SESSION_COOKIE_SECURE
  EXECPLUS_TRUSTED_PROXIES
  EXECPLUS_CONNECTOR_ALLOW_PRIVATE_HOSTS
  EXECPLUS_LOCAL_REGISTRATION_ENABLED
)
dry_run=0
for argument in "$@"; do
  case "$argument" in
    --dry-run) dry_run=1 ;;
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

restore_key() {
  local file="$1" key="$2" saved="$3" temporary present value
  present="$(grep -c "^$key=" "$saved" || true)"
  value="$(env_value "$key" "$saved")"
  printf '+ restore %s in %s\n' "$key" "$file"
  ((dry_run)) && return 0
  temporary="$(mktemp "$file.XXXXXX")"
  KEY="$key" VALUE="$value" PRESENT="$present" awk '
    index($0, ENVIRON["KEY"] "=") == 1 { if (!done && ENVIRON["PRESENT"] != "0") print ENVIRON["KEY"] "=" ENVIRON["VALUE"]; done = 1; next }
    { print }
    END { if (!done && ENVIRON["PRESENT"] != "0") print ENVIRON["KEY"] "=" ENVIRON["VALUE"] }
  ' "$file" > "$temporary"
  chmod --reference="$file" "$temporary"
  chown --reference="$file" "$temporary"
  mv "$temporary" "$file"
}

test "$(id -u)" -eq 0 || { echo "Run with sudo." >&2; exit 1; }
test -f "$state" || { echo "No $state: Syntelio was not made public with go-public.sh." >&2; exit 1; }
stamp="$(env_value STAMP "$state")"
saved="$app_env.pre-public-$stamp"
test -f "$saved" || { echo "Missing the saved settings $saved." >&2; exit 1; }
((dry_run)) && echo "Dry run: nothing below is executed."

if ((dry_run == 0)); then
  exec 9>"$lock"
  flock -x 9
fi

if [[ -f "$public_env" ]]; then
  run docker compose -f "$here/compose.yaml" -f "$here/compose.public.yaml" --env-file "$public_env" rm --force --stop caddy
else
  run docker rm --force oisol-execplus-caddy-1
fi

run cp -p "$app_env" "$app_env.pre-private-$(date -u +%Y%m%dT%H%M%SZ)"
for key in "${keys[@]}"; do
  restore_key "$app_env" "$key" "$saved"
done

compose=(docker compose -f "$here/compose.yaml")
if [[ "$(docker image inspect --format '{{.Id}}' oisol-execplus/api:demo)" == "$(env_value API_IMAGE "$state")" ]]; then
  run docker tag "oisol-execplus/web:pre-public-$stamp" "$web_image"
else
  echo "A newer release is active, so the website is rebuilt for the tunnel address."
  run "${compose[@]}" build web
fi
run "${compose[@]}" up -d --no-build --no-deps --force-recreate api jobs web

if [[ "$(env_value UFW_RULES "$state")" == 1 ]] && command -v ufw >/dev/null; then
  run ufw delete allow 80/tcp
  run ufw delete allow 443/tcp
fi

if ((dry_run)); then
  echo "Dry run finished."
  exit 0
fi
mv "$state" "$state.closed-$(date -u +%Y%m%dT%H%M%SZ)"

for _ in $(seq 30); do
  if curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:18401/health/ready; then
    echo "Syntelio is private again: open it through the SSH tunnel at http://localhost:18400/workspace"
    exit 0
  fi
  sleep 3
done
echo "The API did not report ready. Check: docker logs oisol-execplus-api-1 --tail 50" >&2
exit 1
