> **File use case:** Evidence ledger for the requested agent and dashboard enhancement.
> **What it does:** Separates observed ThoughtSpot presentation, documented behavior and ExecPlus design choices without claiming private implementation access.

# Meaning-first reference audit — October 14, 2026

The user explicitly requested REA inspection and improvements to existing data
understanding, conversational guidance and dashboard presentation. This authorizes
the enhancement slice; it does not establish competitor parity or authorize new
connectors, model providers, statistical methods or production gate changes.

## Questions and evidence

| Question | Finding | Evidence and boundary |
| --- | --- | --- |
| How is an answer presented? | The official example shows a descriptive answer title, short interpretation, optional work disclosure, query tokens, a chart card and a nearby follow-up composer. Chart/table/expand controls share the card header. | REA **A2** below: pixels in a public documentation screenshot, not an authenticated answer we generated. |
| How is a dashboard arranged? | The public example has a title and purpose sentence above consistent cards: a headline metric, category chart and compact table, with a trend below. | REA **D1**: documentation example only. |
| How does saved knowledge affect answers? | Official guidance describes applying column metadata, shared business memory, personal context and authorized external knowledge. Shared definitions remain distinct from personal preferences; context cannot grant access. | [ThoughtSpot setup guide](https://spotter-coaching.thoughtspot.com/docs/introduction.html), reviewed October 14. This is a vendor description, not verified private backend behavior. |
| How can users inspect interpretation? | Documentation describes query tokens, source selection, conversational follow-ups and explicit reset. Tokens can expose the selected measure, aggregation and grouping. | [Getting started](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-getting-started), REA **A1/A2**. The documented workflow was not run against a tenant. |
| Does memory guarantee a correct answer? | The documentation says reference questions guide intent and column use, rather than forcing a fixed response. Its troubleshooting guide acknowledges ambiguous language and probabilistic model behavior. | [Reference questions](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-reference-questions), [Troubleshooting](https://docs.thoughtspot.com/cloud/26.9.0.cl/spotter-troubleshoot). No accuracy benchmark was performed. |

## REA capture ledger

Used the existing project-only REA CLI and `data/agent-tools/browser.py` with its
separate Chrome profile. Browser navigation and scrolling were performed through
the helper/CDP and Playwright; REA only observed the resulting pages. Discovery
preceded inspection. No credentials, customer tenant, trial signup or uploaded
ExecPlus data were supplied to ThoughtSpot.

| ID | Public target and retained evidence | Result |
| --- | --- | --- |
| P1 | [Spotter product page](https://www.thoughtspot.com/product/agents/spotter); page `ev_03a997993c72f7c7e9d30961a3755fc6214da744a6d114d07f808fad04139e5b`; screenshot `ev_6fe10d583477258772c2b1ff6cb19078693a7fd4a25f344a461aaeeb34b372fd` | Public marketing page rendered; promotional modal obscured much of its product illustration. Not used as proof of application behavior. |
| A1 | [Getting started](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-getting-started); accessibility-text page `ev_6082a9867ef38c971fa22d686b01c552ea8e663a6c75a9b7d0c8dde3ebf5c803` | Public explanatory text and image labels observed. |
| A2 | Same page, scrolled to answer illustration; page `ev_92107bda835b7577f2bbdb8f7a4a5ef58cc1685bf10224b02f111ac130ba0cd8`; screenshot `ev_9a0c95206c22f26ae45703808aafc927d26a365b98bd316216fdf2b68b1419a1` | Answer layout visible at a 1440-pixel browser window. |
| D1 | [Using Liveboards and Answers](https://docs.thoughtspot.com/cloud/26.10.0.cl/liveboards); page `ev_3694733d7bcb3a7a292fe5337fbf0141df18d57c1a5a54be13da7080a48b689d`; screenshot `ev_8ef7a608143dedf1e5c0b3f1b8f9355d41795860f0a30217420eb86a70fd34fc` | Public dashboard illustration inspected. |

Full JSON and integrity-checked screenshots remain ignored locally under
`data/agent-evidence/20261014T120622461488Z`,
`20261014T120716970306Z`, `20261014T120729705673Z`,
`20261014T120811694506Z` and `20261014T120850226929Z`.
The requested accessibility capture and target inventories are under
`data/agent-tools/browser/`. They are investigation material, not application assets.

REA coverage is attach-window and origin limited. The captures do not establish
earlier network activity, private API contracts, SQL generation, retrieval quality,
model prompts, tenant permissions or calculation accuracy. The public documentation
contained an unresolved `spotter-user-interface` reference; direct web access to
that page failed, so no finding depends on it.

## ExecPlus enhancement map

These are implementation choices informed by the reference, not claims that
ThoughtSpot uses the same code or architecture.

| Existing experience | Reusable ExecPlus components | Achievable enhancement | Explicit limit |
| --- | --- | --- | --- |
| Understand my data | Governed description/column meanings, private reading notes, actor goal, `DatasetGuide`, deterministic profile | Lead with the dataset's purpose in everyday language. Group relevant fields by meaning. Clearly identify saved facts, tentative interpretation and the few unanswered details. | Do not invent measured outcomes, domain thresholds, units, row meaning or cause-and-effect. A model-generated interpretation remains fallible. |
| Use my answers | `KnowledgeService.reading_context`, intent routing, private threads and current-source checks | Reuse the current upload's authorized notes and confirmed definitions; make the context used inspectable. Ask only about material missing or conflicting details. | Notes cannot override permissions or confirmed units/required filters. Stale and other-user context must not leak. |
| What can I do next? | Existing suggestions and forecast/anomaly/scenario/allocation handoffs | Offer a small number of relevant questions and supported actions, preserving the selected measure when safe. | A forecast still needs actual dates and adequate complete periods; a season label cannot create a timeline. Decision constraints must remain explicit. |
| Answer readability | Ask panel, existing chart/table controls and source evidence | Present short meaning-first sections and put detailed source/context information in a secondary disclosure. | The disclosure contains inputs and verifiable evidence, never hidden model reasoning. Exact result strings remain unchanged. |
| Home/dashboard clarity | Analytics Home, existing studies/boards and data-source state | Put the saved purpose and current goal near the question composer. Keep cards and actions visually consistent and progressively disclose technical review forms. | Do not fabricate findings for empty states or label snapshot boards as automatically live. Existing refresh and explicit rerun rules remain authoritative. |

## Acceptance boundary

Reference inspection is complete for public presentation and documentation; tenant
execution and private internals remain unresolved and are unnecessary for this
bounded enhancement. Implementation acceptance still requires context/privacy and
staleness tests, missing-definition behavior, honest unsupported-analysis messages,
desktop/mobile browser checks and exact-result regression checks. This audit alone
does not mark implementation, deployment, model quality or any product feature as
complete. No external assets or branding should be copied into ExecPlus.
