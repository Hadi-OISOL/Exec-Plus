# Intelligence reference adoption

> **File use case:** Source and security ledger for the October 18 proactive intelligence work.
> **What it does:** Separates reviewed design guidance, proposed application adaptations, installed development tools, and unsupported third-party capabilities.

## Reviewed snapshots

All five requested repositories were cloned successfully into ignored
`data/agent-tools/references/intelligence/`. Existing references and installed skills
were preserved. Clone checkout is source inspection, not package execution. No
upstream installer, downloaded script, browser helper, market API or Trellis MCP
server was executed. No global configuration, dependency or provider changed.

| Repository | Exact source pin | License |
| --- | --- | --- |
| [AlphaGBM/skills](https://github.com/AlphaGBM/skills/tree/b625a392c83dd39f7a4735c19ca3f0e7ead851a9) | `b625a392c83dd39f7a4735c19ca3f0e7ead851a9` | MIT |
| [HadiAbbasIsDev/Trellis](https://github.com/HadiAbbasIsDev/Trellis/tree/104ee0b03d30569e9ba36971dd343e4e507a5f4a) | `104ee0b03d30569e9ba36971dd343e4e507a5f4a` | MIT |
| [VoltAgent/awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills/tree/ad6cb6c88a4859aecdcb414edeb11d3065610c6d) | `ad6cb6c88a4859aecdcb414edeb11d3065610c6d` | MIT |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/56ea9cf174ed86786187daa9de0e6247cb0747e4) | `56ea9cf174ed86786187daa9de0e6247cb0747e4` | MIT |
| [oil-oil/oil-ui](https://github.com/oil-oil/oil-ui/tree/feb1f95e8cec48bb8ba35181cb66f94f23b1b6fc) | `feb1f95e8cec48bb8ba35181cb66f94f23b1b6fc` | MIT |

Each snapshot retains its original LICENSE. Copyright holders are oil-oil (2026),
Next Level Builder (2024), VoltAgent (2026), AlphaGBM (2026), and Hadi Abbas (2026).
The OpenClaw catalogue's MIT license covers its catalogue, not every linked skill.
Any later copied code or substantial reference text must retain the relevant MIT
notice in the shipped attribution inventory. This report copies no implementation.

## Practical selection and current adoption

The small development set remains the existing project-local `ui-ux-pro-max` and
`skill-inspector`. UIUX's existing upstream pin is **identical** to the new clone;
reinstallation would add no capability. Existing local safeguards remain intact.
The installer skill was reviewed, but no additional package met the task's scope
and execution boundary. No raw third-party SKILL.md was activated merely because
its repository was requested. New skill installation count is zero.

Actual work in this slice: source pinning; static scans; source review; sharing
Oil's concrete hierarchy/viewport rules with the UI implementer; mapping Trellis
retrieval and AlphaGBM comparability rules to the backend implementer. Application
implementation and tests belong to the intelligence feature ledger; these source
reviews alone do not prove application integration or live behavior.

| Reference | Appropriate use in ExecPlus | Boundary / status |
| --- | --- | --- |
| Oil UI | Use existing tokens, one dominant action per section, evidence and state before decoration; remove nested containers/redundant borders; inspect long content, narrow screen, focus and 200% zoom. | Selected inert `references/visual-language.md` and `layout-and-viewport.md` reviewed and communicated. Original updater, promotion, media and browser scripts remain unexecuted. |
| UIUX Pro Max | Apply current local accessibility, keyboard focus, readable type and responsive guidance to actionable insight rows. | Existing reviewed skill preserved at matching upstream pin. No new Tailwind/shadcn CLI or expanded skill bundle installed. |
| Trellis | Retrieve compact relevant memory summaries under a hard budget, expand only needed bodies, distinguish superseded decisions from current ones, keep indexes disposable. | Source architecture reviewed. Adapt inside the existing authorized service; no filesystem vault or new MCP dependency. |
| AlphaGBM | Compare only matching identity/version/date/unit evidence; separate changed facts from changed wording/methods, preserve missing deltas and unresolved questions. | `alphagbm-investment-review` reviewed as an evidence-contract reference. Market workflows and runner are not installed. |
| Awesome OpenClaw | Discovery catalogue for future narrowly selected tools. | Catalogue/category links inspected only. Listed third-party skills were not fetched, scanned or approved; catalogue inclusion is not security evidence. |

## Source-specific integration map

### UI

Oil's `references/visual-language.md` starts with hierarchy and spacing, then type,
color and detail. It explicitly preserves useful existing variables/components,
keeps necessary information in dense tools, and discourages containers inside
containers. Its viewport reference requires checking long/empty content, actual
focus visibility, scroll ownership and overflow. The practical mapping is a
concise observation, its source/evidence status, and one clear exploration action;
secondary details remain available. This does not authorize hiding exact values,
uncertainty, permissions or evidence in order to look cleaner.

UIUX remains the installed search-based implementation guide, with the repository's
existing native controls and Radix Select. The new upstream checkout also contains
other CLI asset skills; they are not automatically suitable for this stack.

### Private memory

Trellis `packages/core/src/tokenize.ts` is a small, pure reuse candidate: split
camelCase and snake_case, retain the lowercase compound form, and match Unicode
letters/numbers. A Python port can support source/field-name relevance without
adding dependencies. `packages/core/src/bm25.ts` adds independently weighted
fields. If ported, retain the upstream Hadi Abbas MIT notice alongside the port.

Trellis `packages/core/src/retrieve.ts` implements BM25 seeds, bounded graph
expansion (default two hops), confidence/recency ranking, supersession redirection
and a hard item cap. `packages/mcp/src/format.ts` returns compact summaries before
body expansion and explicitly separates historical superseded nodes. Its token
estimate is characters/4, not a verified tokenizer guarantee for arbitrary text.

ExecPlus can adopt the *bounded retrieval design* using only existing
actor/workspace-private, explicitly saved memory records. Permission filtering
must happen before ranking; forgetting, revocation and source changes must remain
effective at use/publication time. Derived relevance is not numerical evidence or
user confirmation. Do not import another person's vault or promote a tentative
model inference into confirmed business meaning. No graph traversal should cross
ownership/source boundaries.

Trellis's MCP footer actively encourages automatic memory writes and its wiring
can add agent instructions/hooks. Those are unsuitable for ExecPlus's explicit
save contract. A type comment describes reconfirming timestamps on retrieval;
inspected current search/expand handlers do **not** implement such a write. Do not
claim that read-time mutation was observed. The current application should retain
its own explicit lifecycle rather than copying the tool's broad write-back policy.

### Proactive observations

AlphaGBM `skills/core/alphagbm-investment-review/references/investment-review.md`
and `scripts/review_engine.py` provide a concrete before/after comparability
contract. For ExecPlus, bind each finding to dataset/revision/meaning/receipt
identity; do not interpret a changed publication timestamp as new source data.
One directly applicable instruction is: “Separate changed evidence from changed
writing, methodology, candidate selection or timestamps.” For narrative-v2, render
observed evidence, tentative interpretation and missing-evidence follow-up as
separate fields; a formatting change is not another verified result. Retain the
AlphaGBM MIT notice for substantial adapted text/code.

Keep actual missing values distinct from zero. An observation can identify a
question worth exploring; it cannot establish cause, crop advice or a future
outcome. Existing governed calculation tools remain responsible for numbers.

The runner's local review accepts only its own versioned financial JSON workflows;
it is not a general ExecPlus dataset analyzer. Copying that runner would add
irrelevant APIs and schema assumptions. Source-level design adaptation is the
appropriate reuse, with explicit mapping in the implementation ledger.

## Security review

SkillSpector 2.12.0 ran locally with `--no-llm`. No model was called. Raw reports,
source excerpts and exact clone pins are retained under the ignored reference
folder. Static scans are risk signals, not safety certification.

| Target | Static result | Combined verdict and action |
| --- | --- | --- |
| Oil UI full snapshot | 100/100, CRITICAL, DO_NOT_INSTALL; partial coverage | **CAUTION** for inert reviewed references; do not activate the raw package. Its real updater/environment/local-state/browser surfaces are unnecessary for this task. |
| AlphaGBM investment-review | 65/100, HIGH, DO_NOT_INSTALL; all six components scanned | **CAUTION** as inert evidence-contract reference; no runner installation. The credentialed API surface is documented but unrelated to the task. |
| Existing local UIUX | Fresh rescan stopped after over two minutes without a report; incomplete. Prior completed evidence remains in `docs/project-skill-adoption.md`. | Preserve the existing scoped development installation; no blanket approval of the expanded upstream bundle. |
| Trellis | Manual source review, not a SkillSpector skill-package scan | **CAUTION** as architecture reference. Wiring/hooks, filesystem writes and broad memory-write instructions need a separate integration decision. |
| OpenClaw catalogue | Manual catalogue/license review only | **CAUTION** for discovery. Linked packages remain individually unreviewed and uninstalled. |

Oil `TT3` points at `check_update.py:111`: an environment-overridable API base flows
to a public version request. The inspected request does not send a credential;
this scanner label alone does not establish credential theft. Nevertheless,
`check_update.py` reads Oil token/config state for its update workflow, writes
user-level cache state, and can invoke the pinned Oil CLI for explicit updates.
`recommend_once.py` writes a user-level promotion marker. None are needed here.
`LP1` flags capability/declared-tool mismatches; `E2` includes an allowlisted
update environment and test fixtures. `P2` at `shoot.mjs:957` is a Unicode emoji
regex, not an observed hidden instruction. The inspected `PE3` test hits are
synthetic credential/path rejection fixtures; `OH1` hits are browser/media test
subprocesses. These explanations do not turn partial coverage into certification.
All high/critical hit contexts were retained and reviewed in
`oil-high-source-context.txt`; the package remains unactivated.

AlphaGBM `TT3` at `scripts/run.py:128` follows `ALPHAGBM_API_KEY` into the documented
Authorization header. The code checks official HTTPS origins and rejects redirects.
The separate local `review` branch reads bounded regular JSON files and loads its
bundled comparison module without an API call. The shared runner still exposes
many account-backed commands, so its `LP3` undeclared-capability warning matters:
installing this broad runner for generic analytics would be unnecessary. No key
was read or configured during review.

## Verification boundary

All five git clone commands returned success; exact HEADs and MIT notices were
read. This is not execution testing of third-party software. No market data,
private application data, live account, scheduled automation or external model
was used. Existing product acceptance counts and all production gates remain
unchanged by this reference work. UI/functionality claims require the feature's
own tests and browser evidence.
# Additional ThoughtSpot runtime observation

On 18 October, REA inspected the public `https://www.thoughtspot.com/product`
page through an isolated local Chrome profile. Evidence
`ev_d143f08eb7e1dea6afe07b68faf13b80f06c4d2ce79a82a182286d09b749a6a8`
records the DOM/accessibility structure and scope limits. A compact private capture
is under `data/verification/2026-10-18/intelligence-upgrade/thoughtspot-rea.json`.
Observed presentation progresses from search to insights and Liveboards, with
role-specific entry points. ExecPlus adapts that interaction idea through visible
findings, question entry and contextual actions using its existing authorized services.
This is public product-page evidence, not access to ThoughtSpot's private application
or backend. Marketing capability claims were not independently verified. No ThoughtSpot
code, branding, customer records or proprietary assets were imported.

