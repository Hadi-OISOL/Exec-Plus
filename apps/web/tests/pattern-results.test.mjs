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
new Function("require", "module", "exports", javascript)(createRequire(import.meta.url), compiled, compiled.exports);
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
const render = result => renderToStaticMarkup(createElement(PatternResults, { result, evidence: { query_id: "private-receipt", result_checksum: "checksum" } }));

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
