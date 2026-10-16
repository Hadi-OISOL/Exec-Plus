> **File use case:** Records observed portable-result export checks and remaining release work.
> **What it does:** Separates file-content, permission, browser and deployment evidence without hiding failed attempts.

# Portable-result export verification

## Final private-demo release

Application `867c5a0` is deployed on schema `0020`. Combined final backend coverage,
restricted images, live API/browser acceptance, preserved data/configuration and
checked pre/post backups are recorded in the
[release ledger](verification-remaining-work-release.md). Earlier pending-deployment
statements below describe their historical checkpoints. Production acceptance
remains separate; no production gate is cleared.


Status: implementation and focused backend/browser checks complete; global checks and
private-demo release verification remain. This is not deployed acceptance evidence.

The final combined backend run passes **96 tests** in 52.795 seconds, with no failures
or skips. It covers saved-answer PDF exports, portable renderers, authorized result
exports and pure analysis-report builders. Overlapping earlier runs are not added to
this count. Five architecture checks and the current 55 frontend unit tests passed;
frontend types and lint passed after the policy-panel effect was completed. The earlier
lint failure during that parallel implementation remains in the local evidence.

Independent readers inspect actual bytes using openpyxl and spreadsheet XML,
zipfile/CSV/JSON, Pillow and pypdf. Checks preserve long decimal strings, null versus
empty text, every returned table row, formula-like text, exact source evidence and
1200-period forecast history. PDF maps contain actual image objects and all recorded
fields. PNG tests verify signed zero, actual scatter x coordinates, null line gaps and
complete metadata. Oversized or unrenderable content receives a bounded refusal.

Service checks cover private ownership, workspace membership, share revocation during
rendering, source changes during rendering and owner-private audit events. Four new
row/column-policy checks independently inspect each downloaded format: hidden field
meanings, excluded rows and original full-file fingerprints are absent, permitted exact
values remain and another person's old answer cannot be exported. Restricted evidence
contains an explicit withholding marker; internal replay receipts remain unchanged.
The first run exposed a real conversation-plan
source allowlist gap; the policy implementation now accepts its typed access references
and the four-format rerun passes.

Three existing diagram/report browser journeys pass. The new all-format journey now
passes in **16.2 seconds**, including three 1440/390/320 layouts with no page errors or
horizontal overflow, four independently inspected downloads, failed-download retry,
source preservation and a delayed Excel response during a parent display-setting
change. Its retained attempts first encountered the shared readiness migration
mismatch, then an incomplete fictional definition fixture, then an ambiguous select
label lookup. The test now uses an explicit confirmed grain and the combobox's semantic
role. The fourth attempt downloaded files successfully but expected the shorter source
spelling instead of the executed result's exact twelve-place decimal string; its
assertion now matches the recorded result. An actual download cancellation issue caused
by an unstable parent object dependency was fixed and is covered by the delayed response.

Retained evidence is in ignored
`data/verification/2026-10-16/remaining-work/exports/`. It includes the initial failures,
final combined XML/log, restricted-policy recheck, renderer checks and fictional image
previews. The signed PNG, actual data-map PDF page and small-screen controls were visually
inspected. A long-decimal axis-label overlap found in the downloaded PNG was repaired
with a wider chart gutter and value-preserving compact axis formatting; fourteen
renderer checks pass after that repair, and the regenerated artifact was inspected.
The rendering geometry still keeps the original exact metadata. Production build and
private-demo preservation checks remain due.

The final storage-boundary recheck passes **47 PDF/export tests** in 79.857 seconds,
including two new real PostgreSQL checks. A second connection obtains the workspace
row lock with `NOWAIT` during every source read and rendering call for PDF and PNG.
The checks would fail immediately if replay or rendering retained that lock. Export
services already kept external work outside their final permission transactions; no
export implementation change was needed for the related upstream locking repair.
The first recheck could not collect while the separate metering work temporarily
duplicated a schema table name; that error and the successful rerun are retained.
