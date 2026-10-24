> **File use case:** Records the requested Replica review and bounded project adoption.
> **What it does:** Identifies the pinned source, selected installation, security findings and the workflow applied to the ThoughtSpot reference task.

# Replica reference adoption — October 18

One project-local skill, `replica-recon`, is installed under
`.agents/skills/replica-recon/`. Its source is
[Jakeschincariol/replica-skill at 77c9436fb3d18c3d58169efb8caf4fe906b0dc51](https://github.com/Jakeschincariol/replica-skill/tree/77c9436fb3d18c3d58169efb8caf4fe906b0dc51).
The MIT license, Copyright (c) 2026 Jake Schincariol, is preserved beside the
installed skill and in the ignored source snapshot. The system skill installer
installed that exact revision with an explicit project destination. No global
skill directory, plugin registration, company configuration or dependency changed.
The installed skill becomes discoverable on the next turn; its instructions were
read and applied during this task.

The first clone failed because local DNS could not resolve GitHub. A later retry
succeeded after name resolution recovered; the successful checkout's exact HEAD
was verified. Neither downloaded Python helpers nor upstream tests were executed.

## Security review and installation decision

**Verdict: CAUTION for the selected, bounded development workflow.** This is a
source review and partial static scan, not a safety certification or evidence that
the entire eleven-skill pack should be activated.

SkillSpector ran with `--no-llm`. The full repository report is 54/100, HIGH,
`DO_NOT_INSTALL`, with six findings and partial coverage. A separate scan of
`replica-recon` reports 0/100, LOW, `CAUTION`, no findings and partial coverage.
The locally adapted installed folder was scanned again: 0/100, LOW, `CAUTION`,
no findings and partial coverage (`replica-installed-scan.json`).
Its installed payload is Markdown and a CSV template, plus the retained license;
there is no executable, dependency manifest or MCP server in that selected folder.
Raw reports remain in ignored
`data/agent-tools/references/intelligence/replica-skillspector.json` and
`replica-recon-scan.json`; the original full-pack warnings remain retained.

| Finding | Source inspection and decision |
| --- | --- |
| HIGH YR4, `replica-launch/listing.py:33` and `tests/test_contrast_listing.py:55` | The combination of description keys and Unicode joiners triggered a metadata-poisoning signature. Source uses those keys for app-store listing fields and joiners for emoji-length counting, with corresponding synthetic tests. These files are outside the installed skill. This inspection explains those matches; it does not validate the linter's correctness. |
| MEDIUM RP1, `replica-test/SKILL.md:48–49` and `replica-deploy/SKILL.md:32` | Unpinned `npx playwright` instructions can fetch packages. Existing project Playwright tooling already serves this task. Those skills were not installed and their commands were not run. |
| LOW EA3, `README.md:116` | “also run any” describes running an individual pack skill. It does not itself execute anything. The local scope explicitly prevents automatic chaining into unrelated workflows. |

The selected skill's public-source observation, explicit uncertainty and
reference-only screenshot rules fit the authorized work. Local instructions
preserve the established target/scope instead of repeating confirmation, use the
pinned project REA browser and separate profile, keep captures ignored, preserve
Syntelio's existing feature IDs/gates, and prevent automatic architecture,
provider, deployment or memory-write changes. The remaining ten skills stay
uninstalled. Design/test/diff instructions were read as inert workflow references.

## Actual application to the ThoughtSpot task

The following bounded mapping was supplied to the UI implementer. It is a work
contract derived from Replica's recon, design, test and diff workflows. It is not
a claim that ThoughtSpot's authenticated screens or internal backend were seen.
Root's separate REA capture ledger owns actual observations and screenshots.

| Flow | Syntelio implementation target | Observation needed before a comparison claim | Verification |
| --- | --- | --- | --- |
| F01 Ask a question and inspect the answer | Existing conversation composer, verified result and explanation hierarchy | The referenced public demonstration or authorized screen, its route/state and source URL | A synthetic question yields its exact calculation and accessible explanation; actual steps are recorded. |
| F02 Inspect evidence and return | Existing source/receipt details with visible scope and freshness | Evidence interaction observed in a public walkthrough or authorized account; otherwise mark unknown | Keyboard open/close, focus return, exact values and current permissions. |
| F03 Continue an earlier result | Existing governed follow-up and private context reference | Observed continuation behavior, including what persists between visits; backend memory design remains unknown | Current source/memory checks, ambiguous recall clarification and second-actor denial. |
| F04 Recover from an unavailable result | Existing empty, loading, error and permission states | Record only states actually observed in the reference; absent states remain unknown | Local synthetic failures, readable recovery action, no false success or disclosed private data. |

Use stable screen IDs under these flows and connect them to existing feature IDs;
do not substitute an upstream feature CSV for the canonical 64-row ledger. For
each screen record its purpose, entry route, components, states actually seen and
source. For an inferred behavior, record the evidence and confidence separately.
Reuse Syntelio's current tokens, components and original copy/assets.

Compare layouts only at matched viewport and state, using 1440×900 and 390×844
where useful, with equivalent data shape and the same selected view. Check long
content, keyboard navigation and focus alongside empty/loading/error states.
Count clicks only from an observed complete flow. Report a concrete behavior gap
or improvement; a numerical parity percentage is unsupported without a complete,
verified feature matrix. Marketing pages alone cannot establish application parity.

No ThoughtSpot account was accessed by this review, no reference asset was shipped,
and no competitor source, private endpoint, automatic crawler or model/provider
call was used. Product behavior and release acceptance remain in the main
intelligence-upgrade verification ledger.
