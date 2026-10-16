/* Use case: Verifies the installed renderer preserves chart evidence and missingness.
What it does: Runs actual ECharts SVG rendering against exact, signed, null, duplicate and late-row fixtures. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import * as echarts from "echarts/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import ts from "typescript";

echarts.use([BarChart, LineChart, ScatterChart, GridComponent, MarkLineComponent, TooltipComponent, DataZoomComponent, SVGRenderer]);
const require = createRequire(import.meta.url);
const modules = {};
for (const name of ["visualization-values", "lieflat-chart-presets", "documd-chart-presets", "echarts-answer-plot"]) {
  const source = await readFile(new URL(`../src/app/workspace/${name}.${name === "echarts-answer-plot" ? "tsx" : "ts"}`, import.meta.url), "utf8");
  const compiled = { exports: {} };
  const load = path => path.endsWith(".module.css") ? { default: new Proxy({}, { get: (_, key) => key }) } : modules[path] ?? require(path);
  new Function("require", "module", "exports", ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText)(load, compiled, compiled.exports);
  modules[`./${name}`] = compiled.exports;
}
const { makeLieflatBarOption } = modules["./lieflat-chart-presets"];
const { makeDocumdLineOption } = modules["./documd-chart-presets"];
const { makeDotOption } = modules["./echarts-answer-plot"];
const points = rows => rows.map(row => ({ row, label: String(row[0]), raw: row[1], value: row[1] === null ? null : Number(row[1]) }));

function render(option, check) {
  const chart = echarts.init(null, undefined, { renderer: "svg", ssr: true, width: 720, height: 420 });
  try {
    chart.setOption(option);
    const svg = chart.renderToSVGString();
    assert.doesNotMatch(svg, /NaN|Infinity/);
    check(chart, svg);
  } finally { chart.dispose(); }
}

test("actual SVG dots distinguish missing values from zero and preserve signed geometry", () => {
  const source = points([["Negative", "-50.000"], ["Missing", null], ["Zero", "0.000"], ["Positive", "100.00"]]);
  render(makeDotOption(source, 0, 3, true, 720), chart => {
    const data = chart.getModel().getSeriesByIndex(0).getData();
    assert.equal(data.hasValue(1), false);
    assert.equal(data.hasValue(2), true);
    assert.equal(data.getItemGraphicEl(1), undefined);
    assert.ok(data.getItemGraphicEl(2));
    assert.ok(data.getItemLayout(0)[0] < data.getItemLayout(2)[0]);
    assert.ok(data.getItemLayout(2)[0] < data.getItemLayout(3)[0]);
  });
});

test("negative-only dots keep zero at the actual upper scale endpoint", () => {
  const source = points([["Lower", "-50.000"], ["Higher", "-10.000"]]);
  render(makeDotOption(source, 0, 1, true, 720), chart => {
    assert.equal(chart.getOption().xAxis[0].max, 0);
    assert.equal(chart.getOption().xAxis[0].min, -1);
  });
});

test("actual Lieflat/ECharts bars can navigate the last of 365 rows including repeated labels", () => {
  const source = points(Array.from({ length: 365 }, (_, index) => [index === 364 ? "Last returned row" : "Repeated label", String(index + 1)]));
  const original = structuredClone(source);
  render(makeLieflatBarOption({ points: source, start: 357, end: 364, reducedMotion: true, width: 720 }), (chart, svg) => {
    assert.equal(chart.getOption().series[0].data.length, 365);
    assert.equal(chart.getModel().getSeriesByIndex(0).getData().getRawIndex(364), 364);
    assert.match(svg, /Last returned row/);
  });
  assert.deepEqual(source, original);
});

test("actual line renderer keeps absent observations invalid and never smooths across them", () => {
  const source = points([["Before", "-1e308"], ["Absent", null], ["After", "1e308"], ["Zero", "-0.000"]]);
  render(makeDocumdLineOption({ points: source, start: 0, end: 3, reducedMotion: true, width: 720 }), chart => {
    const data = chart.getModel().getSeriesByIndex(0).getData();
    assert.equal(data.hasValue(1), false);
    assert.equal(data.hasValue(3), true);
    assert.equal(chart.getOption().series[0].connectNulls, false);
    assert.equal(chart.getOption().series[0].smooth, false);
    assert.deepEqual(chart.getOption().series[0].data, [-1, null, 1, -0]);
  });
});

test("renderer treats source labels as text and exact cells are not converted back from geometry", () => {
  const source = points([["<img onerror=alert(1)>", "9007199254740993.000001"], ["Other", "0.000000000001"]]);
  render(makeLieflatBarOption({ points: source, start: 0, end: 1, reducedMotion: true, width: 720 }), (_, svg) => {
    assert.doesNotMatch(svg, /<img|<script/);
    assert.equal(source[0].raw, "9007199254740993.000001");
    assert.equal(source[1].raw, "0.000000000001");
  });
});
