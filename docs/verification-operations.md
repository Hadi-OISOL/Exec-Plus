> **File use case:** Records evidence for the October 6 operations priorities.
> **What it does:** Separates passing checks and measured improvements from pending release acceptance.

# Operations slice verification

**Status:** Complete for the approved local/test and private-demo operations slice.
Migration 0015 is deployed, regression and eight-user checks pass, and the checked
post-release backup is retained. The final report artifact is recorded below.

Scope: internal staff admin console, private customer-support workflow, product
usage/activation/cohort reporting and measured reporting/frontend optimization.
See [the preimplementation audit](operations-gap-audit.md) and
[contracts](operations-console-support.md). Phase 5 remains In progress for this
bounded slice; its commercial/production acceptance criteria are not complete.

## Local checks

- Ten pure reporting cases pass: UTC/year boundaries, mature/null/zero cohorts,
  valid windows and empty observations. Eleven real PostgreSQL reporting/HTTP cases
  verify tenant/role scoping, historical versus current membership, exclusion of
  automated activity, bounded projections, compatible onboarding, revocation,
  statement-consistent snapshots and exact large-integer wire values.
- Support/admin integration and persistence tests cover grants, revocation, private
  request ownership, conflict handling, lifecycle, diagnostic ownership and fixed
  metadata, audit rollback, UUID/literal search and migration preservation.
- The final full backend/architecture suite passes **869 cases** (53 new), with
  one warning hidden by the repository's existing pytest configuration, in 482.34
  seconds. The earlier pre-snapshot run passed 866 cases. An intervening retry used
  a stale application database port instead of the test endpoint; it was interrupted
  after connection-refused fixture errors and preserved separately.
- Ruff and full mypy over 148 source files, TypeScript, ESLint, nine frontend tests
  and the production build pass. All 24 real-service browser journeys pass, including
  live model chat, prior forecasts/jobs and four new operations cases. The Next.js
  file-purpose header is restored.
- The clean non-root candidate image passes API/CLI imports and eight concurrent
  exact/calendar/forecast computations (32 query IDs), without optional scientific
  libraries or network access.

## Measured reporting optimization

`scripts/benchmark_operations.py` creates a disposable PostgreSQL schema with
fictional records, migrates it, compares independent legacy/new computations and
cleans it up. The final large fixture contains 100,000 audit and 100,000 usage
events plus 25,000 of each for another tenant, twenty datasets and 200 uploads per
tenant, fifty historical people, 48 current members and fourteen weeks of history.

Seven warm repetitions on the local environment produced:

| Measure | Before | After |
| --- | ---: | ---: |
| Manager overview median | 1,934.907 ms | 241.882 ms |
| Manager overview returned SQL rows | 200,269 | 44 |
| Separate Python allocation peak | 148,365,675 bytes | 29,605 bytes |
| Resource totals projection median | 10.542 ms | 0.970 ms |
| Resource totals SQL queries | 26 | 1 |

Manager/member overviews and resource totals match the independent legacy reference.
The final product report matches a separate cohort reference: 225.424 ms median,
229.292 ms p95, one aggregate SQL statement and one transferred JSON row containing
bounded report arrays. Eight concurrent repository calls pass with 535.484 ms p95
and 545.222 ms total wall time. The final measurement includes the single-statement
snapshot improvement; the preceding multi-statement report is preserved separately.
The smaller 20,000-event fixture passes separately. Plans show broad workspace scans
on a workload where the selected tenant owns most rows; no unproven index was added.

These are local warm repository calls with fixed method order on a shared host.
They exclude browser, HTTP/authentication and network overhead. Python allocations
exclude PostgreSQL/native memory. The totals projection excludes the compatible
legacy usage-event list. This establishes the measured improvement on these fixtures,
not a general speed guarantee, sustained VPS load or representative alpha capacity.
Reports remain ignored under `data/operations-evaluation/`.

## Frontend evidence

Four new browser journeys pass within the full 24-case real-service suite, covering support lifecycle,
version conflicts, explicit staff grants/revocation, protected API envelope checks,
private-owner access, usage/cohort definitions, session-expiry/account-switch cleanup,
revoked-access cleanup and 320/390/1280-pixel layouts.
The initial ID-search failure was fixed with exact UUID lookup alongside literal
name/subject search. The first full run had 23 passes and one test-harness route
cleanup failure; waiting for the held response before unregistering the route fixed
that race. Failed runs and corrected API-envelope assertions remain retained.

A production build reduced initial referenced JavaScript from 734,931 to 659,486
raw bytes and from 216,432 to 199,900 gzip bytes (7.64% lower), with nine scripts
in both builds. This is a byte comparison, not a measured page-latency improvement.
Optional views load on demand. Invitations load only when Team opens; the new staff
access check remains an intentional sign-in request, so no blanket reduction in
all sign-in requests is claimed. Final session-expiry and revoked-access cleanup passed the full browser suite;
the final production build, nine frontend tests, TypeScript and ESLint pass.

## Private VPS release

The existing remote source matched the preceding Phase 4C release before mutation.
The source checkpoint is `releases/pre-operations-20261006/source`, API/web rollback
tags are `pre-operations-20261006`, and checked pre-release backup is
`20261006T080234Z`. Candidate images were built separately and clean-tested before
promoting them. Activation held the shared maintenance lock and stopped API/jobs.

