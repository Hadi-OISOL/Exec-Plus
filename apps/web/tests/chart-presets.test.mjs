/* Use case: Protects evidence identity when adapting third-party chart templates.
What it does: Checks complete returned populations, null gaps, signed finite geometry, exact labels and bounded reduced-motion behavior. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";
import { init, use as register } from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, DataZoomComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";

register([LineChart, GridComponent, DataZoomComponent, TooltipComponent, SVGRenderer]);

async function loadPreset(filename) {
  const source = await readFile(
    new URL(`../src/app/workspace/${filename}`, import.meta.url),
    "utf8",
  );
  const javascript = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  return import(
    `data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`
  );
}

const { makeLieflatBarOption } = await loadPreset("lieflat-chart-presets.ts");
const { makeDocumdLineOption } = await loadPreset("documd-chart-presets.ts");
const point = (raw, label = "Category") => ({
  raw,
  label,
  row: [label, raw],
  value: raw === null ? null : Number(raw),
});
const options = (points, overrides = {}) => ({
  points,
  start: 0,
  end: points.length - 1,
  reducedMotion: false,
  width: 1200,
  ...overrides,
});

test("template navigation preserves all 365 returned rows and their original indices", () => {
  const points = Array.from({ length: 365 }, (_, index) =>
    point(index === 180 ? null : String(index), `Day ${index + 1}`),
  );
  const original = structuredClone(points);
  const bar = makeLieflatBarOption(options(points, { start: 175, end: 185 }));
  const line = makeDocumdLineOption(options(points, { start: 175, end: 185 }));
  assert.deepEqual(points, original);
  assert.equal(bar.series[0].data.length, 365);
  assert.equal(line.series[0].data.length, 365);
  assert.equal(bar.series[0].data[180].value, null);
  assert.equal(line.series[0].data[180], null);
  assert.equal(bar.yAxis.data[364], "Day 365");
  assert.equal(line.xAxis.data[364], "Day 365");
  for (const option of [bar, line]) {
    assert.equal(option.dataZoom[0].filterMode, "none");
    assert.equal(option.dataZoom[0].startValue, 175);
    assert.equal(option.dataZoom[0].endValue, 185);
  }
});

test("signed extreme magnitudes remain finite and include the truthful zero baseline", () => {
  const points = [point("-1e308"), point("0.000"), point("1e308")];
  const bar = makeLieflatBarOption(options(points));
  const line = makeDocumdLineOption(options(points));
  assert.deepEqual(bar.series[0].data.map((entry) => entry.value), [-1, 0, 1]);
  assert.deepEqual(line.series[0].data, [-1, 0, 1]);
  assert.equal(bar.xAxis.min, -1);
  assert.equal(bar.xAxis.max, 1);
  assert.equal(line.yAxis[0].min, -1);
  assert.equal(line.yAxis[0].max, 1);
  assert.deepEqual(bar.series[0].markLine.data, [{ xAxis: 0 }]);
  const zero = makeLieflatBarOption(options([point("0.00")]));
  assert.equal(zero.xAxis.min, 0);
  assert.equal(zero.xAxis.max, 1);
  assert.equal(zero.series[0].data[0].value, 0);
  const negatives = [point("-20"), point("-10")];
  const negativeBar = makeLieflatBarOption(options(negatives));
  const negativeLine = makeDocumdLineOption(options(negatives));
  assert.equal(negativeBar.xAxis.max, 0);
  assert.equal(negativeLine.yAxis[0].max, 0);
  assert.deepEqual(negativeLine.series[0].data, [-1, -0.5]);
});

test("bar labels retain raw decimal precision rather than normalized geometry", () => {
  const precise = "9007199254740993.000001";
  const points = [point(precise), point("-12.3400"), point(null)];
  const bar = makeLieflatBarOption(options(points));
  assert.equal(bar.series[0].label.formatter({ dataIndex: 0 }), precise);
  assert.equal(bar.series[0].label.formatter({ dataIndex: 1 }), "-12.3400");
  assert.equal(bar.series[0].label.formatter({ dataIndex: 2 }), "");
  assert.equal(bar.series[0].label.show, false);
  assert.equal(bar.series[0].data[0].name, "Category");
});

test("observed line never invents a smoothed path or bridges missing periods", () => {
  const points = [point("2"), point(null), point("8")];
  const connected = makeDocumdLineOption(options(points));
  assert.equal(connected.series[0].smooth, false);
  assert.equal(connected.series[0].connectNulls, false);
  assert.deepEqual(connected.series[0].data, [0.25, null, 1]);
  assert.equal(connected.series[0].markLine, undefined);
  assert.equal(connected.yAxis.length, 1);
  const separated = makeDocumdLineOption(
    options(points, { connectLinePoints: false }),
  );
  assert.equal(separated.series[0].lineStyle.width, 0);
});

test("reduced motion disables animation and ordinary stagger has a finite upper bound", () => {
  const points = Array.from({ length: 1000 }, (_, index) => point(String(index)));
  const bar = makeLieflatBarOption(options(points));
  assert.equal(bar.animationDelay(999), 640);
  const quietBar = makeLieflatBarOption(options(points, { reducedMotion: true }));
  const quietLine = makeDocumdLineOption(options(points, { reducedMotion: true }));
  for (const option of [quietBar, quietLine]) {
    assert.equal(option.animation, false);
    assert.equal(option.animationDurationUpdate, 0);
  }
  assert.equal(quietBar.animationDelay(999), 0);
});

test("showing a full year retains every bar without forcing thick marks or overlapping labels", () => {
  const points = Array.from({ length: 365 }, (_, index) => point(String(index)));
  const bar = makeLieflatBarOption(options(points));
  assert.equal(bar.series[0].data.length, 365);
  assert.equal(bar.series[0].barWidth, undefined);
  assert.equal(bar.series[0].barMaxWidth, 16);
  assert.equal(bar.yAxis.axisLabel.interval, "auto");
  assert.equal(bar.yAxis.axisLabel.hideOverlap, true);
  assert.equal(bar.series[0].label.show, false);
  const close = makeLieflatBarOption(options(points, { start: 350, end: 357 }));
  assert.equal(close.series[0].label.show, true);
  assert.equal(close.series[0].label.formatter({ dataIndex: 350 }), "350");
});

test("narrow observed-only plots render every included non-null mark despite thinned date labels", () => {
  const points = Array.from({ length: 28 }, (_, index) => point(index === 15 ? null : String(index + 10), `2020-01-${String(index + 1).padStart(2, "0")}`));
  const chart = init(null, null, { renderer: "svg", ssr: true, width: 220, height: 300 });
  try {
    chart.setOption(makeDocumdLineOption(options(points, { connectLinePoints: false, width: 220, reducedMotion: true })));
    const svg = chart.renderToSVGString();
    const symbols = svg.match(/<path[^>]*fill="#fff"[^>]*stroke="#176c64"/g) || [];
    assert.equal(symbols.length, 27);
  } finally { chart.dispose(); }
});

test("negative outside values have their own gutter before the category labels", () => {
  const points = [point("200", "Cash"), point("-200", "Equity"), point("0", "Internal")];
  const bar = makeLieflatBarOption(options(points));
  assert.equal(bar.series[0].label.formatter({ dataIndex: 1 }), "-200");
  assert.equal(bar.series[0].data[1].value, -1);
  assert.ok(bar.yAxis.axisLabel.margin >= 40);
  assert.equal(bar.grid.left - bar.yAxis.axisLabel.margin, 108);
  const mobile = makeLieflatBarOption(options(points, { width: 320 }));
  assert.equal(mobile.series[0].label.show, false);
  assert.equal(mobile.grid.left, 88);
});

const { chartTheme } = await loadPreset("chart-theme.ts");
test("dark palette changes presentation while preserving exact rows, functions and light options", () => {
  const formatter = value => value;
  const option = { axisLabel: { color: "#53625f", formatter }, data: [["South", "9007199254740993.0001"], ["#176b57", null]], animation: false };
  assert.equal(chartTheme(option, false), option);
  const dark = chartTheme(option, true);
  assert.equal(dark.axisLabel.color, "#bbcec7");
  assert.equal(dark.axisLabel.formatter, formatter);
  assert.deepEqual(dark.data, option.data);
  assert.equal(option.axisLabel.color, "#53625f");
});
