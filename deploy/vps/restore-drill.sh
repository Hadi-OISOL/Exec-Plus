#!/usr/bin/env bash
# Use case: Rehearses a private-demo recovery without touching running application data.
# What it does: Restores a checksummed backup into isolated temporary containers and verifies it.
set -euo pipefail
umask 077
root=/sdb-disk/OISOL_ExecPLUS
backup_id="${1:?backup timestamp required}"
release="${2:?explicit application commit required}"
migration="${3:?expected schema version required}"
[[ "$backup_id" =~ ^[0-9]{8}T[0-9]{6}Z$ ]]
[[ "$release" =~ ^[a-f0-9]{7,40}$ ]]
[[ "$migration" =~ ^[0-9]{4}$ ]]
test "$(id -u)" -eq 0
backup="$root/backups/$backup_id"
test -d "$backup"
(cd "$backup" && sha256sum -c SHA256SUMS)
image="oisol-execplus/api:candidate-$release"
docker image inspect "$image" >/dev/null
nonce="$(python3 -c 'import secrets; print(secrets.token_hex(6))')"
name="execplus_restore_$nonce"
dns_name="${name//_/-}"
folder="$root/ops/restore-$nonce"
mkdir "$folder"
mkdir "$folder/objects"
started="$(date +%s)"
database_id=''
objects_id=''
network_id=''
cleanup() {
  status=$?
  trap - EXIT
  if [[ "$status" -ne 0 && -n "$objects_id" ]]; then
    docker logs "$objects_id" > "$folder/object-store.log" 2>&1 || true
    docker inspect -f '{{json .State}}' "$objects_id" > "$folder/object-store-state.json" || true
  fi
  if [[ -n "$database_id" ]]; then docker rm -f "$database_id" >/dev/null; fi
  if [[ -n "$objects_id" ]]; then docker rm -f "$objects_id" >/dev/null; fi
  if [[ -n "$network_id" ]]; then docker network rm "$network_id" >/dev/null; fi
  rm -rf -- "$folder/objects"
  exit "$status"
}
trap cleanup EXIT
python3 - "$backup/objects.tar.gz" "$folder/objects" <<'PY'
import pathlib, sys, tarfile
destination = pathlib.Path(sys.argv[2]).resolve()
with tarfile.open(sys.argv[1], "r:gz") as archive:
    members = archive.getmembers()
    if len(members) > 100000 or sum(item.size for item in members) > 20 * 1024**3:
        raise ValueError("Recovery rehearsal archive exceeds declared resource limits")
    for item in members:
        target = (destination / item.name).resolve()
        if ((target != destination and destination not in target.parents)
                or not (item.isfile() or item.isdir())):
            raise ValueError("Recovery archive contains an unsupported entry")
    archive.extractall(destination, members=members)
PY
network_id="$(docker network create --internal --label execplus.recovery="$nonce" "$name")"
database_image="$(docker inspect -f '{{.Config.Image}}' oisol-execplus-postgres-1)"
storage_image="$(docker inspect -f '{{.Config.Image}}' oisol-execplus-storage-1)"
database_id="$(docker run -d --name "${name}_db" --network "$name" \
  --label execplus.recovery="$nonce" --memory 1g --cpus 2 \
  --env-file "$root/secrets/database.env" -e "POSTGRES_DB=$name" \
  --tmpfs /var/lib/postgresql/data:rw,size=1g "$database_image")"
for attempt in {1..30}; do
  if docker exec "$database_id" pg_isready -U execplus -d "$name" >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$database_id" pg_isready -U execplus -d "$name" >/dev/null
docker exec -i "$database_id" pg_restore --exit-on-error --no-owner \
  -U execplus -d "$name" < "$backup/database.dump"
objects_id="$(docker run -d --name "${name}_objects" --network "$name" \
  --network-alias "${dns_name}-objects" \
  --label execplus.recovery="$nonce" --memory 1g --cpus 2 \
  --env-file "$root/secrets/storage.env" \
  --mount "type=bind,source=$folder/objects,target=/data" \
  "$storage_image" server /data)"
docker run --rm --network "$name" --read-only --cap-drop ALL \
  --security-opt no-new-privileges --memory 2g --cpus 2 \
  --tmpfs /tmp:rw,size=1g,mode=1777 --env-file "$root/secrets/app.env" \
  "$image" python -c \
  'import sys,time,urllib.request
failure="unknown"
for attempt in range(30):
 try:
  urllib.request.urlopen("http://"+sys.argv[1]+"-objects:9000/minio/health/ready", timeout=2); break
 except OSError as error:
  failure=type(error).__name__+":"+str(getattr(error,"code","unavailable")); time.sleep(1)
else: raise SystemExit("Isolated object store did not become ready ("+failure+")")' "$dns_name"
docker run --rm --network "$name" --read-only --cap-drop ALL \
  --security-opt no-new-privileges --memory 2g --cpus 2 \
  --tmpfs /tmp:rw,size=1g,mode=1777 --env-file "$root/secrets/app.env" \
  --mount "type=bind,source=$root/source/scripts/verify_recovery_snapshot.py,target=/tmp/verify-recovery-snapshot.py,readonly" \
  "$image" python /tmp/verify-recovery-snapshot.py --name "$name" \
  --expected-migration "$migration" --replay-limit 20 > "$folder/verification.json"
python3 - "$folder" "$backup_id" "$release" "$started" <<'PY'
import json, pathlib, sys, time
folder = pathlib.Path(sys.argv[1])
report = json.loads((folder / "verification.json").read_text())
report.update(backup=sys.argv[2], application=sys.argv[3], elapsed_seconds=int(time.time())-int(sys.argv[4]),
              network="isolated-internal", exposed_ports=0, live_volumes_mounted=False)
(folder / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: report[key] for key in ("passed", "migration", "verified_objects", "receipts", "elapsed_seconds")}))
print("Recovery evidence saved:", folder / "verification.json")
PY
