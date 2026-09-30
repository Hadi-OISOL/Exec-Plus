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
restart_services() { "${compose[@]}" start storage api >/dev/null; }
trap restart_services EXIT
"${compose[@]}" stop api
"${compose[@]}" stop storage
"${compose[@]}" exec -T postgres pg_dump -U execplus -d execplus -Fc > "$backup/database.dump"
tar -C "$root/objects" -czf "$backup/objects.tar.gz" .
cd "$backup"
sha256sum database.dump objects.tar.gz > SHA256SUMS
sha256sum -c SHA256SUMS
printf 'Backup saved: %s\n' "$backup"
