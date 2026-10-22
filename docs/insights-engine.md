> **File use case:** Contract and design record for the automatic analyst-team overview.
> **What it does:** Defines the `insights-v1` payload, its analysts, cross-checks, narration and bounds.

# Insights engine (analyst team)

`GET /workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/analyst-overview`
(not `/insights`: that older path belongs to the activation insights list and is unchanged)
returns a structured overview for the overview screen. It runs on request (the
frontend calls it when the overview first opens, next to `/discovery`), applies
the same permission-scoped snapshot, saved-meaning gate and final source-freshness
recheck as discovery, and stops work when the browser disconnects (HTTP 499).

## Pipeline

1. **Field selection** reuses discovery's measure/category rules: identifiers,
   codes, years, ratings, inconsistent and empty fields are skipped. Up to six
   measures and four categories (2-30 values) are ranked by the existing
   exploration rank. Confirmed measures with required population filters, or
   declared min/max/count calculations, are skipped with a stated limitation.
2. **One governed projection query** (`SELECT <fields> FROM "dataset" ORDER BY ...
   LIMIT 50001`) runs through the DuckDB executor and stores an owner-private
   `analysis` receipt. All analysts compute from its typed rows with exact
   `Decimal` arithmetic.
3. **Analysts** (deterministic, no model):
   - `quality`: row count, empty cells per field, repeated rows, constant fields,
     negative values in measures.
   - `composition`: category counts and shares (donut; at most 8 slices, the rest
     merged into "Other").
   - `distribution`: min, quartiles, median, mean, max and equal-width histogram bins.
   - `segment`: average of a measure per category group (groups of at least 5 rows,
     at most 12 groups); largest gap between highest and lowest group.
   - `relationship`: Pearson/Spearman for every measure pair through the existing
     `PatternStatistics` port (SciPy); heatmap matrix of the rank score.
   - `outlier`: the existing robust MAD/IQR detector (`detect_distribution`,
     threshold 3.5) per measure, for measures with at most 1,000 distinct values.
4. **Cross-checker**: each card's headline numbers are recomputed by a second,
   independent path and the card is **dropped** when any check disagrees.
   SQL checks run a separate single-aggregate DuckDB query (`COUNT(*)`, `COUNT(col)`
   or `AVG(col)`, with bound `WHERE` filters) and store an ordinary receipt.
   Relationship scores are recomputed with a pure-Python Pearson/average-rank
   implementation (tolerance 0.000001). At most 24 SQL checks run per overview.
5. **Narrator**: the configured primary model (provider-neutral `LanguageModel`
   port) may only (a) order card IDs, (b) pick one server-rendered statement per
   card as its headline and (c) pick up to five next actions from the server-built
   action list. It never writes text or numbers. Any invalid reply, provider
   failure or 20-second timeout falls back to the deterministic ranking with the
   same structure; `narration.route` and `narration.fallback_reason` say which ran.

## Payload `insights-v1`

All numbers are **strings** (exact decimals; parse for plotting). Fields marked `?`
may be `null`.

```jsonc
{
  "version": "insights-v1",
  "dataset_name": "farm.csv",
  "definition_state": "inferred",          // inferred | confirmed | needs_review | ...
  "sources": [{ "...": "same as discovery" }],
  "narration": { "route": "deterministic:insights-v1", "fallback_reason": null },
  "kpis": [
    { "id": "rows", "label": "Rows", "value": "100", "unit": null, "detail": "Checked by a separate count query." }
    // ids: rows, columns, measures, categories, completeness (unit "%"), duplicate_rows
  ],
  "insights": [                              // already ordered for display
    {
      "id": "composition:Soil_Type",          // stable across runs for the same file
      "analyst": "composition",               // quality | composition | distribution | segment | relationship | outlier
      "title": "How rows split by Soil_Type",
      "summary": "Clay is the largest Soil_Type group with 31 of 100 rows (31%).",
      "statements": ["...", "..."],           // all server-rendered; summary is one of them
      "evidence": [ { "label": "Largest group", "value": "Clay", "unit": null } ],
      "chart": {
        "type": "donut",                      // pie | donut | bar | histogram | heatmap | scatter | box
        "title": "Rows by Soil_Type",
        "x": { "field": "label", "label": "Soil_Type", "unit": null },
        "y": { "field": "count", "label": "Rows", "unit": null },
        "value"?: { "field": "score", "label": "Rank relationship", "unit": null },  // heatmap only
        "rows": [ { "label": "Clay", "count": "31", "percent": "31.0" } ]
      },
      "cross_check": {
        "status": "verified",                 // verified | not_applicable (dropped cards never appear)
        "checks": [
          { "label": "Rows where Soil_Type = Clay", "primary": "31", "secondary": "31",
            "method": "duckdb-count", "query_id": "uuid?", "agrees": true }
        ]
      },
      "actions": [ { "id": "show_group:Soil_Type:Clay", "kind": "show_group",
                     "label": "Show records where Soil_Type is Clay",
                     "payload": { "type": "ask", "question": "Show all records where Soil_Type equals Clay" } } ]
    }
  ],
  "next_actions": [ /* up to 5 action objects, same shape as card actions */ ],
  "cross_check": { "verified": 9, "dropped": [ { "id": "segment:...", "reason": "..." } ] },
  "limits": { "rows": 50000, "measures": 6, "categories": 4, "checks": 24, "slices": 8, "groups": 12 },
  "limitations": ["..."]
}
```

### Chart rows by type

