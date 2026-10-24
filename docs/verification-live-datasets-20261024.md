> **File use case:** Verification record for the fourth live multi-dataset run, on release 4028b7309e58531f.
> **What it does:** Grades 81 live answers (plus clicked choices) and chat history against runs 1-3.

# Live multi-dataset verification — release 4028b7309e58531f (schema 0031), 2026-10-24

Same 12 seeded fictional datasets (fresh uploads, profile-v4) and 81 questions. One new fictional account, hosted DeepSeek, private VPS through the existing forward; the account was disabled afterwards. Where a reply offered clickable choices the first one was sent in the same thread (9 clicks) and graded with the question. Numbers were checked against pandas on the same files; no executed number disagreed.

| Run | Release | PASS | PARTIAL | FAIL |
|---|---|---|---|---|
| 1 | a5d380f2541ef5bd | 36 | 16 | 29 |
| 2 | f590a4a813287580 | 48 | 22 | 11 |
| 3 | 93d29ec6abe39458 | 54 | 19 | 8 |
| 4 | 4028b7309e58531f | 62 | 19 | 0 |

Run 4 vs run 3: 11 better, 2 worse. Latency median 10.0 s, max 27.0 s. Jobs not succeeded: 0.

## Per dataset (PASS/PARTIAL/FAIL)

| Dataset | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| retail_sales | 3/2/4 | 6/2/1 | 7/1/1 | 7/2/0 |
| finance_ledger | 5/0/2 | 5/2/0 | 5/2/0 | 5/2/0 |
| hr_employees | 5/1/2 | 6/2/0 | 7/1/0 | 7/1/0 |
| clinic_visits | 4/2/1 | 7/0/0 | 7/0/0 | 7/0/0 |
| iot_sensors | 2/2/3 | 2/3/2 | 3/3/1 | 4/3/0 |
| customer_survey | 3/1/2 | 3/2/1 | 4/1/1 | 4/2/0 |
| inventory | 3/1/2 | 3/2/1 | 4/1/1 | 6/0/0 |
| marketing_funnel | 2/1/3 | 2/4/0 | 2/4/0 | 2/4/0 |
| messy_store_sales | 0/1/5 | 1/1/4 | 1/1/4 | 4/2/0 |
| restaurant_daily | 3/1/3 | 5/1/1 | 5/2/0 | 6/1/0 |
| urdu_sales | 3/3/0 | 5/1/0 | 6/0/0 | 6/0/0 |
| wide_plants | 3/1/2 | 3/2/1 | 3/3/0 | 4/2/0 |

## Chat history

- Workspace with 60 threads: `GET /workspaces/{wid}/threads` returned 200 and listed 50 (10 not listed).
- Workspace with 12 threads: `GET /workspaces/{wid}/threads` returned 200 and listed 12 (0 not listed).
- The list is a plain array capped at 50 newest threads with no paging cursor, so older threads in a busy workspace cannot be reached from it.
- Continuing a past thread works: the follow-up "and only for laptops?" on the Roman-Urdu region thread kept the revenue-by-region plan and added a product filter, and the thread then held 2 turns. But the filter used the value `laptops` (the data says `Laptop`), so the result was empty and the reply said only "No nonmissing group values are available to rank" — a silent empty answer.

## Changes since run 3

- #2 retail_sales: "and which region sells the most laptops?" FAIL → PASS — Follow-up kept revenue and filtered Laptop: West 272,264.56 first, all 4 regions exact
- #33 iot_sensors: "when did they happen?" FAIL → PASS — Clickable 'Which timestamp has the highest maximum temperature_c?' -> 2025-03-19 18:00 49.5, 03-09 08:00 46.09, 09:00 45.98 first, exact (sensor not named)
- #40 customer_survey: "What are customers complaining about?" FAIL → PASS — No documents, so exact word counts over 356 written answers (app/crashes/often 64, recommend 62, great/service 57) match pandas; says not sentiment
- #44 inventory: "How many SKUs are below their reorder point?" PARTIAL → PASS — Deterministic reorder rule: 55 below reorder point, 2 exactly at it, SKU-0141 short by 116 first; exact
- #48 inventory: "What should I reorder first?" FAIL → PASS — Same deterministic reorder rule (largest shortfall first), exact
- #56 messy_store_sales: "What is the total sales amount?" FAIL → PASS — N/A read as missing: 418,984.96 exact
- #57 messy_store_sales: "Sales by store" FAIL → PARTIAL — Sums exact but 'Store 1' and ' store 1 ' still separate groups (148,124.57 / 145,128.65)
- #58 messy_store_sales: "How many rows have missing sales?" FAIL → PASS — is_missing filter: 15 rows exact
- #61 messy_store_sales: "monthly sales trend" FAIL → PASS — 5 months exact (Jan 80,448.26 ... May 93,806.21)
- #64 restaurant_daily: "Do weekends get more orders than weekdays?" PARTIAL → PASS — Per-calendar-day averages: weekday 101.60, weekend 135.15 exact, totals follow
- #76 wide_plants: "Which plant has the highest metric_05_defects?" PARTIAL → PASS — Returns exactly the 3 tied plants P004/P078/P097 at 30 (narrative still says 'open the table' rather than naming them)
- #4 retail_sales: "Compare revenue in North vs South" PASS → PARTIAL — REGRESSION: correction did not produce a grouped plan this time; clarification offers only 'records by region' (no revenue choice); clicked counts exact (E280/N312/S288/W320) but revenue not compared
- #42 customer_survey: "which channel should we fix first?" PASS → PARTIAL — REGRESSION: first choice is now 'total of nps_score by channel' (a sum of scores, favours the channel with most responses); clicked sums exact (Mobile 756/Store 589/Web 682); 'average' is the second choice

