/* Use case: Protects the pure layout helpers of the public-site receipt kit.
What it does: Checks that the perforated edge polygon spans the full width with alternating teeth and that bar widths clamp to 0–100% without touching displayed strings. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function loadHelpers() {
  const source = await readFile(new URL("../src/app/site/receipt/receipt.tsx", import.meta.url), "utf8");
  const compiled = { exports: {} };
  const stubs = { "./receipt.module.css": {}, "./stamp": { Stamp: () => null }, react: {}, "react/jsx-runtime": { jsx: () => null, jsxs: () => null } };
  new Function("require", "module", "exports", ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText)(path => stubs[path] ?? {}, compiled, compiled.exports);
  return compiled.exports;
}

test("tearPoints covers the full width with alternating teeth", async () => {
  const { tearPoints } = await loadHelpers();
  const points = tearPoints(4, 4).split(" ");
  assert.deepEqual(points, ["0,0", "100,0", "100,4", "75,0", "50,4", "25,0", "0,4"]);
  assert.equal(tearPoints(24).split(" ").length, 27);
});

test("barWidth clamps shares into a percentage", async () => {
  const { barWidth } = await loadHelpers();
  assert.equal(barWidth(1), "100%");
  assert.equal(barWidth(1599.96 / 1744.51), "91.7%");
  assert.equal(barWidth(-2), "0%");
  assert.equal(barWidth(7), "100%");
});