| type | x.field / y.field | row keys |
|---|---|---|
| `donut`/`pie` | `label` / `count` | `label`, `count`, `percent` (one decimal) |
| `bar` (segment) | `label` / `value` | `label`, `value` (group mean), `count` |
| `bar` (quality) | `label` / `value` | `label` (field), `value` (empty cells) |
| `histogram` | `label` / `count` | `label`, `start`, `end`, `count` (last bin includes its end) |
| `heatmap` | `x` / `y`, `value.field` = `score` | `x`, `y`, `score` (Spearman, 6 dp), `support` |

| `box` (outlier) | `label` / `median` | `label`, `low`, `q1`, `median`, `q3`, `high`; chart also has `outliers: [{value, count}]` (at most 50) |

`scatter` is reserved in the type list and not produced by `insights-v1`.
Statements show readable numbers (exact Decimal half-even: 2 decimals when |v| >= 1,
3 significant figures below 1; outlier boundaries stay exact). `evidence`, chart rows and
cross-check values keep exact strings, and the cross-checker compares exact values only.
`chart` may be `null` (e.g. a quality card with nothing to plot).

### Action catalog

| kind | label pattern | payload |
|---|---|---|
| `check_missing` | Check missing values in {field} | `{type: "prepare", column}` |
| `review_duplicates` | Review {n} repeated rows | `{type: "prepare", check: "duplicate_rows"}` |
| `investigate_outliers` | Investigate {n} unusual {measure} rows | `{type: "anomalies", metric, filters: [{column, operator: "gte"/"lte", value}]}` |
| `compare_groups` | Compare {measure} across {category} | `{type: "ask", question}` |
| `show_group` | Show records where {category} is {value} | `{type: "ask", question}` |
| `explore_relationship` | Check how {a} relates to {b} | `{type: "patterns", columns: [a, b]}` |
| `what_if` | Run what-if on {measure} | `{type: "scenario", metric, aggregation}` (confirmed, complete, fixed-unit only) |
| `review_meaning` | Confirm what {measure} measures | `{type: "review_meaning", column}` (inferred meaning only) |
| `ask` | Ask: {question} | `{type: "ask", question}` |

`outlier` filter values are the exact boundary values: flagged rows are those with
`value >= upper` or `value <= lower`; either filter may be absent.

### Compatibility

`insights-v1` is new and additive; `/discovery` (`discovery-v1`) is unchanged.
Future incompatible changes must use a new `version` value; readers should ignore
unknown keys and render only known chart types.

## Limits and honest scope

- Files above 50,000 rows return KPIs and limitations without analyst cards.
- Recomputed on every request (no cache); each request stores one projection and
  up to 24 check receipts, plus one narration model call when a model is configured.
- Without confirmed meaning, units are `null` and cards state that meaning is inferred.
- Outliers are exploratory unusualness, not errors; group gaps and relationships
  are associations, not causes. No forecast or prediction is made.
- Fields whose names match a reserved query word (for example `load`) are skipped
  with a limitation, because the shared read-only SQL guard rejects them.

## Verification (2026-10-19, local, agent C)

- `apps/api/tests/test_insights.py`: 22 unit cases on the reference farm file and small
  fixtures (each analyst against independent recomputation/SciPy, cross-checker drops,
  narration selection and seven fallback paths, meaning gate, row cap) pass.
- `apps/api/tests/test_insights_integration.py` (endpoint, receipt replay, row/column
  policy, other-workspace denial) is written but **skipped**: no
  `EXECPLUS_TEST_DATABASE_URL` was available. Not yet run against PostgreSQL/MinIO.
- Reference file result: 11 verified cards (quality, 3 composition, 3 distribution,
  3 segment, 1 relationship), 0 dropped, no outliers flagged at threshold 3.5.

## Related: suggestions from column names (2026-10-20)

- `GET .../understanding` adds `unit_suggestions: [{column, unit, currency, source, question}]`
  for unconfirmed measures whose name ends in an unambiguous unit token (`mm`, `°C` from
  `_C` after a temperature word, `km/h`, `hectare`, `hours`, `%`, ISO currency codes and
  others; `pH` for pH fields; `%` for humidity). `question` is the matching missing-detail text.
  Ambiguous names (`Soil_Moisture`, `Electrical_Conductivity`, `_m` without a length word,
  `per` ratios) stay as questions. Saved definitions are never changed by the server.
- The Data understanding panel lists them under "Suggested units" with an
  "Accept suggested units" button that only fills the draft; the user must still confirm.
  Guided review pre-fills the unit input, and the data reading rows carry
  `unit_source: "suggested from column name" | "model" | "saved" | ""`.
- `infer_definition` proposes the new `agriculture` domain when at least three agriculture
  words (soil, crop, irrigation, rainfall, harvest, sowing, mulching, ...) appear in column
  names and no sales/inventory/HR tag applies. It is a proposal only.

## Related: grounded next steps in chat (2026-10-22)

- Open advice questions ("What should I do to grow sales?", "what should HR focus on?",
  "batao kya karna chahiye?") run `build_insights` without narration and return a
  `DatasetGuide` (focus `next_steps`, route `deterministic:next-steps-v1`). Up to five
  steps are taken in a fixed order (unusual values, group gap, largest group, data gaps,
  related fields, typical range), cards about a measure named in the question first.
- Each step quotes the card's server-rendered summary, so every figure comes from the
  projection receipt and survived the cross-checker. Each step's follow-up question goes
  into the existing `suggestions` field (clickable in the chat). The reply says the steps are
  suggestions from patterns, not causes. When no card qualifies (unconfirmed saved meaning,
  more than 50,000 rows, no eligible fields) the previous guidance path answers instead.
