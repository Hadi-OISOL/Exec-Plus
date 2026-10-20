/* Use case: Protects exact values in the shared chart kit, the analyst overview mapping and chart-type selection.
What it does: Checks exact decimal addition and "Other" folding, share text, count-up end frames, exact table views, insights-v1 chart/action mapping and real ECharts SVG output for every kit chart kind. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import * as echarts from "echarts/core";
import { BarChart, BoxplotChart, HeatmapChart, LineChart, PieChart, SankeyChart, ScatterChart, TreeChart, TreemapChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import ts from "typescript";

echarts.use([PieChart, BarChart, LineChart, ScatterChart, HeatmapChart, BoxplotChart, TreemapChart, SankeyChart, TreeChart, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent, SVGRenderer]);
const require = createRequire(import.meta.url);
const modules = {};
for (const [key, file] of [["../visualization-values", "visualization-values.ts"], ["./chart-values", "charts/chart-values.ts"], ["../charts/chart-values", "charts/chart-values.ts"], ["./chart-tokens", "charts/chart-tokens.ts"], ["./chart-options", "charts/chart-options.ts"], ["./insights-model", "insights/insights-model.ts"]]) {
  const source = await readFile(new URL(`../src/app/workspace/${file}`, import.meta.url), "utf8");
  const compiled = { exports: {} };
  new Function("require", "module", "exports", ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(path => modules[path] ?? require(path), compiled, compiled.exports);
  modules[key] = compiled.exports;
}
const { addExact, bucketSlices, shareText, donutEligible, selectAnswerChart, specTable, countUpFrames, chartSummary, readableMetric, humanName, humanizeFields, humanizeSpec } = modules["./chart-values"];
const { defaultTokens } = modules["./chart-tokens"];
const { makeKitOption, escapeHtml } = modules["./chart-options"];
const { chartSpecFromInsight, actionIntent } = modules["./insights-model"];

test("exact decimal addition keeps every digit, sign and scale", () => {
  assert.equal(addExact(["0.1", "0.2"]), "0.3");
  assert.equal(addExact(["9007199254740993", "1"]), "9007199254740994");
  assert.equal(addExact(["1.50", "-2.125", ".5"]), "-0.125");
  assert.equal(addExact(["-0.000000000001", "0.000000000001"]), "0.000000000000");
  assert.equal(addExact(["1e3"]), null);
  assert.equal(addExact([]), null);
});

test("slices beyond the limit fold into an exact Other with its members", () => {
  const slices = ["10", "9", "8", "7", "6", "5", "4", "3", "2.5"].map((value, index) => ({ label: `G${index}`, value }));
  const folded = bucketSlices(slices, 7);
  assert.equal(folded.length, 7);
  assert.deepEqual(folded.slice(0, 6).map(slice => slice.label), ["G0", "G1", "G2", "G3", "G4", "G5"]);
  assert.equal(folded[6].label, "Other (3 groups)");
  assert.equal(folded[6].value, "9.5");
  assert.deepEqual(folded[6].members.map(slice => slice.value), ["4", "3", "2.5"]);
  assert.equal(bucketSlices(slices.slice(0, 3), 7).length, 3);
});

test("shares are display strings and donuts refuse negative or empty parts", () => {
  assert.equal(shareText("31", "100"), "31.0%");
  assert.equal(shareText("1", "100000"), "<0.1%");
  assert.equal(shareText("1", "0"), "");
  assert.equal(donutEligible(["2", "1"]), true);
  assert.equal(donutEligible(["2", "-1"]), false);
  assert.equal(donutEligible(["0", "0"]), false);
  assert.equal(donutEligible(["2", null]), false);
  assert.equal(donutEligible(["5"]), false);
});

test("chart form follows the answer's recommendation when the data allows it", () => {
  const shares = ["3", "2", "1"];
  assert.equal(selectAnswerChart({ recommended: "pie", fallback: "bar", values: shares, allowLine: false }), "pie");
  assert.equal(selectAnswerChart({ recommended: "donut", fallback: "bar", values: ["3", "-1"], allowLine: false }), "bar");
  assert.equal(selectAnswerChart({ recommended: "line", fallback: "bar", values: shares, allowLine: true }), "line");
  assert.equal(selectAnswerChart({ recommended: "line", fallback: "bar", values: shares, allowLine: false }), "bar");
  assert.equal(selectAnswerChart({ recommended: "scatter", fallback: "bar", values: shares, allowLine: false }), "dot");
  assert.equal(selectAnswerChart({ recommended: null, fallback: "line", values: shares, allowLine: true }), "line");
  assert.equal(selectAnswerChart({ recommended: undefined, fallback: "pie", values: ["1", "-2"], allowLine: false }), "bar");
});

test("count-up frames end on the exact display string and skip non-numbers", () => {
  for (const display of ["9,007,199,254,740,993", "-1.25", "0.1", "100", "+3.500"]) {
    const frames = countUpFrames(display);
    assert.equal(frames.at(-1), display);
    assert.ok(frames.length > 1);
    assert.ok(frames.every(frame => !/NaN|Infinity|e/.test(frame)));
  }
  assert.deepEqual(countUpFrames("Missing"), ["Missing"]);
  assert.deepEqual(countUpFrames("0"), ["0"]);
  assert.equal(countUpFrames("-1.25")[0].startsWith("-"), true);
});

test("table views show the original strings, including unbucketed slices", () => {
  const donut = { kind: "donut", title: "Rows", slices: [{ label: "<b>A</b>", value: "0.100000000000" }, { label: "B", value: "0.2" }] };
  const table = specTable(donut);
  assert.deepEqual(table.rows[0], ["<b>A</b>", "0.100000000000", "33.3%"]);
  assert.deepEqual(specTable({ kind: "bar", title: "x", categories: ["N"], series: [{ name: "v", values: [null] }] }).rows, [["N", "Missing"]]);
  assert.deepEqual(specTable({ kind: "heatmap", title: "h", x: ["a", "b"], y: ["a"], cells: [{ x: "b", y: "a", value: "-0.123456" }] }).rows, [["a", "Missing", "-0.123456"]]);
  assert.match(chartSummary(donut), /Donut chart: Rows\. 2 items\. Largest: B, 0\.2\./);
});

test("insights-v1 charts map to kit specifications with exact strings", () => {
  const donut = chartSpecFromInsight({ type: "donut", title: "Rows by Soil_Type", x: { field: "label", label: "Soil_Type" }, y: { field: "count", label: "Rows" }, rows: [{ label: "Clay", count: "31", percent: "31.0" }, { label: "Other", count: "4", percent: "4.0" }] });
  assert.equal(donut.kind, "donut");
  assert.deepEqual(donut.slices[0], { label: "Clay", value: "31" });
  assert.deepEqual(donut.slices[1].members, []);
  const box = chartSpecFromInsight({ type: "box", title: "Rainfall", x: { field: "label", label: "Measure" }, y: { field: "median", label: "Rainfall_mm", unit: "mm" }, rows: [{ label: "Rainfall_mm", low: "1.5", q1: "400", median: "800.25", q3: "1200", high: "2999.99" }], outliers: [{ value: "9000.1", count: "2" }] });
  assert.deepEqual(box.groups[0], { label: "Rainfall_mm", min: "1.5", q1: "400", median: "800.25", q3: "1200", max: "2999.99" });
  assert.deepEqual(box.outliers, [{ group: "Rainfall_mm", value: "9000.1", count: "2" }]);
  const heat = chartSpecFromInsight({ type: "heatmap", title: "r", x: { field: "x", label: "" }, y: { field: "y", label: "" }, value: { field: "score", label: "Rank relationship" }, rows: [{ x: "a", y: "b", score: "0.512345" }] });
  assert.deepEqual(heat.cells, [{ x: "a", y: "b", value: "0.512345" }]);
  const names = ["a", "b", "c"];
  const square = chartSpecFromInsight({ type: "heatmap", title: "r", x: { field: "x", label: "" }, y: { field: "y", label: "" }, value: { field: "score", label: "" }, rows: names.flatMap(x => names.map(y => ({ x, y, score: x === y ? "1" : `0.${x}${y}`.replace(/[a-c]/g, c => String(c.charCodeAt(0) - 96)) }))) });
  assert.deepEqual(square.x, ["a", "b"]);
  assert.deepEqual(square.y, ["b", "c"]);
  assert.deepEqual(square.cells.map(cell => `${cell.x}${cell.y}:${cell.value}`), ["ab:0.12", "ac:0.13", "bc:0.23"]);
  const bar = chartSpecFromInsight({ type: "bar", title: "Mean", x: { field: "label", label: "Region" }, y: { field: "value", label: "Yield" }, rows: [{ label: "West", value: "12.000001", count: 9 }] });
  assert.deepEqual(bar.series[0].values, ["12.000001"]);
  assert.equal(chartSpecFromInsight({ type: "unknown", title: "", x: {}, y: {}, rows: [{}] }), null);
  assert.equal(chartSpecFromInsight(null), null);
});

test("proposed action payloads become safe navigation intents", () => {
  assert.deepEqual(actionIntent({ id: "a", kind: "show_group", label: "", payload: { type: "ask", question: "Show Clay" } }), { type: "ask", question: "Show Clay" });
  assert.deepEqual(actionIntent({ id: "b", kind: "check_missing", label: "", payload: { type: "prepare", column: "x" } }), { type: "prepare" });
  assert.deepEqual(actionIntent({ id: "c", kind: "investigate_outliers", label: "", payload: { type: "anomalies", metric: "Rainfall_mm" } }), { type: "anomalies", metric: "Rainfall_mm" });
  assert.deepEqual(actionIntent({ id: "d", kind: "what_if", label: "", payload: { type: "scenario", metric: "m", aggregation: "avg" } }), { type: "scenario", metric: "m", aggregation: "avg" });
  assert.equal(actionIntent({ id: "e", kind: "what_if", label: "", payload: { type: "scenario", metric: "m", aggregation: "median" } }), null);
  assert.deepEqual(actionIntent({ id: "f", kind: "explore_relationship", label: "", payload: { type: "patterns", columns: ["a", "b"] } }), { type: "ask", question: "Find patterns between a and b" });
  assert.deepEqual(actionIntent({ id: "g", kind: "review_meaning", label: "", payload: { type: "review_meaning" } }), { type: "review" });
  assert.equal(actionIntent({ id: "h", kind: "x", label: "", payload: { type: "delete_everything" } }), null);
  assert.equal(actionIntent({ id: "i", kind: "ask", label: "", payload: { type: "ask", question: "" } }), null);
});

const specs = [
  { kind: "donut", title: "d", slices: [{ label: "<img onerror=alert(1)>", value: "3" }, { label: "B", value: "0" }, { label: "C", value: "1.5" }] },
  { kind: "bar", title: "b", categories: ["A", "B"], series: [{ name: "v", values: ["-1.25", null] }] },
  { kind: "bar", title: "g", horizontal: false, categories: ["A", "B"], series: [{ name: "x", values: ["1", "2"] }, { name: "y", values: ["3", null] }] },
  { kind: "line", title: "l", area: true, x: ["1", "2", "3"], series: [{ name: "v", values: ["1", null, "3"] }] },
  { kind: "histogram", title: "h", bins: [{ label: "0–10", count: "4" }, { label: "10–20", count: "0" }] },
  { kind: "scatter", title: "s", xName: "x", yName: "y", points: [{ x: "1", y: "2" }, { x: "3", y: "-4" }] },
  { kind: "heatmap", title: "c", x: ["a", "b"], y: ["a", "b"], cells: [{ x: "a", y: "b", value: "0.9" }, { x: "b", y: "a", value: null }] },
  { kind: "boxplot", title: "x", groups: [{ label: "m", min: "1", q1: "2", median: "3", q3: "4", max: "5" }], outliers: [{ group: "m", value: "9" }] },
  { kind: "treemap", title: "t", nodes: [{ name: "A", value: "3" }, { name: "B", value: "1" }] },
  { kind: "sankey", title: "k", nodes: ["A", "B"], links: [{ source: "A", target: "B", value: "2" }] },
  { kind: "tree", title: "r", root: { name: "file", children: [{ name: "Measures", children: [{ name: "x" }] }] } },
];

test("every kit chart renders real SVG without invalid geometry or injected markup", () => {
  for (const dark of [false, true]) for (const spec of specs) for (const width of [320, 720]) {
    const option = makeKitOption(spec, defaultTokens(dark), { reducedMotion: dark, width });
    assert.equal(option.animation, !dark);
    if (!dark) { assert.equal(option.animationDuration, 600); assert.equal(option.animationEasing, "cubicOut"); }
    const chart = echarts.init(null, undefined, { renderer: "svg", ssr: true, width, height: 320 });
    try {
      chart.setOption(option);
      const svg = chart.renderToSVGString();
      assert.doesNotMatch(svg, /NaN|Infinity|<img|<script/, `${spec.kind} ${width}`);
    } finally { chart.dispose(); }
  }
});

test("tooltips escape source labels and show exact values", () => {
  assert.equal(escapeHtml(`<a href="x">'&`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;");
  const option = makeKitOption(specs[0], defaultTokens(false), { reducedMotion: true, width: 600 });
  const html = option.series[0].tooltip.formatter({ dataIndex: 0 });
  assert.match(html, /&lt;img onerror=alert\(1\)&gt;/);
  assert.match(html, /66\.7%/);
  const bar = makeKitOption({ kind: "bar", title: "b", categories: ["A"], series: [{ name: "v", values: ["9007199254740993.000001"] }] }, defaultTokens(false), { reducedMotion: true, width: 600 });
  assert.match(bar.series[0].tooltip.formatter({ dataIndex: 0 }), /9,007,199,254,740,993\.000001/);
});

test("readable labels round only the display and keep small values meaningful", () => {
  const cases = { "9.291538461538": "9.29", "81.964444444444": "81.96", "1533.38": "1,533", "0.2127": "0.213", "0.212692": "0.213", "0.000123456": "0.000123", "-0.00004": "-0.00004", "1234567.891": "1,234,568", "0.100000000000": "0.1", "-1.25": "-1.25", "-1.255": "-1.26", "9007199254740993.000001": "9,007,199,254,740,993", "100.56": "100.6", "-0.000001": "-0.000001", "0.99995": "1", "2.995": "3", "31": "31", "-0.00000001": "-0.00000001" };
  for (const [exact, shown] of Object.entries(cases)) assert.equal(readableMetric(exact), shown, exact);
  assert.equal(readableMetric(null), "Missing");
  assert.equal(readableMetric("Clay"), "Clay");
});

test("field names read as words without touching other text", () => {
  assert.equal(humanName("Field_Area_hectare"), "Field Area hectare");
  assert.equal(humanizeFields("Wheat has the highest average Field_Area_hectare; Rain_fed stays", ["Field_Area_hectare", "Crop_Type"]), "Wheat has the highest average Field Area hectare; Rain_fed stays");
  assert.equal(humanizeFields("Soil_pH_x vs Soil_pH", ["Soil_pH", "Soil_pH_x"]), "Soil pH x vs Soil pH");
});

test("display names change consistently in a chart without touching values", () => {
  const spec = { kind: "heatmap", title: "Soil_pH vs Rain_mm", x: ["Soil_pH"], y: ["Rain_mm"], cells: [{ x: "Soil_pH", y: "Rain_mm", value: "0.123456" }] };
  const shown = humanizeSpec(spec, ["Soil_pH", "Rain_mm"]);
  assert.deepEqual(shown.cells, [{ x: "Soil pH", y: "Rain mm", value: "0.123456" }]);
  assert.equal(shown.title, "Soil pH vs Rain mm");
  assert.equal(spec.x[0], "Soil_pH");
  const bar = humanizeSpec({ kind: "bar", title: "t", categories: ["Rain_fed", "Soil_pH"], series: [{ name: "Soil_pH", values: ["1"] }] }, ["Soil_pH"]);
  assert.deepEqual(bar.categories, ["Rain_fed", "Soil pH"]);
});
