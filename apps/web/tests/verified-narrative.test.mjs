/* Use case: Protects readable explanations and historical plain-text evidence.
What it does: Verifies semantic section rendering, exact text retention and safe escaping of untrusted content. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/verified-narrative.tsx", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const compiled = { exports: {} };
new Function("require", "module", "exports", javascript)(createRequire(import.meta.url), compiled, compiled.exports);
const { VerifiedNarrative } = compiled.exports;
const render = narrative => renderToStaticMarkup(createElement(VerifiedNarrative, { narrative }));

const narrative = {
  version: "verified-narrative-v1", mode: "fallback",
  segments: [
    { statement_id: "F1", text: "The total is 9007199254740993.000001.", evidence_ids: ["receipt-one"], kind: "observation" },
    { statement_id: "F2", text: "Recorded association does not establish causation.", evidence_ids: ["receipt-one"], kind: "limitation" },
  ],
};

test("exact values, mandatory limits and evidence render accessibly in fallback mode", () => {
  const html = render(narrative);
  assert.match(html, /aria-label="Result explanation"/);
  assert.match(html, /9007199254740993\.000001/);
  assert.match(html, /data-kind="limitation"/);
  assert.match(html, /Recorded association does not establish causation/);
  assert.equal((html.match(/receipt-one/g) ?? []).length, 1);
  assert.match(html, /<summary>Explanation evidence<\/summary>/);
});

test("source quotations and labels stay plain escaped text", () => {
  const html = render({ ...narrative, segments: [{ ...narrative.segments[0], text: '<script>alert("bad")</script> **claim**' }] });
  assert.doesNotMatch(html, /<script>|<strong>/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /\*\*claim\*\*/);
});

test("unknown narrative versions leave existing answer renderer unchanged", () => {
  assert.equal(render({ ...narrative, version: "unknown" }), "");
});
