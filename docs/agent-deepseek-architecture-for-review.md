# ExecPlus agent and DeepSeek architecture — standalone review handoff

> **Purpose:** Give another engineer or Claude enough context to review how ExecPlus understands questions, sends information to its models, runs tools, and returns answers. This describes the implemented system, including its limits, rather than the intended future product.
>
> **Prepared:** 18 October 2026, from local source checkpoint `6bca30e` on `phase2`. Last verified private runtime: release `c34536b8540f7c6d`, schema `0029`, checked on 17 October. This document did not re-inspect the server, call a model, or deploy anything. Runtime configuration below is historical observed configuration, explicitly separated from source defaults.
>
> **Sharing:** Examples are fictional. No real session token, provider key, server address, private source rows, or customer identifiers are included. This file can be read independently of the repository; source paths identify where to inspect further if repository access is later provided.

## 1. What the owner wants, and what exists today

The owner wants a conversational data analyst: understand everyday English/Roman Urdu, remember relevant user context, ask only necessary questions, choose the right analysis, explain actual findings naturally, draw appropriate visuals, and export reports.

**Today, ExecPlus implements a bounded, application-controlled analysis workflow.** It uses language models for certain interpretation and reading tasks. Python services select and execute authorized operations, calculate results, validate evidence, and construct much of the final answer.

It does not currently run an open-ended collection of specialist agents that discuss a problem, repeatedly call tools, inspect their results, and compose a final researched response. A stronger model alone does not expand the allowed tools, context, output contracts, or number of analysis steps.

The current division of responsibility is:

| Part | Actual job |
| --- | --- |
| Next.js browser UI | Select source, collect questions/preferences, submit jobs, display tables/charts/evidence, offer downloads. |
| FastAPI application and worker | Authenticate, build authorized context, route tasks, enforce budgets, dispatch services, validate and save results. |
| Local Qwen selector | Give an advisory route/column hint for some questions; also choose existing dashboard summary evidence statements. |
| Hosted DeepSeek | Propose typed analysis plans, write tightly bounded qualitative dataset readings, draft upload-understanding proposals, select supporting document passages. |
| Analytical services | Perform the actual queries, statistics, forecasts, scenarios and bounded optimization. |
| PostgreSQL and object storage | Retain metadata, permissions, definitions, private context, jobs, evidence and source files. |

“Agent tools” in this document means trusted ExecPlus service operations. It does **not** mean the model has shell access, arbitrary SQL access, downloaded skills execution, unrestricted internet access, or direct database credentials.

## 2. Request architecture

```text
Browser: selected workspace + dataset + upload + private thread
    |
    | question + request_id (existing authenticated session)
    v
FastAPI: create durable job; check ownership, source, queue/allowances
    |
    v
Worker -> ThreadService: reconstruct relevant, authorized prior context
    |
    v
IntentRouterService
    |
    +--> AnalyticsService.describe / descriptive_snapshot
    |      PostgreSQL: definitions, access policy, private goal/memory
    |      Object storage: source file + active transformation revision
    |      Apply row/column scope -> authorized schema/profile/snapshot
    |
    +--> Deterministic route if a supported task/action already matches
    |      diagram / canonical records / patterns / guidance / PDF link
    |
    +--> Otherwise construct context packet
           |
           +--> optional local Qwen route/column hint
           |       invalid hint can be discarded
           |
           +--> hosted DeepSeek: typed JSON proposal
                   |
                   v
           Validate route, fields, filters, scope and bounded plan
                   |
          +--------+-------------------+--------------------+
          |                            |                    |
          v                            v                    v
    Numeric/record service      Qualitative reading   Document retrieval
    or pattern comparison       (separate model call   + model selection
          |                      when needed)          of passage IDs
          v                            |                    |
    Governed query / statistics        |                    |
          +----------------------------+--------------------+
                                       |
                                       v
                    Recheck permissions + source/context versions
                    Save private turn + immutable evidence references
                                       |
                                       v
                    Browser polls job/result -> typed result renderer
```

Important: these branches do not all run for every question. Some finish without any model call. A direct orientation request can enter the qualitative reading path without the main planner. A model-classified orientation can need a planner call followed by a reading call.

The request-activity list represents recorded application stages, such as planning, query execution and evidence verification. It is not a transcript of model reasoning or proof that multiple autonomous agents debated the answer.

## 3. Which model handles which operation

Last verified model configuration on 17 October:

```text
EXECPLUS_LLM_MODE=hosted
EXECPLUS_LLM_SMALL_MODEL=deepseek-v4-pro
EXECPLUS_LLM_LARGE_MODEL=deepseek-v4-pro
EXECPLUS_LLM_SELECTION_MODEL=qwen3:4b
```

These are configured names observed in the deployment; this document makes no independent claim about the provider's model catalogue or model capabilities.

