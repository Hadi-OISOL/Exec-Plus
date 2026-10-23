# Bounded conversational agent harness

Implementation contract, October 18, 2026. Release acceptance and measured results are recorded separately in `agent-harness-implementation.md`; this document alone does not establish a deployment.

The application owns authorization, planning contracts, execution and publication. Models interpret language and select presentations of already verified facts. They cannot run arbitrary SQL, shell commands, plugins, network requests or filesystem operations.

## Turn lifecycle

1. Bind the private thread to its actor, workspace, upload, current revision and access policy.
2. Reconstruct bounded relevant task context, pending clarification and authorized result references. Keep saved personal preferences separate from analytical filters.
3. Offer the existing typed capability catalogue and validate the proposed operation and all fields, conditions and units.
4. Execute one supported operation, or at most two independent governed data queries when compound orchestration is enabled. Stop on cancellation, stale context, missing authorization, unsupported dependencies or exhausted budgets.
5. Reuse the ordinary analytical services and their immutable receipts. The language model does not calculate the answer.
6. Optionally construct a bounded factual presentation packet from authorized results and the definitions used by their receipts. Ask the main model to select wording variants and ordering; validate every selected statement and evidence reference.
7. Recheck permissions and versions before publishing the answer. Persist the exact selected presentation with the original evidence.
8. Reopen the receipt and reconstruct its authorized facts before serving a historical presentation. Reject altered text, missing facts, wrong evidence IDs or forbidden source access.

The recorded activity stages describe application operations, not private model reasoning or an invented debate among autonomous agents.

## Feature switches and compatibility

| Setting | Default | Effect |
| --- | --- | --- |
| `EXECPLUS_AGENT_CONTEXT_ENABLED` | `false` | Bounded verified-result context and follow-up handling. |
| `EXECPLUS_AGENT_ORCHESTRATION_ENABLED` | `false` | Two independently validated data-query steps within the existing job budget. |
| `EXECPLUS_AGENT_SYNTHESIS_ENABLED` | `false` | Saved, evidence-checked wording selection with deterministic fallback. |
| `EXECPLUS_AGENT_RETRIEVAL_EXPANSION_ENABLED` | `false` | Conservative English synonym hints for document candidate discovery. |

No migration is required. These switches govern new work; historical answers retain their original receipts. A compound result keeps the existing `mixed` answer kind, uses `coverage=data`, retains the first calculation in `data`, and adds the second in `additional_data`. It does not imply a document search occurred. PDF, Excel and CSV exports include both calculations and original source evidence.

The private VPS composition explicitly opts in through `deploy/vps/agent-harness.env`. It loads the existing private `app.env` afterward, so an operator can persistently override individual switches there without editing credentials or replacing compatible readers. General application and `.env.example` defaults remain off. Activating this composition still requires the recorded release gates.

Turning flags off is an operational fallback for new requests. Already saved compound answers and narratives require the compatible new reader; do not roll back to an older reader that silently omits their second result. Prefer disabling the new paths while retaining the compatible images. Never restore an earlier database over newer user work.

## Facts, language and privacy

Narrative selection is intentionally constrained: the model chooses among application-authored factual variants. It cannot invent a new explanation, change a value or unit, remove a mandatory limitation, add a cause, or perform arithmetic between results. Unsupported, oversized or timed-out presentations retain the exact typed renderer or deterministic wording. A fallback is recorded separately from a successful model selection.

Packets include authorized computed facts, units, scope and evidence IDs. Table follow-up context contains field names, counts, scope and receipt references, not individual record cells. Scalar result context can include its verified scalar value. Document quotations and some grouped result labels can still be sensitive; authorized model context is not anonymization.

Missing fixed units remain explicit. A historical USD result cannot be relabeled EUR by a later definition edit. Counts of records remain distinct from counts of nonmissing values. Extrema retain ties within the existing record limit. Observed cohort differences do not establish causes or intervention effects.

