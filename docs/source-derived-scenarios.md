> **File use case:** Defines the source-derived sales, quantity and cost scenario contract.
> **What it does:** Separates exact hypothetical arithmetic, required business declarations and observed implementation evidence.

# Source-derived scenarios

Status: **Local implementation and focused browser checks complete; not deployed.** The numerical/query module, protected API, saved replay, four export formats and step-by-step screen are implemented. New and existing scenario browser journeys pass, including widths 1440/390/320. Combined release gates and a separate private-demo release remain pending. Existing aggregate, compound-percentage and daily-change scenarios remain unchanged. No private-demo deployment or production acceptance is claimed.

## Question this method answers

“What would these recorded sales and costs become if I changed price, quantity and costs by the percentages I supply?”

This is a declared arithmetic model. It does not learn whether customers buy less when prices rise, predict future dates, decide which costs are variable, or infer whether periods overlap. The user must explicitly confirm those meanings before running it. No source rows or definitions are rewritten.

## Declared source model

The registered method is `source-unit-economics-v1`. One confirmed source supplies separate quantity, sales and variable-cost columns; an optional fourth column supplies fixed costs already allocated once per source row. All rows contribute once to the selected population. Rows must represent additive transactions or explicitly declared non-overlapping periods. Unknown grain, stock snapshots, customer-grain and survey-grain sources are refused by this model.

Two explicit interpretations are supported:

| Basis | Sales column means | Variable-cost column means | Baseline calculation |
| --- | --- | --- | --- |
| Per unit | Price per one declared quantity unit | Variable cost per that same unit | Sum each row's quantity × price and quantity × unit cost |
| Row totals | Recorded sales amount for that row's quantity | Recorded variable costs for that same quantity | Sum the recorded sales and variable-cost amounts |

The per-unit model uses individual row products. It never multiplies an unweighted average price by total quantity. The row-total model does not divide sales by quantity to invent a unit price. A row with zero quantity and nonzero sales/variable-cost totals is refused because its interpretation is incompatible with uniform unit scaling.

Quantity needs a fixed non-currency unit. Every sales/cost field needs the same confirmed currency code, without a varying unit/currency column. The user confirms that per-unit prices and costs refer to the selected quantity unit. The method does not convert currencies or infer ratios from a column name.

Every selected field must be present on every matched row. Exactly one complete projection is used, capped at 10,000 rows; the query fetches up to 10,001 so an over-limit population is refused rather than sampled. Numeric values are finite, below 1e38 in absolute value and have at most 38 decimal places. Signed records, including declared returns or credits, remain signed and show a warning.

All selected measures must have the same effective governed filters. A missing filter on one measure is not silently combined with a different measure's filter. The caller can explicitly supply a common supported population filter. Existing mandatory definitions and row/column access policies still apply before projection.

## Alternatives and sensitivity

One to five distinct named alternatives each declare four percentage changes: price, quantity, variable cost per unit and included fixed cost. Zero explicitly means unchanged. Each change is between -100% and 10,000%. Without a selected fixed-cost source column, fixed costs are omitted as zero and cannot receive a nonzero change.

Let the original totals be quantity `Q`, sales `R`, variable costs `V` and included fixed costs `F`. Let `p`, `q`, `v`, `f` be the declared change factors, each `1 + percentage/100`.

```text
conditional quantity       = Q × q
conditional sales          = R × p × q
conditional variable costs = V × v × q
conditional fixed costs    = F × f
total included costs       = conditional variable costs + conditional fixed costs
contribution               = conditional sales - conditional variable costs
remaining amount           = contribution - conditional fixed costs
margin percent             = remaining amount / conditional sales × 100
```

Quantity response is independent of the price assumption. The same row/product mix is retained. Fixed costs do not change automatically when quantity changes. Negative outcomes remain visible; no zero clipping or integer quantity rounding is applied. Margin is unavailable at zero sales. Remaining amount and margin reflect only the selected costs and are not audited net profit.

An optional sensitivity view accepts one driver and two to twenty-one explicitly supplied increasing, distinct percentages. Each point varies only that driver against the original baseline; every other change is zero. It does not vary around a selected alternative, infer an “optimal” setting or label a range as a confidence interval.

Amounts use a private 256-digit Decimal context with half-even rounding, sufficient for the bounded inputs and multiplications. Ratios use 28 significant digits. All retained amounts and differences are exact strings; plot coordinates are approximate. Source data, request assumptions and computed result remain separate.

