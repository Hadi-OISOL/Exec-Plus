> **File use case:** Records acceptance evidence for dashboard and conversation refinement.
> **What it does:** Retains checks, failures, exact-value/privacy boundaries and private-release recovery.

# Dashboard and conversation refinement verification — October 13

Baseline: `4efb6da` on `phase2`, clean tracked worktree at task start. Prior
scenario/onboarding integration is already in that commit. The initial binary
checkpoint is empty; private data remains untouched. No commit/push occurred here.
Read the [audit](interface-polish-gap-audit.md) and [contract](interface-polish.md).

## Local evidence

- Self-hosted Manrope includes the upstream OFL and checksum provenance. Installed
  Anthropic frontend-design and Vercel design/React skills are local tooling, not
  application dependencies. No external font request or new chart runtime is added.
- Two new frontend unit cases cover exact grouped KPIs and truthful stage collapse,
  including retries, unknown states and prototype-property names. All **19** pass.
- Existing chart browser coverage adds typography, finite animation, reduced-motion
  and early chart-control placement checks, preserving signed values, unsafe decimals,
  missingness, keyboard expansion and real server filter/drill-down.
- One new real-worker browser case proves broad goal → source-specific clarification
  → repeated uncertainty → chosen task in the same thread → exact verified total.
  All **38 distinct browser journeys** pass in 4.6 minutes with live DeepSeek.
  Prior presentation-only final run passed 37; the focused harness run passed five.
- Initial targeted backend guidance/architecture recheck: 50 pass in 21.62 seconds.
  The first harness subset passes 72 in 37.79 seconds. Final targeted run passes
  **102** in 108.67 seconds, including the narrowed measure-choice/filter-context
  guard and eleven new goal cases. Exact arithmetic remains in the existing executor.
- Ruff, mypy (156 runtime/script files), TypeScript, ESLint, optimized local and VPS
  API/web builds pass. The final candidate matches 182 selected local runtime/font/
  migration file hashes. Non-root API image with no network passes profile/clarification
  checks without optional scientific libraries.

- The full backend/architecture run passes **978** in 644.44 seconds. One subsequent
  filtered-clarification case plus final focused rechecks give **979 distinct cases**
  (eleven new). The existing python-multipart deprecation warning remains.
- Private VPS API/jobs/web release is healthy on unchanged **0017**. All 46 data-table
  hashes/counts plus migration metadata (47 entries) are identical across activation.
  Models, environment secrets, ports and production evidence are unchanged.
- Eight deployed accounts each receive metadata guidance, a focused goal question,
  execute the chosen total and then a maximum: **8/8**, 16 exact numeric answers,
  24 layouts, zero browser errors, loaded self-hosted font and unchanged existing
  source meaning in **85.161 seconds**. This is functional evidence, not sustained
  load or representative customer quality/performance acceptance.
- The eight private threads retain their goal choices and deny 56 cross-user reads.
  All 16 original answers independently reproduce exact typed receipt checksums.
  Ordinary numerical receipts retain their existing workspace-scoped policy: 224
  cross-user authorized query/replay controls pass. This repair does not make ordinary
  receipts owner-private; bounded decision-analysis receipts still are owner-private.
- Four retained profile-v1/v2 receipts replay exactly after release. Production
  preflight still fails on all eight blocked gates, as expected.

## Release and recovery

Checked pre-release backup: **20261013T121947Z**. Source/image checkpoint:
`releases/pre-polish-20261013/source`, API/web tags `pre-polish-20261013`.
The maintenance-lock activation stopped API/jobs, compared table fingerprints,
installed matching API/web images and restarted API/web/jobs with healthy readiness.
No migration or source-data edit was performed. New private turns, choices, jobs and
receipts must survive rollback; restore matching previous source/images without
restoring an older database over new work. Checked post-release backup **20261013T125517Z** preserves the new turns/choices/jobs and
receipts. Database/object checksums pass; API/jobs/storage restart with healthy
readiness. Refresh and backup timers remain active. The regenerated Desktop
DOCX/PDF preserves the original 64 feature IDs/names and ten-page layout.