## Boundaries

- The two-step plan supports independent calculations. Result-dependent arithmetic, implicit joins, arbitrary multi-step loops and causal prescriptions remain unsupported.
- Existing forecast, anomaly, scenario and decision panels retain their governed services and prerequisites. This change does not make every panel operation autonomously executable from chat.
- The main provider and local selector remain separately configured; model names are not changed by this implementation. With the new context flag enabled, planning skips the optional local selector after the recorded
  three-case comparison. The legacy context-off path retains it, and dashboard statement selection
  still uses local Qwen. Hosted interpretation and narrative selection use the existing main model;
  no model name changed. This narrow measurement is not general language-quality proof.
- Document expansion improves candidate discovery for a small explicit synonym set. It does not rename columns, establish equivalence, or turn a candidate passage into evidence without the existing quotation checks.
- Operational diagnostics retain fixed outcome codes, route attribution and evidence references. General logs must not contain raw questions, model replies, credentials or uploaded records.
- Private-VPS acceptance is distinct from independent production security, scale and availability acceptance.

## Operator fallback for new turns

Keep the current compatible API/jobs/web images and schema. In the existing private
`/sdb-disk/OISOL_ExecPLUS/secrets/app.env`, set only these nonsecret keys to `false`:

```dotenv
EXECPLUS_AGENT_CONTEXT_ENABLED=false
EXECPLUS_AGENT_ORCHESTRATION_ENABLED=false
EXECPLUS_AGENT_SYNTHESIS_ENABLED=false
EXECPLUS_AGENT_RETRIEVAL_EXPANSION_ENABLED=false
```

Do not replace the file or change credentials. Recreate the two processes under the existing lock:

```sh
sudo flock /run/lock/execplus-maintenance.lock docker compose \
  -f /sdb-disk/OISOL_ExecPLUS/source/deploy/vps/compose.yaml \
  up -d --no-build --no-deps --force-recreate api jobs
curl --retry 10 --retry-delay 2 --retry-connrefused -fsS \
  http://127.0.0.1:18401/health/ready
```

Check worker processing and reopen an existing compound result with both receipts. Disabling
new planning must not erase historical results. These are operator fallback instructions,
not actions performed by this document.

## October 20, 2026 — Ranked plans, model-selected patterns and answer presentation

Measured on the offline farm evaluation (`apps/api/tests/fixtures/harness_eval_farm.json`,
48 questions, on a seeded synthetic 100-row farm table run through the real thread API).
The planner is scripted to reply with the ideal plan for each question. So this measures
what the harness can express, validate and present. It does not measure DeepSeek's
language quality.

| Run | Before (`42da96b`) | After |
| --- | --- | --- |
| Scripted planner, routed to the expected governed outcome | 34 / 48 | 48 / 48 |
| Scripted planner, full pass (chart and 2-3 follow-ups too) | 9 / 48 | 48 / 48 |
| Model disabled (`DisabledLanguageModel`), 27 marked questions | 0 / 27 | 27 / 27 |

Of the 14 routing failures before:

- Seven came from the plan language itself: no ranked groups, no ordered top-N records, and
  no way for the planner to choose the pattern tool.
- Six are offered phrasings that are scripted with no planner reply. At baseline they
  needed a model plan, so they fail in this test. A real model might have planned them, so
  the model-disabled run is the fair measure for these six.
- One is "any unusual rows?", which reached no governed tool.

Before, every model-disabled question ended with "could not complete safely".

### Plan grammar additions (validated server-side; old plans unchanged)

- Numerical: optional `"order": "asc|desc"` (only with `group_by`) and `"limit": 1-1000`
  (only with `order`). SQL orders by the calculated value with `NULLS LAST`, then by the
  group fields, so ties replay identically. The prompt asks for `order` with no limit for
  "which group has the most …", so tied groups stay visible. With an explicit top-N limit, a
  group tied with the last shown group can be left out. Ties are broken alphabetically.
