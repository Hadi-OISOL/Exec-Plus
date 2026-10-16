> **File use case:** Assesses the data-analysis references requested for ExecPlus.
> **What it does:** Maps useful ideas to existing tools, records a project-local skill installation and separates supported behavior from future ML work.

# Data tools: adoption review

Reviewed October 16, 2026. These repositories provide useful numerical methods,
analysis examples and development guidance. They do not supply a drop-in agent
that knows the meaning of every uploaded file. ExecPlus still needs confirmed
field meaning, authorized tools and measured evidence for each supported method.

## Sources and reproducibility

| Reference | Reviewed commit | License | Local reference |
| --- | --- | --- | --- |
| [oneDAL](https://github.com/uxlfoundation/oneDAL/tree/eeb645077424fe8534060d74a044a120384db325) | `eeb645077424fe8534060d74a044a120384db325` | Apache 2.0 | `data/agent-tools/references/uxlfoundation--oneDAL/` |
| [SQL Data Analytics Project](https://github.com/DataWithBaraa/sql-data-analytics-project/tree/b99f16a26197ff0d36131867af319238aec23dd8) | `b99f16a26197ff0d36131867af319238aec23dd8` | MIT | `data/agent-tools/references/DataWithBaraa--sql-data-analytics-project/` |
| [Medical Research Skills](https://github.com/aipoch/medical-research-skills/tree/686e09dfdb45d9fa1a08664f06bb93769b3c9d91) | `686e09dfdb45d9fa1a08664f06bb93769b3c9d91` | MIT | `data/agent-tools/references/aipoch--medical-research-skills/` |

The sources, downloaded datasets and third-party tools remain local and ignored.
No upstream data is committed to ExecPlus. The original reference licenses are
retained. The new fictional demo has its own versioned generator and independent
checks; it is not a renamed copy of the SQL project's sales data.

## What is useful now

The SQL project has a clear progression: inspect structure, inspect categories and
dates, check totals, compare groups, then investigate time and segments. Its
[change-over-time example](https://github.com/DataWithBaraa/sql-data-analytics-project/blob/b99f16a26197ff0d36131867af319238aec23dd8/03_scripts/07_change_over_time_analysis.sql)
also illustrates why displayed date labels and chronological ordering are distinct.
We use this progression to organize the [ExecPlus walkthrough](demo-data-guide.md).

| Analytical question | ExecPlus route today | Boundary |
| --- | --- | --- |
| What does this file describe? | Upload reading; **Help me understand this data**; saved definitions and optional personal memory | Qualitative explanation, not a measured result |
| Are values missing or repeated? | Profile and **Check data quality** | Consistency checks do not prove business correctness |
| What is the total or average? | Validated SUM/AVG/MIN/MAX/COUNT through DuckDB | Confirmed meanings, units and required filters govern the query |
| How do regions or categories compare? | Grouped exact queries, charts and studies | Use the intended aggregation; do not sum ratios or durations by default |
| How do observations vary by date? | Grouped date queries and descriptive studies | Observed points are not forecasts; missing periods are not filled with zero |
| Which fields move together? | Measured patterns and **Compare groups** | Coverage, exclusions and pooled/within-group distinction remain visible; no causal claim |
| Which values are unusual? | Existing MAD/IQR analysis, optionally grouped | A flag is a comparison with a baseline, not proof of an error |
| What might the next periods look like? | Explicit forecast setup over complete dated periods | Current baseline candidates and held-out errors; no general AutoML claim |
| What if I assume a change? | Explicit percentage or daily-change scenarios | Arithmetic on user assumptions, not a learned intervention effect |
| Which choices fit my limits? | Exact bounded allocation with resource limits and rules | Supplied fixed costs/additive benefits; no external action |

The SQL reference's running totals, rolling averages, year-over-year windows,
custom customer segments and customer/product reports are useful future method
specifications. They are **not all supported conversational operations today**.
Its scripts use SQL Server features and a warehouse schema. Do not paste its
initialization script or unrestricted SQL into the ExecPlus control-plane database.
A future port must use the existing validated query/method boundary, typed source
receipts and permission checks. A chart that sorts already returned groups is not
an independently implemented ranking or cohort method.

## oneDAL: a future numerical adapter, not agent memory

The reviewed [oneDAL README](https://github.com/uxlfoundation/oneDAL/blob/eeb645077424fe8534060d74a044a120384db325/README.md)
describes accelerated tabular machine-learning routines with C++/DPC++ APIs and a
Python route through the Scikit-learn extension. The tree includes regression,
decision forests, clustering, covariance and related methods. Its
[system requirements](https://github.com/uxlfoundation/oneDAL/blob/eeb645077424fe8534060d74a044a120384db325/docs/source/system-requirements.rst)
identify platform and compiler/runtime requirements for different interfaces.

ExecPlus already has exact DuckDB aggregation and pinned SciPy/NumPy relationship
statistics. Replacing those established paths would duplicate capability without
an observed benefit. oneDAL has not been built, installed into application images
or benchmarked on this workload. No speed or accuracy improvement is claimed.

A suitable future use is an optional implementation behind a bounded numerical
port, after a concrete prediction or clustering contract exists. For example,
regression requires an actual target and predictor values available when the
prediction is made. The library does not establish these business facts. A future
adapter must preserve dataset ownership, source freshness, method/engine versions,
private model artifacts, reproducible estimates and complete deletion/rebuild
boundaries. Approximate learned outputs must remain separate from exact totals.

## One general analysis skill, scoped to this project

The selected skill is
[exploratory-data-analysis](https://github.com/aipoch/medical-research-skills/blob/686e09dfdb45d9fa1a08664f06bb93769b3c9d91/scientific-skills/Data%20Analysis/exploratory-data-analysis/SKILL.md).
Its useful structure is: identify the file, inspect metadata and completeness,
separate findings from recommendations, then state suitable next analyses and
limitations. The generic CSV/XLSX guidance fits development and local fixture
review. The clinical and other domain-specific skill collections are not enabled.

The official skill-installer helper is used with this exact commit and destination
`.agents/skills/exploratory-data-analysis/`, within this checkout. This installs
coding-agent guidance; it does not register a product agent tool, expand supported
upload formats or install optional Python dependencies. The skill will be available
for subsequent project turns after client discovery. ExecPlus runtime does not
execute its bundled analyzer or arbitrary user/model-supplied Python.

The upstream skill's broad format catalog is not evidence that ExecPlus accepts
those formats. The inspected bundled analyzer reads only the first 10,000 CSV/TSV
rows with pandas; its generic analysis function has no XLSX branch despite the
reference catalog describing Excel. Its ordinary floating-point summaries do not
satisfy ExecPlus's exact-value receipt contract. Reading the first records does
not make that subset representative. ExecPlus's existing complete-population limits
and explicit coverage remain authoritative. The reviewed statistical-analysis skill
has useful assumption/effect-size guidance, but was not selected for installation:
its additional inference dependencies and methods are outside this release.

## What a useful ML extension still needs

A real prediction task should specify, in plain language, what is being predicted,
for which record or future period, when the prediction is made and how the outcome
will later be observed. Only fields available at that time may enter the model.
An example is predicting next week's daily orders from completed prior days; it is
not the same task as explaining an association between current-day orders and sales.

Before runtime adoption:

1. Define target, row meaning, units, eligible features and intended population.
2. Partition by time or entity as appropriate, and keep preprocessing and model
   selection out of the held-out test data. Prevent identifiers, future values and
   target-derived columns from leaking the answer.
3. Compare a simple baseline with the proposed method on independently held-out
   examples. Report errors, coverage, subgroup weaknesses and out-of-scope inputs.
4. Bound training/inference resources and implement immutable private artifacts,
   versioned preprocessing, current-permission checks and repeatable reopening.
5. Evaluate on representative examples before making quality claims. A deliberately
   patterned synthetic sample demonstrates a workflow, not real predictive quality.

The current retail kit has deliberate relationships and unusually clean coverage.
Training on it could produce an attractive demonstration while saying little about
real-world prediction. No learned model is trained or deployed in this release.
The existing forecast and scenario paths remain the meaningful supported options.

## Release boundary

This review supplies concrete analysis guidance, a local skill and an adoption map.
There is no new runtime ML package, connector, clinical workflow, arbitrary-code
executor or model-provider change. Personal memory affects new qualitative readings
and suggestions; it is excluded from numerical query planning and cannot supply
filters, values or units. All 64 feature IDs, **37 Done / 16 Partial / 11 Not yet**,
and the eight blocked production gates remain unchanged.
