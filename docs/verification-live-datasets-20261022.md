> **File use case:** Verification record for the live multi-dataset re-run after release f590a4a813287580.
> **What it does:** Compares 81 graded live answers before and after the October 22 harness repairs.

# Live multi-dataset verification — release f590a4a813287580 (schema 0030), 2026-10-22

Same 12 seeded fictional datasets and 81 questions as the baseline run on release a5d380f2541ef5bd. One new fictional account, hosted DeepSeek, private VPS through the existing forward; the account was disabled afterwards. Numbers were checked against an independent pandas computation of the same files.

| Run | PASS | PARTIAL | FAIL |
|---|---|---|---|
| Baseline (a5d380f2541ef5bd) | 36 | 16 | 29 |
| After (f590a4a813287580) | 48 | 22 | 11 |

Improved: 22 questions. Worse: 0. Latency median 9.2 s, max 17.5 s. Jobs not succeeded: 3 (all the messy-file N/A conversion error, D25). No executed number disagreed with pandas.

## Per dataset (before → after, PASS/PARTIAL/FAIL)

| Dataset | Before | After |
|---|---|---|
| retail_sales | 3/2/4 | 6/2/1 |
| finance_ledger | 5/0/2 | 5/2/0 |
| hr_employees | 5/1/2 | 6/2/0 |
| clinic_visits | 4/2/1 | 7/0/0 |
| iot_sensors | 2/2/3 | 2/3/2 |
| customer_survey | 3/1/2 | 3/2/1 |
| inventory | 3/1/2 | 3/2/1 |
| marketing_funnel | 2/1/3 | 2/4/0 |
| messy_store_sales | 0/1/5 | 1/1/4 |
| restaurant_daily | 3/1/3 | 5/1/1 |
| urdu_sales | 3/3/0 | 5/1/0 |
| wide_plants | 3/1/2 | 3/2/1 |

## All questions

