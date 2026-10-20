# Natural-language record counts and group comparisons

This repair addresses rejected crop-stage counts, unnecessary clarification for
“maximum soil moisture is of what?”, and follow-up questions about a selected
outcome. It uses the existing conversation planner, authorized query engine,
pattern service, private thread history and portable reports. No model provider,
runtime dependency, database schema or access boundary changes.

## Coordinated execution

The configured local selection model gives an advisory route/field hint. The
configured hosted planner receives saved meanings, the current question,
source-bound structured conversation context and a small set of relevant recorded
category labels. It proposes typed tools; the server validates and executes them.
A single bounded correction can repair an invalid count plan within the existing
model-call budget/deadline. The models never calculate the reported values.

A count of records uses `COUNT(*)`, including rows with unrelated missing cells.
An explicit count of a visible field uses `COUNT(field)` and excludes nulls. It
is not a distinct-entity count. Hidden/ignored fields and measures blocked by
hidden required-filter/unit fields remain unavailable. Existing row policies and
saved required filters remain enforced.

Questions about which record has the highest/lowest measure select rows with a
validated max/min expression. Ties are retained within the existing row limit;
nulls are not contenders. A request for the number alone remains an aggregation.
All columns, conditions and expressions pass the existing bounded SQL validator.

The registered `compare_cohort` tool compares one exact text-category value with
all other nonmissing values. The planner can choose it from ordinary language;
canonical quoted button actions work offline. Unsupported extra filters, time
windows and named second-group comparisons clarify rather than silently broadening
the population. This bounded tool does not implement arbitrary pairwise cohorts.

## Comparison evidence and limits

The method projects at most 10,000 matching rows, twelve eligible numeric measures
and three additional text categories through the existing governed pattern query.
Numeric measures need a confirmed fixed unit and compatible required filters.
Identifiers, ignored fields, ordinal codes and conflicting values are excluded.
A declared non-average calculation is never silently replaced by an average.

The output records exact group counts, per-measure nonmissing counts, means,
medians, mean differences and pooled-standard-deviation ordering, plus category
counts and shares. Means/differences use twelve decimal places; ordering scores
and shares use six. Each numeric comparison requires five present observations
per group and twenty in total. Sparse measures stay visible without fabricated
statistics. Missing target labels are counted separately, not treated as controls.

The comparison is descriptive. A stage label is not independent proof of harvest
readiness, and observed differences do not establish causes, intervention effects
or days to harvest. Crop mix, field differences and unrecorded conditions can
explain or reverse a pooled difference. There is no adjusted causal estimator or
calibrated prediction in this tool. It explains the missing information needed
for stronger conclusions and asks for recorded definitions instead of guessing.

## Saved results and presentation

One versioned private receipt retains source revisions, definitions, selected
fields, target label, required filters, exact result and checksums. Reopening
rebuilds and verifies it under current source access and existing owner rules.
A following question can reuse only the authorized structured target and current
source references; previous model prose cannot override permission or meaning.

The chat leads with counts, readable comparison cards, exact tables and explicit
limitations. Keyboard-accessible overflow preserves mobile tables. Next-question
actions are disabled while a request runs. PDF, Excel and CSV-evidence downloads
reuse authorized saved values; cohort PNG is unavailable because no supported
standalone export chart has been defined. Old saved answers remain immutable.

See [verification](verification-harvest-language-repair.md) for retained failures,
current test evidence and deployment status.
