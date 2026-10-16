> **File use case:** Defines the personal-memory, fictional-sample and studio-interface contracts.
> **What it does:** Records user behavior, privacy, compatibility and the limits of this enhancement.

# Personal agent and analytics studio

The [delivery plan](personal-agent-studio-plan.md) combines a reproducible demo kit,
explicit personal context and a refreshed workspace. The [reference audit](personal-agent-reference-audit.md)
records Google documentation and REA evidence. See the separate verification ledger
for actual test and deployment results; this contract does not itself prove release.

## Personal memory

**My memory** stores a role/perspective (300 characters), usual focus (500
characters) and explanation style (`concise` or `step_by_step`). Saving is explicit.
The same person can reuse these preferences across files in the same workspace.
Another workspace has separate memory. There is no automatic extraction from all
past conversations and no access to other people's memories.

Memory reaches new qualitative upload readings and chat explanations, including
their starter suggestions. It is bounded, untrusted context; current questions,
file-specific private goals and confirmed meanings take precedence. It cannot
confirm a unit, calculate a number or authorize access. It is deliberately absent
from numerical planning and its advisory selector: remembered preferences cannot
introduce new implicit query filters or change a calculation's population.

Deterministic results, original source bytes and existing saved replies are not
rewritten to match a style preference. An unavailable or invalid model may still
use the existing explicit profile-based fallback. Personalization is advisory,
not a guarantee that a model will phrase every response as requested.

The authenticated endpoints are:

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/workspaces/{workspace_id}/agent-memory` | Returns only the current actor's memory; missing memory is empty version zero. |
| PUT | Same | Accepts `expected_version`, `role`, `focus`, `explanation_style`; rejects unknown fields and conflicting versions. |
| DELETE | Same, with `expected_version` query parameter | Clears role/focus and resets style, while retaining an incremented revision. |

Migration **0018** adds `agent_memories`, keyed by workspace and user, with a
composite membership foreign key. Removing membership deletes active memory;
rejoining starts empty. Edits lock the workspace and compare versions. The user
cannot specify another actor in the payload or URL. Audit records contain only
identifiers/action metadata and are visible to their actor under the existing
private-event rules, including when another member is an administrator.

Reading checks current memory before model correction and before publication.
Private conversation evidence retains only its memory version/timestamp reference,
not the remembered text. A change or deletion during work rejects stale
publication. Old authorized replies continue to reopen with their original
content; they do not require the current memory to match a historical reference.

**Forget my memory** clears future active use. It does not rewrite old replies,
delete dataset-specific goals or erase retained backups. A tombstone revision
prevents competing stale saves. Downgrade refuses while memory rows, including
tombstones, exist, so rollback must preserve new saved work. Never restore an old
database merely to revert application code after users have saved new results.

## Demonstration data

The versioned `retail-v1` generator supplies 1,095 region-days over every day in
2025: eight numerical measures, three non-date categories, one identifier and one
date. It deliberately contains useful descriptive relationships, a pooled-versus-
within-region reversal and three unusual support-ticket counts. The separate
`actions-v1` generator supplies six hypothetical fixed-cost/additive-benefit choices.
Neither example is real customer evidence or a learned causal model.

Both use the existing authorized sample-import and definition-review flow. The
five prior sample versions retain their original bytes. Samples are not
automatically confirmed. A generator writes local CSVs, instructions and checksums
into ignored `data/demo-kit/`, refuses to replace edited artifacts and requires no
external download. Only generators, instructions and tests are committed.

The [easy walkthrough](demo-data-guide.md) supplies definitions, supported questions,
forecast coverage, scenario assumptions, allocation rules and independently checked
expected results. The real-service tests exercise exact queries, pattern and group
receipts, anomaly coverage, forecast replay, scenario arithmetic and selection
constraints. Favorable synthetic data demonstrates supported behavior without
proving representative model quality or production readiness.

## Interface and tools

The studio uses a light navigation shell, a prominent question composer, separate
source context and task cards for existing analytical workflows. Personal memory
has its own view. Sample cards start the existing import flow. Chart/table/source
controls remain attached to results; optional details do not compete with the
main task. Mobile layouts, keyboard focus and reduced-motion behavior retain
their existing contracts. Numerical strings and saved evidence are unchanged.

The dataset-summary action explicitly says **Summarize dataset insights**, because
its existing endpoint summarizes dataset insights rather than whichever analysis
card happens to be visible. This labeling change does not add a new summary method.

Missing-unit review now asks for the **unit** directly and preserves the existing
column description separately. A meaning-only answer cannot complete that question.
Skipped details remain unfinished. Confirmation uses the saved overview's actual
missing details rather than equating a confirmed version with complete definitions.
The main editor stays mounted after saving, preserving its selected field and
success feedback. If the save succeeds but the follow-up read fails, the message
distinguishes those outcomes and offers a read retry without repeating the write.

The reported four-column version-three source was inspected without editing it.
Its two missing questions contain server text, and its three saved versions all
have empty revenue/cost units. Those observations explain why confirmation alone
did not remove the questions; they do not establish what the intended units were.
The release fixes future entry and reopening, without inventing or replacing any
user definition. Existing unanswered fields still need an explicit answer.

Selected project-local design and exploration skills support development, not
runtime execution of arbitrary skills. The [data-tool review](data-tool-adoption-review.md)
records oneDAL and SQL references. The [Lieflat assessment](lieflat-charts-assessment.md)
records its noncommercial license and reference-only installation. Original SVG
improvements make labels and observed/estimated points easier to distinguish while
retaining exact values, missing-point gaps and existing evidence controls.

The agent continues to use its registered profile, query, document, pattern and
group-comparison operations. Forecasts, scenarios, anomaly checks and allocations
retain dedicated forms and explicit assumptions. Personal memory is not a plugin
loader or arbitrary code runner. This slice adds no provider, dependency, connector,
public listener or automatic external action. Broad advanced methods and all
production gates remain separate.
