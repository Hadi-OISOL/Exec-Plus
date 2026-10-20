/* Use case: Verifies the actual diagram renderer only displays supplied membership.
What it does: Checks SVG output, complete field navigation, literal labels and narrow-screen branch rendering without invented relationships. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as echarts from "echarts/core";
import { TreeChart } from "echarts/charts";
import { SVGRenderer } from "echarts/renderers";
import ts from "typescript";

echarts.use([TreeChart, SVGRenderer]);
const require = createRequire(import.meta.url);
const modules = {};
for (const [path, filename] of [["../theme-control", "../theme-control.tsx"], ["./chart-theme", "chart-theme.ts"], ["./charts/chart-tokens", "charts/chart-tokens.ts"]]) {
  const dependency = await readFile(new URL(`../src/app/workspace/${filename}`, import.meta.url), "utf8");
  const loaded = { exports: {} };
  new Function("require", "module", "exports", ts.transpileModule(dependency, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText)(require, loaded, loaded.exports);
  modules[path] = loaded.exports;
}
const source = await readFile(new URL("../src/app/workspace/diagram-results.tsx", import.meta.url), "utf8");
const compiled = { exports: {} };
new Function("require", "module", "exports", ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText)(path => path.endsWith(".module.css") ? { default: {} } : modules[path] ?? require(path), compiled, compiled.exports);
const { DiagramResults, makeDiagramOption } = compiled.exports;
const node = (id, kind, label) => ({ id, kind, label, data_type: "", role: "", meaning: "", unit: "", currency: "" });
const diagram = {
  version: "dataset-structure-v2", title: "How this file is organised", description: "", row_meaning: "", definition_state: "needs_review", scope: "all_fields", total_fields: 23, shown_fields: 23,
  nodes: [node("dataset", "dataset", "This file"), node("role-metric", "group", "Measures"), ...Array.from({ length: 23 }, (_, i) => node(`field-${i}`, "field", i === 22 ? "<img onerror=alert(1)>" : `Measure ${i + 1}`)), node("unlinked", "field", "Not linked")],
  edges: [{ source: "dataset", target: "role-metric", relation: "contains" }, ...Array.from({ length: 23 }, (_, i) => ({ source: "role-metric", target: `field-${i}`, relation: "contains" }))], limitations: [],
};
function render(option, width = 720) {
  const chart = echarts.init(null, undefined, { renderer: "svg", ssr: true, width, height: 460 });
  try { chart.setOption(option); const svg = chart.renderToSVGString(); assert.doesNotMatch(svg, /NaN|Infinity|<img|<script/); return svg; } finally { chart.dispose(); }
}

test("overview renders only declared file membership, not field relationships", () => {
  const option = makeDiagramOption(diagram, "", 0, 720, true);
  assert.deepEqual(option.series[0].data[0].children.map(child => child.id), ["role-metric"]);
  assert.match(render(option), /Measures/);
  assert.doesNotMatch(render(option), /Not linked|Measure 1/);
  assert.equal(option.animation, false);
});

test("a late diagram window reaches the final exact field without changing the source", () => {
  const before = structuredClone(diagram);
  const option = makeDiagramOption(diagram, "role-metric", 20, 720, true);
  const fields = option.series[0].data[0].children[0].children;
  assert.deepEqual(fields.map(field => field.id), ["field-20", "field-21", "field-22"]);
  assert.equal(fields[2].name, "<img onerror=alert(1)>");
  assert.match(render(option), /Measure 21/);
  assert.deepEqual(diagram, before);
});

test("narrow diagram shows the selected branch with bounded readable nodes", () => {
  const option = makeDiagramOption(diagram, "role-metric", 0, 250, true);
  assert.equal(option.series[0].data[0].id, "role-metric");
  assert.equal(option.series[0].data[0].children.length, 10);
  assert.match(render(option, 250), /Measures/);
  assert.equal(option.series[0].expandAndCollapse, false);
});

test("a diagram can replace its root and visible field window on the same renderer", () => {
  const chart = echarts.init(null, undefined, { renderer: "svg", ssr: true, width: 720, height: 460 });
  try {
    for (const [width, branch, first] of [[720, "", 0], [720, "role-metric", 20], [250, "role-metric", 0], [720, "", 0]]) {
      chart.clear();
      chart.setOption(makeDiagramOption(diagram, branch, first, width, true), { notMerge: true });
      assert.doesNotMatch(chart.renderToSVGString(), /NaN|Infinity/);
      assert.equal(chart.getOption().series[0].data[0].id, branch && width < 500 ? branch : "dataset");
    }
  } finally { chart.dispose(); }
});

test("earlier saved diagrams distinguish analysis roles from current saved field roles", () => {
  const field = { ...node("field-id", "field", "Record_ID"), role: "identifier" };
  const current = { ...diagram, nodes: [field, ...diagram.nodes], definition_state: "confirmed" };
  const markup = renderToStaticMarkup(createElement(DiagramResults, { diagram: current }));
  assert.match(markup, /<dt>Saved role<\/dt><dd>identifier<\/dd>/);
  assert.doesNotMatch(markup, /This earlier map|Earlier analysis role/);
  const earlier = { ...current, version: "dataset-structure-v1", nodes: [{ ...field, role: "dimension" }, ...diagram.nodes] };
  const legacy = renderToStaticMarkup(createElement(DiagramResults, { diagram: earlier }));
  assert.match(legacy, /This earlier map uses analysis groups. Ask again for a map of your saved field roles./);
  assert.match(legacy, /<dt>Earlier analysis role<\/dt><dd>dimension<\/dd>/);
  assert.doesNotMatch(legacy, /<dt>Saved role<\/dt>/);
});
