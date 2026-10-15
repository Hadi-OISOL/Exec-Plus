> **File use case:** Describes the focused workspace and bounded reading recovery.
> **What it does:** Defines the behavior delivered by the first two October 15 improvement phases.

# Focused experience and reliable reading

The [four-phase plan](clean-experience-plan.md) separates today's interface and
understanding work from the next internal analytics and quality slices. Public
reference evidence and library decisions are in the
[REA audit](clean-experience-reference-audit.md).

## One primary task

Home, conversation and review have separate work areas. Source selection and
optional findings remain available without competing with the current question.
Chat stays mounted while hidden so switching views does not abandon an active
job. Existing navigation, saved answers, patterns, forecasts, scenarios and
decision tools retain their permissions and calculation contracts.

The data reading asks one question at a time. Back retains edits. Saving progress
still requires an explicit review/save; partial answers remain a draft rather
than confirming fields the user skipped. If saving definitions succeeds but
saving notes fails (or vice versa), Retry attempts only the failed part. Source
and account changes must not reuse another source's draft.

Charts fit narrow screens while exact evidence remains available. Brief loading
and view transitions respect reduced motion. Decorative movement is finite and
never invents calculation values or completion percentages. No new runtime UI
dependency is required for this slice.

## Saved context and a bounded correction

The upload reading receives saved descriptions, roles, meanings, units, currency
and per-row unit references. Saved answers are preserved by server-owned merging,
not just a model instruction. Unsaved unit suggestions must be explicitly present
in the field name to be offered; all suggestions still require review. Missing
questions come from actual definition gaps and ignore deliberately ignored fields.

Both upload reading and chat interpretation use the shared `read_validated`
helper. A malformed, oversized, truncated or otherwise invalid reply can receive
one fresh correction, within the same forty-second deadline and existing model
and provider budgets. The rejected reply is not echoed into the correction
prompt. This covers invalid content returned by the provider; a provider that
rejects an incomplete response before returning content still uses fallback.
Provider failures and exhausted budgets do not create a retry loop.
Validation is not weakened to make a model reply pass.

Before another model call, current authorization and source context are checked
again. Cancellation waits for any active source read to finish cleanup; this can
extend elapsed wall time beyond the model deadline. Before publication, the
reading also rechecks current definitions and
revision; chat additionally verifies its private goal and authorized reading
notes. A changed source asks the user to reopen or ask again. A provider failure
or repeated invalid output uses explicit profile-based fallback, not a claimed
successful interpretation.

The reading remains qualitative and fallible. It does not compute business
answers, infer causal effects, invent units/dates or confirm shared definitions.
Governed queries and existing exact receipts still supply numerical evidence.
Historical saved replies remain immutable; ask again for an enhanced reading.

## Compatibility and remaining work

Schema stays 0017. Existing request/response shapes remain compatible; the
reading can additionally return `repaired` and a server-owned `next_question`.
Providers, model choices, network exposure, session rules and private ownership
are unchanged. The feature ledger retains all 64 IDs and 37 Done / 16 Partial /
11 Not yet. All eight production gates remain blocked.

Representative understanding quality and sustained performance still require
approved real examples and acceptance criteria. The next session's internal
analytics work is described in the plan; this release does not claim full
ThoughtSpot parity or completion of every Partial feature.