| Operation | Current wiring | What the model can return |
| --- | --- | --- |
| Advisory data selection | Separate selector, SMALL; last verified local Qwen | JSON `route` and existing `columns`, only a hint. |
| Natural-language plan | Main model, LARGE; last verified hosted DeepSeek | One supported typed plan, clarification, or unsupported response. |
| General dataset explanation | Main model, LARGE | Short summary, conceptual field connections, up to two exploration choices. |
| Upload understanding draft | Separate adapter using main provider/models, LARGE | Proposed meaning/role/unit questions; saved answers still take precedence. |
| Supporting-document selection | Main model, LARGE | Passage IDs and supported/missing/conflicting status; not a freely written answer. |
| Dashboard “summary” | **`SummaryService(selector or model)`**, SMALL | One to three existing evidence IDs. With the selector configured, this is local Qwen. |
| Query math, rows, cohort statistics, forecast fitting, scenario math, allocation | Server analytical services | Verified computed results, without delegating the arithmetic to DeepSeek. |
| Chart rendering and PDF/Excel generation | Frontend/server renderers | Render existing authorized results; no model required to generate the file. |

**There is no current fast-DeepSeek-versus-pro-DeepSeek specialist team.** Both main tiers point at the same configured name in the last verified release. Tier selection and a separate selector are routing mechanisms, not multiple persistent agent personalities.

Source: `apps/api/src/execplus/bootstrap.py::build_runtime`, `build_language_model`, `build_selection_model`.

## 4. Where the agent's knowledge comes from

### 4.1 Source data and confirmed meaning

Uploaded/imported tables are retained in object storage. Profiling and safe transformations produce versioned metadata and an active revision. The application reconstructs that revision when reading the data.

The model-facing view combines:

- Visible column names and types.
- Eligible metrics and dimensions.
- Saved definitions: row meaning, domain, description, roles, meanings, units/currencies and declared metric rules.
- Profile facts such as row/column counts, missing cells, conflicts and date boundaries where the specific path includes them.
- Dataset-level row and column restrictions, applied **before** the model context is assembled.

Confirmed definitions override guesses based on names. Definitions attached to a different revision can become `needs_review`. Unknown units do not become percentages, currencies or physical units simply because the model guesses them.

`AnalyticsService.descriptive_snapshot` loads the source and definitions, applies `scope_snapshot`, obtains private context where permitted, and rechecks source authorization. Restricted views do not receive the dataset-private goal or reading notes; supporting-document search and upload brief require full dataset access. Row restrictions also affect what profiling information can be safely shown.

### 4.2 Three different kinds of saved context

| Context | Scope and use |
| --- | --- |
| Business definitions | Shared, versioned dataset meaning, governed by confirmation rules. Used to validate calculations. |
| Private dataset goal / authorized reading notes | A private goal and source notes that may be owner-private or explicitly shared. Can help interpret the request; cannot override confirmed meaning or permissions. |
| “My memory” | Explicit actor-and-workspace-private `role`, `focus`, and `explanation_style`. Used for qualitative wording/suggestions; not automatic facts or numerical filters. |

The application does not train or fine-tune DeepSeek on these records. It serializes selected context into each relevant request.

## 5. Exactly what leaves the application in model requests

“Not sending the whole CSV” does **not** mean “sending no data.” Field labels, definitions, category values, notes, document passages, questions and some computed statements can themselves be sensitive.

| Call | Included context | Excluded or bounded context |
| --- | --- | --- |
| Local advisory selection | The assembled planner context plus the question. | Not merely the column list: it can include goal, notes and prior structured task context. Same context construction as the main plan, before its selection hint is appended. |
| Main DeepSeek planning | Capability catalogue; visible schema; saved definitions; compact profile; private goal if available; relevant structured prior context; accessible document names; bounded recent reading notes; eligible recorded category labels; question; optional selection hint. | No entire table dump, unrestricted database, full conversation transcript or query result history. Planner does not directly receive `AgentMemory.context()`. |
| Dataset qualitative reading | Question; definition status; saved description/grain; first 80 visible fields with saved definitions; exploration catalogue; private goal; explicit personal memory; authorized reading notes. | No raw source rows, full numerical distribution or newly computed correlation results. Marks columns truncated above 80. |
| Upload-understanding draft | Profile metadata for up to 80 columns, saved meanings/units, role/grain suggestions, explicit personal memory. | Optional source samples only when `data_brief_sample_values > 0`; details below. |
| Document selection | Search question and up to five authorized passages, each with a local alias, text and document name. | Not the entire document collection; no internet search. Returns at most three selected IDs. |
| Dashboard summary selection | Already computed, server-authored evidence sentences under aliases such as `E1`. | No full dataset, transcript, private memory or freeform user question in this call. Model cannot author new summary claims under its contract. |

### 5.1 Planner packet detail

`IntentRouterService._describe_view` includes all visible column names/types, metric/dimension lists and the saved definition object. Unlike the qualitative reading, this schema description is **not limited to the first 80 columns**. The HTTP request byte limit is the final transport bound; there is no token-aware context packing here.