## All questions

| # | Dataset | Question | R1 | R2 | R3 | R4 | Clicked choice | Defect | Note |
|---|---|---|---|---|---|---|---|---|---|
| 0 | retail_sales | What is the total revenue? | PASS | PASS | PASS | PASS |  |  | 2,266,798.06 exact |
| 1 | retail_sales | Top 3 products by total revenue | PASS | PASS | PASS | PASS |  |  | Exact; Laptop named |
| 2 | retail_sales | (+) and which region sells the most laptops? | FAIL | FAIL | FAIL | PASS |  | D6 | Follow-up kept revenue and filtered Laptop: West 272,264.56 first, all 4 regions exact |
| 3 | retail_sales | Show the monthly revenue trend | FAIL | PASS | PASS | PASS |  |  | 12 months exact |
| 4 | retail_sales | Compare revenue in North vs South | FAIL | PASS | PASS | PARTIAL | How many records are there by region? | D1 | REGRESSION: correction did not produce a grouped plan this time; clarification offers only 'records by region' (no revenue choice); clicked counts exact (E280/N312/S288/W320) but revenue not compared |
| 5 | retail_sales | Are there any unusual orders? | FAIL | PASS | PASS | PASS |  |  | Unusual-values scan |
| 6 | retail_sales | Forecast revenue for the next 3 months | PARTIAL | PARTIAL | PARTIAL | PARTIAL |  | D15 | Forecast needs confirmed meanings |
| 7 | retail_sales | What should I do to grow sales? | PARTIAL | PARTIAL | PASS | PASS |  | D13 | Grounded next steps, clickable |
| 8 | retail_sales | kul revenue kitni hai region wise? | PASS | PASS | PASS | PASS |  |  | Exact |
| 9 | finance_ledger | What is the total amount of debit entries? | PASS | PASS | PASS | PASS |  |  | 2,805,395.19 exact |
| 10 | finance_ledger | Which account has the highest total amount? | PASS | PASS | PASS | PASS |  |  | Rent named, exact |
| 11 | finance_ledger | Total amount by cost center | PASS | PASS | PASS | PASS |  |  | Exact |
| 12 | finance_ledger | (+) only for Salaries | PASS | PASS | PASS | PASS |  |  | Exact |
| 13 | finance_ledger | How did monthly spending change over the year? | FAIL | PARTIAL | PARTIAL | PARTIAL |  |  | 12 months exact but credits and debits summed together |
| 14 | finance_ledger | What is our net income (credits minus debits)? | FAIL | PARTIAL | PARTIAL | PARTIAL | What is the total of amount_pkr by entry_type? | D26 | Now offers the right part first: total by entry_type -> credit 975,525.51 / debit 2,805,395.19 exact; net (-1,829,869.68) still not computed |
| 15 | finance_ledger | Is anything wrong with this ledger? | PASS | PASS | PASS | PASS |  |  | Quality check |
| 16 | hr_employees | How many employees are there? | PASS | PASS | PASS | PASS |  |  | 300 exact |
| 17 | hr_employees | Average monthly salary by department | PASS | PASS | PASS | PASS |  |  | Exact |
| 18 | hr_employees | What share of employees left the company? | PASS | PASS | PASS | PASS |  |  | 216/84 exact |
| 19 | hr_employees | (+) which department has the most leavers? | PASS | PASS | PASS | PASS |  |  | Sales 20 named |
| 20 | hr_employees | Is salary related to performance score? | FAIL | PARTIAL | PARTIAL | PARTIAL |  | D9 | Needs confirmed meanings; links overview |
| 21 | hr_employees | Who are the top 5 earners? | PASS | PASS | PASS | PASS |  |  | Top 5 exact |
| 22 | hr_employees | Hiring trend by year | FAIL | PASS | PASS | PASS |  |  | 10 years exact |
| 23 | hr_employees | what should HR focus on? | PARTIAL | PARTIAL | PASS | PASS |  | D13 | Grounded next steps |
| 24 | clinic_visits | How many visits per clinic? | PASS | PASS | PASS | PASS |  |  | Exact |
| 25 | clinic_visits | Average wait time by department | PASS | PASS | PASS | PASS |  |  | Exact |
| 26 | clinic_visits | What is the 30-day readmission rate? | PARTIAL | PASS | PASS | PASS |  |  | 0.27 |
| 27 | clinic_visits | (+) break it down by age band | FAIL | PASS | PASS | PASS |  |  | Readmission by age band exact |
| 28 | clinic_visits | Which clinic has the longest waits? | PASS | PASS | PASS | PASS |  |  | Clinic C named |
| 29 | clinic_visits | Weekly visit trend | PARTIAL | PASS | PASS | PASS |  |  | 27 weeks exact |
| 30 | clinic_visits | Any anomalies in wait times? | PASS | PASS | PASS | PASS |  |  | Scan guide |
| 31 | iot_sensors | Average temperature per sensor | PASS | PASS | PASS | PASS |  |  | Exact |
| 32 | iot_sensors | Which sensor had abnormal temperature spikes? | PARTIAL | PARTIAL | PARTIAL | PARTIAL |  | D8 | Scan guide; S3 not named in chat |
| 33 | iot_sensors | (+) when did they happen? | FAIL | FAIL | FAIL | PASS | Which timestamp has the highest maximum temperature_c? | D26 | Clickable 'Which timestamp has the highest maximum temperature_c?' -> 2025-03-19 18:00 49.5, 03-09 08:00 46.09, 09:00 45.98 first, exact (sensor not named) |
| 34 | iot_sensors | Show daily average temperature trend | FAIL | FAIL | PASS | PASS |  | D18 | 30 daily averages exact |
| 35 | iot_sensors | What is the maximum power draw? | PASS | PASS | PASS | PASS |  |  | 140 exact |
| 36 | iot_sensors | Is humidity related to temperature? | FAIL | PARTIAL | PARTIAL | PARTIAL |  | D9 | Needs confirmed meanings |
| 37 | iot_sensors | Forecast temperature for the next week | PARTIAL | PARTIAL | PARTIAL | PARTIAL |  | D15 | Forecast needs confirmed meanings |
| 38 | customer_survey | What is the average NPS score? | PASS | PASS | PASS | PASS |  |  | 5.0675 exact |
| 39 | customer_survey | How many responses per satisfaction level? | PASS | PASS | PASS | PASS |  |  | Exact |
| 40 | customer_survey | What are customers complaining about? | FAIL | FAIL | FAIL | PASS |  | D16 | No documents, so exact word counts over 356 written answers (app/crashes/often 64, recommend 62, great/service 57) match pandas; says not sentiment |
| 41 | customer_survey | Compare NPS by channel | PASS | PASS | PASS | PASS |  |  | Exact |
| 42 | customer_survey | (+) which channel should we fix first? | PARTIAL | PARTIAL | PASS | PARTIAL | What is the total of nps_score by channel? | D26 | REGRESSION: first choice is now 'total of nps_score by channel' (a sum of scores, favours the channel with most responses); clicked sums exact (Mobile 756/Store 589/Web 682); 'average' is the second choice |
| 43 | customer_survey | What percentage of responses agree or strongly agree? | FAIL | PARTIAL | PARTIAL | PARTIAL |  |  | Counts with shares (43.75% combined not stated) |
| 44 | inventory | How many SKUs are below their reorder point? | FAIL | PARTIAL | PARTIAL | PASS |  | D10 | Deterministic reorder rule: 55 below reorder point, 2 exactly at it, SKU-0141 short by 116 first; exact |
| 45 | inventory | Total inventory value by warehouse | FAIL | FAIL | PASS | PASS |  | D20 | Inventory value exact |
| 46 | inventory | Which category has the slowest moving stock? | PASS | PASS | PASS | PASS |  |  | Exact |
| 47 | inventory | (+) list the 5 SKUs with the most days since last sale | PASS | PASS | PASS | PASS |  |  | Exact incl. ties |
| 48 | inventory | What should I reorder first? | PARTIAL | PARTIAL | FAIL | PASS |  | D27 | Same deterministic reorder rule (largest shortfall first), exact |
| 49 | inventory | Total units on hand | PASS | PASS | PASS | PASS |  |  | 60,090 exact |
| 50 | marketing_funnel | Total spend by channel | PASS | PASS | PASS | PASS |  | D19 | Exact; Organic now shown as 0 |
| 51 | marketing_funnel | What is the conversion rate from clicks to purchases by channel? | FAIL | PARTIAL | PARTIAL | PARTIAL | What is the total purchases by channel? | D26 | Parts now keep 'by channel'; clicked purchases by channel exact; rate not computed |
| 52 | marketing_funnel | Which channel has the lowest cost per purchase? | FAIL | PARTIAL | PARTIAL | PARTIAL | What is the total of spend_usd by channel? | D26 | Spend by channel offered first; clicked exact; cost per purchase not computed |
| 53 | marketing_funnel | (+) how has it trended over the weeks? | FAIL | PARTIAL | PARTIAL | PARTIAL |  |  | Follow-up after click: weekly spend exact, not cost per purchase |
| 54 | marketing_funnel | Total signups | PASS | PASS | PASS | PASS |  |  | 15,232 exact |
| 55 | marketing_funnel | Where should I move budget? | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Show the average of impressions by channel | D26 | Weak choices for budget question; clicked average impressions exact |
| 56 | messy_store_sales | What is the total sales amount? | FAIL | FAIL | FAIL | PASS |  | D25 | N/A read as missing: 418,984.96 exact |
| 57 | messy_store_sales | Sales by store | FAIL | FAIL | FAIL | PARTIAL |  | D23 | Sums exact but 'Store 1' and ' store 1 ' still separate groups (148,124.57 / 145,128.65) |
| 58 | messy_store_sales | How many rows have missing sales? | FAIL | FAIL | FAIL | PASS |  | D22 | is_missing filter: 15 rows exact |
| 59 | messy_store_sales | Total units | FAIL | PASS | PASS | PASS |  |  | 3,755 exact |
| 60 | messy_store_sales | Is this data clean? | PARTIAL | PARTIAL | PARTIAL | PARTIAL |  | D23 | Missing cells now correct (Sales Amount 15); label variants still not flagged |
| 61 | messy_store_sales | monthly sales trend | FAIL | FAIL | FAIL | PASS |  | D25 | 5 months exact (Jan 80,448.26 ... May 93,806.21) |
| 62 | restaurant_daily | Total revenue for the year | PASS | PASS | PASS | PASS |  |  | 58,832,300 exact |
| 63 | restaurant_daily | Revenue by branch | PASS | PASS | PASS | PASS |  |  | Exact |
| 64 | restaurant_daily | Do weekends get more orders than weekdays? | FAIL | FAIL | PARTIAL | PASS |  | D21 | Per-calendar-day averages: weekday 101.60, weekend 135.15 exact, totals follow |
| 65 | restaurant_daily | Which month had the highest revenue? | FAIL | PASS | PASS | PASS |  |  | 2025-08 first, exact |
| 66 | restaurant_daily | (+) and the lowest? | FAIL | PASS | PASS | PASS |  |  | 2025-12 first, exact |
| 67 | restaurant_daily | Average delivery time by branch | PASS | PASS | PASS | PASS |  |  | Exact |
| 68 | restaurant_daily | Forecast orders for next month | PARTIAL | PARTIAL | PARTIAL | PARTIAL |  | D15 | Forecast needs confirmed meanings |
| 69 | urdu_sales | Total sales by city | PASS | PASS | PASS | PASS |  |  | Exact |
| 70 | urdu_sales | kis shehar ki farokht sab se zyada hai? | PARTIAL | PASS | PASS | PASS |  |  | Exact |
| 71 | urdu_sales | کل فروخت کتنی ہے؟ | PASS | PASS | PASS | PASS |  |  | 5,114,840 exact |
| 72 | urdu_sales | How many customers in total? | PASS | PASS | PASS | PASS |  |  | 19,337 exact |
| 73 | urdu_sales | Monthly sales trend | PARTIAL | PASS | PASS | PASS |  |  | 6 months exact |
| 74 | urdu_sales | batao kya karna chahiye? | PARTIAL | PARTIAL | PASS | PASS |  | D13 | Grounded next steps |
| 75 | wide_plants | Total output for metric 01 by country | PASS | PASS | PASS | PASS |  |  | Exact |
| 76 | wide_plants | Which plant has the highest metric_05_defects? | PARTIAL | PARTIAL | PARTIAL | PASS |  | D12 | Returns exactly the 3 tied plants P004/P078/P097 at 30 (narrative still says 'open the table' rather than naming them) |
| 77 | wide_plants | What is the overall defect rate? | FAIL | PARTIAL | PARTIAL | PARTIAL | What is the total of metric_01_defects? | D26 | Parts only (metric_01_defects 2,979 exact); overall 2.771% not reachable |
| 78 | wide_plants | How many plants per country? | PASS | PASS | PASS | PASS |  |  | Exact |
| 79 | wide_plants | Summarize this data | PASS | PASS | PASS | PASS |  |  | Grounded summary |
| 80 | wide_plants | Which metrics have the most defects? | FAIL | FAIL | PARTIAL | PARTIAL | What is the total of metric_01_defects? | D14 | Friendly + clickable; cross-column ranking unsupported |