- Rows: optional `"order_by": {"column": "<numeric measure>", "direction": "asc|desc"}`,
  not combinable with `extremum`. Every selected field breaks ties.
- New planner kind `{"kind": "patterns", "columns": [...]}` runs the existing
  `explore_patterns` service, with the same confirmed-meaning, row-filter and receipt guards
  as the deterministic pattern path.
- Job plan bodies leave out unused optional keys, so earlier plans keep their exact shape.

The planner prompt now includes ranking, share, comparison, distribution and scatter rules,
a Roman Urdu/Hindi word hint, and nine few-shot examples. The examples use illustrative
field names and no data values.

### New response fields for the frontend (additive)

Every numerical or record answer body (`kind` absent, or `data` / `additional_data` inside
`mixed`) now has a `presentation` object:

```json
"presentation": {
  "chart": {"type": "bar", "x": "Region"},
  "share_of_total": [{"label": "Yes", "percent": "49.0"}],
  "follow_ups": ["Which Region has the highest average Rainfall_mm?", "..."]
}
```

- `chart.type` is one of `kpi`, `bar`, `grouped_bar` (`x`, `series`, `y`), `pie` (`label`,
  `value`), `line` (date groups), `scatter` (`x`, `y`: exactly two numeric record columns),
  `histogram` (`x`: one numeric record column) or `table`. Pie is chosen only for whole
  count or sum results of at most twelve groups when the question asks for a share,
  percentage or distribution, or asks for a pie. A chart word in the question
  (pie/bar/line/table) is honoured when the result fits it. Ranked results never use pie.
- `share_of_total` lists each group's exact share of the returned total, as decimal strings
  rounded half-up to one place. It is set only for a single-group count or sum with
  non-negative values that is not ranked, and is empty otherwise.
- `follow_ups` holds two or three questions phrased from real, authorized field names that
  the answer did not already use. They are worked out at answer time from the router's
  access-scoped view, saved in the private turn evidence as `follow_ups`, and returned
  unchanged when the answer is reopened. Legacy `/ask` answers return them too. Saved-item
  answers show a chart but no follow-ups. If an access policy later hides a field, a
  follow-up already saved on that same actor's private turn can still name it.

### Offered questions and the offline model

The question templates the application offers itself are planned exactly, with no model
call (`canonical_question` in `domain/intent.py`, route `deterministic:offered-question-v1`).
These come from suggestions, insight actions and follow-ups. They need exact field names:
`What is the <total|average|minimum|maximum|count> of X [by Y]?`, `Show the … of X by Y`,
`What is the average X [by Y]?`, `Show|Compare average X by Y`,
`Which Y has the highest <op> X?`, `Which Y has the most records?`,
`How many records are there [by Y]?`, `Show [all] records where Y equals V`,
`Show the first 10 records`, and `Does X relate to Z?` (pattern scan). Each one still goes
through the same plan validation, governed definitions and receipts as a model plan. Every
generated follow-up is one of these templates, so follow-up buttons keep working when the
model is unavailable.

With `EXECPLUS_LLM_MODE=disabled`, a free-form question used to fail with "could not
complete safely". It now gets a completed clarification with choices that work without a
model. `ModelDisabledError`, a subclass of `ProviderUnavailableError`, makes this distinction.
Hosted provider failures still produce the earlier `failed` turn.

### Offline fallback planner (model disabled only)

`domain/offline_planner.py` runs only when the planner raises `ModelDisabledError`. It never
replaces the hosted model. Route: `deterministic:offline-plan-v1`.

- It matches field names loosely. Every non-unit word of the name must appear in the
  question: "rainfall" matches `Rainfall_mm`, "soil moisture" matches `Soil_Moisture`, and
  "mulching" matches `Mulching_Used`. When several fields match, the more specific match
  wins. A category matched by only part of its name ("irrigation" for `Irrigation_Type`)
  resolves to the single measure that contains that word (`Previous_Irrigation_mm`), so
  "which crop needs the most irrigation?" ranks crops by average previous irrigation.
