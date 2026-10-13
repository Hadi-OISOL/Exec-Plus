> **File use case:** Records acceptance of the teammate onboarding integration.
> **What it does:** Retains local checks, deployed evidence, failures and rollback boundaries.

# Guided onboarding integration verification — October 13, 2026

Accepted for supported local/test and private-demo operation. This is not full
commercial onboarding or production acceptance. Teammate `ba11afb` checkout inputs
were its 14-line page diff and two guided-review files; current local baseline is
`639e28c` on `phase2`. Original inputs and preexisting uncommitted work are preserved
under ignored `data/onboarding-merge-20261013/`. No Git commit, push or branch merge
was performed; reviewed frontend changes were integrated into the current files.

## Checks and evidence

- 67 targeted backend/architecture contract cases pass in 44.00 seconds, using
  disposable PostgreSQL schemas/MinIO buckets. An existing python-multipart
  deprecation warning remains. This rechecks existing understanding/guidance/scenario
  contracts; the earlier 968-case scenario evidence is not a fresh full-backend run.
- Six new real-service browser cases pass: optional skip; separate private-note/shared
  draft saves; 12-column focused review; optimistic stale conflict; ordinary-member
  privacy/edit limits; explicit note sharing without confirmation.
- The full live-model browser run passes all **37 distinct journeys** in 4.2 minutes.
  The focused six-case run took 30.7 seconds. All 17 frontend unit tests, TypeScript,
  ESLint, local optimized build, Ruff and mypy (156 files) pass.
- VPS candidate web build passes. All 174 selected Python/migration/web-source files
  match the local candidate hashes. Only web is recreated: API/jobs container IDs and
  image hashes are retained; schema remains 0017. No model, secret environment, public
  port, identity or email configuration changed.
- Eight real deployed demo accounts each upload a new fictional CSV, save a private
  interpretation and explicitly save shared corrections as a draft. **8/8 pass**:
  eight uploads/notes/drafts, zero automatic confirmations, 56 unauthorized citation
  denials and 56 list omissions, 24 layouts (1440/390/320), zero browser errors.
  Authorized citation controls pass for each owner; source profiles remain unchanged
  and the preexisting shared dataset meaning is unchanged. Total 78.387 seconds.
  This is a short functional rehearsal, not sustained-load or customer acceptance.
- Four historical profile-v1/v2 receipts pass independent exact typed-checksum replay.
  Sessions were renewed privately because previous tokens had expired.
- The regenerated Desktop DOCX/PDF retains all 64 original feature IDs/names and
  ten pages; previous report filenames are synchronized after backups. A report
  checker initially included the summary-count table, then was corrected to inspect
  only feature tables. The output was not changed for that checker correction.
- `make production-preflight` fails as expected with all eight evidence gates blocked;
  no demo evidence clears production readiness.

## Retained failures and limits

The initial lint attempt caught impure `Date.now()` in render; filenames now bind to
source revision. The first VPS checker attempted a hidden upload form without
opening Data library and timed out before uploading. Its failure log is retained;
only checker navigation changed before the passing rehearsal. The optional notes
endpoint has no exactly-once guarantee after an interrupted connection; the UI
blocks overlapping saves and explains uncertain completion rather than false success.

## Commands executed

From repository root, except npm commands use `apps/web`:

```bash
EXECPLUS_TEST_DATABASE_URL='postgresql+psycopg://execplus:execplus@localhost:55433/execplus' python3 -m pytest apps/api/tests/test_understanding.py apps/api/tests/test_dataset_guidance.py apps/api/tests/test_scenarios_integration.py tests/test_architecture.py -o addopts='' -q
EXECPLUS_TEST_DATABASE_URL='postgresql+psycopg://execplus:execplus@localhost:55433/execplus' EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py
npm run typecheck
npm run lint
npm test
npm run build
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
git diff --check
make production-preflight
PYTHONPATH=data/report-tools python3 scripts/build_feature_report.py --output /home/it-admin/Desktop/ExecPlus_VC_Feature_Report_2026-10-13.docx
libreoffice -env:UserInstallation=file:///tmp/execplus-onboarding-report-lo --headless --convert-to pdf --outdir data/onboarding-merge-20261013 /home/it-admin/Desktop/ExecPlus_VC_Feature_Report_2026-10-13.docx
node data/onboarding-merge-20261013/eight-users.mjs --run
python3 data/onboarding-merge-20261013/check_legacy_receipts.py --run --output data/onboarding-merge-20261013/legacy-after.json
```

Remote operator actions were invoked over the existing verified SSH master:

```bash
sudo bash deploy/vps/backup.sh
sudo bash /tmp/execplus-onboarding-prepare.sh
sudo flock /run/lock/execplus-maintenance.lock docker compose -f deploy/vps/compose.yaml run --rm -T operator python scripts/provision_demo.py --confirm-fictional-demo --output /run/execplus-demo/sessions.json
sudo bash /tmp/execplus-onboarding-activate.sh
curl -fsS http://127.0.0.1:18401/health/ready
sudo systemctl is-active execplus-refresh.timer execplus-backup.timer
```

The ignored prepare script copies live source into a candidate, overlays only the
three frontend inputs and builds a separate candidate web tag. The activation script
holds the maintenance lock, checkpoints source/web image, copies the three reviewed
files and runs `docker compose ... up -d --no-deps web`. Private preparation,
build/check/backup logs, scripts, screenshots and source hashes remain in
`data/onboarding-merge-20261013/` and remote `ops/onboarding-20261013/`.

## Recovery and remaining work

Frontend rollback checkpoint: `releases/pre-onboarding-20261013/source`, image
`oisol-execplus/web:pre-onboarding-20261013`. Restore matching frontend files and
retag/recreate only web under the maintenance lock; retain all new notes and drafts.
Do not restore an old database over new user work. Pre-release checked backup:
**20261013T114537Z**. Post-release checked backup: **20261013T115029Z**, database/object checksum checks pass; API/jobs/storage restart successfully with healthy readiness. Refresh and backup timers remain active.

Feature 18 remains Done; 47 remains Partial. The report retains **37 Done /16 Partial
/11 Not yet** and all original 64 IDs. All eight production gates remain blocked;
Phase 4D/4E and broad Phase 6 are not completed by this frontend release. See
[Partial closure dependencies](partial-feature-closure-plan.md).
