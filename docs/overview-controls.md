> **File use case:** Records the requested open overview and interaction repair.
> **What it does:** Defines the visible sections, accessible controls and observed release checks.

# Open overview and comfortable controls

The October 16 request removes the extra expansion step for **Charts & dashboard
controls** and **First findings from your file**. Both sections now appear directly
on Overview in Simple and Expert modes. Their charts, exact tables, filters,
exports and existing evidence controls retain their behavior. Meaning review and
the conversation remain separate views. Technical source details can still be
expanded when needed.

Simple/Expert remains a native radio group with arrow-key navigation and a visible
keyboard focus outline. A shared highlight slides between the choices over 240 ms;
changing modes preserves chart state and does not repeat calculations. The Expert
focus control appears below the mode switch so the switch stays in place.
Section entrances and dropdown transitions are finite; reduced-motion preferences
disable them.

Analysis focus uses the actual pinned **Radix Select 2.3.8** component, themed for
Syntelio, with managed focus, keyboard selection, typeahead, Escape dismissal,
selected indicators and viewport-aware positioning. Its source is the
[official Select documentation](https://www.radix-ui.com/primitives/docs/components/select).
The wrapper adds explicit labels and explanatory option text. Other form controls
retain their existing behavior. Full dependency versions, integrity values and
licenses ship in `apps/web/public/third-party/radix-select/`; the reviewed production
dependency audit reports zero vulnerabilities at this check, not a future guarantee.

## Verification and release

TypeScript, ESLint, all **59 frontend unit tests** and local/VPS production
builds pass. **Twelve distinct focused browser journeys** have passing executions
across an initial eleven passes/one failure and one corrected recheck. The initial
new test sent dependent keyboard events before Radix finished moving focus;
waiting for the actual focused option repairs the test without changing the app.
That failure is retained. Checks cover existing chart/table/filter/receipt/export
behavior, source switching, private conversation evidence and saved review gates.

The deployed browser check passes in **20.987 seconds**: six real-data layouts
(Simple and Expert at 1440/390/320), three dropdown layouts, native radio arrows,
Radix Home/End/typeahead/selection/Escape and restored focus, plus reduced motion.
Two exact KPI values, three trend rows, one category row and six findings tables
match their actual API evidence. There are no page/HTTP errors, horizontal
overflow, automatic downloads or hosted reading requests. All five selected-source
artifact hashes and private memory remain unchanged. Ordinary calculated reads
can append query receipts and usage/audit records. The first live helper run also
sent Enter before a deferred Home focus update; its failure is retained, and only
that missing focus wait changed before the passing run. Desktop controls, narrow
menus and loaded chart/findings captures received visual inspection.

Web **5c48d3c** is deployed over running API/jobs **867c5a0**, on unchanged schema
**0020**. The same UI change is retained on personal `phase2`; the backport's ancestry
is merged without changing the already matching development files. This separate
web build keeps the requested repair independent of the pending 0024 backend
release. Activation copied only web source and package manifests. API, jobs,
database and storage container IDs/images/start times and configuration match
across activation. No migration, model-provider or network-exposure change occurred.
The backup procedure separately pauses and restarts the existing writers/storage.

Checkpoint: `pre-overview-5c48d3c-20261016`. The pre-release backup
`20261016T134653Z` and post-release backup `20261016T135121Z` pass database/object
archive checksums. Final readiness/web, all five containers, model/refresh/backup
services, unchanged configuration and all six loopback listeners pass on 0020. Rollback restores only the previous web source/manifests
and image; it does not restore the database or overwrite saved work. The first
activation attempt stopped at an incorrect source-file guard before any mutation;
correcting that guard allowed the reviewed procedure to complete. The initial
web readiness probe refused a connection during startup; the bounded retry passed.

Private evidence lives under `data/verification/2026-10-16/overview-ui/` and
`overview-web/live-5c48d3c-2026-10-16T13-50-21.609Z/`. The earlier combined
backend/browser work remains separate evidence for the unfinished independent-tools
release: 2,380 backend passes and 71 browser passes/three explicit model skips
precede this UI change. The 0024 candidate is **not deployed**, and its eventual
web build must include this repair. Feature counts remain **39 Done / 16 Partial /
9 Not yet** across the original 64 IDs; all eight production gates remain blocked.
