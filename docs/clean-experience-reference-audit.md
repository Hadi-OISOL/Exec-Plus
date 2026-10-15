> **File use case:** Reference evidence for the October 15 focused analytics experience.
> **What it does:** Separates observed public interfaces, documented behavior, dependency research and ExecPlus design choices.

# Clean experience reference audit — October 15, 2026

The requested scope is to make existing analysis easier to understand, reduce
crowding, improve questions and add purposeful motion. The first two delivery
phases cover interface focus and context reuse. Wider statistical methods and
external integrations retain their own acceptance requirements.

## Public interface observations

REA inspected five documentation illustrations in a separate project browser.
These are observations of public documentation, not interactions with a licensed
ThoughtSpot or Metabase tenant. The visible examples cannot establish backend
implementation, private prompts, response quality, latency or actual animation
timings. No ExecPlus source rows, credentials or sessions were sent to either site.

| Reference | Observed or documented behavior | ExecPlus adaptation |
| --- | --- | --- |
| ThoughtSpot question composer, C1 | The source selector sits beside the question input; the main question is visually prominent. | Show the selected file compactly and keep changing it a deliberate action. |
| ThoughtSpot answer, C2 | One large chart dominates the response. Chart/table and expand controls sit close to it; explanatory text and secondary actions surround the result. | Give the answer space. Keep exact values and chart controls together; reveal detailed evidence on demand. |
| ThoughtSpot edit view, C3 | The field list and full editing controls occupy a separate view with explicit completion/discard actions. | Avoid displaying source setup, full review, Home and conversation as competing primary tasks. |
| Metabase builder, C4 | Data, filtering and summary occupy separate blocks, followed by a clear visualization action. | Present analysis setup as a small sequence with an obvious next step. |
| Metabase preview, C5 | The selected step can expose a compact results preview without replacing the whole editor. | Keep optional details near their context without permanently filling the page. |

ThoughtSpot documents follow-up questions, resetting an analysis, source choice,
chart/table switching and a stop action during an active question. These support
reusing existing private threads and real job cancellation rather than adding a
separate interaction system. Its accuracy and speed descriptions are vendor
claims, not ExecPlus targets proven by this investigation.
[ThoughtSpot getting started](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-getting-started).

