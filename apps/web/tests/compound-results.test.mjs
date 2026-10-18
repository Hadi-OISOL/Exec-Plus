/* Check exact compound values and dispatch to the existing table/chart components. */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/compound-results.tsx", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const compiled = { exports: {} };
const nativeRequire = createRequire(import.meta.url);
const calls = [];
const require = name => {
  if (name === "./answer-visualization") return { AnswerVisualization: props => { calls.push(["chart", props]); return null; } };
  if (name === "./explore-components") return { RecordTable: props => { calls.push(["table", props]); return null; } };
  return nativeRequire(name);
};
new Function("require", "module", "exports", javascript)(require, compiled, compiled.exports);
const { CompoundResults } = compiled.exports;
const lineage = { query_id: "query-two", metric: "Revenue", aggregation: "sum", records_analyzed: 8, filters: ["Region = West"], sql: "SELECT 1" };
const render = results => renderToStaticMarkup(createElement(CompoundResults, { results }));

test("additional scalar keeps decimal precision and its own scope and evidence", () => {
  const html = render([{ value: "9007199254740993.000001", lineage }]);
  assert.match(html, /9007199254740993\.000001/);
  assert.match(html, /Calculation 2/);
  assert.match(html, /Region = West/);
  assert.match(html, /query-two/);
});

test("additional grouped results reach existing chart with unchanged cells", () => {
  calls.length = 0;
  const rows = [["West", "9007199254740993.000001"], ["East", null]];
  render([{ rows, columns: ["Region", "__value"], lineage }]);
  assert.equal(calls[0][0], "chart");
  assert.deepEqual(calls[0][1].rows, rows);
});

test("additional records reach exact table without treating identifiers as chart measures", () => {
  calls.length = 0;
  const rows = [["<script>", null]];
  render([{ rows, columns: ["ID", "Revenue"], matched_records: 12, lineage: { ...lineage, aggregation: "rows" } }]);
  assert.equal(calls[0][0], "table");
  assert.deepEqual(calls[0][1].data.rows, rows);
  assert.equal(calls[0][1].data.matched_records, 12);
});
