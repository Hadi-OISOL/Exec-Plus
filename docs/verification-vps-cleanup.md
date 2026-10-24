# Private VPS cleanup — 19 October 2026

User-authorized maintenance; no application deployment or restart.

- Main filesystem observed usage: 185,562,488,832 → 163,675,869,184 bytes (83% → 73%). Net decrease **21.887 GB / 20.38 GiB**. Available space afterward: 60,934,197,248 bytes.
- Secondary filesystem observed decrease: 222,400,512 bytes. Filesystem deltas include concurrent normal server activity; they are not a sum of Docker logical layer sizes.
- Removed 147 old Syntelio image tags across 95 unused images. Preserved every container-referenced image, active release 9ce1f703b13b957f and previous release 0d6af5f7b68d02d3 images. No force removal or global image/container/volume prune.
- Two build-cache prunes matched only descriptions containing execplus, apps/api or apps/web and last use older than 24 hours. Reported reclaim: 558.6 MB and 2.616 GB. Second pass followed image removal. Other shared/unattributed cache remains intentionally; remaining cache is not all classified as unrelated or safe to delete.
- Removed 62 redundant intraday backups. Retained 25: latest backup for every represented day, plus current/previous releases' pre/post backups. All retained backup manifests passed checksums before removal. Latest post-release backup passed again afterward. No restore performed; checksums are not a fresh restore rehearsal.
- Removed 25 Syntelio staging tar archives older than 48 hours using explicit filename patterns. No general /tmp purge.
- Preserved live database/object storage, secrets, current source, release source snapshots, operational documentation and audit evidence. Small historical source/docs were not treated as junk without evidence. No scheduled retention policy changed.

## Verification

All 24 containers retain identical IDs, image IDs, restart counts, running states and mounts. API readiness reports PostgreSQL/object storage available; workspace HTTP 200. Previous release's two image IDs still exist. Application tests were not rerun because no runtime source or configuration changed; this is maintenance verification, not new feature acceptance.

Evidence and exact removal manifests: ignored `data/verification/2026-10-19/vps-cleanup/`. Initial checksum command failed because administrator could not enter the protected backup directory; rerun under sudo passed before backup deletion. No data was changed by that failed command.

Old image artifacts and redundant backup timestamps referenced in historical verification documents may now be retired; those historical test records remain valid, but do not imply all old deployment artifacts remain available. Current saved data must never be replaced with an older backup simply to roll back code.