Metabase documents a sequence from data selection through filtering and summary
to visualization. Each step can preview its first ten result rows. This is a
design reference; ExecPlus continues using its authorized queries and existing
evidence limits. [Metabase query builder](https://www.metabase.com/docs/latest/questions/query-builder/editor).

Its visualization guide connects chart choice to the question: rows for many
categories, scatterplots for paired numerical values, and tables for records.
ExecPlus should keep a readable exact table available even when a chart is the
default. [Metabase visualization guide](https://www.metabase.com/docs/latest/questions/visualizations/visualizing-results).

The embedding documentation distinguishes loading, error and empty states. We
adopt that distinction in our own components, without adopting its embedding SDK
or paid features. [Metabase state documentation](https://www.metabase.com/docs/latest/embedding/sdk/loading-and-errors).

## REA evidence ledger

The installed project CLI is `rea@6.4.0`. `list-browser-targets` preceded capture
for each origin. Playwright performed navigation and scrolling; REA passively
inspected the resulting page and captured the visible viewport. The local helper
validated each PNG signature and SHA-256. The owned inspection browser was stopped
after capture. Existing application browsers and the VPS tunnel were untouched.

| ID | Capture folder under ignored `data/agent-evidence/` | Page evidence | Screenshot evidence |
| --- | --- | --- | --- |
| C1 | `20261015T181223080414Z` | `ev_d5c838031a443932230fa886a632a0a6e04bdb3fe23171b79c3ca0e93476b331` | `ev_211eaa5c44a1d7f9f980f7e57d696afcb08b2b6311edae62a09dc4d90b1f96c1` |
| C2 | `20261015T181234287374Z` | `ev_595d7d9537d14633ee1081f64c2de8cf6aa83e54e4841e3bbdd7d9f2f7bba897` | `ev_79e7d4a8eab8b796cd020eed8573fd20705d2a9c63cd15a4ab000720e5fa2878` |
| C3 | `20261015T181248969102Z` | `ev_4e813047563eddcaf88a0d5a59eb27979b0b27d0a702f08c48114ceba751adf5` | `ev_18c4b5bcb73d94506152fbaf4adab3c1649ffd079821f9eac4d5234e3b41c28e` |
| C4 | `20261015T181306979365Z` | `ev_d81d138ea1402fa236f0f7ac65645422516bdb7443e8714f76bc64969954959d` | `ev_1d07a7e7c2310604cab6c19e9daa24ea8748ce664871fd7b8ce6764ba87f586e` |
| C5 | `20261015T181318434732Z` | `ev_068c63bf245bda2974f605947191b3c112b28679b5fa9ba32df03d37d4f18f60` | `ev_feafb647076ee4a9a42a368794ef3d570896977f34094581abb6068d752e74b6` |

C1–C3 target the linked ThoughtSpot getting-started page. C4–C5 target the linked
Metabase query-builder page. The selected origins were only
`https://docs.thoughtspot.com` and `https://www.metabase.com`. Discovery evidence
remains in `data/agent-tools/browser/oct15-targets.json` and
`oct15-metabase-targets.json`. Coverage begins when REA attaches; prior traffic,
cookies, storage values and raw response bodies are not retained. Screenshot
coverage is limited to the visible viewport and does not prove dynamic behavior.

## Open-source review and dependency decision

Two GitHub libraries were evaluated against the existing React 19 / Next.js
application. Registry metadata was checked on October 15; versions below describe
the reviewed packages, not a promise about future releases. No global packages,
third-party service, chart engine or runtime library were installed for this audit.

| Candidate | Observed fit | Decision |
| --- | --- | --- |
| [`@radix-ui/react-dialog` 1.3.1](https://github.com/radix-ui/primitives) | MIT; published peer ranges include React and React DOM 19. The package supplies modal focus handling, Escape dismissal and return to the trigger. Its own unpacked package is 107,250 bytes; this excludes dependencies and is not a browser bundle measurement. | Preferred candidate if a new true modal needs a maintained focus-management primitive. The current design uses native disclosures and existing controls, so there is no material need to add it in this slice. |
| [`motion` 14.3.0](https://github.com/motiondivision/motion) | MIT; published peers include React and React DOM 18/19. Depends on `framer-motion` 14.3.0 and `tslib`. The package alone is 809,291 unpacked bytes, excluding those dependencies. | Keep finite CSS/SVG transitions for the present scope. Reconsider only if measured interaction needs coordinated layout/exit animation that CSS cannot maintain simply. |

Licenses: [Radix MIT text](https://github.com/radix-ui/primitives/blob/main/LICENSE),
[Motion MIT text](https://github.com/motiondivision/motion/blob/main/LICENSE.md).
If either is adopted later, retain its license notices and inspect the resolved
dependency tree. Compatible peer ranges alone are not integration tests.

The [Radix Dialog documentation](https://www.radix-ui.com/primitives/docs/components/dialog)
describes focus trapping, accessible titles/descriptions and keyboard behavior.
These remain requirements for any custom modal regardless of library choice.
The [Motion accessibility guide](https://motion.dev/docs/react-accessibility)
describes respecting the user's reduced-motion setting and replacing large
transforms with gentler transitions. The same rule applies to our CSS motion.

Public source/license/package snapshots and retrieval hashes are retained under
ignored `data/agent-evidence/2026-10-15-clean-experience/libraries/`. These are
research artifacts, not copied application source. The useful integration in this
slice is the interaction pattern; existing native browser and React facilities
already implement it without adding runtime dependencies.

## Implementation and verification obligations

These are ExecPlus choices, not claims about competitor internals:

- Keep one primary workspace task visible: Home, conversation, exploration or
  review. Maintain access to source selection and saved work through named controls.
- Put clarification beside the conversation that needs it. Reuse saved meanings
  and private goals, ask for material gaps, and preserve answers when returning.
- Give result charts space and retain units, exact values, nulls, signs and source
  controls. Do not animate number labels through invented intermediate totals.
- Use brief transitions for changing context and finite decorative loading motion.
  Real server activity supplies progress; never invent percentages or hidden work.
- Honor reduced motion, visible keyboard focus and small-screen layouts. Collapsing
  details changes presentation only; it must not change permissions or evidence.
- Test that navigation keeps private conversation state and saved results, source
  changes invalidate pending work, empty/error states remain useful, and a user can
  complete the journey at desktop and narrow mobile widths.

Actual application test results belong in the delivery verification ledger. This
research establishes design evidence and dependency choices, not deployment
acceptance, user-research results or full ThoughtSpot feature parity.
