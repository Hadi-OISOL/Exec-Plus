> **File use case:** Records the follow-up to the user's report that the interface still looked unchanged.
> **What it does:** Separates verified deployment from experience gaps, and tracks the Prepare data repair and its evidence.

# Prepare data experience repair

## Report and diagnosis

On October 16 the user reported that the changes still looked or worked poorly,
and asked whether Docker images had needed rebuilding. Fresh checks of their
confirmed URL, `http://localhost:18400/workspace`, show application `327ba7d`.
The web image was built at 11:18:58 and started at 11:20:59 Pakistan time. API/jobs
also use the preceding verified release. All thirteen referenced web assets load;
the served studio CSS hash matches the running container and the VPS source CSS
matches the checkout. No service listens at localhost:3000. These checks do not
establish what an already-open browser tab has retained.

A fresh browser in the existing demo account shows the new Home and My memory
menu. One confirmed gap is visible in Prepare data: the old “6. Understand your data”
heading, large raw quality paragraphs, zero-count remediation advice, schema table
and cleaning controls remain the dominant experience. Passing functional tests
and serving a new stylesheet did not establish that this screen met the user's
request. The prior completion message overstated the completeness of UI work.

The user subsequently confirms that neither My memory nor the new Overview
heading appears in their existing tab. A hard refresh and, if unchanged, a
screenshot have been requested. Their tab remains unverified; these fresh-browser
checks do not establish caching as its cause or resolve that reported mismatch.

The investigation makes no source/definition changes. Twelve settled layouts
show no page/HTTP errors or horizontal overflow. Missing-unit questions are
readable; confirmed definitions remain collapsed until the user opens them. Their
tested write flow is outside this presentation repair. Private screenshots and
network evidence stay under `data/verification/2026-10-16/ui-delivery-investigation/`
and `studio-delivery-check/`.

## Bounded repair

The profile view now shows current row/field
counts, a clear explanation/review action and concise actual file checks first.
Detailed column inspection, cleaning and revision history remain accessible in
deliberate disclosures. Exact returned values, source identity, preview-before-
apply and restore safeguards remain unchanged. The review action uses neutral
wording that also fits already-saved definitions; it does not imply that every
file needs to be explained again. No new chart library, backend
method, model provider, dependency, schema or permission is introduced.

A source review also identified a partial-refresh risk: after successful cleaning,
a failed history fetch could leave a consumed preview attached to a newer active
revision and fail to refresh dependent panels. This is a source-level finding,
not an observed user incident. A successful write now clears the consumed preview
and selections, invalidates dependent views and locks further edits until a full
profile/history reload succeeds. Both reads complete before replacing local
state. Manual reload still invalidates dependent views when recovering from other
revision changes. A focused failure-case check verifies that recovery does not
repeat the write.

File consistency does not imply correct business records, complete definitions or
forecast eligibility. Mixed row/cell check counts must not be added together and
called affected rows. The existing cleaning journey must still verify its original
score, preview, apply and restore outcomes. Backend contracts and real data remain
unchanged. The requested larger experience is not declared accepted by the user
merely because this focused repair passes.

## Verification and release

Four selected real-service browser journeys pass: cleaning/preview/apply/restore,
Prepare-to-reading reopening, confirmed-v3 unit answers and studio/sample
navigation. The cleaning journey retains 93.33→100 consistency scores and the
three→two→three row apply/restore behavior. It now simulates a successful apply
followed by a failed history GET, verifies that the consumed preview disappears,
editing stays locked until a read retry and only one apply POST occurs. Changing
mapping also invalidates the old preview. Native disclosures work by keyboard;
nine profile/preview layouts cover 1440/390/320 pixels without page overflow.

The first four-journey run passes in 28.5 seconds. Visual review then repairs a
narrow-screen score wrap and aggressive preview-cell word wrapping. A subsequent
check initially fails because its broad “Cleaning preview” locator also matches
the new keyboard-scrollable “Cleaning preview rows” region; the exact locator
passes in 13.8 seconds. This is a retained helper failure, not a product error.
These runs cover four distinct journeys, not five. All 29 frontend unit tests,
TypeScript, ESLint, five architecture checks and the final local production build
pass. The final wording adjustment was followed by a fresh production build.
The previous full backend suite is historical evidence, not a fresh rerun for
this web-only change. The restore operation shares the reviewed recovery helper;
its failed-read branch was not separately injected in the browser test.

The checked pre-release backup is `20261016T072438Z`. Database and source-object
archive checksums pass and services restart healthy. This is archive-integrity
evidence, not a restore drill. All eight production gates and the 64-item feature
statuses remain unchanged.

Web application `aded714` is built and activated; API/jobs retain `327ba7d` and
schema remains **0018**. The source/image checkpoint is
`pre-prepare-aded714-20261016`. Activation runs under the maintenance lock and
verifies unchanged API/jobs/PostgreSQL/storage container identities, image IDs,
start times and environment checksum. The new web image is
`sha256:252cd39e7eda80f6e5bc836c579f986be660c46827e4af31b3c6fddc59a33011`.
An initial readiness curl encounters the expected connection refusal while web
starts; its configured retry succeeds. This is retained in the activation log.

A read-only live browser check passes in 15.701 seconds across nine Prepare,
column and saved-meaning layouts at 1440/390/320 pixels. It verifies My memory,
the new Overview and Prepare headings, zero page/HTTP errors and no overflow.
The reported source's metadata, original bytes, profile, history and saved
definitions match their pre-release snapshots. No real definitions or source
data were written by these checks. Confirmed version three and its two genuine
missing-unit questions remain intact. Screenshots and evidence stay ignored in
`data/verification/2026-10-16/prepare-redesign/` and `prepare-repair/`.

Checked post-release backup `20261016T073434Z` preserves the current saved work;
both archive checksums pass and writers/storage restart healthy. No restore drill
was performed. Post-backup runtime checks confirm five running containers with
zero recorded restarts, ready database/storage, workspace HTTP 200, unchanged
schema 0018, six loopback listeners and active model/refresh/backup units. Preserve
all saved work if rolling back this web-only change. The user has not yet
confirmed the refreshed screen in their own tab.
