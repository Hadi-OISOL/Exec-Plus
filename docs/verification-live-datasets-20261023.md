> **File use case:** Verification record for the third live multi-dataset run, on release 93d29ec6abe39458.
> **What it does:** Grades 81 live answers (plus clicked choices) and compares them with the two earlier runs.

# Live multi-dataset verification — release 93d29ec6abe39458 (schema 0030), 2026-10-23

Same 12 seeded fictional datasets (fresh uploads) and 81 questions as runs 1 and 2. One new fictional account, hosted DeepSeek, private VPS through the existing forward; the account was disabled afterwards. When a reply offered clickable choices, the first one was sent in the same thread, as the web does (9 clicks), and graded with the question. Numbers were checked against pandas on the same files; no executed number disagreed.

| Run | Release | PASS | PARTIAL | FAIL |
|---|---|---|---|---|
| 1 | a5d380f2541ef5bd | 36 | 16 | 29 |
| 2 | f590a4a813287580 | 48 | 22 | 11 |
| 3 | 93d29ec6abe39458 | 54 | 19 | 8 |

Run 3 vs run 2: 8 better, 1 worse. Latency median 9.2 s, max 22.7 s. Jobs not succeeded: 3 (messy-file N/A, D25).

## Per dataset (PASS/PARTIAL/FAIL)

| Dataset | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| retail_sales | 3/2/4 | 6/2/1 | 7/1/1 |
| finance_ledger | 5/0/2 | 5/2/0 | 5/2/0 |
| hr_employees | 5/1/2 | 6/2/0 | 7/1/0 |
| clinic_visits | 4/2/1 | 7/0/0 | 7/0/0 |
| iot_sensors | 2/2/3 | 2/3/2 | 3/3/1 |
| customer_survey | 3/1/2 | 3/2/1 | 4/1/1 |
| inventory | 3/1/2 | 3/2/1 | 4/1/1 |
| marketing_funnel | 2/1/3 | 2/4/0 | 2/4/0 |
| messy_store_sales | 0/1/5 | 1/1/4 | 1/1/4 |
| restaurant_daily | 3/1/3 | 5/1/1 | 5/2/0 |
| urdu_sales | 3/3/0 | 5/1/0 | 6/0/0 |
| wide_plants | 3/1/2 | 3/2/1 | 3/3/0 |

## Changes since run 2

- #7 retail_sales: "What should I do to grow sales?" PARTIAL → PASS — Five data-grounded next steps (cross-checked figures) with five clickable questions
- #23 hr_employees: "what should HR focus on?" PARTIAL → PASS — Five grounded next steps with clickable questions
- #34 iot_sensors: "Show daily average temperature trend" FAIL → PASS — Timestamp now a date-time: 30 daily averages, first 22.8489/22.9167/22.8597 match pandas
- #42 customer_survey: "which channel should we fix first?" PARTIAL → PASS — Clickable 'Which channel has the lowest average nps_score?' -> Store 4.75 first, exact
- #45 inventory: "Total inventory value by warehouse" FAIL → PASS — SUM(on_hand_units * unit_cost_pkr) by warehouse: 25,430,835.65 / 24,543,724.97 / 25,333,392.65 exact
- #64 restaurant_daily: "Do weekends get more orders than weekdays?" FAIL → PARTIAL — Weekday/weekend grouping works and is exact (26,518 vs 14,056) but uses SUM, so it implies weekdays get more; per-day averages are 101.6 vs 135.15
- #74 urdu_sales: "batao kya karna chahiye?" PARTIAL → PASS — Grounded next steps in English with Urdu field names, clickable questions
- #80 wide_plants: "Which metrics have the most defects?" FAIL → PARTIAL — Friendly message + clickable working questions (metric_01_defects 2,979 exact); cross-column ranking still unsupported
- #48 inventory: "What should I reorder first?" PARTIAL → FAIL — REGRESSION (model variance): ranks by days since last sale (stale stock), not low stock vs reorder point

## All questions