Migration 0015 preserved hashes/counts for **all 40 existing data tables** and added
`staff_grants`, `staff_audit`, `support_tickets` and `support_events`. API readiness,
web HTTP 200 and the jobs container pass after restart. Only the existing demo owner
received an explicit internal admin grant; the other seven accounts remain ordinary
users. No model setting, network exposure or production gate changed.

Post-deployment compatibility passes six checks: four October 4 receipts (two
profile-v1 and two profile-v2) match independent typed result checksums, and an
existing Phase 4C forecast/comparison reopen with identical metadata/evidence/result
hashes. All return HTTP 200.

The deployed rehearsal passes **8/8 browsers** in 114.171 seconds with no failed
attempt. Eight fictional requests complete staff assignment/triage, replies,
escalation and resolution, then requester reopening/reply and saved-history reload.
All 56 timeline events are retained; sixteen requester report windows and eight
staff aggregate reports pass. The staff directory UI passes, and 36 precise access
denials have 36 successful authorized controls. Staff access does not unlock the
other seven workspaces' datasets/profiles. Forty-eight screenshots cover usage and
support at 1440/390/320 pixels. This is a short functional rehearsal, not sustained
load, paid-customer retention or production security acceptance.

Post-release backup **20261006T082942Z** stopped API/jobs before storage, verified
both database and object-archive checksums, restarted all services and passed API
readiness. Refresh and backup timers remain active. It is an on-server demo backup;
it does not close off-server recovery/production restore gates. Previous images
expect 0014: preserve new staff/support metadata and plan compatibility before any
rollback. All changes remain uncommitted on `phase2`; this work did not push/merge.

Private evidence remains under `data/vps-private/operations/`; local browser and
bundle evidence under `data/operations/`; benchmark outputs under
`data/operations-evaluation/`. Generated data, session credentials and logs remain
ignored. The source/image checkpoint retains the prior release.

## Report upkeep

The original report was first backed up and updated for verified Phase 4C (32 Done /
15 Partial / 17 Not yet). After operations acceptance the final report now records
**36 Done / 13 Partial / 15 Not yet** across the same 64 original feature lines.
Rows 26, 48, 49 and 51 are Done for their stated private-demo scope. Row 50 stays
Partial: measured optimization is delivered, representative broader acceptance is not.

Both Desktop DOCX copies (`ExecPlus_VC_Feature_Report_2026-10-05.docx` and
`ExecPlus_VC_Feature_Report_2026-10-06.docx`) are updated; the October 6 PDF matches.
The original names/order, styles, header, 87 paragraphs, ten tables and ten-page
layout are preserved. Cover, commercial-readiness and evidence pages were visually
inspected. The competitor table/links retain their original **October 5** research
date; they were not re-researched during this coding slice. The prior report copies
and audit are retained under `data/reports/2026-10-06/backups/`, with final hashes and
structural checks in `data/reports/2026-10-06/report-validation.json`.

`docs/product-feature-audit.json` and `scripts/build_feature_report.py` retain the
reproducible status/evidence source. Generated reports/tooling remain ignored and
outside application dependencies. The handoff now requires report upkeep after each
verified delivery; statuses must reflect tested scope rather than feature intentions.

## Remaining gaps

All acceptance checks for this bounded private-demo slice pass. General performance
completion still requires representative alpha workloads, sustained service budgets
and wider upload/dashboard/export measurements. Paid-plan administration, billing,
external help desks/email, production staff/support privacy/access procedures,
public identity, off-server recovery and all eight production evidence gates remain
open. The production checker returns the expected exit 1; no gate was cleared.
Phase 4D exports and 4E connectors remain unfinished; Phase 6 remains Frozen.

## Reproducible commands

Local integration/browser commands use the disposable test PostgreSQL/MinIO
endpoints; credentials shown here are the committed local fixture defaults.
Live browser model credentials come from ignored configuration and are not printed.

```bash
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus \
EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 -m pytest
EXECPLUS_BROWSER_LIVE_MODEL=1 \
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus \
EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=http://localhost:19000 python3 scripts/check_browser.py
npm run lint:web
npm run typecheck:web
npm run test:web
npm run build:web
node --check scripts/check_operations_vps.mjs
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:15433/execplus \
python3 scripts/benchmark_operations.py --events 100000 --repetitions 7 \
  --output data/operations-evaluation/reporting-100000-final-20261006.json
make production-preflight
node scripts/check_operations_vps.mjs data/vps-private/sessions.json \
  data/vps-private/operations/eight-operations-20261006.json
python3 data/vps-private/operations/check_compatibility.py --run \
  --output data/vps-private/operations/compatibility-20261006.json
PYTHONPATH=data/report-tools python3 scripts/build_feature_report.py \
  --output /home/it-admin/Desktop/ExecPlus_VC_Feature_Report_2026-10-06.docx
git diff --check
```

The first full backend attempt was stopped after 180 passing cases when search
regressions required a fresh suite; the later pre-snapshot run passed 866 cases.
Do not add overlapping targeted and full-run counts together. Private logs retain
all attempts, including failures and interrupted environment mistakes.

VPS operations used the existing restricted SSH control connection. The isolated
candidate builder and maintenance-locked activation script are retained privately
as `data/vps-private/operations/build-candidate.sh` and `deploy-candidate.sh`.
The checked backup command was
`sudo -n bash /sdb-disk/OISOL_ExecPLUS/source/deploy/vps/backup.sh`. Granting staff used the operator
CLI `python -m execplus.manage grant-staff --email <existing-demo-owner> --role admin`;
no credentials were included in report artifacts. See the runbook for operator use.
