> **File use case:** Owner-requested plan for a friendlier Syntelio interface with visible, proactive analyst agents after upload.
> **What it does:** Describes the target experience, a wireframe, the agent team, phased delivery and the rules that keep every number exact.

# Live analyst experience — plan

## Goal (owner, October 26)

After a user uploads data, Syntelio should feel like a team of analysts going to work on it
side by side: you can watch them work, and each one reports what you most need to know, in
plain language, with the next thing to do. The whole interface should be simpler and friendlier.

## Target experience

1. **Upload** → the tray shows progress; the moment the file is readable the user lands on
   "Your data is being analysed".
2. **Analyst team board** (live): one card per analyst agent showing status
   (waiting → working → done), what it is checking right now ("Comparing 3 regions…"), and its
   finding as soon as it is ready. Cards fill in one by one — no waiting for everything.
3. **"What you should know"** at the top: the 3–5 most important findings ranked across all
   agents, each one sentence + the exact number + a small chart + a button
   ("See breakdown", "Ask about this", "Pin to dashboard", "Fix this data").
4. **Auto dashboard** below (already built), then **"Questions you could ask next"** chips.
5. **Ask Syntelio** stays one click away; any finding can be opened in chat with its context.

## Wireframe

```
┌──────────────────────────────────────────────────────────────────────────┐
│  sales_2025.xlsx · 2.4M rows · analysed in 38 s          [Ask Syntelio]  │
├──────────────────────────────────────────────────────────────────────────┤
│  WHAT YOU SHOULD KNOW                                                    │
│  ① Revenue fell 12% in March — mostly the North region (−PKR 4.1M)  [See]│
│  ② 3% of orders have no amount — 71,204 rows                        [Fix]│
│  ③ Weekends sell 33% more per day than weekdays                     [Ask]│
├───────────────────────────────┬──────────────────────────────────────────┤
│  ANALYST TEAM (live)          │  YOUR DASHBOARD                          │
│  ✓ Data quality      done     │  [KPI] [KPI] [KPI]                       │
│  ✓ Trends            done     │  [Trend line ...........]                │
│  ● Drivers   comparing regions│  [Top products] [Share by region]        │
│  ○ Forecast          waiting  │                                          │
│  ○ Opportunities     waiting  │  Questions you could ask next:           │
│                               │  (Why did March drop?) (Best day?) (...) │
└───────────────────────────────┴──────────────────────────────────────────┘
```

## The analyst agents

Each agent is server code that plans and runs governed queries; the language model only
words, ranks and suggests — it never computes a number. Every finding keeps its receipt and
passes the existing cross-checker before it can appear.

| Agent | What it tells the user | Exists today? |
|---|---|---|
| Data quality | missing values, N/A placeholders, duplicates, label variants, odd values — with a fix button | yes (extend) |
| Overview | size, time range, main measures and categories in one sentence | partly (brief) |
| Trends | direction, growth, seasonality, best/worst periods | new |
| Drivers | which groups explain a change (root cause, accounting attribution) | yes (contribution) — wire in |
| Segments | biggest gaps between groups, top/bottom performers | yes |
| Unusual values | spikes and outliers, including over time | yes |
| Relationships | what moves together (not cause) | yes |
| Forecast preview | next periods with an honest range, if history allows | yes (quick start) — wire in |
| Opportunities | concrete next steps from the above, labelled as suggestions | yes (next steps) — wire in |

## Technical approach

- **Run agents as parallel jobs** in the existing jobs worker after profiling (Parquet-backed),
  each writing progress events (`working: comparing regions`) and its finding when done.
- **Stream progress to the page** with the existing job-event polling (or Server-Sent Events)
  so cards update live; reduced-motion respected; nothing is invented while waiting.
- **"What you should know" ranker:** server scores findings by size of effect, data coverage,
  user goal and novelty; the model may re-order and pick a headline from server-written
  sentences only (existing narrator rule). Without a model a fixed score is used.
- **Plain-language wording:** every finding has a short sentence, the exact figure, and a
  "how we know" disclosure (query + receipt) for trust.
- **Friendlier interface pass:** fewer menus on the first screen, clear next-step buttons,
  consistent empty states, human wording instead of technical labels, mobile-first cards,
  accessibility checks. Use the ui-ux-pro-max and frontend-ui-engineering skills.

## Phases

1. **Live analyst board + "What you should know"** using the existing analysts, auto dashboard
   and next steps (mostly wiring + UI + progress events).
2. **New agents:** Trends, Drivers wired to contribution, Forecast preview, Opportunities;
   cross-checked findings and action buttons ("See breakdown", "Fix this data").
3. **Friendlier interface pass** across Overview, Ask Syntelio, Data library and Prepare data;
   user testing with the live 12-dataset set; measure time-to-first-insight.

## Rules kept

- No model arithmetic; every number from governed queries with receipts; cross-checker on.
- Correlation and attribution are labelled as such — no causal claims.
- Private by default; findings respect dataset access rules.
- Old saved answers and dashboards reopen unchanged.