`_describe_profile` includes row/column counts and at most 12 relevant column entries: fields with missing values, type conflicts, invalid dates, date types, or at most one distinct value. It also reports whether those entries were truncated. This is a selected quality/structure summary, not comprehensive EDA.

`_category_context`:

1. Matches question tokens/explicit field mentions against visible text dimensions, excluding identifier-tagged columns.
2. Considers at most eight matching category fields.
3. Includes a field's sorted nonblank values only if it has at most 12 distinct values and no encountered value longer than 200 characters.
4. Omits the whole field's value list if those bounds are exceeded; it does not claim a partial list is complete.

This helps map “harvest stage” to an actual recorded label. It is based on name/token matching, not a general semantic value search. A high-cardinality field or paraphrase with no field-name overlap may therefore provide the planner much less grounding.

Reading notes come from the upload-specific `data-reading-<upload-prefix>.md` documents visible to the actor. Selection uses at most three chunks from the newest matching documents; prompt text is capped at 1,500 characters per chunk. This is **recent-note selection**, not query-ranked retrieval over every saved note.

### 5.2 Optional upload samples

Source default: `EXECPLUS_DATA_BRIEF_SAMPLE_VALUES=0`. The current live value was **not inspected for this document**.

When enabled, `domain/data_brief.py::sample_values` supplies up to the configured 1–20 most common values per field and the first three example rows. Individual values are truncated to 40 characters, and the model packet includes only its first 80 columns.

Identifier roles and a name-pattern list (email/phone/address/account/name and related terms) are replaced with `(withheld)`. This is a heuristic, **not comprehensive sensitive-data detection**. Definitions, questions and notes are not made non-sensitive by that sample mask. No claim of universal anonymization is appropriate.

### 5.3 No hidden access to other knowledge

DeepSeek does not directly query PostgreSQL, read object storage, browse websites, search arbitrary files, or inspect all users' history. Its input is whatever the relevant service puts in `ModelMessage.content`.

Downloaded development skills, REA, UI design references and chart templates are not automatically included in runtime prompts. Curated EDA/SQL guidance is adapted into a small application-owned reading catalogue. Actual charts reuse bundled rendering components/templates; this does not grant a model new analysis capabilities.

## 6. The actual HTTP request to the provider

`application/contracts.py` defines a provider-neutral `ModelRequest(messages, tier, temperature=0.0)`. `OpenAICompatibleLanguageModel.complete` resolves the tier to a configured model and performs:

```text
POST <configured base URL>/chat/completions
Content-Type: application/json
Accept-Encoding: identity
Authorization: Bearer <server-held key, only when configured>
```

Illustrative body, with abbreviated fictional content:

```json
{
  "model": "<configured large model>",
  "messages": [
    {
      "role": "system",
      "content": "Classify the request and return a supported JSON plan. Never calculate the answer. Use exact visible fields; preserve conditions."
    },
    {
      "role": "user",
      "content": "Metrics: moisture\nDimensions: stage, crop\nSaved definitions: <authorized definitions>\nObserved category values: stage=[Growing,Ready]\nQuestion: How many records are at Ready stage?"
    }
  ],
  "temperature": 0.0,
  "max_tokens": 1024
}
```

The value `1024` above is the source default, not a newly verified live setting. Configured JSON mode adds `"response_format":{"type":"json_object"}`; configured reasoning effort adds `reasoning_effort`. The selector is explicitly built with JSON mode, 512 output tokens and reasoning effort `none`.

There are **no provider `tools`, `tool_choice` or `tool_calls` fields**. The model returns JSON in `choices[0].message.content`; Python parses it and dispatches a trusted operation. No provider-managed conversation ID is used. Each HTTP attempt constructs a new client; conversation context is assembled by ExecPlus.

Byte limits: 1 MiB serialized request and 2 MiB response. The adapter streams response bytes into a bounded buffer; that is transport reading, **not token streaming to the chat UI**. Non-identity compressed responses are refused. Input tokens are not counted in advance by a tokenizer, and byte limits do not establish compatibility with a model's context window.

## 7. Routing and tool selection

The main planner prompt supports these response kinds:

| Kind | Meaning / execution |
| --- | --- |
| `numerical` | One measure with `sum`, `avg`, `count`, `min` or `max`, optional grouping and filters. |
| `rows` | Bounded visible records, optional filters and a min/max extremum. |
| `overview` | Orientation, quality, structure, next steps, or up to three named field explanations. |
| `diagram` | Map fields within the selected file; no inferred join or causal diagram. |
| `cohort_comparison` | One exact category value versus the other nonmissing values. |
| `textual` | Search supporting documents and select quotations. |
| `mixed` | One data operation plus one document query; neither silently replaces the other. |
| `ambiguous` | Ask for a missing decision/input. |
| `unsupported` | Explain that the requested plan is outside supported scope. |

Before that model call, the router also has deterministic branches: canonical comparison/record buttons, recognized structural diagrams, explicit pattern/group-relationship requests, advanced-analysis guidance, and recognized explanations/acknowledgements. These branches can bypass the model planner. The exact ordering matters: an early heuristic can decide what the request means before DeepSeek sees it.

