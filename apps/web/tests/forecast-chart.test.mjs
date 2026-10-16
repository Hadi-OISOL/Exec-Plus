/* Use case: Protects exact forecast display while improving the chart interface.
What it does: Checks finite rendering, explicit uncertainty, missing observations and keyboard inspection without changing saved values. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/forecast-results.tsx", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
const compiled = { exports: {} };
const require = createRequire(import.meta.url);
const valuesSource = await readFile(new URL("../src/app/workspace/visualization-values.ts", import.meta.url), "utf8");
const values = { exports: {} };
new Function("require", "module", "exports", ts.transpileModule(valuesSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(require, values, values.exports);
const load = name => name.endsWith(".module.css") ? { default: new Proxy({}, { get: (_, key) => key }) } : name === "./visualization-values" ? values.exports : name.startsWith("./") ? {} : require(name);
new Function("require", "module", "exports", javascript)(load, compiled, compiled.exports);
const { ForecastChart } = compiled.exports;
const run = { request: { metric: "revenue", frequency: "daily" }, evidence: { unit: "USD" }, result: { history: [{ period: "2026-01-01", actual: "0" }, { period: "2026-01-02", actual: null }, { period: "2026-01-03", actual: "-0.0000000000001" }] } };
const rows = [{ period: "2026-01-04", estimate: "9007199254740993.000001", lower: "9007199254740992.000001", upper: "9007199254740994.000001", actual: null }];
const render = (input = run, forecast = rows) => renderToStaticMarkup(createElement(ForecastChart, { run: input, rows: forecast }));

test("forecasts keep exact values, distinct observed and estimated regions, and accessible inspection", () => {
  const html = render();
  assert.match(html, /9007199254740993\.000001/);
  assert.match(html, /-0\.0000000000001/);
  assert.match(html, /First forecast value/);
  assert.match(html, /Forecast starts 2026-01-04/);
  assert.match(html, /Uncertainty range/);
  assert.match(html, /Awaiting actual data/);
  assert.match(html, /Use left and right arrow keys to inspect periods/);
  assert.match(html, /Axis labels and chart positions are approximate/);
  assert.match(html, /aria-label="Inspect previous period"/);
  assert.equal((html.match(/class="forecastActual"/g) ?? []).length, 2);
  assert.equal((html.match(/class="forecastEstimate"/g) ?? []).length, 1);
  assert.doesNotMatch(html, /<polyline|<path|NaN|Infinity/);
});

test("opposite extreme values normalize before subtraction and never generate infinite chart coordinates", () => {
  const html = render({ ...run, result: { history: [{ period: "2026-01-01", actual: "-1e308" }, { period: "2026-01-02", actual: "1e308" }] } }, [{ ...rows[0], estimate: "0", lower: "-1e308", upper: "1e308" }]);
  assert.doesNotMatch(html, /NaN|Infinity/);
  assert.match(html, /<dd>0<\/dd>/);
  assert.match(html, /-1e308 to 1e308/);
});

test("missing history cannot become zero and intervals retain separate observed values", () => {
  const html = render({ ...run, result: { history: [] } }, [{ ...rows[0], actual: "0" }, { ...rows[0], period: "2026-01-05", actual: null }]);
  assert.equal((html.match(/class="forecastActual"/g) ?? []).length, 1);
  assert.equal((html.match(/class="forecastEstimate"/g) ?? []).length, 2);
  assert.match(html, /class="forecastBand"/);
  assert.match(html, /Last value before forecast<\/span><strong title="Not available">Not available/);
  assert.match(html, /<dt>Observed<\/dt><dd>0<\/dd>/);
  assert.doesNotMatch(html, /<polyline|<path/);
});

test("empty or nonfinite series provide an honest values-table fallback", () => {
  assert.match(render({ ...run, result: { history: [] } }, []), /No finite values can be plotted/);
  const html = render({ ...run, result: { history: [{ period: "2026-01-01", actual: "1e999" }] } }, []);
  assert.match(html, /original values remain in the table/);
  assert.doesNotMatch(html, /<svg|NaN|Infinity/);
});

test("history without predictions cannot draw a negative-width forecast region", () => {
  const html = render(run, []);
  assert.match(html, /No forecast period/);
  assert.doesNotMatch(html, /class="forecastZone"|width="-|NaN|Infinity/);
  assert.equal((html.match(/class="forecastActual"/g) ?? []).length, 2);
});

test("large highlights remove only insignificant zeros while retaining raw titles and meaningful decimals", () => {
  const html = render({ ...run, result: { history: [{ period: "2026-01-03", actual: "4000.000000000000" }] } }, [{ ...rows[0], estimate: "9007199254740993.000001000000" }]);
  assert.match(html, /<strong title="4000\.000000000000">4,000<\/strong>/);
  assert.match(html, /<strong title="9007199254740993\.000001000000">9,007,199,254,740,993\.000001<\/strong>/);
  assert.match(html, /<dd>9007199254740993\.000001000000<\/dd>/);
});