- It recognises average, total, minimum, maximum and count; grouping words ("by", "per",
  "each", "wise", "which", "vs"); share or percentage wording (count by the category, so
  shares and a pie are returned); ranking words ("highest", "most", "top N"); and
  relationship wording (pattern scan).
- It refuses rather than guesses. Any row restriction ("in", "where", "only", "above",
  …), a stray number, more than one candidate measure, or an unmatched category value
  returns a completed clarification instead of a broader answer. For example, "average
  rainfall in the north" is never answered as the overall average.
- The clarification choices are offered templates built from the matched fields first,
  and then from other real fields. They vary by question.

"Any unusual / weird / odd rows or values", "outliers" and "anomalies" now return a guide
whose action opens the automatic unusual-values scan. This applies with or without the
model, and no confirmed meanings are needed.

## October 22, 2026 — Live multi-dataset evaluation and harness repairs

A fictional account asked 81 realistic questions about 12 generated datasets (retail,
ledger, HR, clinic visits, hourly IoT, survey, inventory, marketing funnel, a messy
semicolon file, a 62-column file, Urdu-script headers and an XLSX) on the private VPS
with hosted DeepSeek, before these repairs. Every job finished (median 8.9 s, max 24.6 s)
and every number that was executed matched an independent pandas check. The failures
were all about *which* calculation ran or how the reply described it:
36 PASS / 16 PARTIAL / 29 FAIL. The account was disabled afterwards. These repairs are
local only; they are not deployed and have not been re-measured live.

### Defect catalogue (live evidence → status in this checkout)