The selector only knows `overview`, `numerical` and `rows`, and accepts up to 24 known column names. Its hint is advisory. The main planner can select a richer kind. An invalid hint is ignored and noted in the route string; it does not become an executed plan.

`domain/intent.py::route_response` parses the returned JSON. It rejects unknown fields/metrics, invalid aggregations, unsupported filters and malformed shapes. Query plans allow up to 10 grouping fields and 20 filters. Row requests default to 100 records and allow at most 1,000. “All” in this contract means a bounded result, not an unbounded download.

The versioned `AnalysisPlan` lists allowed operations, dependencies, sources, output kinds and verification policies. It describes a bounded workflow assembled by the application, not a model-authored arbitrary program. At most one data-query stage and one document-retrieval stage are permitted in the durable conversation budget.

### Existing analytics are broader than the chat planner

Forecasting, anomalies, scenarios, allocation, consolidation and other product features have separate server services and UI/API entrypoints. Their existence does not mean a chat request can autonomously combine all of them.

For example, the conversation's `analysis_guidance` can explain prerequisites and offer an action into an analysis panel. It is not a generic agent that invents scenario formulas, fits an arbitrary model, opens another tool, evaluates it and returns a final recommendation in the same turn.

## 8. How numbers become trusted answers

For a supported numerical/record plan:

1. Reconstruct the authorized source revision and apply the current dataset access policy.
2. Apply confirmed semantic rules, units and required filters through the governing services.
3. Generate a bounded parameterized SQL statement from the typed plan. The model does not write executable SQL in this route.
4. Parse/validate SQL again with the narrow allowed grammar. Require authorized snapshot tables, bound values and a read-only operation.
5. Execute against an in-memory DuckDB snapshot, with external access, extension auto-install/loading and disk spill disabled.
6. Retain query/source/definition references, parameters, counts, checksums and an execution receipt.
7. Recheck current access/source state before publishing or reopening the result.
8. Render the exact result and evidence. Scalar assembly checks that result/query IDs and analyzed-row counts agree.

Decimal input is validated rather than silently rounded or skipped. Decimal precision and average handling use explicit server arithmetic; JSON serialization preserves Decimal values as strings and protects large integers. Statistical methods have their own documented rounding/method limits. “Verified” means evidence and computation checks passed, not that source data is representative or that an association is causal.

Source query defaults: 15 seconds, 256 MiB, one DuckDB thread, at most 200,000 input rows and 2,000,000 input cells. Executor result limit is 100,000; normal planned aggregates have a separate default 10,000-row limit, while chat record requests cap at 1,000. Configuration can tighten these limits. These are distinct controls, not promises that every method accepts the maximum input.

**The standard numerical answer does not go back through DeepSeek for a rich final explanation.** `AnswerAssembler`, API serialization and typed frontend renderers construct it from evidence. Similarly, cohort results are presented from their computed result contract. This is a major reason the experience can feel less conversational than a general chat agent.

## 9. Three examples using fictional data

Assume visible fields `record_id`, `crop`, `stage`, `moisture`; `Ready` is an observed stage label. These examples explain contracts, not findings about the user's uploaded file.

### A. “How many records are at Ready stage?”

Expected proposal:

```json
{
  "kind": "numerical",
  "plan": {
    "metric": "*",
    "aggregation": "count",
    "group_by": [],
    "filters": [{"column": "stage", "operator": "eq", "value": "Ready"}]
  }
}
```

`COUNT(*)` counts matching records even if unrelated cells are missing. `COUNT(moisture)` would instead count nonmissing moisture values. Neither means distinct crops. The application must not silently substitute one meaning for the other.

A follow-up such as “And Growing?” can receive the previous structured count/filter context. If a preceding clarification exists, the packet contains its original question, clarification, latest reply and recognized choices.

### B. “Maximum moisture is of what?”

Expected proposal:

```json
{
  "kind": "rows",
  "plan": {
    "columns": [],
    "filters": [],
    "limit": 100,
    "extremum": {"column": "moisture", "direction": "max"}
  }
}
```

The server returns the record(s) attaining the maximum, retaining ties within the row limit. Empty `columns` means all currently visible fields. A request for only the maximum number uses the numerical route instead. Required filters still apply; missing values are not maximum contenders.

### C. “What is different about Ready-stage records?”

Expected proposal:

```json
{
  "kind": "cohort_comparison",
  "target_column": "stage",
  "target_value": "Ready",
  "columns": []
}
```

The comparison service uses up to 10,000 matching rows, 12 eligible measures and three additional text categories. It computes group counts, nonmissing coverage, means, medians, differences, standardized ordering and category shares. Numeric comparisons require fixed confirmed units and at least five present observations per side and 20 total. Sparse results remain explicit.

