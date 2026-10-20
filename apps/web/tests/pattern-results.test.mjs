/* Use case: Protects measured-pattern presentation and honest empty states.
What it does: Checks exact numerical labels, escaped data, coverage and accessible evidence disclosures. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/pattern-results.tsx", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const compiled = { exports: {} };
const require = createRequire(import.meta.url);
const helpers = {};
for (const [key, file] of [["../visualization-values", "visualization-values.ts"], ["./charts/chart-values", "charts/chart-values.ts"]]) {
  const helper = { exports: {} };
  new Function("require", "module", "exports", ts.transpileModule(await readFile(new URL(`../src/app/workspace/${file}`, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(name => helpers[name] ?? require(name), helper, helper.exports);
  helpers[key] = helper.exports;
}
new Function("require", "module", "exports", javascript)(name => name.endsWith(".module.css") ? { default: new Proxy({}, { get: (_, key) => key }) } : helpers[name] ?? require(name), compiled, compiled.exports);
const { PatternResults } = compiled.exports;
const base = {
  version: "pattern-exploration-v1", engine_version: "test-engine", status: "patterns_found",
  coverage: { source_rows: 42, filtered_rows: 40, eligible_columns: 4, checked_candidates: 6, suppressed_candidates: 5, selected_findings: 1 },
  findings: [], limitations: ["Exploratory screen, not a causal conclusion."], exclusions: [{ column: "id", reason: "Identifier" }],
};
const finding = {
  id: "first", type: "group_difference", title: "Amounts differ by group", summary: "These groups have different recorded averages.", columns: ["group", "amount"],
  score: "0.900001", support: 38, excluded: 2,
  chart: { kind: "bar", x: "group", y: "amount", points: [{ x: "A", y: "9007199254740993.000001", count: 20 }, { x: "B", y: "-0.0000000000001", count: 18 }] },
  notes: ["Check with new observations."],
};
const render = (result, props = {}) => renderToStaticMarkup(createElement(PatternResults, { result, evidence: { query_id: "private-receipt", result_checksum: "checksum" }, ...props }));

test("measured cards retain exact labels, missing coverage and private receipt details", () => {
  const html = render({ ...base, findings: [finding] });
  assert.match(html, /9007199254740993\.000001/);
  assert.match(html, /-0\.0000000000001/);
  assert.match(html, /Based on 38 rows · 2 excluded/);
  assert.match(html, /approximate statistical score, not a probability/);
  assert.match(html, /Source receipt: private-receipt/);
  assert.match(html, /<details class="patternDetails"><summary>See values and method/);
  assert.doesNotMatch(html, /<details[^>]+open/);
  assert.match(html, /do not prove that one thing caused another/);
});

test("weak and insufficient data remain distinct useful empty states", () => {
  const weak = render({ ...base, status: "no_strong_patterns" });
  const sparse = render({ ...base, status: "insufficient_data" });
  assert.match(weak, /No clear pattern found/);
  assert.match(weak, /did not pass this method/);
  assert.match(sparse, /A little more data is needed/);
  assert.match(sparse, /too limited for a supported comparison/);
  assert.doesNotMatch(weak + sparse, /class="patternFinding"/);
});

test("unsafe labels remain text and extreme plotting values never become invalid coordinates", () => {
  const html = render({ ...base, findings: [{ ...finding, type: "numeric_relationship", title: "<script>alert(1)</script>", chart: { kind: "scatter", x: "measurement", y: "response", points: [{ x: "-1e308", y: "1e308" }, { x: "1e308", y: "-1e308" }] } }] });
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>|cx="NaN"|cy="NaN"|Infinity/);
  assert.match(html, /approximate coordinates/);
});

test("conditional category combinations keep observed row counts visible", () => {
  const html = render({ ...base, findings: [{ ...finding, type: "category_association", chart: { kind: "matrix", x: "condition", y: "outcome", points: [{ x: "Warm", y: "Dry", count: 17 }, { x: "Cool", y: "Wet", count: 21 }] } }] });
  assert.match(html, /Appear together/);
  assert.match(html, /<strong>17<span class="srOnly"> rows/);
  assert.match(html, /<td>Cool<\/td><td>Wet<\/td><td>21<\/td>/);
});

test("weak measured comparisons stay separate from screened findings and retain signed statistics", () => {
  const html = render({ ...base, status: "no_strong_patterns", exploratory: [{ ...finding, strength: "weak", type: "numeric_relationship", title: "Two fields checked", summary: "No clear pattern in these records.", score: "0.120000", statistics: { pearson: "-0.120000", spearman: "-0.080000" } }] });
  assert.match(html, /No clear pattern found/);
  assert.match(html, /Small relationships worth a look/);
  assert.match(html, /Weak relationship · exploratory/);
  assert.match(html, /not reliable rules or predictions/);
  assert.match(html, /Straight-line relationship<\/dt><dd>-0\.120000/);
  assert.doesNotMatch(html, /Here is what stands out|Move together/);
});

const grouped = {
  version: "group-relationship-comparison-v1", engine_version: "fixture", status: "compared", columns: ["amount", "response"], group_by: "region", units: { amount: "PKR", response: "mm" },
  pooled: { support: 45, statistics: { pearson: "-0.900001", spearman: "-0.880000" }, directions: { pearson: "negative", spearman: "negative" }, chart: { kind: "scatter", x: "amount", y: "response", points: [{ x: "9007199254740993.000001", y: "-0.0000000000001", group: "<North>" }] }, notes: ["Every covered row contributes once."] },
  groups: [
    { id: "north", label: "<North>", rows: 20, complete_pairs: 20, excluded_pairs: 0, status: "eligible", statistics: { pearson: "0.700001", spearman: "0.880000" }, directions: { pearson: "positive", spearman: "positive" } },
    { id: "south", label: "South", rows: 27, complete_pairs: 25, excluded_pairs: 2, status: "eligible", statistics: { pearson: null, spearman: "0.120001" }, directions: { pearson: "unavailable", spearman: "weak" } },
    { id: "sparse", label: "Small group", rows: 3, complete_pairs: 3, excluded_pairs: 0, status: "sparse", statistics: null, directions: null },
  ],
  comparisons: { pearson: { reversal_groups: ["<North>"], same_direction_groups: [], weak_groups: [], unavailable_groups: ["South"] }, spearman: { reversal_groups: ["<North>"], same_direction_groups: [], weak_groups: ["South"], unavailable_groups: [] } },
  coverage: { source_rows: 50, filtered_rows: 50, covered_rows: 45, excluded_rows: 5, missing_category_rows: 0, missing_pair_rows: 2, sparse_group_rows: 3, constant_group_rows: 0, unstable_group_rows: 0, observed_groups: 3, eligible_groups: 2 },
  limitations: ["Observed associations, not causes."], exclusions: [],
};

test("group comparisons preserve exact scores, source values and excluded coverage without causal claims", () => {
  const html = render(grouped);
  assert.match(html, /The combined view can hide a different direction/);
  assert.match(html, /Straight-line direction reverses here/);
  assert.match(html, /Rank direction reverses here/);
  assert.match(html, /-0\.900001/);
  assert.match(html, /9007199254740993\.000001/);
  assert.match(html, /-0\.0000000000001/);
  assert.match(html, /&lt;North&gt;/);
  assert.doesNotMatch(html, /<North>|cx="NaN"|cy="NaN"/);
  assert.match(html, /Rows left out<\/dt><dd>5/);
  assert.match(html, /Small group<\/strong>: Fewer than 20 complete pairs/);
  assert.match(html, /Source receipt: private-receipt/);
  assert.match(html, /They do not show that one measure causes the other/);
  assert.doesNotMatch(html, /<details[^>]+open/);
});

test("weak, unavailable and insufficient group comparisons do not fabricate reversals or pooled scores", () => {
  const weak = render({ ...grouped, comparisons: { pearson: { reversal_groups: [] }, spearman: { reversal_groups: [] } } });
  assert.match(weak, /Read both views before drawing a conclusion/);
  assert.match(weak, /Unavailable/);
  assert.match(weak, /No clear direction/);
  assert.doesNotMatch(weak, /direction reverses here/);
  const sparse = render({ ...grouped, status: "insufficient_data", pooled: null, groups: [grouped.groups[2]] });
  assert.match(sparse, /More comparable groups are needed/);
  assert.match(sparse, /No combined relationship is claimed/);
  assert.doesNotMatch(sparse, /All included groups together|class="relationshipScore"|-0\.900001/);
});

test("record charts expose exact unit-aware inspection and keyboard guidance without creating a trend", () => {
  const html = render({ ...base, findings: [{ ...finding, type: "numeric_relationship", chart: { kind: "scatter", x: "rainfall", x_unit: "mm", y: "revenue", y_unit: "USD", points: [{ x: "0", y: "9007199254740993.000001" }, { x: "10.00001", y: "-0.0000000000001" }] } }] });
  assert.match(html, /Use left and right arrow keys to inspect records/);
  assert.match(html, /role="group" tabindex="0"/);
  assert.match(html, /<dd>0 mm<\/dd>/);
  assert.match(html, /<dd>9007199254740993\.000001 USD<\/dd>/);
  assert.match(html, /Inspect a plotted record/);
  assert.match(html, /approximate coordinates and axis labels/);
  assert.doesNotMatch(html, /<polyline|<path|NaN|Infinity/);
});

test("blank plotted fields are omitted rather than displayed as a measured zero", () => {
  const html = render({ ...base, findings: [{ ...finding, type: "numeric_relationship", chart: { kind: "scatter", x: "measure", y: "result", points: [{ x: "", y: "7" }, { x: "0", y: "2" }, { x: "3", y: "" }] } }] });
  assert.equal((html.match(/<circle/g) ?? []).length, 1);
  assert.match(html, /1 displayed points/);
  assert.match(html, /<td><\/td><td>7<\/td>/);
});

const cohort = {
  version: "cohort-comparison-v1", engine_version: "fixture", status: "compared",
  target: { column: "Crop_Growth_Stage", value: "Harvest" },
  coverage: { source_rows: 64, filtered_rows: 61, target_rows: 20, other_rows: 40, missing_target_rows: 1 },
  numeric: [
    { column: "Rainfall_mm", unit: "mm", target_count: 20, other_count: 40, target_mean: "8.000000000001", other_mean: "5", target_median: "7", other_median: "4", difference: "3.000000000001", standardized_difference: "0.100000", status: "compared" },
    { column: "Fixed_reading", unit: "mm", target_count: 20, other_count: 40, target_mean: "0", other_mean: "0", target_median: "0", other_median: "0", difference: "0", standardized_difference: null, status: "compared" },
  ],
  categories: [{ column: "Crop_Type", target_observed: 20, other_observed: 40, levels: [{ value: "Rice", target_count: 10, other_count: 30, target_share: "0.500000", other_share: "0.750000" }, { value: "Wheat", target_count: 10, other_count: 10, target_share: "0.500000", other_share: "0.250000" }] }],
  limitations: ["These observations do not establish a cause."],
  exclusions: [{ column: "Soil_Moisture", reason: "Confirm its unit before comparing." }],
  next_steps: ["Check the crop mix before comparing conditions."],
  suggestions: ['Show records where Crop_Growth_Stage is "Harvest"'],
};

test("targeted group comparison keeps returned precision, weak/equal gaps, denominators and missing labels", () => {
  const html = render(cohort);
  assert.match(html, /What is different about Harvest/);
  assert.match(html, /Harvest rows<\/dt><dd>20/);
  assert.match(html, /Other group rows<\/dt><dd>40/);
  assert.match(html, /Missing group label<\/dt><dd>1/);
  assert.match(html, /all other nonmissing values of Crop_Growth_Stage/);
  assert.match(html, /8\.000000000001 mm/);
  assert.match(html, /3\.000000000001 mm/);
  assert.match(html, /Fixed_reading/);
  assert.match(html, /<dd>0 mm<\/dd>/);
  assert.match(html, /0\.100000/);
  assert.match(html, /0\.500000/);
  assert.match(html, /Source receipt: private-receipt/);
  assert.match(html, /do not explain why a difference happened/);
  assert.doesNotMatch(html, /significant difference|recommended irrigation|prediction accuracy:|<details[^>]+open/);
});

test("sparse cohort values stay unavailable rather than receiving zero gaps or bars", () => {
  const html = render({ ...cohort, status: "insufficient_data", numeric: [{ ...cohort.numeric[0], target_count: 1, other_count: 0, target_mean: null, other_mean: null, target_median: null, other_median: null, difference: null, standardized_difference: null, status: "insufficient_data" }], categories: [] });
  assert.match(html, /What we can compare for Harvest/);
  assert.match(html, /not enough comparable values/);
  assert.match(html, /<td>1<\/td><td>Not available<\/td><td>Not available/);
  assert.match(html, /<td>0<\/td><td>Not available<\/td><td>Not available/);
  assert.doesNotMatch(html, /patternBarChart|Average difference ·|<dd>0 mm/);
});

test("cohort source labels and server next steps remain escaped and actions respect busy state", () => {
  const result = { ...cohort, target: { column: "<stage>", value: "<script>Harvest</script>" }, next_steps: ['<img src=x onerror="unsafe()">'], suggestions: ['Compare "<script>"', "x".repeat(501)] };
  const available = render(result, { onAsk: () => {} });
  const busy = render(result, { onAsk: () => {}, busy: true });
  assert.match(available, /&lt;script&gt;Harvest&lt;\/script&gt;/);
  assert.match(available, /&lt;img src=x/);
  assert.doesNotMatch(available, /<script>|<img/);
  assert.equal((available.match(/ disabled=""/g) ?? []).length, 1);
  assert.equal((busy.match(/ disabled=""/g) ?? []).length, 2);
  assert.match(available, /These are investigation steps/);
  assert.doesNotMatch(render(result), /Ask about this comparison/);
});

test("cohort plotting never rounds its exact table values or hides an unavailable standardized gap", () => {
  const result = { ...cohort, numeric: [{ ...cohort.numeric[0], target_mean: "9007199254740993.000001", other_mean: "-0.0000000000001", target_median: "9007199254740993.000001", standardized_difference: null }] };
  const html = render(result);
  assert.match(html, /9007199254740993\.000001/);
  assert.match(html, /-0\.0000000000001/);
  assert.match(html, /Standardized difference: <strong>Not available/);
  assert.match(html, /bar lengths are illustrative/);
  assert.match(html, /role="region" aria-label="Exact group values for Rainfall_mm"/);
  assert.doesNotMatch(html, /NaN|Infinity/);
});
