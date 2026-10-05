#!/usr/bin/env bash
# Use case: Captures a consistent private-demo database and object-store backup on sdb.
# What it does: Pauses only ExecPlus writers and retains checksummed, private recovery artifacts.

set -euo pipefail
umask 077
root=/sdb-disk/OISOL_ExecPLUS
compose=(docker compose -f "$root/source/deploy/vps/compose.yaml")
test "$(id -u)" -eq 0
exec 9>/run/lock/execplus-maintenance.lock
flock -x 9
mountpoint -q /sdb-disk
backup="$root/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$backup"
active_services="$("${compose[@]}" ps --services --status running)"
mapfile -t running <<< "$active_services"
restart=()
for service in storage api jobs; do
  for active in "${running[@]}"; do
    if [[ "$service" == "$active" ]]; then restart+=("$service"); fi
  done
done
restart_services() {
  if ((${#restart[@]})); then "${compose[@]}" start "${restart[@]}" >/dev/null; fi
}
trap restart_services EXIT
"${compose[@]}" stop api jobs
"${compose[@]}" stop storage
"${compose[@]}" exec -T postgres pg_dump -U execplus -d execplus -Fc > "$backup/database.dump"
tar -C "$root/objects" -czf "$backup/objects.tar.gz" .
cd "$backup"
sha256sum database.dump objects.tar.gz > SHA256SUMS
sha256sum -c SHA256SUMS
printf 'Backup saved: %s\n' "$backup"
