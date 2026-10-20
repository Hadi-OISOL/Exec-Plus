/* Use case: Guards the analyst overview's rendered output on the server before any browser effect runs.
What it does: Renders the real InsightsOverview, KpiRow and ProposedActions with an insights-v1 fixture and checks readable labels, exact titles, human field names, grouped sections and safe defaults. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const compiled = { exports: {} };
  cache.set(file, compiled);
  const output = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
  const local = path => {
    if (path.endsWith(".module.css")) return { default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (!path.startsWith(".")) return require(path);
    const base = resolve(dirname(file), path);
    return load([`${base}.ts`, `${base}.tsx`].find(existsSync));
  };
  new Function("require", "module", "exports", output)(local, compiled, compiled.exports);
  return compiled.exports;
}
const { InsightsOverview, ProposedActions, proposedFromInsights, insightTabs } = load(resolve(dirname(fileURLToPath(import.meta.url)), "../src/app/workspace/insights/insights-overview.tsx"));

const payload = {
  version: "insights-v1", dataset_name: "farm.csv", definition_state: "inferred",
  kpis: [{ id: "rows", label: "Rows", value: "100" }, { id: "completeness", label: "Complete cells", value: "99.123456", unit: "%", detail: "Checked for Soil_Type." }],
  insights: [
    { id: "segment:Field_Area_hectare:Crop_Type", analyst: "segment", title: "Field_Area_hectare by Crop_Type", summary: "Wheat has the highest average Field_Area_hectare (9.2915).",
      evidence: [{ label: "Highest average", value: "9.291538461538", unit: "hectare" }],
      chart: { type: "bar", title: "Average Field_Area_hectare by Crop_Type", x: { field: "label", label: "Crop_Type" }, y: { field: "value", label: "Field_Area_hectare" }, rows: [{ label: "Wheat", value: "9.291538461538" }] },
      cross_check: { status: "verified", checks: [{ label: "Average", primary: "9.2915", secondary: "9.2915", method: "duckdb-avg", agrees: true }] },
      actions: [{ id: "a", kind: "show_group", label: "Show records where Crop_Type is Wheat", payload: { type: "ask", question: "Show all records where Crop_Type equals Wheat" } }] },
    { id: "composition:Soil_Type", analyst: "composition", title: "How rows split by Soil_Type", summary: "Clay is largest.", chart: { type: "donut", title: "Rows by Soil_Type", x: { field: "label", label: "Soil_Type" }, y: { field: "count", label: "Rows" }, rows: [{ label: "Clay", count: "31" }, { label: "Silt", count: "69" }] } },
  ],
  next_actions: [{ id: "n", kind: "what_if", label: "Run what-if on Soil_pH", payload: { type: "scenario", metric: "Soil_pH", aggregation: "avg" } }],
};

test("the overview opens on Highlights with tab counts, readable labels, human names and exact titles", () => {
  const html = renderToStaticMarkup(createElement(InsightsOverview, { state: { root: "r", payload }, retry: () => {}, onAction: () => {} }));
  assert.match(html, /role="tablist"/);
  assert.match(html, /role="tab" aria-selected="true"[^>]*>Highlights</);
  assert.match(html, />Composition<span class="tabCount">1<\/span>/);
  assert.match(html, />Group comparisons<span class="tabCount">1<\/span>/);
  assert.ok(html.indexOf(">Composition<") < html.indexOf(">Group comparisons<"));
  assert.match(html, /data-insight-tab="highlights"/);
  assert.equal((html.match(/data-insight="/g) ?? []).length, 2);
  assert.match(html, /9\.29 hectare/);
  assert.match(html, /title="Highest average: 9\.291538461538 hectare"/);
  assert.match(html, /Field Area hectare by Crop Type/);
  assert.match(html, /title="Field_Area_hectare by Crop_Type"/);
  assert.match(html, /Double-checked/);
  assert.match(html, /99\.12/);
  assert.match(html, /<span class="tileLabel">Rows<\/span>/);
  assert.match(html, /title="99\.123456"/);
  assert.doesNotMatch(html, /<details[^>]* open/);
});

test("tabs group cards by topic and keep empty topics out", () => {
  const tabs = insightTabs([...payload.insights, { ...payload.insights[0], id: "q", analyst: "quality" }, { ...payload.insights[0], id: "x", analyst: "future_kind" }]);
  assert.deepEqual(tabs.map(tab => [tab.key, tab.cards.length]), [["highlights", 4], ["composition", 1], ["segment", 1], ["quality", 1], ["more", 1]]);
});

test("loading and failure states render safely", () => {
  assert.match(renderToStaticMarkup(createElement(InsightsOverview, { state: null, retry: () => {}, onAction: () => {} })), /aria-busy="true"/);
  assert.match(renderToStaticMarkup(createElement(InsightsOverview, { state: { root: "r", error: "boom" }, retry: () => {}, onAction: () => {} })), /Try again/);
});

test("proposed actions show human labels but send the original payload", () => {
  const sent = [];
  const items = proposedFromInsights(payload.next_actions, intent => sent.push(intent), text => text.replaceAll("Soil_pH", "Soil pH"));
  assert.equal(items[0].label, "Run what-if on Soil pH");
  items[0].run();
  assert.deepEqual(sent, [{ type: "scenario", metric: "Soil_pH", aggregation: "avg" }]);
  assert.match(renderToStaticMarkup(createElement(ProposedActions, { items })), /Run what-if on Soil pH/);
  assert.equal(proposedFromInsights(payload.next_actions, () => {})[0].label, "Run what-if on Soil_pH");
});