This tool does not establish what **caused** readiness or how an intervention would change another crop. The other group is all other nonmissing labels, not an arbitrarily specified second cohort. Extra filters/time windows need a supported prepared source or clarification. No calibrated time-to-harvest prediction or agronomic recommendation is created from the label alone.

## 10. Conversation memory and where continuity can be lost

`ThreadService.run_turn` reconstructs selected context from private saved turns:

- Previous executed metric/aggregation/grouping/filters, rather than all old prose.
- A previous document-search question when relevant.
- The latest guide and pending clarification.
- An authorized previous cohort **request and source references**, not its entire computed result.

It stops carrying an old calculation across completed new orientation/field explanation, diagram and pattern tasks. This avoids an unrelated old calculation contaminating a new task. It also means users expecting every prior fact to remain conversationally available can encounter a boundary.

The latest explicit question takes precedence. New orientation can use the current source; a stale continuation cannot quietly reuse old definitions. Source, definition and access versions/checksums bind context to the data it described.

For an explicit “explain again/make it simpler” continuation, a qualitative reading may receive up to 3,500 characters of the previous guide. This is allowed only when its digest matches current sources, private goal, reading notes and memory revision. That prose is explicitly untrusted context.

Persistent personal memory is deliberately small: role up to 300 characters, focus up to 500, style `concise` or `step_by_step`. It requires explicit saves; it is not inferred from every conversation. Forget changes future use, while immutable historical answers can remain readable. Current reading context checks prevent forgotten/edited preferences from being reintroduced through old guide prose.

Important distinction: the general planner receives a dataset-private goal and notes but does **not** directly receive the personal-memory object. Personal memory is supplied to qualitative readings and upload-understanding drafts. There is no single unified memory packet shared identically across all tasks.

## 11. Reading, retrieval and summaries are different pipelines

### General dataset explanation

The reading contract requires exactly `summary`, `connections`, and `explore`. Summary length is at most 360 characters; one to three connections each use one to six supplied fields with at most 200 characters of meaning; zero to two exploration choices are allowed.

It explicitly forbids invented findings, numeric claims, correlations, causes, prescriptions and pretending to have read rows. Parsing rejects unexpected shapes, unsupported fields and prose containing digits (after removing known field names), links, markup or control characters. Suggestions are rendered into executable questions only after meaning/unit readiness checks.

This intentionally describes what the file appears to contain and what could be explored. It does not secretly perform EDA and summarize its results. A request to “understand the data” and a request to “find measured patterns” enter different mechanisms.

### Supporting-document retrieval

`KnowledgeService` searches documents the actor can access in the selected dataset, with full dataset access required. It refuses collections above 20 documents for this path; search questions cap at 500 characters. Passage checksums and current authorization are verified.

Supported documents here are UTF-8 TXT/Markdown, at most 1 MiB each. Chunks are at most 1,000 characters and start every 900 characters, giving 100-character overlap. The five candidate passage texts therefore occupy at most approximately 5,000 characters, plus names, the question and instructions. This is separate from table ingestion and does not imply arbitrary PDF/document parsing in this retrieval path.

`ReferenceHybridRanker` combines lexical overlap with local 128-bucket hashed token-count vectors and reciprocal-rank fusion. It is **not a learned semantic embedding model**. Passages with no lexical overlap are excluded. `vector_mode` currently accepts only `disabled`; no external vector database is wired into this runtime.

Five candidate passages are sent to the main model. It chooses at most three IDs and `supported`, `missing` or `conflicting` coverage. The server returns the original authorized quotations. It does not ask DeepSeek to write an unconstrained explanation combining them. A mixed answer keeps calculated data, quotations and limitations separate.

### Dashboard summary

`statement_bank` creates exact sentences such as `sum of revenue: 100.25.` from executed cards, aliases them `E1`, `E2`, and asks the model for only:

```json
{"evidence_ids": ["E1", "E2"]}
```

The service verifies one to three distinct valid IDs and concatenates the original sentences. It cannot produce a rich “why this matters” narrative under that output contract. With the last verified selector configured, this step uses local Qwen.

## 12. Corrections, failures, latency and budgets

| Layer | Implemented bound / behavior |
| --- | --- |
| Question input | Up to 500 characters. |
| Durable conversation job | Default 100-second wall budget, 20 MiB source-input bound, at most four plan steps, three logical model calls, seven provider attempts, one query stage and one retrieval stage. |
| Main plan generation | Initial proposal and optional count-plan correction share 40 seconds. |
| Qualitative reading | At most two LARGE calls sharing 40 seconds; accepted response text at most 32,000 characters before schema parsing. |
| Document evidence selection | 40-second enclosing deadline. |
| Main provider adapter | 60-second HTTP timeout, up to three attempts. Outer task deadlines can cancel it sooner. |
| Upload brief adapter | 120-second HTTP timeout, output-token default 4,096; enclosing qualitative deadline is still 40 seconds. |
| Local selector | 20-second HTTP timeout, one attempt, 512 output tokens. |
| Main output setting | Source default 1,024 output tokens, configurable up to 8,192. Live value not rechecked here. |

