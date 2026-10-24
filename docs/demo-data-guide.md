> **File use case:** Gives users a clear walkthrough for the fictional Syntelio starter kit.
> **What it does:** Defines the data, review answers, supported questions and independently checked results.

# Start here: your Syntelio demo data

Start with **Retail demo**. It is a made-up online shop with a full year of daily
records. It gives Syntelio enough information to show useful charts, find patterns,
compare groups, spot unusual values and try a forecast. Every value is fictional;
the patterns were deliberately built into this example. It is a walkthrough, not
proof that the same patterns exist in a real business.

## Open the data

1. Open Syntelio and go to **Prepare data** / the data library.
2. Choose **Explore retail demo**. This creates a separate sample dataset.
3. Review the meaning using the answers below, then explicitly confirm it.
4. Go to Home and ask **Help me understand this data**.

You can also upload `execplus-retail-daily-v1.csv` from the local `data/demo-kit/`
folder. `execplus-actions-v1.csv` is the separate decision example described below.
The imported sample and the local CSV contain identical rows. Your existing files
are not replaced. Sample imports still need your meaning review; downloading or
importing a file does not confirm its definitions.

## What to tell Syntelio

- **Business domain:** sales.
- **One row represents:** other / record. In the description, say **one complete
  day of retail operations in one fictional region**. It is not one order.
- **Description:** Fictional daily retail operations for North, Central and South
  from January 1 to December 31, 2025. Sales amounts and advertising spend use USD.
  Daily sales are after the stated discount, before returns, tax and shipping.
  These synthetic records are for learning and testing only.
- **Update behavior:** snapshot. **Sensitivity:** internal.
- **My private goal:** Help me understand sales patterns, compare regions, check
  unusual support volumes and prepare a short daily sales forecast. Explain simply.

The file has **1,095 rows**, **13 columns**, **365 consecutive dates**, **three
regions** and no missing cells. Each region has exactly one row on each date.

| Column | Role / meaning | Unit | Default calculation |
| --- | --- | --- | --- |
| `Record_ID` | Identifier for this region and date | None | Do not sum |
| `Date` | Date: completed day of operations | Calendar date; no time zone conversion | Group by day |
| `Region` | Category: North, Central or South | None | Group records |
| `Campaign` | Category: Standard or Promotion | None | Group records |
| `Week_Part` | Category: Weekday or Weekend | None | Group records |
| `Orders` | Metric: orders completed in this region and day | orders | Sum |
| `Revenue_USD` | Metric: sales after discounts, before returns, tax and shipping | USD; currency USD | Sum |
| `Ad_Spend_USD` | Metric: advertising spend in this region and day | USD; currency USD | Sum |
| `Visits` | Metric: recorded website visits | visits | Sum |
| `Returns` | Metric: returns processed that day, including older orders | returns | Sum |
| `Delivery_Hours` | Metric: average delivery duration for this region and day | hours | Average |
| `Discount_pct` | Metric: stated daily sales discount | percent, where 5 means 5% | Average |
| `Support_Tickets` | Metric: support tickets opened that day | tickets | Sum |

Choose **metric** for all eight numeric fields. Use **dimension/category** for the
three category fields and for the date field, whose detected type must remain
**date**. If a column asks for its date meaning, enter “completed day of operations”.
Set missing-value handling to “exclude missing values”; this version has none.
Leave per-row currency/unit columns and required filters empty.

In **Metric definitions**, add the calculations in the last column for the eight
metrics. For `Delivery_Hours` and `Discount_pct`, an average means an equally
weighted average of region-days. It is not an order-weighted average. Summing these
two fields would not have a useful business meaning. Do not add an order-count
definition for `Record_ID` or call the 1,095 rows 1,095 orders.

## Try these, in this order

### 1. Understand and check the numbers

Ask these short questions one at a time:

- **Help me understand this data**
- **Total Revenue_USD?**
- **Total Orders?**
- **Total Revenue_USD by Region?**
- **Average Delivery_Hours by Region?**
- **Total Revenue_USD by Date?**
- **Show records where Region is North**

This order moves from understanding the file to totals, category comparisons,
changes over dates and individual records. A record request is a bounded preview;
check its displayed row limit and coverage. A daily chart shows observed daily
totals. It is not a running total or a year-over-year calculation.

With the full file and no filters, total revenue is **8,235,156.60 USD**, total
orders are **141,464**, advertising spend is **901,678.00 USD** and visits are
**2,546,220**. These are sums of fictional source values, not model estimates.

### 2. Find patterns and compare groups

Ask **Find patterns in this data**. Orders and visits have a strong relationship
because the example was built that way. Several relationships reflect how regions
were constructed; they are not proof that advertising, discounts or another
field caused the outcome.

Then open **Compare groups** and choose:

- First measure: `Ad_Spend_USD`.
- Second measure: `Revenue_USD`.
- Category: `Region`.

The supported exact question is:

> Compare the relationship between "Ad_Spend_USD" and "Revenue_USD" within groups of "Region".

The combined relationship is negative, but the relationship inside each region is
positive. This deliberate example shows why grouping matters: regions have
different base sales volumes, sale values and advertising budgets. The approximate
Pearson scores are **−0.923299** overall, **0.779377** North, **0.840858** Central and
**0.859925** South. Each regional result covers 365 rows. Do not interpret this as
an advertising return-on-investment estimate or a recommendation to change spending.

### 3. Spot unusual values

Open **Recommendations → Unusual values**. Choose `Support_Tickets`, group by
`Region`, use threshold **3.5**, materiality **0** and minimum group size **8**.
The example deliberately includes three large values:

| Date | Region | Support tickets |
| --- | --- | ---: |
| 2025-03-15 | North | 180 |
| 2025-07-01 | Central | 240 |
| 2025-10-14 | South | 300 |

The anomaly result compares values with their regional baseline; it does not
identify a cause or certify an error. Use the records table to inspect the dates.

### 4. Try a real time-series forecast

Open **Forecasts** and use:

- Date column: `Date`; metric: `Orders`; calculation: **Sum**.
- Frequency: **Daily**; forecast length: **7 days**.
- Coverage: **2025-01-01** to **2025-12-31**.
- Confirm that this synthetic file covers every complete day in that interval.
- Expand the optional seasonal setting and enable the **7-day seasonal** candidate.

The forecast estimates the next seven days **after this file ends**: January 1–7,
2026. It is not a forecast from today's date. The chart includes held-out error
checks and heuristic ranges; a clean dataset does not guarantee a perfect forecast.
The file also supports a 30-day daily horizon. Twelve complete months are enough
only for shorter supported monthly horizons, not a twelve-month-ahead forecast.

### 5. Try a simple what-if

Open **Scenarios**. Select `Revenue_USD`, **Sum**, and create an alternative named
“Assume revenue rises 10%”, with **Percentage change: 10**. Confirm this is your
assumption. The whole-file baseline is **8,235,156.60 USD** and the assumed result
is **9,058,672.26 USD**, a difference of **823,515.66 USD**.

This changes the chosen total by your stated percentage. It does not infer that
raising advertising or a price would cause that change.

## Try the separate decision demo

Choose **Try decision demo**, or upload `execplus-actions-v1.csv`. It contains six
fictional choices. One row is one possible action. Use domain **operations**,
row meaning **record**, and describe it as a list of optional one-time actions.

| Column | Meaning | Role and unit |
| --- | --- | --- |
| `Action` | Unique action name | Identifier or category |
| `Cost_USD` | Declared cost of choosing this action once | Metric, USD, currency USD |
| `Benefit_USD` | Assumed extra contribution from choosing it once, not predicted revenue | Metric, USD, currency USD |
| `Staff_Hours` | Declared staff time needed once | Metric, hours |

Confirm those definitions. In **Recommendations → Budget allocation**, use:

- Candidate: `Action`; cost: `Cost_USD`; benefit: `Benefit_USD`.
- Budget: **1,000**; budget increment: **1**; maximum quantity per action: **1**.
- Second resource: `Staff_Hours`; available hours: **10**.
- Prerequisite: **Email campaign needs Tracking setup**.
- Exclusion: **Search ads cannot be chosen with Social ads**.
- Confirm the fixed-cost, additive-benefit assumptions.

The best allowed selection is **Tracking setup + Email campaign + Search ads**.
It uses **1,000 USD** and **9 hours**, with an assumed benefit of **160 USD**.
All 64 possible zero-or-one combinations are small enough to check exactly. The
benefits are supplied assumptions. Saving or approving the result does not run
campaigns, spend money, or predict actual uplift.

## Reproduce and verify the kit

From the project directory, run:

```bash
PYTHONPATH=apps/api/src .venv/bin/python scripts/create_demo_kit.py
```

The generated files and checksums stay in ignored `data/demo-kit/`. The generator
refuses to replace a file you edited; use `--output data/demo-kit-another-copy` if
needed. Source-controlled generators and tests preserve the version; generated
CSV datasets are not committed. Existing five sample versions retain their bytes.

These files fit the current bounds: fewer than 10,000 rows, eight numeric measures,
three non-date categories, three groups with well over twenty complete pairs,
365 consecutive daily periods and six allocation candidates. No external service,
connector, new model, invented date, automatic meaning confirmation or automatic
action is needed. The real-service regression checks exact totals, forecast
eligibility/replay, grouped directions, three anomalies, scenario arithmetic and
the rule-constrained selection. Functional success on this deliberately helpful
example is not representative model-quality or production acceptance.