| ID | Observed behaviour | Root cause | Status |
| --- | --- | --- | --- |
| D1 | "North vs South", "Agree or Strongly agree" returned an empty table as a success | Model emitted two equality filters on one field; nothing rejected an impossible AND | Fixed: parser flags `contradictory_filters`, one correction round, then a clarification with working grouped choices |
| D2 | "Monthly trend", "which month", "by year", "weekly" grouped by raw day, often sorted by value | Plan grammar had no calendar grain; trends kept a value ordering | Fixed: optional `period` (week/month/quarter/year), explicit-grain inference, chronological trends, follow-ups inherit the period |
| D3 | Defect rate → `COUNT(*)`; net income → credits only; conversion rate → `SUM(purchases)`; cost per purchase → `SUM(spend)` | Model substituted one aggregate for arithmetic between results | Fixed: derived-measure guard clarifies and offers each part as a working question |
| D4 | Every sum on the messy file blocked: "Group or filter by Units…", even "Total units" | Numeric `Units` quantity treated as a per-row unit-label column | Fixed: numeric `unit`/`units` fields are quantities; text labels, currency fields and explicit mappings keep the guard |
| D5 | Grouped sums/averages never named the leader ("A common confirmed unit is needed…") even though the table was ranked | v2 narrative refused all unit-less rankings | Fixed in new narrative v3 (one field, no unit-label grouping, no per-row unit mapping); v2 answers reopen unchanged |
| D5b | "break it down by age band", "when did they happen?" lost the previous result | Pronoun follow-ups were not recognised as contextual | Fixed: pronoun/"break it down" follow-ups receive prior context and the scope check |
| D6 | "and which region sells the most laptops?" rejected as changing an earlier condition, no choices | Scope check required the old grouping to survive even when it became a filter | Fixed: dropping a group is allowed when it becomes an equality filter or the user names the new grouping |
| D7 | "Is humidity related to temperature?" → "your question also limits which rows" | "related to <field>" read as a row restriction | Fixed |
| D8 | "Any unusual orders?" blocked by pattern readiness | Anomaly wording only matched "unusual values/rows/entries" | Fixed: unusual/abnormal/suspicious/spikes open the automatic scan |
| D9 | Relationship question on inferred data offered only "Finish data review" | Chat patterns need confirmed meanings; the overview does not | Mitigated: guide now also offers the overview relationship card |
| D10 | "SKUs below their reorder point" → "Use a valid numeric filter value" | Field-vs-field comparison unsupported; raw validation message leaked | Message fixed; capability still missing |
| D11 | 0.265 displayed as 0.26 | Half-even display rounding | Fixed in v3 (half-up); v2 wording kept |
| D12 | "Which plant has the highest X?" returned top-5 rows of 62 columns; three tied plants not named | Model chose `order_by` + limit instead of `extremum`; record narrative never names rows | Open |
| D13 | "What should I do / HR focus on / grow sales" → orientation reading or bare refusal | No recommendation tool; refusal offers no clickable next step | Fixed locally: open advice questions run the deterministic analyst team (`insights-v1`) and return 3-5 cross-checked findings as labelled suggestions, each with a clickable follow-up question in `suggestions` (route `deterministic:next-steps-v1`, no model call). Time movers/declining segments are not covered (insights-v1 has no time analyst) |
| D14 | "Which metrics have the most defects?" (compare totals across columns) → count clarification with no choices | Cross-column comparison unsupported | Message fixed: validator text is hidden and clickable working questions are offered (see D24); capability still missing |
| D15 | Forecast questions on unconfirmed files → "Confirm the current data meanings" | Forecasts require confirmed meanings and fixed units by design | Open (by design; zero-config forecast quick start exists only in the panel) |
| D16 | "What are customers complaining about?" → document search with no documents | Free-text field questions routed as `textual` | Open |
| D17 | Model clarification candidates ("Lowest average NPS score") are not clickable | Choices are filtered to real field names | Fixed: the prompt asks for complete questions; options that plan deterministically (`canonical_question`, now incl. "Which X has the lowest …") become buttons, others are dropped and replaced by up to three working questions about the named fields. Clicks run as `deterministic:offered-question-v1`; a stale clarification still refuses |
| D18 | Hourly `2025-03-01 00:00:00` timestamps profiled as text: no daily trend, no forecast | Profiler date detection is date-only | Open |
| D19 | Exact zero serialized as `0E-12` | `str(Decimal)` at the HTTP boundary | Open (cosmetic; receipts unaffected) |
| D20 | "Inventory value by warehouse" → `SUM(on_hand_units)` | Product of two fields unsupported; not caught by the derived-measure words | Fixed locally: optional plan key `times` gives `SUM/AVG(a * b)` (validated at the DuckDB boundary, exact Decimal, overflow errors instead of rounding); quantity x money stays in that currency, money x money and mixed currencies are refused; a named value on a summed quantity clarifies with clickable product choices. Old plans compile to identical SQL |
| D21 | "Weekends vs weekdays" → daily ranking | No weekday grain | Fixed locally: `period` `weekday` (`STRFTIME(date, '%u %A')`, ISO 1 Monday..7 Sunday) and `weekend` (ISO day >= 6), inferred from day-of-week and weekend wording; follow-ups inherit them |
| D22 | "Rows with missing sales" → "The model proposed an invalid filter" | No is-missing filter operator | Open |
| D23 | Quality check missed `Store 1` / `" store 1 "` label variants | Profiler does not compare trimmed/case-folded labels | Open |
| D24 | "Use a calendar period only when grouping by one date field" / "Rank groups with order asc or desc…" shown to users | Plan-validator text was raised as the refusal | Fixed: every plan-parser failure is marked `invalid_plan`, gets one correction round with the validator reason, then becomes a friendly clarification with 2–3 clickable working questions. Social/clarification reply checks and execution-time guards keep their existing messages |

