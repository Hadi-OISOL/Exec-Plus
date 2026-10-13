> **File use case:** Explains bounded anomaly and decision analysis for users and maintainers.
> **What it does:** Defines eligibility, exact evidence, private review and future method boundaries.

# Anomalies and decisions

The October 10 private-demo extension adds **Anomalies & decisions** to workspace
navigation. Select a CSV/XLSX source, review its business meanings and fixed units,
then choose a method. This is an exploratory tool and a declared allocation model;
it is not universal anomaly detection or an autonomous business decision maker.

For a fictional walkthrough, run `python3 scripts/create_decision_demo.py` and
upload the generated files from `data/decision-demo-v1/`. Confirm PKR for `amount`
in the anomaly file. For allocation, confirm PKR for cost and a declared common
benefit unit for benefit; choose `action` as the candidate identifier, a budget
of `5.00`, quantum `0.50` and maximum quantity `2`. Under the fictional linear
assumptions, two Campaign A units have cost `5.00` and conditional benefit `10.00`.
These invented inputs are walkthrough examples, not customer performance evidence.

## Unusual values

Select one numerical measure, a threshold from 3 to 10 (default 3.5), and an optional
minimum absolute difference from the median in that measure's unit. An optional
category equality filter restricts the population. Confirmed metric filters also
apply; filters are never silently removed to enlarge a small sample.

At least eight complete numerical values and at most 1,000 distinct values are
required. The query reads the full supported snapshot and counts repeated values;
the 1,001st distinct value triggers refusal, rather than a partial analysis. Missing
or invalid values require correction or a deliberately selected eligible population.
Existing executor input, cell, memory and time budgets remain in force.

The method uses a frequency-weighted median and MAD with modified score
`0.67448975 × absolute difference / MAD`. Inclusive interpolated quartiles supply
IQR fences when MAD is zero. If both MAD and IQR are zero, values differing from
the constant central reference are flagged without a statistical score. An entirely
constant population has no findings. Threshold comparisons are strict; materiality
includes differences equal to the declared minimum. Decimal computation uses an
explicit precision budget; repeating statistical ratios are finite approximations.

Each finding represents a distinct value and its record count, not identified rows.
It can be labelled **Investigate**, **Expected**, **Data issue** or **Dismissed**, with
a note. Labels are human feedback, not confirmed truth or automatic retraining.
The score is not a probability, calibrated false-alarm rate, fraud verdict or
causal explanation. Seasonal, time-series, multivariate and drift detectors remain
future separately evaluated methods.

## Conditional allocation recommendations

Each uniquely identified source row describes one allowed candidate action with
a positive per-unit cost and nonnegative per-unit benefit. The user confirms that
costs are fixed and benefits are additive and linear, with common declared units.
Historical sales, profit or stock values must not be treated as intervention
benefits without that interpretation being justified by the operator.

Declare a budget, its numerical quantum and a default maximum integer quantity.
Optional candidate-specific minimum/maximum quantities express mandatory or
restricted choices. Budget and costs must be exact quantum multiples. Limits are
20 unique candidates, quantities 0–10, at most 5,000 budget units and a conservative
one-million-transition work bound. Unsupported problems are refused; no quantum
rounding or approximate solver silently changes the problem.

The standard-library dynamic program finds the exact optimum **within this declared
single-budget model**. Ties choose greatest benefit, then lowest cost, then lexical
candidate quantities. The result includes selected quantities, exact cost/benefit,
unused budget and a do-nothing alternative. A mandatory minimum can make do-nothing
infeasible. If minimums cannot fit the budget, the recommendation is explicitly
infeasible and cannot be approved. No constraint is relaxed automatically.

Benefits remain conditional estimates, not predicted or causal business outcomes.
Multiple resources, nonlinear effects, inventory policies, workforce rules and
causal estimates require separately validated decision modules. No model calculates
the numerical answer, and no external action is executed.

## Evidence and private review

Runs are immutable and private to their creator, including in shared workspaces.
Workspace administrators and internal staff cannot view another user's run. The
underlying analysis receipt is private too and cannot be published through the
ordinary saved-answer sharing path. There are at most 50 runs per dataset/person
and 200 review events per run; archival/pagination is a future lifecycle extension.

Every run retains source upload/revision/understanding, method version, request,
units, query receipt and checksums. Reopening reconstructs original bytes and
meaning, rebuilds the validated query, compares the complete typed execution
receipt, and recalculates the method result. Permission is required throughout.
Old forecasts, studies and ordinary query receipt contracts remain unchanged.

Recommendations support **Approve**, **Reject** and **Reopen for review** with a
mandatory note. Review events append with an expected version; concurrent edits
conflict instead of replacing history. Approval requires a feasible result and the
current revision, understanding and accepted refresh source. A subsequent source
change leaves the original approval in history but makes it ineffective for current
data. Reopen/reject remains available for historical evidence under current access.
Approval is a record only: no spending, source mutation, email or connector call.

Execution uses bounded HTTP requests, off-thread source I/O and numerical work, with
reader cleanup on cancellation. These analyses are not conversation jobs and do
not yet run automatically from refresh/alerts. Private audit records carry
identifiers/outcomes; review notes and source values stay out of general audit/logs.

## API

Let `S=/workspaces/{w}/datasets/{d}/uploads/{u}/decision-analysis` and
`R=/workspaces/{w}/datasets/{d}/decision-analysis`.

| Request | Purpose |
| --- | --- |
| `GET S/options` | Eligible fixed-unit measures and confirmed source identifiers |
| `POST S/anomalies` | Create a private immutable distribution analysis |
| `POST S/allocations` | Create a conditional allocation with explicit assumptions |
| `GET R` | List the caller's saved run metadata |
| `GET R/{id}` | Reproduce original query and analysis before returning it |
| `POST R/{id}/reviews` | Replay evidence and append an optimistic human review |

Create inputs include name, revision/understanding UUIDs and optional governed
filters. Exact numerical inputs are JSON strings. Anomaly inputs add metric,
threshold and materiality. Allocation inputs add entity/cost/benefit columns,
budget/quantum strings, maximum quantity, optional candidate bounds and literal
`assumptions_confirmed: true`. Review inputs contain target (finding ID or
`decision`), supported status, note and expected version. Decimal outputs remain
strings, including zero/sign/scale; callers must not convert them through floats.

Migration **0016** adds `analysis_runs` and `analysis_reviews` with composite
workspace/source/owner constraints. Preserve new analysis/review data before a
rollback; old images expect 0015. Prefer a forward repair over restoring an old
backup over new saved work. The private-demo release does not clear production
gates or claim sustained eight-user load, customer calibration or advanced analytics.
