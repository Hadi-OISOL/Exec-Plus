> **File use case:** Records the October 17 private-demo styling release.
> **What it does:** Separates actual deployed presentation checks from pending backend acceptance.

# October 17 styling release

The root operator activated `oisol-execplus/web:ui-20261017-live5c48d3c`
(`29a4f8f07b56`) on the private VPS. The image uses the existing `5c48d3c`
web source with one changed file, `studio-workspace.css` (SHA256 `64e2e5b1e5db`).
All 179 other/base web-build entries were checked against the source manifest.
This is a CSS-only release. API/jobs remain the prior `867c5a0` release and the
database remains **0020**. The locally integrated connector and Phase 2 backend
are not activated by this release.

Controls retain accessible sizes, keyboard focus and reduced-motion behavior.
Chart/table cards fit narrow layouts; a single finding uses the available width.
Always-open Overview charts and first findings remain open. Exact result strings,
missing values, zeroes, paging, chart navigation and evidence are unchanged.

## Evidence

- The separate candidate passed 59 frontend tests, TypeScript, ESLint and its
  production build. The root reviewed the one-file patch and desktop/mobile images.
- The actual VPS image passed 20 synthetic layouts before activation. After
  activation, the root reran 20 layouts through the existing local tunnel at
  1440, 768, 390 and 320 pixels: no page errors, overflow or unhandled API requests;
  exact values, keyboard navigation, dialog focus return and reduced motion pass.
  API calls were intercepted with explicit fictional fixtures. These are deployed
  web-component checks, not authenticated customer/backend acceptance.
- The root release helper passed nine synthetic success/failure checks locally
  and on the VPS. One maintenance lock covers checked pre-backup, the web switch
  and checked post-backup. Actual running image IDs, configuration hashes, source
  hashes, schema, readiness, web HTTP, six loopback listeners and model/timers pass.
- API/jobs/postgres/storage container identity and start times match immediately
  before and after the web switch. Backup procedures deliberately restart storage,
  API and jobs before/after that window; no claim is made that those services never
  restarted during the full operation. No schema migration or data restore ran.

The checkpoint is `web-only-20261017T153601311884Z`; its prior actual web image is
`95d578257239`. An older handoff recorded a different mutable-tag image value.
The actual running container image, preserved in checkpoint metadata, controls
rollback; the old handoff value was not used.

Checked backups are **20261017T153602Z** and **20261017T153628Z**. Both database
and object checksums, dump catalog, gzip and tar catalog checks pass. The helper
initially used microsecond/phase suffixes that the existing restore command would
reject. A separately reviewed repair atomically renamed only the two directories
with no-overwrite semantics. Five synthetic repair checks pass; archive checksums
and directory identity remain unchanged. Original completion metadata and the
old-to-new mapping are retained, with corrected references in a separate report.
This naming defect is retained rather than hidden. No restore was performed.

Private evidence lives under
`data/verification/2026-10-17/ui-coordination/root-web-release/`, including the
executed bundle, original and corrected completion records, metadata, compatibility
repair and `live-synthetic/2026-10-17T15-36-56.628Z/` images/results.

The local Phase 2 six-journey anomaly/calendar/scenario browser recheck also passes
on this stylesheet in 107.541 seconds. That newer local application is separate
from the older live backend. Full Phase 2 acceptance and its migration/release
remain pending. Production security, public hosting and external providers remain
independently gated.
