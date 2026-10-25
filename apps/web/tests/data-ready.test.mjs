/* Use case: Guards the "Your data is ready" card shown after upload.
What it does: Renders DataReady on the server with fixtures and a mocked dataset-purpose request, checking exact values, real analyst statuses, purpose fallbacks and question chips. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const compiled = { exports: {} };
  cache.set(file, compiled);
  const output = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
  const local = path => {
    if (path.endsWith(".module.css")) return { default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (!path.startsWith(".")) return require(path);
    const base = resolve(dirname(file), path);
    return load([`${base}.ts`, `${base}.tsx`].find(existsSync));
  };
  new Function("require", "module", "exports", output)(local, compiled, compiled.exports);
  return compiled.exports;
}
const { DataReady, analystTeam, loadPurpose, profileAnswer, purposePath, questionChips } = load(resolve(dirname(fileURLToPath(import.meta.url)), "../src/app/workspace/insights/data-ready.tsx"));

const root = "/workspaces/w1/datasets/d1/uploads/u1";
const purpose = {
  version: "dataset-purpose-v1", summary: "Sales leads by region and owner.",
  benefits: ["See which regions bring the most leads"],
  suggested_questions: [{ title: "Best region", question: "Which region has the most leads?" }],
  profile_question: { question: "What best describes you?", choices: ["Sales manager", "Owner"] },
};
const insights = {
  version: "insights-v1", dataset_name: "leads.csv", definition_state: "inferred", kpis: [],
  insights: [{ id: "segment:a", analyst: "segment", title: "Deal_Value by Region", summary: "North is highest.",
    evidence: [{ label: "Highest average", value: "9.291538461538", unit: "PKR" }],
    actions: [{ id: "x", kind: "show", label: "Show North deals", payload: { type: "ask", question: "Show deals in North" } }] }],
};
const noop = () => {};
const props = (extra = {}) => ({ fileName: "leads.csv", rows: 1200, columns: 8, seconds: "1.4", summary: "Fallback summary.", confirmed: false,
  insights: { status: "done", payload: insights }, team: analystTeam({ reading: "done", insights: { status: "done", payload: insights }, dashboard: "working", purpose: "done" }),
  questions: questionChips(purpose, ["Fallback question?"]), words: text => text, onAsk: noop, onDashboard: noop, onReview: noop, onQuestion: noop, onAction: noop, onSee: noop, ...extra });

test("the purpose request maps the upload root and hides itself on 404 or a wrong version", async () => {
  assert.equal(purposePath(root), "/workspaces/w1/uploads/u1/dataset-purpose");
  const asked = [];
  const ok = await loadPurpose(root, async path => { asked.push(path); return purpose; });
  assert.deepEqual(asked, ["/workspaces/w1/uploads/u1/dataset-purpose"]);
  assert.equal(ok.status, "done");
  assert.equal((await loadPurpose(root, async () => { throw new Error("404 Not Found"); })).status, "unavailable");
  assert.equal((await loadPurpose(root, async () => ({ version: "other" }))).status, "unavailable");
});

test("the ready card shows the file, exact finding value, purpose and primary actions", () => {
  const html = renderToStaticMarkup(createElement(DataReady, { ...props(), purpose }));
  assert.match(html, /Your data is ready/);
  assert.match(html, /leads\.csv/);
  assert.match(html, /1,200 rows × 8 columns · first reading in 1\.4 s/);
  assert.match(html, /Sales leads by region and owner\./);
  assert.doesNotMatch(html, /Fallback summary/);
  assert.match(html, /9\.291538461538 PKR/);
  assert.match(html, /Show North deals/);
  for (const label of ["Ask Syntelio", "See dashboard", "Review meanings", "How this data can help you", "What best describes you?", "Sales manager", "Best region"]) assert.ok(html.includes(label), label);
});

test("without a purpose the card falls back to the first reading and its suggestions", () => {
  const html = renderToStaticMarkup(createElement(DataReady, props({ questions: questionChips(undefined, ["Fallback question?"]) })));
  assert.match(html, /Fallback summary\./);
  assert.match(html, /Fallback question\?/);
  assert.doesNotMatch(html, /How this data can help you/);
});

test("analyst statuses come from real request states", () => {
  const working = analystTeam({ reading: "done", insights: { status: "working" }, dashboard: "waiting", purpose: "unavailable" });
  assert.deepEqual(working.map(item => item.status), ["done", "working", "working", "working", "working", "working", "working", "waiting", "unavailable"]);
  const done = analystTeam({ reading: "done", insights: { status: "done", payload: insights }, dashboard: "done", purpose: "done" });
  assert.equal(done.find(item => item.id === "segment").detail, "Found 1 thing worth a look");
  assert.equal(done.find(item => item.id === "quality").detail, "Nothing stood out");
  const html = renderToStaticMarkup(createElement(DataReady, props({ insights: { status: "working" } })));
  assert.match(html, /still checking/);
  assert.match(html, /aria-busy="true"/);
});

test("profile choices become a chat answer", () => {
  assert.equal(profileAnswer("Sales manager"), "I am a Sales manager");
  assert.equal(profileAnswer("Owner"), "I am an Owner");
});
