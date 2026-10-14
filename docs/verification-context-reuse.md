> **File use case:** Records verification of the saved-context repair.
> **What it does:** Separates observed user symptoms, regression evidence and private release checks.

# Context reuse verification — October 14

## Observed problem

Read-only inspection of the affected confirmed agricultural upload found twenty
columns, meanings on the first ten only, three declared metric units and eight
missing units. Forecast options already used those three saved units. No date
column exists, so a time-series forecast is unsupported. The recorded conversation
was a dataset-orientation request; its deterministic response omitted the saved
description. One private data-reading note existed. No exception was observed in
the inspected API/worker logs; service restart counts were zero.

The repair does not edit the user's dataset, answers, notes or goals. Missing
business meanings and units still require the user's answer. Describing a file
cannot create historical dates or a trained irrigation prediction model.

## Implemented behavior

- Reading covers every source column. New reviews with skipped fields or unknown
  row meaning retain a draft instead of confirming an unreviewed whole schema.
- Manual reopening preserves existing answers and asks only missing meanings or
  units. A changed source revision requires review against the current columns.
- Dataset explanations use saved descriptions/field meanings. Planning receives
  the caller's private goal and up to three verified passages from accessible
  reading notes for the selected upload. Other files' notes and other people's
  private goals/notes do not enter planning. General documents retain their
  separate explicit retrieval path. Failed note verification fails safely.
- Notes are untrusted context, not instructions or confirmed measurement rules.
  Confirmed definitions, permissions, exact query validation and required filters
  retain priority. No model computes numerical answers.
- Chat and forecasts use one eligibility projection. Missing dates, missing units
  and unconfirmed meaning have separate explanations. Tool handoffs preserve an
  explicitly named measure and open forecast/anomaly/scenario/allocation setup.
  This is setup assistance, not arbitrary autonomous tool execution: complete
  periods, assumptions, budgets and resource constraints still need declarations.
- Complete saved meanings remain editable in a collapsed editor. Existing forecast,
  scenario, decision, private-history and numerical replay contracts stay intact.

## Verification ledger

- Initial targeted backend selection: 111 passed, two failed. The new generic
  document retrieval broadened planner context and exposed a storage error earlier
  than the existing evidence path. Restricting context to the current upload's
  reading notes and sanitizing verification failure restored the intended boundary.
  Thirty focused context/unified-conversation cases then passed.
- Full backend/architecture suite: **1,058 passed**. Final focused eligibility checks:
  **41 passed**, including the later changed-upload-schema and missing-unit handoff
  cases: **1,060 distinct backend passes** across these runs. Ten context cases are new.
- Initial browser selection: eight passes and one exact-label locator failure in
  the new missing-detail test. A textbox-role selector fixed it. All six reading
  journeys then passed, including twenty fields, an incomplete draft, missing-only
  resumption, chat-to-analysis measure selection and narrow layouts. Together with
  the existing two forecast journeys and analysis-extension journey, nine distinct
  browser journeys passed. The dated forecast test retains later-actual comparison
  and exact evidence replay; the undated test shows a precise unsupported state.
- Nineteen frontend unit tests, Ruff, mypy (162 files), TypeScript, ESLint and local
  production build pass. A fresh candidate VPS build and clean non-root,
  read-only/network-disabled computation checks pass.

## Private release and live evidence

Application release **d40bc6d** is deployed with API, jobs and web on unchanged
migration **0017**. The checkpoint is `pre-d40bc6d-20261014`. All 47 control-plane
table fingerprint entries and the environment-file checksum match across
activation. Checked pre-release backup `20261014T115717Z` and post-release backup
`20261014T120913Z` both pass database/object archive checksums. The latter retains
the fictional verification work; neither backup is a restore rehearsal.

The initial live twenty-column fixture (`day`, `amount`, eighteen generic factors)
received a safe profile fallback because the hosted model reply did not pass
validation. A repeat produced the same fallback. The original raw replies were
not retained, so the exact validation reason is unknown. A separate retry stopped
at a browser-test navigation error for a returning user; explicitly opening Data
library corrected the test. All failed logs/screenshots remain in the evidence
folder. Live model reading of that twenty-column fixture is **not verified**;
the local twenty-column review regression remains valid separately.

A clearer, fictional three-column daily fixture passed the live browser journey
in **44.8 seconds** with hosted `deepseek-v4-pro`: reviewed every field, saved
confirmed meanings with no remaining questions, and added a private current-upload
note defining “wetness” as the `amount` column. The real planner used that note for
“What is the average wetness?” and the deterministic calculation returned the exact
string `20.500000000000`. Chat handed the explicitly named `amount` measure to
forecast setup; after the tester declared complete daily coverage, the saved
forecast's first estimate was `41.0`. Layouts at 1440, 390 and 320 pixels passed
without page errors. This is one functional journey, not a model-quality benchmark.

A read-only check of the reported agricultural file confirms that its original
definition is preserved and still confirmed. Fifteen columns have a missing meaning
or unit, eight unit questions remain, and three metrics are eligible. Its only
forecast blocker is the missing timeline. Saved answers were not overwritten or
silently completed.

After the post-release backup, API readiness and workspace HTTP 200 pass; API,
jobs and web are running with zero recorded container restarts. Model, refresh
and backup services/timers are active. All six project listeners remain bound to
loopback. The host lacks `rg`; repeating the listener inspection with `grep`
succeeded without changing configuration.

Detailed logs and fictional artifacts are ignored under
`data/verification/2026-10-14/context-repair/`. Existing historical browser/load
rehearsals are not claimed as newly rerun. Functional fictional checks do not
establish representative prediction quality or sustained performance. Schema 0017,
providers, loopback exposure, feature status counts and production gates are unchanged.