Durable-job counters apply when that execution context is active. Standalone summary/upload-brief endpoints still use provider accounting, but do not automatically inherit every durable-job counter.

The adapter retries transient HTTP 429/500/502/503/504, transport/timeouts and malformed response bodies, with 0.5- and 1-second backoffs. Other HTTP failures stop retrying. Truncation (`finish_reason=length`), oversize/compression failures and cancellation stop that adapter call.

A qualitative validation failure or truncation can trigger one fresh application-level correction, using the original messages plus a trusted error-specific instruction. The rejected answer is not appended as authoritative context. Freshness is checked before retry. If this still fails, the UI receives an explicit notice and deterministic saved-information guidance; it is not presented as successful AI interpretation.

The planner has a **narrow count-plan repair**, not a universal self-correction loop for every invalid plan. Other unsupported fields/shapes/conditions can still become a clarification or refusal. Selector failure can fall through to the main planner, but still costs time and can consume a logical call.

Jobs have idempotent request identifiers, leases, retries/recovery, cancellation and independently authorized status/result endpoints. A user-visible completed job can represent a completed clarification rather than a successful calculation. A worker retry is not the same as another reasoning agent.

## 13. Usage accounting and observability

Each model attempt is attributed to actor, workspace, operation and a fixed category such as conversation, data reading, document answer or summary. Reservation/dispatch happens before sending; settlement tracks reported usage and outcome. Workspace locking prevents concurrent allowance bypasses. Retries are separately accounted attempts.

Admission/accounting-storage failure prevents dispatch. Settlement failure prevents publishing an otherwise successful provider reply, so a successful HTTP call alone does not establish a successful user answer. Without a configured usage policy there is no additional policy allowance cap; global job/compute/transport limits still apply.

Provider-reported input/output/cache token counts are used only when valid. Configured prices produce estimates, not invoices. Unknown usage is not silently recorded as zero. The reservation amount is configured exposure, **not a proven token/cost upper bound**. Byte limits and allowances should not be described as exact provider spending caps.

Model accounting stores operational metadata, not raw prompts, rows, generated content or provider keys. Qualitative logs record fixed validation/failure codes. Conversation/evidence storage still retains user questions and authorized results; “logs omit prompts” is not the same as “the app stores no user data.”

Useful diagnostic records include job IDs/events, source/definition/access references, typed plan/checksum, turn kind/status, validation issue codes, query receipts and provider-attempt records. Avoid adding raw customer prompts/replies to general logs to improve diagnosis; synthetic replay fixtures or explicitly controlled redacted diagnostics are safer.

**Known attribution limitation:** `IntentRouterService._compare_cohort` returns `model_route="deterministic:cohort-comparison-v1"` even after a hosted planner chose that tool. That field identifies the final computation, not the entire planning route. Do not infer “DeepSeek was never called” from that route alone; correlate job/provider accounting. This documentation does not repair that limitation.

## 14. What has been fixed versus what deserves review

### Reported defects already repaired in the last verified release

- Generic menus for valid general-understanding questions: the overview acceptance/dispatch contradiction was repaired. General orientation no longer inherently requires a metric.
- Crop-stage record counts rejected as unsupported metrics: explicit `*` record counting and bounded count correction were added; named-field nonnull counts remain distinct.
- “Maximum soil moisture is of what?” unnecessarily asking scalar-versus-group-versus-record: planner guidance and a typed extrema record query now support the intended records, including ties.
- Selected-outcome comparison: a registered cohort tool now computes governed observed differences, with source-bound follow-up context and protected exports.

These repairs passed named tests and selected hosted checks. They do not establish broad natural-language accuracy or prove that every paraphrase works.

### Current design constraints and concrete review leads

| Item | Established fact | What Claude should investigate |
| --- | --- | --- |
| Limited orchestration | One bounded typed route; no general tool-result/replan loop; one data-query stage. | Can a small evidence-preserving multi-step planner answer realistic compound questions without arbitrary execution? |
| Restricted final synthesis | Numerical/cohort answers use typed renderers; summaries concatenate selected statements; documents return quotations. | Could an evidence-linked explanation layer improve natural language without changing or inventing computed claims? |
| Uneven context | Planner, reading, summary and brief receive different packets; prior cohort results are not passed into the next planner. | Which genuine follow-ups fail because relevant verified result context is absent? |
| Heuristic routing | Several recognizers run before the main model, and cohort/filter boundaries use bounded language checks. | Test unseen English/Roman Urdu, negation, pronouns and compound conditions; do not remove safe refusals merely to increase answer rate. |
| Category grounding | Name/token overlap; at most 12 distinct values per eligible field. | Do unfamiliar aliases or larger categories cause unsupported values or unnecessary clarification? |
| Retrieval quality | Local token overlap/hash ranking, excluding zero-overlap passages. | How often do synonyms or paraphrases miss relevant authorized notes/documents? |
| Qualitative limitations | Metadata-only explanation, narrow output schema and digit/markup validation. | Is factual useful prose being rejected or over-constrained, and can typed evidence support richer explanations? |
| **Conflicting upload prompt** | `data_brief.SYSTEM_PROMPT` says “you never see row values”; enabled samples append instructions saying example values/rows are supplied. | Resolve this contradiction in a future tested change; do not claim samples are metadata-only. Impact depends on whether sampling is enabled. |
| Prompt size | Planner includes full visible schema/definitions; no input tokenizer. | Measure prompt tokens, truncation and output completeness on wide datasets using synthetic inputs. |
| Serial model calls | Optional local selection, hosted planning and a later reading/document call run within small shared budgets. | Measure whether the selector improves decisions enough to justify latency and budget use. |
| Provenance visibility | Final cohort route overwrites upstream planner route in that field. | Preserve both planning and execution attribution without storing private prompt text. |
| Safety versus semantics | A valid schema/SQL plan proves executability, not that it matches every nuance of the user's language. | Build semantic regression cases where dropped conditions, wrong populations or wrong count meaning would produce a plausible but wrong result. |