## Retained failures

The first focused chart assertion compared capitalized Manrope against generated
lowercase CSS and failed; corrected case-insensitive assertion passed. One earlier
full browser run passed 36 but lost the inferred-meaning metric note during copy
reduction. Notes were restored as a disclosure, with a visible inferred/confirmed
meaning label, before both final full runs. ESLint first raced browser test-results
cleanup and then was invoked from the wrong config directory; a scoped run from
apps/web passes. An initial targeted command named a nonexistent jobs test file and
collected no cases; the corrected subset and final target pass. The first deployed
checker assumed cost was an eligible suggested measure; the current file offers
benefit instead. The second checker matched all activity sections rather than the
latest turn. Both were checker-only corrections; runtime images stayed unchanged
between deployed attempts. The receipt checker initially assumed ordinary queries
were owner-private; inspection confirmed the existing workspace-scoped contract, so
its expectation became authorized controls while thread-denial checks stayed intact.
All failed logs/reports remain retained.

The full backend run began before the final narrow measure-choice refinement; final
102-case rechecks cover that refinement, with an additional regression ensuring
filters remain in pending context. Do not describe the earlier full run as a fresh
full test of that subsequent narrow branch.

## Commands

```bash
python3 /home/it-admin/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo anthropics/skills --path skills/frontend-design
python3 /home/it-admin/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo vercel-labs/agent-skills --path skills/web-design-guidelines skills/react-best-practices
EXECPLUS_TEST_DATABASE_URL='postgresql+psycopg://execplus:execplus@localhost:55433/execplus' python3 -m pytest apps/api/tests tests -o addopts='' -q
EXECPLUS_TEST_DATABASE_URL='postgresql+psycopg://execplus:execplus@localhost:55433/execplus' python3 -m pytest apps/api/tests/test_conversation_goals.py apps/api/tests/test_partner_conversation.py apps/api/tests/test_dataset_guidance.py apps/api/tests/test_conversation_jobs.py apps/api/tests/test_intent_router_integration.py apps/api/tests/test_unified_conversation.py -o addopts='' -q
EXECPLUS_TEST_DATABASE_URL='postgresql+psycopg://execplus:execplus@localhost:55433/execplus' EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
git diff --check
make production-preflight
node data/interface-polish-20261013/live-check.mjs --run
node data/interface-polish-20261013/receipts-and-privacy.mjs
```

Web commands run in `apps/web`: `npm run typecheck`, `npx eslint src e2e tests`,
`npm test`, `npm run build`. Scoped ESLint excludes generated browser directories
that are concurrently removed/recreated by Playwright. Installed skill/raw rules and
font download provenance are in the audit/font README.

Ignored evidence directory: `data/interface-polish-20261013/`. It retains scripts,
source hashes, check/build logs, baseline and final screenshots, failures and deployed
reports. Remote commands included `sudo bash deploy/vps/backup.sh`, isolated candidate API/web
builds, the prepared `sudo bash /tmp/execplus-polish-activate-final.sh`, readiness and
timer checks. Private prepare/activation/clean-image scripts are retained alongside
the logs. The DOCX was regenerated with `PYTHONPATH=data/report-tools python3
scripts/build_feature_report.py --output /home/it-admin/Desktop/ExecPlus_VC_Feature_Report_2026-10-13.docx`
and converted with headless LibreOffice; earlier filenames were synchronized after
backups. VPS candidate/build records live under `ops/polish-20261013/`. Runtime
configuration, model choice, ports and migration **0017** remain unchanged.

## Limits

This repairs supported conversation routing/clarification and presentation. It does
not deliver arbitrary multi-step agent programs, general causality, new forecast/
optimization methods, production model evaluation or universal data understanding.
Choices never auto-confirm shared meanings or change data. Unclear/unsupported
requests and stale sources still require clarification or an explicit limitation.
All eight production gates stay blocked, broad Phase 6 stays Frozen and feature
counts remain **37 Done /16 Partial /11 Not yet**.