| # | Dataset | Question | Before | After | Defect | Note |
|---|---|---|---|---|---|---|
| 0 | retail_sales | What is the total revenue? | PASS | PASS |  | 2,266,798.06 exact |
| 1 | retail_sales | Top 3 products by total revenue | PASS | PASS | D5 | Laptop/Phone/Tablet exact; narrative now names Laptop |
| 2 | retail_sales | (+) and which region sells the most laptops? | FAIL | FAIL | D6 | Still rejected as changing an earlier condition, no choices (true West 301 units / 272,264.56) |
| 3 | retail_sales | Show the monthly revenue trend | FAIL | PASS | D2 | 12 calendar months, chronological, all 12 totals match pandas |
| 4 | retail_sales | Compare revenue in North vs South | FAIL | PASS | D1 | Filter-plan correction ran; all 4 regions grouped, North 611,773.62 vs South 540,241.49 exact |
| 5 | retail_sales | Are there any unusual orders? | FAIL | PASS | D8 | Opens the automatic unusual-values scan |
| 6 | retail_sales | Forecast revenue for the next 3 months | PARTIAL | PARTIAL | D15 | Forecast still needs confirmed meanings |
| 7 | retail_sales | What should I do to grow sales? | PARTIAL | PARTIAL | D13 | Refuses causal advice, no clickable next step |
| 8 | retail_sales | kul revenue kitni hai region wise? | PASS | PASS | D5 | Region totals exact; narrative names North |
| 9 | finance_ledger | What is the total amount of debit entries? | PASS | PASS |  | 2,805,395.19 exact |
| 10 | finance_ledger | Which account has the highest total amount? | PASS | PASS | D5 | Rent 524,700.62 named as highest |
| 11 | finance_ledger | Total amount by cost center | PASS | PASS | D5 | Exact; Karachi named |
| 12 | finance_ledger | (+) only for Salaries | PASS | PASS |  | Salaries by cost centre exact; HQ named |
| 13 | finance_ledger | How did monthly spending change over the year? | FAIL | PARTIAL | D2 | Now 12 months chronological and exact, but sums credits and debits together (spending = debits) |
| 14 | finance_ledger | What is our net income (credits minus debits)? | FAIL | PARTIAL | D3 | No wrong number now: model asks which entry_type values mean credit/debit; candidates not clickable (D17) |
| 15 | finance_ledger | Is anything wrong with this ledger? | PASS | PASS |  | Quality check |
| 16 | hr_employees | How many employees are there? | PASS | PASS |  | 300 exact |
| 17 | hr_employees | Average monthly salary by department | PASS | PASS | D5 | Exact; Engineering named |
| 18 | hr_employees | What share of employees left the company? | PASS | PASS |  | No 216 / Yes 84 exact |
| 19 | hr_employees | (+) which department has the most leavers? | PASS | PASS |  | Sales 20 named |
| 20 | hr_employees | Is salary related to performance score? | FAIL | PARTIAL | D9 | Still needs confirmed meanings, now links to the overview relationship card |
| 21 | hr_employees | Who are the top 5 earners? | PASS | PASS |  | Top 5 exact |
| 22 | hr_employees | Hiring trend by year | FAIL | PASS | D2 | 10 calendar years, counts match pandas (33,37,27,29,32,30,27,30,32,23) |
| 23 | hr_employees | what should HR focus on? | PARTIAL | PARTIAL | D13 | Generic orientation reading |
| 24 | clinic_visits | How many visits per clinic? | PASS | PASS |  | A 193 / B 198 / C 209 exact |
| 25 | clinic_visits | Average wait time by department | PASS | PASS | D5 | Exact; Orthopedics named |
| 26 | clinic_visits | What is the 30-day readmission rate? | PARTIAL | PASS | D11 | 0.265 now displayed 0.27 (half-up) |
| 27 | clinic_visits | (+) break it down by age band | FAIL | PASS | D5b | Follow-up kept readmission: 0-17 0.1654, 18-39 0.2515, 40-64 0.3469, 65+ 0.2866 exact |
| 28 | clinic_visits | Which clinic has the longest waits? | PASS | PASS | D5 | Clinic C 64.91 named |
| 29 | clinic_visits | Weekly visit trend | PARTIAL | PASS | D2 | 27 calendar weeks; first weeks 15/25/25 match pandas |
| 30 | clinic_visits | Any anomalies in wait times? | PASS | PASS |  | Scan guide |
| 31 | iot_sensors | Average temperature per sensor | PASS | PASS | D5 | Exact; S2 named |
| 32 | iot_sensors | Which sensor had abnormal temperature spikes? | PARTIAL | PARTIAL | D8 | Now opens the unusual-values scan (proper tool) but does not name S3 in chat |
| 33 | iot_sensors | (+) when did they happen? | FAIL | FAIL | D5b | Previous turn was a guide, so 'they' has no result to refer to; asks what events |
| 34 | iot_sensors | Show daily average temperature trend | FAIL | FAIL | D24 | NEW message leak: 'Use a calendar period only when grouping by one date field' (timestamp is text, model asked for day period) |
| 35 | iot_sensors | What is the maximum power draw? | PASS | PASS |  | 140 exact |
| 36 | iot_sensors | Is humidity related to temperature? | FAIL | PARTIAL | D9 | No false row-restriction any more (D7 fixed); needs confirmed meanings, links overview |
| 37 | iot_sensors | Forecast temperature for the next week | PARTIAL | PARTIAL | D18 | Timestamp still profiled as text |
| 38 | customer_survey | What is the average NPS score? | PASS | PASS |  | 5.0675 exact |
| 39 | customer_survey | How many responses per satisfaction level? | PASS | PASS |  | Counts exact |
| 40 | customer_survey | What are customers complaining about? | FAIL | FAIL | D16 | Still routed to document search with no documents |
| 41 | customer_survey | Compare NPS by channel | PASS | PASS | D5 | Exact; Mobile named |
| 42 | customer_survey | (+) which channel should we fix first? | PARTIAL | PARTIAL | D17 | Reasonable question, candidates not clickable |
| 43 | customer_survey | What percentage of responses agree or strongly agree? | FAIL | PARTIAL | D1 | No longer empty: counts by level with shares (Agree 87 + Strongly agree 88 = 43.75%), but the combined % is not stated |
| 44 | inventory | How many SKUs are below their reorder point? | FAIL | PARTIAL | D10 | Clear 'comparing two fields is not supported yet' message; still no answer (true 55) |
| 45 | inventory | Total inventory value by warehouse | FAIL | FAIL | D20 | Still SUM(on_hand_units) presented as inventory value |
| 46 | inventory | Which category has the slowest moving stock? | PASS | PASS | D5 | Grocery 112.98 named |
| 47 | inventory | (+) list the 5 SKUs with the most days since last sale | PASS | PASS |  | Exact incl. ties at 200 |
| 48 | inventory | What should I reorder first? | PARTIAL | PARTIAL | D10 | Lowest on-hand rows; ignores reorder point |
| 49 | inventory | Total units on hand | PASS | PASS |  | 60,090 exact |
| 50 | marketing_funnel | Total spend by channel | PASS | PASS | D19 | Exact; Google Ads named; Organic raw value still '0E-12' |
| 51 | marketing_funnel | What is the conversion rate from clicks to purchases by channel? | FAIL | PARTIAL | D3 | No wrong number: model now asks which ratio; candidates not clickable |
| 52 | marketing_funnel | Which channel has the lowest cost per purchase? | FAIL | PARTIAL | D3 | No wrong number: model now asks which ratio; candidates not clickable |
| 53 | marketing_funnel | (+) how has it trended over the weeks? | FAIL | PARTIAL | D2 | Weekly spend, chronological (correct grain) but not cost per purchase, since previous turn was a question |
| 54 | marketing_funnel | Total signups | PASS | PASS |  | 15,232 exact |
| 55 | marketing_funnel | Where should I move budget? | PARTIAL | PARTIAL | D17 | Reasonable question, candidates not clickable |
| 56 | messy_store_sales | What is the total sales amount? | FAIL | FAIL | D25 | Units guard gone, now exposed: 'N/A' text in Sales Amount (row 24) blocks every sum; job status failed |
| 57 | messy_store_sales | Sales by store | FAIL | FAIL | D25 | Same N/A conversion error |
| 58 | messy_store_sales | How many rows have missing sales? | FAIL | FAIL | D22 | Still 'The model proposed an invalid filter' (no is-missing filter) |
| 59 | messy_store_sales | Total units | FAIL | PASS | D4 | Units guard fixed: 3,755 exact |
| 60 | messy_store_sales | Is this data clean? | PARTIAL | PARTIAL | D23 | Quality summary, still misses label variants |
| 61 | messy_store_sales | monthly sales trend | FAIL | FAIL | D25 | Same N/A conversion error |
| 62 | restaurant_daily | Total revenue for the year | PASS | PASS |  | 58,832,300 exact |
| 63 | restaurant_daily | Revenue by branch | PASS | PASS | D5 | Exact; DHA named |
| 64 | restaurant_daily | Do weekends get more orders than weekdays? | FAIL | FAIL | D21 | Answered with weekly totals, not weekday vs weekend (true avg 101.6 vs 135.15) |
| 65 | restaurant_daily | Which month had the highest revenue? | FAIL | PASS | D2 | Calendar months ranked: 2025-08 5,730,400 first, exact |
| 66 | restaurant_daily | (+) and the lowest? | FAIL | PASS | D2 | Follow-up kept month grain: 2025-12 4,058,550 first, exact |
| 67 | restaurant_daily | Average delivery time by branch | PASS | PASS | D5 | Exact; Clifton named |
| 68 | restaurant_daily | Forecast orders for next month | PARTIAL | PARTIAL | D15 | Forecast needs confirmed meanings |
| 69 | urdu_sales | Total sales by city | PASS | PASS | D5 | Exact; Karachi named |
| 70 | urdu_sales | kis shehar ki farokht sab se zyada hai? | PARTIAL | PASS | D5 | Ranked and Karachi named (Roman Urdu) |
| 71 | urdu_sales | کل فروخت کتنی ہے؟ | PASS | PASS |  | 5,114,840 exact |
| 72 | urdu_sales | How many customers in total? | PASS | PASS |  | 19,337 exact |
| 73 | urdu_sales | Monthly sales trend | PARTIAL | PASS | D2 | 6 calendar months, all match pandas |
| 74 | urdu_sales | batao kya karna chahiye? | PARTIAL | PARTIAL | D13 | Generic reading |
| 75 | wide_plants | Total output for metric 01 by country | PASS | PASS | D5 | Exact; AE named |
| 76 | wide_plants | Which plant has the highest metric_05_defects? | PARTIAL | PARTIAL | D12 | Top-5 rows, ties P004/P078/P097 shown but not named |
| 77 | wide_plants | What is the overall defect rate? | FAIL | PARTIAL | D3 | No longer COUNT(*)=200: asks which defect-rate definition; candidates not clickable (true 2.771%) |
| 78 | wide_plants | How many plants per country? | PASS | PASS |  | SA 69 / AE 68 / PK 63 exact |
| 79 | wide_plants | Summarize this data | PASS | PASS |  | Grounded summary |
| 80 | wide_plants | Which metrics have the most defects? | FAIL | FAIL | D14 | Cross-column question now leaks 'Rank groups with order asc or desc…' validation message |
