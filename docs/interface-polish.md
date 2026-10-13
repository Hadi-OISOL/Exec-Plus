> **File use case:** Defines the refined dashboard and conversation presentation.
> **What it does:** Records typography, value rendering, motion and truthful progress contracts.

# Analytics presentation refinement — October 13

The product canvas uses self-hosted Manrope, navy navigation, cloud/white surfaces
and teal chart/action emphasis. Amber identifies negative bars/warnings; colour is
accompanied by signed values and status text. Local fonts include the upstream OFL
license and do not send browser requests to a font CDN. No chart or animation runtime
package is added. Existing lazy-loaded tools remain lazy-loaded.

Chart/dashboard controls precede the conversation. Empty chat areas use a smaller
bounded viewport; dedicated conversation/history/reconnect remain available. Discovery
profile prose and metric notes live in disclosures, with inferred/confirmed meaning
visible and data-quality/coverage limitations retained. A saved review gate cannot be
bypassed by this presentation. The upload wizard is preserved.

KPI display uses grouped decimal strings and removes insignificant trailing zeroes;
no Decimal/unsafe integer is converted to Number, rounded, abbreviated to K/M or
assigned a guessed currency. Original strings remain in titles, evidence and exact
tables. Very long KPIs span their card and use smaller type. Numerical chart labels
and table cells remain original strings; only plot coordinates are approximate.
Negative bars share the zero baseline, explicit nulls stay gaps and observed study
points do not become forecasts. Chart/table/expand/drill controls remain semantic and
keyboard accessible, with focus and current server-authorized filters intact.

Bars reveal with a finite 420ms transform; the plot fades once and interactive controls
use short named-property transitions. The busy pulse stops after three cycles but
status stays visible while the server is working. Reduced-motion disables animations,
transitions and smooth scrolling. There is no invented percentage timer, animated
business-number counter or fabricated trend.

Simple activity shows the latest status for up to four real recorded stages. Repeated
started/completed events fold into one row per stage; retries retain the latest event
status under ordered sequence numbers. No stage is manufactured because a later stage
occurred. The full event history remains behind Recorded actions and opens in Expert.
Unknown stages/statuses, including inherited object property names, cannot render model
prose. Cancellation is pending until server terminal confirmation; changing a source
only detaches the client and does not pretend server work was cancelled. No prompts,
source values or private model chain-of-thought appear in activity.

## Source-bound conversation harness

Broad requests such as “Find patterns” or “analyze my data” ask what to investigate
instead of returning a generic orientation. The question is retained with its source
revision/definitions and up to four supported choices built from accessible schema.
Explicit requests for understanding, quality or a column explanation still receive
metadata-backed guidance. A short uncertain reply keeps the original pending request;
choosing an explicit task continues in the same durable private thread.

A model-selected empty orientation for an unrecognized goal does not become a generic
answer. A calculation misrouted to overview asks which real measure to use; its choices
are bare schema names so the original operation and filters stay in planner context.
A stale source/definition invalidates pending clarification even for deterministic
quality choices. No choice approves a shared meaning, changes source data, creates a
new method or bypasses the existing validated executor. No arbitrary DAG/code runs.

Conversation threads/choices are owner-private. Ordinary numerical receipts retain
their existing workspace-scoped access policy; this change does not tighten that
separate boundary. Decision-analysis receipts remain owner-private.

Turn projections add optional `clarification.choices`; old turn evidence defaults to
no choices. Stored choices are bounded strings and replay/history remain owner-private.
No migration is required. API, jobs and web need matching candidate images, so this
release supersedes the initial frontend-only scope; models and network stay unchanged.

The request also asked to investigate agent correctness. Existing real-service tests
cover ERP column explanations and context follow-ups, exact queries, mixed citations,
private history, reconnect and cancellation. The deployed rehearsal checks guidance
versus Verified calculations on a known fictional source. This does not establish
universal understanding or a new model/reasoning engine. A reported unsupported or
ambiguous query still needs its exact reproduction and safe supported-scope handling.

Sources inspected/installed: [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design),
[Vercel agent skills](https://github.com/vercel-labs/agent-skills) and fresh
[Vercel interface guidelines](https://github.com/vercel-labs/web-interface-guidelines).
Skill tooling is outside the application and becomes automatically available next
turn. See the [pre-change audit](interface-polish-gap-audit.md) and
[verification](verification-interface-polish.md).
