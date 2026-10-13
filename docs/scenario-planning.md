> **File use case:** Explains bounded what-if comparisons and their evidence contract.
> **What it does:** Defines supported assumptions, private history and original-source replay.

# Conditional scenario comparisons

Open **Anomalies & decisions**, then choose **What-if · scenario comparison**.
Choose one confirmed numerical measure and an eligible SUM or AVG, optionally
restricted to a category population. Shared metric filters still apply. Declare
one to five distinct named alternatives and confirm the hypothetical assumptions.

Each alternative either replaces the hypothetical aggregate in its declared unit
or changes it by a declared percentage between -10,000 and 10,000. For example,
an observed total of 0.30 with a +10 percent assumption produces a conditional
0.33. It does not modify rows or imply that raising a price increases revenue.
Negative values and reductions are supported when deliberately declared.

Source records must have complete numerical measures. Empty populations, missing
measures, mixed/undeclared units and unsupported aggregations refuse execution.
Current source and confirmed meaning are checked before calculations and publication.
Three separate governed queries retain the aggregate, present-value count and
population count from the same parsed snapshot. No SQL validator rule is relaxed.

The exact table shows baseline, assumptions, conditional amounts and differences.
Percent differences divide by the absolute baseline and are unavailable when it
is zero. Percent ratios use 28 significant digits; amount calculations retain an
explicit 192-digit Decimal context. Inputs are finite, below 1e38 and at most 38
decimal places; hypothetical outputs must remain below 1e38. Returned values are
strings, preserving zeros, signs and scale. Plot coordinates are approximate.

Saved comparisons are immutable and creator-private, including from workspace
administrators and staff. Reopening reconstructs original source bytes and meanings,
replays all three typed receipts and recalculates the alternatives. A checksum alone
is insufficient. A historical comparison stays available under current permissions
and is explicitly labelled historical after source/meaning changes.

**Create successor comparison** copies explicit assumptions into a new form and
requires renewed acknowledgment. The successor retains its prior run ID and
calculates its own current baseline. Measure, aggregation, declared filters, units,
grain and selected-column meaning must remain compatible. The prior result is
never edited. Changed meanings require an independent comparison. Successor links
do not transfer permissions or borrow private baseline values.

Comparisons cannot be approved as action recommendations. No automatic refresh,
chat dispatch, spending, email or connector call is added. Multiple-driver models,
formulas, demand response, calibrated uncertainty and causal methods remain future
work; VC 57 is only partially covered by this bounded aggregate method.

## API and persistence

`POST /workspaces/{w}/datasets/{d}/uploads/{u}/decision-analysis/scenarios` accepts
name, revision/understanding IDs, metric, aggregation, governed filters, alternatives,
literal `assumptions_confirmed: true` and optional private `parent_run_id`.
Each alternative has exactly `name`, `operation` (`replace` or `percent_change`)
and string `value`. Extra fields and numerical JSON amounts are rejected.

Existing private analysis list/open endpoints return `kind=scenario_comparison`,
method `aggregate-scenarios-v1` and result version `scenario-comparison-v1`.
Evidence adds two coverage query IDs while retaining the primary query ID, source,
definition, units and request/result checksums. Existing v1 anomaly/allocation
evidence and ordinary receipt sharing contracts are unchanged.

Migration 0017 changes only the allowed analysis-kind constraint. It does not
delete or transform existing data. Downgrade refuses while any scenario exists;
preserve new saved work and prefer a forward repair rather than overwrite data.
All analysis kinds share existing limits of 50 runs per dataset/person; archival
and pagination remain future work. The private-demo production gates stay blocked.
