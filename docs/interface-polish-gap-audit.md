> **File use case:** Audits the October 13 dashboard and agent-presentation request.
> **What it does:** Records inspected design resources, observed gaps and acceptance before implementation.

# Dashboard and conversation polish audit

Observed branch is phase2 at 4efb6da, which already contains the earlier scenario/onboarding
integration. The initial tracked worktree is clean; the binary diff checkpoint in ignored
data/interface-polish-20261013 is empty. Preserve that baseline and all private data.
The request authorizes private-demo UI polish and investigation of agent behaviour,
not public identity, new statistical methods or model-provider replacement.

Inspected and installed through the standard skill installer: Anthropic frontend-design,
Vercel web-design-guidelines and react-best-practices. Sources:
https://github.com/anthropics/skills/tree/main/skills/frontend-design and
https://github.com/vercel-labs/agent-skills. Reviewed guidance includes keyboard/focus,
reduced motion, semantic controls, bounded lists, dynamic imports and deriving state.
Fresh Vercel rules were read from
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md.
Skills are local tooling, not dependencies or runtime agents. No downloaded script
is executed by the product. Installed Next font/use-client docs govern implementation.

Observed gaps: Arial workspace overrides the root typography; inconsistent purple/blue
and landing-page greens; tiny metadata and duplicated chart captions. Long raw KPI
values wrap awkwardly and no grouped display exists. Discovery repeats method text,
profile prose and evidence outside expandable details. The active conversation opens
an entire started/completed event log, showing each stage twice rather than a useful
summary; raw status codes/timestamps dominate the answer. Neither event list nor
animation is private model reasoning. Existing cancellation and polling are verified
contracts and must be preserved. Investigate real agent replies before claiming a
functional fix; a visual change alone cannot prove every query works.

Design: navy #16283F for navigation/text; teal #087F8C for chart/action emphasis;
slate #62748A for secondary text; cloud #F3F6FA and white #FFFFFF for canvas/surfaces;
amber #B86616 only for warnings. Manrope variable font, self-hosted with OFL license.
A chart-led analytical canvas, left-aligned headings and compact source context;
reduce duplicate prose through explicit disclosures, never remove warnings/limitations.
Avoid decorative fake trends or percent-complete timers. Motion follows user actions:
finite chart reveal, control transitions and truthful busy indicators with reduced-motion
support. No added chart runtime library or vendor dependency is needed for existing
bounded bars/observed lines.

Acceptance: exact table/source strings unchanged; grouped KPI display never converts
Decimal/unsafe integers through Number, rounds values or assumes units. Null/zero/sign
and observed line gaps remain distinct. Accessible chart expansion, drill filters and
keyboard controls work at 1440/390/320. Activity summaries derive only allowlisted
server stages; missing or failed events never become fabricated success. Simple mode
is concise, Expert retains full recorded evidence. Real guidance/calculation/follow-up,
reconnect/cancellation and no private reasoning exposure must pass browser checks.
New behaviour requires meaningful tests; full browser/static/build checks precede a
frontend-only private release with a web rollback checkpoint. All production gates stay
blocked; feature scores are not increased for a cosmetic update.

## User clarification during implementation

The user clarified that replies default to generic information and must ask relevant
follow-ups. Inspection confirms broad analysis requests are routed directly to an
orientation guide, and model-selected empty overviews can do the same. Extend the
existing bounded conversation harness: explicit goal clarification with source-bound
choices; continue the same durable thread; reject stale clarification context before
deterministic handling; never replace a requested calculation with generic metadata.
Preserve explicit requests for column explanations, quality and dataset understanding.
No arbitrary code/DAG, new model or migration is authorized by this repair. This makes
the release API/jobs plus web rather than frontend-only; retain all image/source
checkpoints and run backend/browser regression before activation.