**October 22 live evidence for the "Safety versus semantics" row.** On 81 questions over
12 fictional datasets the hosted planner produced several executable but wrong plans:
two equality filters on one field for "A vs B" (empty result), a single aggregate for
rates/differences ("conversion rate" → sum of purchases, "net income" → credits only),
and raw-day grouping for "monthly"/"which month". No executed number was arithmetically
wrong. Deterministic post-plan checks for these three classes, a calendar `period`, pronoun
follow-ups and narrative v3 are in the local checkout (not deployed); the full catalogue
and remaining open classes are in `agent-harness.md` (October 22 section).

These are review questions and source-observed constraints, not proof that a particular new user failure has occurred. Do not attribute every refusal to DeepSeek; it may originate in routing, context construction, semantic validation, readiness checks, budget exhaustion or rendering.

## 15. Suggested diagnosis using fictional data

First identify **which boundary failed**, rather than changing model names immediately:

1. Confirm the selected upload/revision, definitions, visible fields and private thread.
2. Determine whether a deterministic branch ran or the model planner ran.
3. Inspect the synthetic/redacted input packet: was the needed definition, category label or prior task present?
4. Compare the typed proposal with the intended operation, population, filters, units and result type.
5. Distinguish schema rejection, missing user input, provider truncation, deadline, usage limit and unsupported tool scope.
6. Verify executed calculations and provenance independently of the wording.
7. Check whether the UI's result type can express the requested explanation/visual, even if the backend result is correct.

Recommended regression matrix:

| Scenario | Expected behavior |
| --- | --- |
| “What is this data about?” and informal paraphrases | Current-context qualitative explanation, not a request to name a metric. |
| Count records with unrelated missing values | `COUNT(*)` agrees with matching records. |
| Explicit count of a named field | Excludes missing values; does not imply distinct entities. |
| “And Growing?” after a stage count | Retains count intent and changes the intended category condition. |
| Highest record with ties and a filter | Returns all eligible ties within limits; same filter inside/outside extremum. |
| “Why did Ready records get there?” | Measured differences if supported, explicit causal limitation, no invented intervention advice. |
| Extra time/region condition on cohort tool | Preserve supported scope or clarify; never silently drop it. |
| Synonym-only supporting-document question | Measure retrieval miss rate; distinguish no evidence from no lexical match. |
| New task followed by a short reply | Old calculation must not reappear incorrectly. |
| Forget memory or change definitions during reading | Freshness guards prevent stale context publication/reuse. |
| Restricted user requests hidden fields/results | No leakage via model prompt, profile, result, saved answer or export. |
| Wide schema / truncated reply / unavailable selector | Explicit bounded behavior, preserved request intent and truthful fallback. |

Existing tests relevant to these boundaries include `test_intent.py`, `test_intent_router_integration.py`, `test_threads_integration.py`, `test_dataset_reading.py`, `test_data_brief.py`, `test_reading_corrections.py`, `test_reading_recovery.py`, `test_agent_memory.py`, `test_cohort_conversations.py`, `test_cohort_scope_boundaries.py`, `test_summary_guard.py`, `test_model_transport_limits.py`, and `test_usage_provider.py`, under `apps/api/tests/`.

Repository tests use pytest with `apps/api/src` configured as the Python path. Integration suites require the documented isolated test services; never point them at the live database. Offline/fake-provider tests establish contracts, not hosted-model language quality. Use a separate authorized synthetic evaluation for that measurement.

Historical evidence: `docs/verification-harvest-language-repair.md` records 442 distinct affected backend/architecture cases, 63 frontend tests, nine targeted browser journeys, and four hosted natural-language checks. This was a focused release gate, not a fresh full-repository run. The four hosted checks took 83.551 seconds combined, not an average per-question latency benchmark. No tests or hosted calls were rerun merely to write this document.

## 16. Source map for an engineer with repository access

All paths below are relative to repository root. Under `apps/api/src/execplus/`:

| File / symbol | Responsibility |
| --- | --- |
| `bootstrap.py::build_runtime` | Concrete wiring; especially `SummaryService(selector or model)`. |
| `bootstrap.py::build_language_model`, `build_selection_model`; `config.py::Settings` | Provider/tier configuration, defaults and limits. |
| `application/contracts.py::ModelRequest`, `ModelResponse` | Provider-neutral message/result contracts. |
| `infrastructure/models/openai_compatible.py::complete` | Actual HTTP body, retries, response parsing and transport caps. |
| `infrastructure/models/accounting.py::AttemptAccounting` | Per-attempt admission and settlement. |
| `application/services/usage_metering.py`; `application/usage_context.py` | Actor/workspace usage attribution and allowance enforcement. |
| `presentation/routes/jobs.py`; `application/services/jobs.py::JobService`, `JobProgress` | Durable submission, progress, cancellation, limits and results. |
| `application/services/threads.py::run_turn`, `publish`, `resolve` | Private history selection, evidence storage and authorized reopening. |
| `application/services/intent_router.py::_SYSTEM_PROMPT`, `ask` | Task contract, early branches and main dispatch. |
| Same file: `_describe_view`, `_describe_profile`, `_category_context`, `_selection` | Exact planner context and local hint. |
| Same file: `_interpret`, `_overview`, `_compare_cohort`, `_execute_data` | Reading, comparison and numerical execution paths. |
| `domain/intent.py::route_response`; `domain/conversation_requirements.py` | Typed proposal validation and contextual/conflicting request checks. |
| `domain/agent_capabilities.py`; `domain/analysis_plan.py` | Trusted operation catalogue and bounded workflow plan. |
| `application/services/analytics.py::descriptive_snapshot`, `_execute`, `_execute_rows` | Authorized source/meaning assembly and execution. |
| `application/services/dataset_access.py`; `domain/dataset_access.py` | Server-enforced dataset policy and source authorization. |
| `domain/semantics.py::plan_query`, `plan_rows`; `infrastructure/query/validation.py` | Typed SQL construction and independent grammar checks. |
| `infrastructure/query/duckdb_executor.py`; `application/services/answers.py` | Actual query evaluation and exact answer assembly. |
| `domain/dataset_reading.py::reading_input`, `parse_reading`, `render_reading` | Dataset explanation input, validation and presentation. |
| `application/services/structured_reading.py::read_validated` | One bounded qualitative correction and fallback reasons. |
| `application/services/data_brief.py`; `domain/data_brief.py` | Upload reading, optional sampling, proposal validation and saved-answer preservation. |
| `domain/agent_memory.py`; `application/memory_context.py` | Explicit private preferences and context-use tracking. |
| `application/services/knowledge.py`; `infrastructure/knowledge.py::ReferenceHybridRanker` | Authorized local passage retrieval. |
| `application/services/document_answers.py::answer` | Model selection and revalidation of supporting citations. |
| `application/services/summaries.py::statement_bank`, `compose` | Exact statement-bank summary selection. |
| `domain/reading_catalog.py` | Curated EDA/SQL exploration recipes, not an executable skills loader. |
| `domain/cohort_comparison.py`; `application/services/patterns.py` | Governed selected-group descriptive comparison. |

Frontend entry points: `apps/web/src/app/workspace/ask-panel.tsx` submits/polls jobs and displays recorded activity; `pattern-results.tsx` renders pattern/cohort evidence; `page.tsx` coordinates workspace/source and analysis panels.

Useful existing design/verification documents: `docs/decisions/architecture.md`, `docs/conversation-harness-repair.md`, `docs/domain-agent-tools.md`, `docs/personal-agent-studio.md`, `docs/harvest-language-repair.md`, `docs/verification-harvest-language-repair.md`.

## 17. Review request to give Claude

> Review the implemented architecture described above against our goal: a grounded conversational data analyst that understands everyday language, uses the correct authorized tools, remembers relevant context, and explains results naturally.
>
> Separate confirmed design limitations from suspected bugs and from features not implemented. Trace a failure through context construction, route selection, validation, execution and rendering before blaming the model. Identify missing evidence you would need from source or synthetic traces.
>
> Prioritize the smallest changes that improve context continuity, tool selection, semantic correctness and evidence-backed explanation. If proposing an orchestrator or specialist models, define their exact input/output contracts, allowed tools, stop conditions, budgets and regression tests. Explain why each additional model call earns its latency/cost.
>
> Preserve tenant/private boundaries, confirmed definitions, units, required filters, exact calculations, immutable evidence, explicit memory saves and honest uncertainty. Do not solve refusals by bypassing validation or fabricate causal advice. Do not assume full chat history, learned embeddings, arbitrary code execution or provider function-calling already exist.
>
> Return: (1) an architecture diagnosis, (2) ranked issues with source references and confidence, (3) concrete staged improvements, (4) regression/evaluation cases, and (5) open questions requiring runtime evidence. Do not request real session tokens, provider keys or customer data.