**Live re-run on release f590a4a813287580 (schema 0030):** 36/16/29 → **48 PASS / 22 PARTIAL /
11 FAIL**, 22 questions better, 0 worse; see `verification-live-datasets-20261022.md`.
Confirmed live: D1, D2, D4, D5, D5b (direct follow-up), D7, D8, D11; D3 now never shows a wrong
single number (the model asks which ratio, but its candidates are not clickable). Not confirmed:
D6 (laptop follow-up still rejected). New: D24 "Use a calendar period only when grouping by one
date field" leaks when the model asks for a day period on a text timestamp; D25 a literal `N/A`
in a numeric column (previously hidden behind the Units guard) fails every sum of that column;
D14 now leaks "Rank groups with order asc or desc…".

**Run 3 on release 93d29ec6abe39458:** 54 PASS / 19 PARTIAL / 8 FAIL (8 better, 1 worse
than run 2); see `verification-live-datasets-20261023.md`. Confirmed live: D13, D14 and D24
messages, D17 clickable choices, D18 date-time profiling, D20 `times`, D21 weekday grouping.
New: D26 offered choices are often irrelevant to the question (net income, cost per
purchase, "when did they happen"); D27 "what should I reorder first" varies between plans
(model variance). D21 sums weekdays against weekends instead of comparing per-day averages.
D6, D16, D22 and D25 remain.

### Behaviour contracts added

- **Contradictory filters.** Two `eq`/`ieq` filters on one field with different values
  (case-insensitive for `ieq`) make a plan invalid (`validation_issue =
  contradictory_filters`) for both numerical and record plans. The model gets one
  correction instruction (route suffix `filter-plan correction`). A second failure
  becomes a clarification whose choices are offered templates (`What is the total of
  <measure> by <field>?`, `How many records are there by <field>?`) that run without a model.
- **Calendar period.** `"period": "week|month|quarter|year"` is valid only with exactly one
  grouped date field. SQL is `CAST(DATE_TRUNC(?, "d") AS DATE) AS "d" … GROUP BY ALL`, with
  the period as the first bound parameter; the execution validator allows `CAST` only to
  `DATE` around a `DATE_TRUNC`. Receipts replay the stored SQL unchanged. After planning,
  `with_time_grain` sets the period when the question names exactly one grain (monthly,
  by month, which month, yearly, weekly, quarterly, Roman Urdu mahina/saal/hafta),
  ignoring windows such as "last month" or "over the year". It drops a value ordering for
  trend wording unless ranking words or a limit are present. A contextual follow-up inherits
  the previous period; the previous-turn context says `grouped by <d> per <period>`.
- **Derived measures.** A single numerical plan is not executed when the question asks for
  arithmetic between results: minus/net/difference between/divided by/margin, "X per Y"
  where Y is a measure, or rate/ratio/percentage wording answered by `SUM/MIN/MAX` or an
  ungrouped record count. Averages (a 0/1 flag average is a rate) and grouped counts (shares)
  still run. The clarification offers each part as an offered template.
- **Follow-ups.** "break/split it down", "<it|this|that> by …" and short wh-questions with
  they/them/it/those are contextual. A previous grouping may be dropped when it becomes an
  equality filter or when the question names the new grouping field.
- **Narrative v3** (`verified-narrative-v3`) is used for new answers. It names the leading
  group of a single-field result without a confirmed unit and adds "No unit is confirmed
  for <field>; groups are compared as recorded in that one field." It still refuses to rank
  when grouping by currency/unit-label fields, for joins, or when a confirmed definition maps
  the measure to a per-row unit column. Display rounding is half-up. v1/v2 saved answers are
  rebuilt with their own builders, so their reopen validation is unchanged. The web renderer
  accepts v3.

Tests: `apps/api/tests/test_live_dataset_defects.py` replays the observed hosted plans
through a scripted planner and the real thread, router, DuckDB and receipt services;
`apps/api/tests/test_confirmed_quantity_units.py` covers the units rule;
`apps/api/tests/test_next_steps_products_weekdays.py` covers D13, D20 and D21 against
independent pandas/Decimal results. These are local repairs, not yet re-measured live.
