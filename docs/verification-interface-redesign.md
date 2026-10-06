> **File use case:** Records acceptance evidence for the October 6 analytics interface redesign.
> **What it does:** Separates inspected reference material, verified presentation work, corrected failures and remaining product boundaries.

# Analytics interface redesign verification

**Status: Complete for local/test and the private-demo presentation slice.** The source baseline is `phase2` commit `769acea`. Read the
[scope audit](interface-redesign-audit.md) for the implementation boundary. An
optional scope question received no answer; the stated analytics-first assumption
governs this slice. The marketing website is outside this delivery.

## Reference and implemented scope

Public ThoughtSpot documentation and screenshots were inspected on October 6,
2026. No authenticated product account was accessed. Original ExecPlus components
use the observed navigation and data-presentation patterns; the external brand,
screenshots and implementation code are not application assets. This work does not
establish complete feature or visual parity with ThoughtSpot.

| Public reference | Observed pattern | Verified ExecPlus presentation |
| --- | --- | --- |
| [Home and navigation](https://docs.thoughtspot.com/cloud/26.9.0.cl/thoughtspot-homepage) | Grouped left navigation, compact top bar, prominent question composer | Analytics shell, source context, home shortcuts and scoped saved-work list |
| [Conversational exploration](https://docs.thoughtspot.com/cloud/26.9.0.cl/spotter-getting-started) | Framed answers, visualization controls and follow-up input | Dedicated conversation view and reusable executed-result presentation |
| [Liveboards and Answers](https://docs.thoughtspot.com/cloud/26.9.0.cl/liveboards) | KPI/chart/table cards and content libraries | Exact-value tables, chart/table switching, expansion and saved-study/dashboard galleries |
| [Liveboard filters](https://docs.thoughtspot.com/cloud/26.9.0.cl/liveboard-filters) | Visible applied-filter state and explicit application | Submitted dashboard-filter strip using the existing governed query path |
| [Drill-down](https://docs.thoughtspot.com/cloud/26.9.0.cl/search-drill-down) | Explore a selected data point | Existing bounded matching-record exploration, including expanded-chart interactions |

Reference-only images and their source register are retained under ignored
`data/interface-reference/`. New frontend files include `analytics-home.tsx`,
`analytics-shell.css`, `answer-visualization.tsx`, `visualization-values.ts`,
`library-controls.tsx`, `saved-result.tsx` and their scoped styles. Existing
workspace, discovery, chat, dashboard, saved-item and study presentation now uses the existing APIs.

No schema migration, backend calculation change, model selection change or network
exposure change is included in this slice. Chart positions remain approximate;
original returned strings, signs, nulls and exact values remain authoritative.
Saved analysis replay and immutable study versions retain their original evidence.
Workspace dashboards retain their six-pin limit and explicit sharing rules.
Only real server activity can appear in action disclosures. No hidden model
reasoning, invented business values, fabricated recency or unsupported control is
part of the accepted design.

## Verification results

| Check | Result | Evidence and scope |
| --- | --- | --- |
| Backend contracts and architecture | 76 passed | Existing saved-item, study, query-precision, analytics and architecture cases; backend implementation is unchanged |
| Frontend unit tests | 17 passed | Eight new numerical visualization regressions plus the prior nine cases |
| Focused new browser journeys | 5 passed in 37.3s | Home (2), libraries (2), visualization (1), real PostgreSQL/MinIO/API and workers |
| Existing plus new browser journeys | All 29 distinct journeys passed | Full attempt: 26 passed, 3 selector/navigation failures; corrected three passed in 27.3s without runtime changes |
| Static checks | Passed | Ruff, mypy (148 files), frontend ESLint, TypeScript and diff whitespace |
| Production builds | Passed locally and on the VPS | Candidate image built before activation; generated Next type-file header restored locally |
| Production preflight | Expected failure | All eight mandatory production gates remain blocked |
| Private VPS | Eight of eight users passed in 43.935s | Eight exact saved replays, 56 private-item denials, eight authorized controls, 72 layouts and zero browser errors |

These 76 backend cases are a targeted regression subset, not another full 869-case
backend run. The preceding operations release retains its historical full-suite
result. Runtime frontend files were frozen before the complete browser run; its
three corrections only adapt existing tests to the deliberate UI changes. A later
caption-only change replaces the synthetic final `__value` heading with its known
metric or count label in dashboard/discovery views. That change passed the focused
visualization browser case (13.3s), fresh local/VPS builds and a deployed two-chart
header check with exact saved replay. The eight-user rehearsal predates this final
caption cleanup. Original source columns and JSON evidence remain unchanged.

## Coverage and corrected failures

New unit cases retain exact decimals/unsafe integers, distinguish booleans and
non-numbers from measures, anchor signed/zero bars, keep finite extreme coordinates,
break lines at explicit nulls, preserve bounded immutable rows and rank decimals
without lossy conversion. Browser cases cover real saved receipts and revocation,
neutral saved guidance/source evidence, study sharing/pins and observed-only points,
server filter bodies, chart/table expansion, Escape/focus, modal drill-down,
metadata-only library search, mobile widths and an incoming question during a real
in-flight job. A derived readable table header leaves original JSON unchanged.

Earlier failed attempts remain retained:

- `focused-browser-first.log`: mobile overflow, changed filter/study selectors and
  a development hot-reload interaction during active edits.
- `library-mobile-diagnostic*.log`: measured HTML overflow came from legacy
  absolutely positioned navigation labels. The new shell restores their normal
  positioning; chart tables keep their own horizontal scroll rather than clipping
  the page indiscriminately.
- `focused-browser-final.log`: four passed and one study summary selector timed
  out; the corrected five all passed in `focused-browser-verified.log`.
- `full-browser.log`: 26 passed, three older assertions targeted hidden discovery,
  an ambiguous page-wide status or a replaced CSS class. Tests now navigate back
  to Overview, scope the workspace notice, and locate the retained bar track.
  `browser-corrected-selectors.log` records all three successful reruns.

Review also corrected saved explanation verification labels, nonzero-width zero
bars, global button styles overriding chart geometry, insufficient small-text
contrast and expanded drill results appearing behind a modal. No acceptance check
was deleted or turned into a skipped test. Earlier failures are not counted as
passes. Desktop and 390/320-pixel screenshots were inspected; these functional
checks are not a sustained-load benchmark or a full accessibility certification.

## Commands

Commands ran from the repository root. The isolated test database and object-store
environment selected local ports 15433 and 19000; model credentials were loaded
privately from existing configuration, never written into reports.

```bash
python3 -m pytest tests/test_architecture.py apps/api/tests/test_saved_items_integration.py apps/api/tests/test_studies.py apps/api/tests/test_query_precision.py apps/api/tests/test_analytics_integration.py -q
npm run test:web
npm run lint:web
npm run typecheck:web
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
python3 scripts/check_browser.py analytics-home.spec.ts library-interface.spec.ts visualization-interface.spec.ts
EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py
EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py workspace.spec.ts --grep 'first file needs|create workspace, invite teammate|upload creates a dataset'
python3 scripts/check_browser.py visualization-interface.spec.ts
npm run build:web
node --check scripts/check_interface_vps.mjs
git diff --check
make production-preflight
```

The browser runner created and removed isolated PostgreSQL schemas and object
buckets. Earlier focused invocations used the visualization/library pair and
saved-library-only mobile diagnostics. Logs, screenshots and build manifests are
ignored under `data/interface-reference/`.

## Private release

The prior source is retained at
`/sdb-disk/OISOL_ExecPLUS/releases/pre-interface-20261006/source`; the prior running
web image is tagged `oisol-execplus/web:pre-interface-20261006`. Every patched
remote file matched the reviewed baseline before staging. The candidate used the
existing pinned Node build image and unchanged deployment settings. Only `web`
was recreated under the existing maintenance lock. API/jobs container identities
and images are unchanged, readiness remains 0015, and the previous verified
worker-aware backup `20261006T082942Z` remains available. There is no database
migration or change requiring a database rollback in this presentation release.

The web-only patch/hash manifest, candidate builds and activation logs are retained
privately. Final test-selector corrections and the subsequent caption cleanup are
present in candidate/deployed source. The caption cleanup was rebuilt before
activation; runtime frontend hashes match the built source.

```bash
node scripts/check_interface_vps.mjs data/vps-private/sessions.json data/vps-private/interface/eight-interface-final-20261006.json
```

The final deployed report records eight successful real guidance jobs and saved
analysis replays, unchanged source metadata and retained Support/Forecasts
navigation. Three views at 1440/390/320 pixels give 72 layout checks. The nine
screenshots contain only the approved fictional source and newly created evidence.
`eight-interface-20261006.json` retains the initial eight sign-in/source selector
timeouts (no jobs/items created). `eight-interface-corrected-20261006.json` retains
the later library visibility-selector failure after eight jobs, queries and private
items were created; those records were preserved. The final run uses combobox and
searchbox roles. Only checker selectors changed between deployed attempts.

The final eight-user report is `data/vps-private/interface/eight-interface-final-20261006.json`;
its log is `data/interface-reference/eight-vps-final.log`. The final caption/replay
probe is `data/interface-reference/deployed-caption-check.json`, with an inspected
dashboard screenshot beside it. Both release activations retained the API/jobs
containers and verified healthy readiness.

## Maintained VC report

The maintained report retains **36 Done / 13 Partial / 15 Not yet**: this interface
improves existing features and does not add competitor parity to the score. The
October 5 comparison remains historical; October 6 public interface research is a
separate review. Phase 4D/4E, commercial readiness, Phase 6 and all production gates
retain their existing boundaries.

Both Desktop DOCX filenames (`ExecPlus_VC_Feature_Report_2026-10-05.docx` and
`ExecPlus_VC_Feature_Report_2026-10-06.docx`) and the October 6 PDF were updated.
Backups are retained under
`data/reports/2026-10-06/backups/pre-interface-report-20261006T103743498516Z`.
The 64 original feature identities/statuses, styles, headers/footers, links,
competitor comparison and ten-page layout were checked; rendered pages 2, 7 and 9
were visually inspected. The preservation/hash evidence lives in
`data/reports/2026-10-06/interface-final/report-validation.json`.

```bash
PYTHONPATH=data/report-tools python3 scripts/build_feature_report.py --output data/reports/2026-10-06/interface-final/ExecPlus_VC_Feature_Report_2026-10-06.docx
libreoffice -env:UserInstallation=file:///tmp/execplus-interface-docx-final --headless --convert-to pdf --outdir /home/it-admin/OISOL/data/reports/2026-10-06/interface-final /home/it-admin/OISOL/data/reports/2026-10-06/interface-final/ExecPlus_VC_Feature_Report_2026-10-06.docx
```
