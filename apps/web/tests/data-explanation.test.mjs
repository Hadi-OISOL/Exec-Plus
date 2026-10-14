/* Use case: Protects readable explanations and historical plain-text evidence.
What it does: Verifies semantic section rendering, exact text retention and safe escaping of untrusted content. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/data-explanation.tsx", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const compiled = { exports: {} };
new Function("require", "module", "exports", javascript)(createRequire(import.meta.url), compiled, compiled.exports);
const { DataExplanation } = compiled.exports;
const render = message => renderToStaticMarkup(createElement(DataExplanation, { message }));

test("meaning and the one clarification have accessible headings while context stays a disclosure", () => {
  const html = render("What this data is about\nField observations.\n\nOne thing to clarify\nWhat does each row describe?\n\nContext used\nSaved definitions; no dates supplied.");
  assert.match(html, /<section[^>]+aria-labelledby="([^"]+)"[^>]*><h3 id="\1">What this data is about<\/h3>/);
  assert.match(html, /data-kind="clarify"/);
  assert.match(html, /<details class="explanationContext"><summary>Context used<\/summary>/);
  assert.doesNotMatch(html, /<details[^>]+open/);
  assert.match(html, /Saved definitions; no dates supplied\./);
});

test("historical paragraphs and unfamiliar headings remain readable without text rewriting", () => {
  const html = render("It contains 100 rows and 20 columns.\n\nUnfamiliar heading\n9007199254740993.000001\nObserved, not predicted.");
  assert.match(html, /<p class="explanationPlain">It contains 100 rows and 20 columns\.<\/p>/);
  assert.match(html, /Unfamiliar heading\n9007199254740993\.000001\nObserved, not predicted\./);
  assert.doesNotMatch(html, /<section/);
});

test("source text stays escaped even inside a recognized explanation section", () => {
  const html = render('What this data is about\n<script>alert("unsafe")</script> & **not markup**');
  assert.doesNotMatch(html, /<script>|<strong>/);
  assert.match(html, /&lt;script&gt;alert\(&quot;unsafe&quot;\)&lt;\/script&gt; &amp; \*\*not markup\*\*/);
});
