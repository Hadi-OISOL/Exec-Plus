> **File use case:** Records reproducible acceptance for approved PostgreSQL imports.
> **What it does:** Separates actual fixture evidence, initial failures and undeployed external setup.

# PostgreSQL source acceptance

Status: the bounded source-import slice passes local acceptance on migration 0023 (working-tree head also
includes the independently developed 0024). Nothing in this report establishes a
customer connection, production TLS acceptance or a VPS source-import deployment.

The adapter reads a separate disposable PostgreSQL database through a dedicated
SELECT-only role. Its test table is not the Syntelio metadata database. Fixtures
verify exact decimal/UTC values, source preservation, a concurrent commit inside
repeatable-read extraction, quoted identifiers, schema changes, unsafe roles,
types, empty text, complete-row/byte/cell limits and content-free failures.
The actual source role cannot delete its rows. Control-plane and non-test loopback
endpoints are refused; a separate regression proves the test switch cannot remove
the control-plane denial. Secret fixtures include invalid permissions, symlinks
and FIFOs. The database and role are removed after each fixture.

The lifecycle tests use real local PostgreSQL metadata and object storage. They
cover exact retained uploads, unconfirmed meanings, same-request idempotency,
one-extraction concurrency, actor-private history, source/policy/member changes
during extraction or object write, operator recovery and capacity, whole-transaction
rollback, uncertain commit recovery and explicit staged-refresh activation.
Extraction proves a second connection can acquire the workspace lock with
`FOR UPDATE NOWAIT`; external work is outside that lock. The final private callback
publishes source history together with the retained upload/candidate. Migration
tests compare every pre-0023 table and refuse lossy source/history downgrade.

The combined source suite passed **83 tests** in 22.683 seconds. The final adapter
deadline recheck passed **27 tests** in 8.805 seconds, including two new shared-time
budget cases, giving **85 distinct source tests** with passing executions. The
existing upload, refresh, lock-boundary, business-meaning and architecture suite
passed **124 tests** in 107.244 seconds. Focused Ruff/mypy passed. Counts overlap
where stated; these are not a new complete-project run.

Private evidence is under `data/verification/2026-10-16/dataset-access/`:
`source-combined-final.log/xml`, `source-deadline-final.log/xml`,
`source-legacy-compatibility.log/xml`. The first compatibility commands named the
architecture test incorrectly and collected no tests; their logs remain retained.
An initial Ruff line-length issue and an unsupported ESLint command option were
corrected before the passing focused static checks.

The real browser journey uses the same adapter against another disposable source.
The initial attempt stopped on an implicit-select `getByLabel` locator despite
the correct accessible combobox being rendered. The next execution saved an
actual import and proved lost-response retry created exactly one attempt, then
stopped because the test used `/download` instead of the existing `/content`
route. These were harness failures; neither caused a product change. The logs
and the retained second failure snapshot are under
`data/verification/2026-10-16/remaining-work/sources-browser-*`.

The complete browser journey then passed in **16.4 seconds** (22.8-second runner).
A final field-choice review added guards for removed approved fields and explicitly
empty drafts; the expanded journey passed in **15.6 seconds** (21.5-second runner).
It verifies no automatic import, exact retained decimal strings, one saved attempt
after a deliberately lost response, unchanged remote rows and original local
bytes, unconfirmed initial meaning, a three-row staged update, explicit activation,
approved-field changes, retained empty choices and disconnect without data loss.
The old upload stays byte-identical. All three 1440/390/320 layouts fit without
horizontal overflow, buttons meet the 44-pixel minimum and there are no page errors.
The 1440/320 screenshots were visually inspected for readable labels/status and
clear action order. The existing offline qualitative-reading fallback appears in
the log because model calls are disabled; it is not counted as a successful model
reading. Final web types/lint and ten focused backend mypy modules pass.

Passing browser evidence: `sources-browser-final.log`,
`sources-browser-draft-recheck.log` and `sources-browser/sources-{1440,390,320}.png`
under `data/verification/2026-10-16/remaining-work/`. Independent source review
found no remaining material confidentiality/publication blocker; its time-budget
observation led to the shared remaining-time checks above. This is bounded
functional evidence, not a sustained-load or independent production security audit.

The local test-only switch and temporary credential directory are created by the
existing disposable browser runner. No real credential is added to Git or the UI.
Deployment, checked backup, actual configured external TLS source acceptance and
broader Sheets/BigQuery/accounting adapters remain separate work.