| # | Dataset | Question | Run 1 | Run 2 | Run 3 | Clicked choice | Defect | Note |
|---|---|---|---|---|---|---|---|---|
| 0 | retail_sales | What is the total revenue? | PASS | PASS | PASS |  |  | 2,266,798.06 exact |
| 1 | retail_sales | Top 3 products by total revenue | PASS | PASS | PASS |  |  | Exact; Laptop named |
| 2 | retail_sales | (+) and which region sells the most laptops? | FAIL | FAIL | FAIL |  | D6 | Still 'changed an earlier condition', no choices (true West 301 units / 272,264.56) |
| 3 | retail_sales | Show the monthly revenue trend | FAIL | PASS | PASS |  |  | 12 months exact |
| 4 | retail_sales | Compare revenue in North vs South | FAIL | PASS | PASS |  |  | Correction ran; North 611,773.62 vs South 540,241.49 exact |
| 5 | retail_sales | Are there any unusual orders? | FAIL | PASS | PASS |  |  | Opens unusual-values scan |
| 6 | retail_sales | Forecast revenue for the next 3 months | PARTIAL | PARTIAL | PARTIAL |  | D15 | Forecast still needs confirmed meanings |
| 7 | retail_sales | What should I do to grow sales? | PARTIAL | PARTIAL | PASS |  | D13 | Five data-grounded next steps (cross-checked figures) with five clickable questions |
| 8 | retail_sales | kul revenue kitni hai region wise? | PASS | PASS | PASS |  |  | Exact; North named |
| 9 | finance_ledger | What is the total amount of debit entries? | PASS | PASS | PASS |  |  | 2,805,395.19 exact |
| 10 | finance_ledger | Which account has the highest total amount? | PASS | PASS | PASS |  |  | Rent named, exact |
| 11 | finance_ledger | Total amount by cost center | PASS | PASS | PASS |  |  | Exact |
| 12 | finance_ledger | (+) only for Salaries | PASS | PASS | PASS |  |  | Exact |
| 13 | finance_ledger | How did monthly spending change over the year? | FAIL | PARTIAL | PARTIAL |  |  | 12 months exact but sums credits with debits (spending = debits) |
| 14 | finance_ledger | What is our net income (credits minus debits)? | FAIL | PARTIAL | PARTIAL | Show the average of amount_pkr by account | D26 | Clickable choices now, but irrelevant (average by account / records by cost centre); clicked answer exact (Software 4,980.66) but does not answer net income; 'total of amount_pkr by entry_type' not offered |
| 15 | finance_ledger | Is anything wrong with this ledger? | PASS | PASS | PASS |  |  | Quality check |
| 16 | hr_employees | How many employees are there? | PASS | PASS | PASS |  |  | 300 exact |
| 17 | hr_employees | Average monthly salary by department | PASS | PASS | PASS |  |  | Exact; Engineering named |
| 18 | hr_employees | What share of employees left the company? | PASS | PASS | PASS |  |  | 216/84 exact |
| 19 | hr_employees | (+) which department has the most leavers? | PASS | PASS | PASS |  |  | Sales 20 named |
| 20 | hr_employees | Is salary related to performance score? | FAIL | PARTIAL | PARTIAL |  | D9 | Needs confirmed meanings; links overview |
| 21 | hr_employees | Who are the top 5 earners? | PASS | PASS | PASS |  |  | Top 5 exact |
| 22 | hr_employees | Hiring trend by year | FAIL | PASS | PASS |  |  | 10 years exact |
| 23 | hr_employees | what should HR focus on? | PARTIAL | PARTIAL | PASS |  | D13 | Five grounded next steps with clickable questions |
| 24 | clinic_visits | How many visits per clinic? | PASS | PASS | PASS |  |  | Exact |
| 25 | clinic_visits | Average wait time by department | PASS | PASS | PASS |  |  | Exact |
| 26 | clinic_visits | What is the 30-day readmission rate? | PARTIAL | PASS | PASS |  |  | 0.265 shown 0.27 |
| 27 | clinic_visits | (+) break it down by age band | FAIL | PASS | PASS |  |  | Readmission by age band exact |
| 28 | clinic_visits | Which clinic has the longest waits? | PASS | PASS | PASS |  |  | Clinic C named, exact |
| 29 | clinic_visits | Weekly visit trend | PARTIAL | PASS | PASS |  |  | 27 weeks exact |
| 30 | clinic_visits | Any anomalies in wait times? | PASS | PASS | PASS |  |  | Scan guide |
| 31 | iot_sensors | Average temperature per sensor | PASS | PASS | PASS |  |  | Exact; S2 named |
| 32 | iot_sensors | Which sensor had abnormal temperature spikes? | PARTIAL | PARTIAL | PARTIAL |  | D8 | Scan guide; S3 not named in chat |
| 33 | iot_sensors | (+) when did they happen? | FAIL | FAIL | FAIL | Does temperature_c relate to humidity_pct? | D26 | Asks which events; only offered choice (temperature vs humidity relationship) is irrelevant and lands on pattern readiness |
| 34 | iot_sensors | Show daily average temperature trend | FAIL | FAIL | PASS |  | D18 | Timestamp now a date-time: 30 daily averages, first 22.8489/22.9167/22.8597 match pandas |
| 35 | iot_sensors | What is the maximum power draw? | PASS | PASS | PASS |  |  | 140 exact |
| 36 | iot_sensors | Is humidity related to temperature? | FAIL | PARTIAL | PARTIAL |  | D9 | Needs confirmed meanings; links overview |
| 37 | iot_sensors | Forecast temperature for the next week | PARTIAL | PARTIAL | PARTIAL |  | D15 | Forecast needs confirmed meanings (no longer claims there is no date column) |
| 38 | customer_survey | What is the average NPS score? | PASS | PASS | PASS |  |  | 5.0675 exact |
| 39 | customer_survey | How many responses per satisfaction level? | PASS | PASS | PASS |  |  | Exact |
| 40 | customer_survey | What are customers complaining about? | FAIL | FAIL | FAIL |  | D16 | Still document search with no documents |
| 41 | customer_survey | Compare NPS by channel | PASS | PASS | PASS |  |  | Exact; Mobile named |
| 42 | customer_survey | (+) which channel should we fix first? | PARTIAL | PARTIAL | PASS | Which channel has the lowest average nps_score? | D17 | Clickable 'Which channel has the lowest average nps_score?' -> Store 4.75 first, exact |
| 43 | customer_survey | What percentage of responses agree or strongly agree? | FAIL | PARTIAL | PARTIAL |  |  | Counts with shares (Agree 87 + Strongly agree 88 = 43.75%); combined % not stated |
| 44 | inventory | How many SKUs are below their reorder point? | FAIL | PARTIAL | PARTIAL |  | D10 | Clear 'comparing two fields not supported yet' message; no answer (true 55) |
| 45 | inventory | Total inventory value by warehouse | FAIL | FAIL | PASS |  | D20 | SUM(on_hand_units * unit_cost_pkr) by warehouse: 25,430,835.65 / 24,543,724.97 / 25,333,392.65 exact |
| 46 | inventory | Which category has the slowest moving stock? | PASS | PASS | PASS |  |  | Grocery named, exact |
| 47 | inventory | (+) list the 5 SKUs with the most days since last sale | PASS | PASS | PASS |  |  | Exact incl. ties |
| 48 | inventory | What should I reorder first? | PARTIAL | PARTIAL | FAIL |  | D27 | REGRESSION (model variance): ranks by days since last sale (stale stock), not low stock vs reorder point |
| 49 | inventory | Total units on hand | PASS | PASS | PASS |  |  | 60,090 exact |
| 50 | marketing_funnel | Total spend by channel | PASS | PASS | PASS |  | D19 | Exact; Organic raw value still '0E-12' |
| 51 | marketing_funnel | What is the conversion rate from clicks to purchases by channel? | FAIL | PARTIAL | PARTIAL | What is the total of clicks? | D26 | Clickable parts; clicked total clicks 135,020 exact, but parts drop 'by channel' and the rate is never computed |
| 52 | marketing_funnel | Which channel has the lowest cost per purchase? | FAIL | PARTIAL | PARTIAL | What is the total of purchases? | D26 | Choices omit spend (offers purchases, average impressions, record count); clicked total purchases 3,698 exact |
| 53 | marketing_funnel | (+) how has it trended over the weeks? | FAIL | PARTIAL | PARTIAL |  |  | Follow-up after the click: weekly clicks, exact (week labels are Monday-truncated), not cost per purchase |
| 54 | marketing_funnel | Total signups | PASS | PASS | PASS |  |  | 15,232 exact |
| 55 | marketing_funnel | Where should I move budget? | PARTIAL | PARTIAL | PARTIAL | Show the average of impressions by channel | D26 | Clickable but weak choices; clicked average impressions by channel exact |
| 56 | messy_store_sales | What is the total sales amount? | FAIL | FAIL | FAIL |  | D25 | N/A in Sales Amount still fails every sum (job failed) |
| 57 | messy_store_sales | Sales by store | FAIL | FAIL | FAIL |  | D25 | Same |
| 58 | messy_store_sales | How many rows have missing sales? | FAIL | FAIL | FAIL | What is the total of Sales Amount? | D22 | Friendly message + clickable choices now, but first choice hits the same N/A failure; no is-missing filter |
| 59 | messy_store_sales | Total units | FAIL | PASS | PASS |  |  | 3,755 exact |
| 60 | messy_store_sales | Is this data clean? | PARTIAL | PARTIAL | PARTIAL |  | D23 | Misses label variants |
| 61 | messy_store_sales | monthly sales trend | FAIL | FAIL | FAIL |  | D25 | Same N/A failure |
| 62 | restaurant_daily | Total revenue for the year | PASS | PASS | PASS |  |  | 58,832,300 exact |
| 63 | restaurant_daily | Revenue by branch | PASS | PASS | PASS |  |  | Exact; DHA named |
| 64 | restaurant_daily | Do weekends get more orders than weekdays? | FAIL | FAIL | PARTIAL |  | D21 | Weekday/weekend grouping works and is exact (26,518 vs 14,056) but uses SUM, so it implies weekdays get more; per-day averages are 101.6 vs 135.15 |
| 65 | restaurant_daily | Which month had the highest revenue? | FAIL | PASS | PASS |  |  | 2025-08 5,730,400 first, exact |
| 66 | restaurant_daily | (+) and the lowest? | FAIL | PASS | PASS |  |  | 2025-12 4,058,550 first, exact |
| 67 | restaurant_daily | Average delivery time by branch | PASS | PASS | PASS |  |  | Exact |
| 68 | restaurant_daily | Forecast orders for next month | PARTIAL | PARTIAL | PARTIAL |  | D15 | Forecast needs confirmed meanings |
| 69 | urdu_sales | Total sales by city | PASS | PASS | PASS |  |  | Exact; Karachi named |
| 70 | urdu_sales | kis shehar ki farokht sab se zyada hai? | PARTIAL | PASS | PASS |  |  | Exact; Karachi named |
| 71 | urdu_sales | کل فروخت کتنی ہے؟ | PASS | PASS | PASS |  |  | 5,114,840 exact |
| 72 | urdu_sales | How many customers in total? | PASS | PASS | PASS |  |  | 19,337 exact |
| 73 | urdu_sales | Monthly sales trend | PARTIAL | PASS | PASS |  |  | 6 months exact |
| 74 | urdu_sales | batao kya karna chahiye? | PARTIAL | PARTIAL | PASS |  | D13 | Grounded next steps in English with Urdu field names, clickable questions |
| 75 | wide_plants | Total output for metric 01 by country | PASS | PASS | PASS |  |  | Exact; AE named |
| 76 | wide_plants | Which plant has the highest metric_05_defects? | PARTIAL | PARTIAL | PARTIAL |  | D12 | Top-5 rows, ties not named |
| 77 | wide_plants | What is the overall defect rate? | FAIL | PARTIAL | PARTIAL | What is the total of metric_01_defects? | D26 | Clickable but parts are single metrics (metric_01_defects 2,979 exact); overall rate 2.771% not reachable |
| 78 | wide_plants | How many plants per country? | PASS | PASS | PASS |  |  | Exact |
| 79 | wide_plants | Summarize this data | PASS | PASS | PASS |  |  | Grounded summary |
| 80 | wide_plants | Which metrics have the most defects? | FAIL | FAIL | PARTIAL | What is the total of metric_01_defects? | D14 | Friendly message + clickable working questions (metric_01_defects 2,979 exact); cross-column ranking still unsupported |
