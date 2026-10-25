/* Use case: Guards the automatic dashboard model: line charts and tile-to-study mapping.
What it does: Loads the real model modules and checks exact line series, study methods for each tile kind and the selection note. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const compiled = { exports: {} };
  cache.set(file, compiled);
  const output = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const local = path => {
    if (!path.startsWith(".")) return require(path);
    const base = resolve(dirname(file), path);
    return load([`${base}.ts`, `${base}.tsx`].find(existsSync));
  };
  new Function("require", "module", "exports", output)(local, compiled, compiled.exports);
  return compiled.exports;
}
const here = dirname(fileURLToPath(import.meta.url));
const { studyMethod, selectionNote } = load(resolve(here, "../src/app/workspace/insights/auto-dashboard-model.ts"));
const { chartSpecFromInsight } = load(resolve(here, "../src/app/workspace/insights/insights-model.ts"));

const tile = (id, kind, columns) => ({ id, kind, columns, title: "t", reason: "r", query_ids: [] });

test("trend tiles become exact line charts", () => {
  const spec = chartSpecFromInsight({ type: "line", title: "amount per month", x: { field: "label", label: "order_date" }, y: { field: "value", label: "amount", unit: "PKR" }, rows: [{ label: "2024-01-01", value: "10.50" }, { label: "2024-02-01", value: null }] });
  assert.equal(spec.kind, "line");
  assert.deepEqual(spec.x, ["2024-01-01", "2024-02-01"]);
  assert.deepEqual(spec.series[0].values, ["10.50", null]);
  assert.equal(spec.unit, "PKR");
});

test("tiles map to existing descriptive study methods for pinning", () => {
  assert.deepEqual(studyMethod(tile("kpi:sum:amount", "kpi", ["amount"])), { kind: "metric", column: "amount", aggregation: "sum", group_by: [] });
  assert.deepEqual(studyMethod(tile("top:avg:score:region", "top", ["score", "region"])), { kind: "metric", column: "score", aggregation: "avg", group_by: ["region"] });
  assert.deepEqual(studyMethod(tile("share:amount:region", "share", ["amount", "region"])), { kind: "metric", column: "amount", aggregation: "sum", group_by: ["region"] });
  assert.deepEqual(studyMethod(tile("category:region", "category", ["region"])), { kind: "distribution", column: "region", aggregation: "count", group_by: [] });
  assert.equal(studyMethod(tile("kpi:rows", "kpi", [])), null);
  assert.equal(studyMethod(tile("analyst:outlier:amount", "analyst", ["amount"])), null);
});

test("the selection note says who picked the tiles", () => {
  assert.match(selectionNote({ selection: { route: "deterministic:auto-dashboard-v1" } }), /fixed score/);
  assert.match(selectionNote({ selection: { route: "deepseek:deepseek-v4-pro" } }), /language model ranked/);
  assert.match(selectionNote({ selection: { route: "user:edit" } }), /You chose/);
});
