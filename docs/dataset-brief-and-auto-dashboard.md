> **File use case:** Contract for the exact dataset brief and the per-dataset automatic dashboard.
> **What it does:** Lists endpoints, payload versions, tile rules, model limits, storage and known limits.

# Dataset brief and automatic dashboard (October 26, Phase 3 items 1–2)

## Dataset brief — `dataset-brief-v1`

`GET /workspaces/{wid}/datasets/{did}/uploads/{uid}/dataset-brief`

- Built by server tools only, through the shared query executor port (`AnalyticsService`
  snapshot + `QueryExecutor`), so it works for any revision the executor can read.
- Per column (first 40; the rest are listed by name): type, role (confirmed/inferred), unit,
  aggregation rule, `present`, `missing`, `distinct`, `min`, `max`, `sum`, top 5 values, flags
  (`na_placeholders`, `label_variants`, `type_conflicts`, `invalid_dates`, `identifier`,
  `mostly_missing`, `constant`, `high_cardinality`, `has_negatives`). All numbers are exact strings.
- One grouped `COUNT(*) … GROUP BY col LIMIT 1001` query per column gives exact figures for up to
  1,000 distinct values; above that, separate `COUNT`/`MIN`/`MAX`/`SUM` and top-5 queries run and
  `distinct` reads "more than 1000". Each query stores an ordinary receipt
  (`deterministic:dataset-brief-v1`).
- Date coverage: first date column, months with data and up to 12 missing months.
- Analyst finding IDs come from `build_insights` (no model). Up to 3 sample rows; identifier and
  personal-looking columns are withheld.
- Cached in process (LRU, 32 entries) by the snapshot's `sources` (revision, checksums,
  understanding, access policy). The intent router uses a cached brief instead of the old profile
  dump, without sums or values, and tells the model never to quote numbers from it.
- Saved-but-unconfirmed meaning: no statistics are calculated (same rule as discovery).

## Automatic dashboard — `auto-dashboard-v1`

| Method | Path | Purpose |
|---|---|---|
| GET | `…/uploads/{uid}/auto-dashboard` | Own latest version for the current source; builds one if missing or stale. Also lists others' shared latest versions. |
| POST | `…/uploads/{uid}/auto-dashboard/rebuild` | New version (model ranking again). |
| GET | `/workspaces/{wid}/auto-dashboards/{id}` | Open own or shared version (access policy rechecked). |
| PATCH | `/workspaces/{wid}/auto-dashboards/{id}` | `{expected_number, shared?, tiles?}`; owner only, latest version only (409 otherwise). `tiles` (≤9 candidate IDs) builds a new version. |

Candidate tiles (each a governed `MetricRequest` or a cross-checked analyst card):

- Always (safe): `kpi:rows`, `category:{col}` (count by up to 3 categories), `volume:{date}:{grain}`,
  analyst `distribution`/`outlier` cards.
- Confirmed meaning with a fixed unit only: `kpi:{sum|avg}:{m}`, `trend:…:{m}:{date}:{grain}`,
  `top:…:{m}:{cat}`, `share:{m}:{cat}` (sum, no negatives, ≤8 groups), analyst
  `relationship`/`segment` cards.
- Grain from date span: ≤45 days day, ≤180 week, ≤1100 month, ≤3700 quarter, else year.
- Deterministic score (+25 when a column matches the private goal); caps per kind; 6–9 tiles.
- Model (if configured): receives the brief and candidate IDs, returns
  `{"tiles":[{"id","title","reason"}]}`. Unknown/repeated IDs, wrong counts or any number not
  already in the candidate's own title/reason/columns reject the reply; the fixed score is used and
  `selection.fallback_reason` says why. Failed tile queries are dropped and backfilled.

Storage: migration **0034_auto_dashboards** (additive table `auto_dashboards`, one row per version,
`(workspace, dataset, upload, owner, number)` unique; downgrade refuses while rows exist).
`down_revision` is `0031` on this branch; rebase it onto the newest head (0033) when merging, and
keep the readiness check (`infrastructure/readiness.py`) on the final head.

Web: `insights/auto-dashboard.tsx` renders first on the dataset Overview with the ECharts kit,
"Why this dashboard" disclosure, edit/share/rebuild, and "Save as study to pin" (creates an
existing descriptive study, which can then be pinned on a six-pin dashboard).

## Limits

- The brief cache is per process; API and jobs each compute their own copy.
- The overview requests both the dashboard and the analyst overview, so analysts run twice per
  first visit.
- Column names containing reserved query words are skipped (shared SQL guard).

## Dataset purpose — `dataset-purpose-v1` (October 26)

`GET /workspaces/{wid}/uploads/{uid}/dataset-purpose` (member of the workspace; dataset access
policy applies through the same snapshot as the brief; 404 for an unknown upload).

`{"version","summary","benefits":[str],"suggested_questions":[{"title","question"}],
"profile_question":{"question","choices":[str]}|null}` — built by `domain/goal_ranking.py`
without a model. Counts come from the profile; every suggested question routes in chat
(goal ranking, `Which <cat> has the highest average <score>?`, `How many records are there by
<cat>?`; the newest-records question needs the planner model). `profile_question` appears only
for rankable files when the caller has no saved role; choices are role labels whose vocabulary
appears in the file's text. Save the answer through `PUT /workspaces/{wid}/agent-memory` (`role`).

## Goal ranking in chat — `deterministic:goal-ranking-v1`

"If I am a software engineer, which lead is the most hot for me?" / "Which leads are the best
fit for me?" (role from the question, else saved memory role, else private goal; otherwise one
"What do you do?" clarification with clickable role choices). Needs a numeric score-like measure
(score, priority, rating, intent, fit…) and descriptive text columns (URL/contact/id excluded).

- Score: a score named in the question; else the model's suggestion (if enabled); else the single
  total/overall score, disclosed with re-rank buttons for the others; else one score; else a
  clarification listing each score as a clickable full question.
- One governed row query (`query_records`, receipt route above or `<provider>:<model>:goal-ranking-v1`)
  returns the rows ordered by that score. The server keeps rows whose text contains at least one
  persona keyword (persona words plus a fixed role vocabulary plus up to 15 model-suggested
  letter-only words; whole token, or prefix for words of five letters or more), then orders by
  score desc, matched-word count desc, original order. Top 5 are shown with exact values.
- No match: one clarification with role choices found in the returned text.
- The model may only pick listed columns and words; any invalid reply uses the rule above.