## Saved-result integration contract

The protected route is `POST /workspaces/{w}/datasets/{d}/uploads/{u}/decision-analysis/source-scenarios`. It uses the existing private `scenario_comparison` persistence kind with the new registered method, without changing schema or the old `/scenarios` input defaults.

The input includes current revision/understanding IDs, explicit column mappings and basis, population filters, alternatives, optional sensitivity, both literal assumption confirmations and an optional private predecessor ID. It accepts no expressions, SQL, code, external target or model-generated formula.

One immutable typed query receipt retains the complete selected projection. Reopening must reconstruct original source bytes/meaning, replay the exact receipt and independently recalculate every retained result. Source and policy references, request/result checksums, method and owner must match. A changed policy prevents publication or access to an incompatible saved scope.

Successors may change declared percentages while keeping the method, source interpretation, column mapping, units, grain, effective filters and selected definitions compatible. They calculate a new baseline and never edit the old comparison. Existing aggregate methods and source-derived methods cannot silently become successors of one another. Scenario comparisons cannot be approved as action recommendations.

Exports retain every baseline/alternative measure and sensitivity point, the explicit formula assumptions, coverage and evidence. Public restricted reports must omit original source fingerprints using the shared evidence sanitizer; the private receipt remains unchanged.

## References and acceptance boundary

The price/volume/cost identities and contribution definition follow the standard accounting relationships explained in [OpenStax, contribution margin](https://openstax.org/books/principles-managerial-accounting/pages/3-1-explain-contribution-margin-and-calculate-contribution-margin-per-unit-contribution-margin-ratio-and-total-contribution-margin). The conditional comparison follows its [sensitivity-analysis discussion](https://openstax.org/books/principles-managerial-accounting/pages/3-3-perform-break-even-sensitivity-analysis-for-a-single-product-under-changing-business-situations). These are formula references; no upstream implementation or template was copied. [Forecasting: Principles and Practice, scenario forecasting](https://otexts.com/fpp3/judgmental.html#scenario-forecasting) distinguishes plausible scenario assumptions from a claim about the most likely outcome.

Local evidence: 118 distinct selected backend checks pass: 39 isolated domain/planning, 25 source-scenario integration, 17 legacy-scenario integration and 37 export-builder checks. They include hand-calculated multi-product values, twenty-five independent Fraction-oracle fixtures, row-total equivalence, high precision, zero/negative values, input/work limits, shared-population/units/grain guards, private replay, policy-revocation races, immutable successors and real PDF/Excel/CSV/PNG extraction. Browser layouts and private-demo acceptance remain pending. Initial failures and their fixes are retained in the [verification ledger](verification-source-scenarios.md). This does not close broader causal, nonlinear, probabilistic or operational decision requirements.

## A small example to try

This entirely fictional CSV has two transaction groups. Set one row to **record**,
`quantity` to a metric with unit **items**, and `sales`, `cost`, `fixed` to metrics
with currency **USD**. Confirm that the row contributions do not overlap.

```csv
region,quantity,sales,cost,fixed
North,2,10,6,3
South,3,20,8,4
```

Under **Anomalies & decisions → What-if → Price, quantity and costs**:

1. Choose **Price and variable cost per unit**. Map quantity to `quantity`, price
   to `sales`, variable cost to `cost`, and allocated fixed costs to `fixed`.
2. Declare price **10%**, quantity **20%**, variable cost **25%**, and fixed cost
   **100%**. Optionally compare price at **-10, 0, 10** percent.
3. Review and confirm the assumptions, then calculate.

The source has sales **80 USD**, variable costs **36 USD**, fixed costs **7 USD**,
and **37 USD** remaining. The declared alternative gives sales **105.6 USD**,
variable costs **54 USD**, fixed costs **14 USD**, and **37.6 USD** remaining.
The separate price sensitivity has **29 / 37 / 45 USD** remaining. These are
arithmetic checks of the invented example, not measured business effects.

The old **One measure** approach remains the default and retains its separate
private history. The source model saves its own immutable comparisons. Back keeps
form drafts; failed saves retain inputs; a successful save followed by failed
history loading still displays the saved result and requires renewed confirmation
before another run. A saved successor keeps every original filter, including
multiple predicates created through the API. Choosing a different row group
explicitly starts an independent comparison.
