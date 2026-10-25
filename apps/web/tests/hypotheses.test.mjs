/* Use case: Guards the "Things we checked for you" section and its private vote.
What it does: Loads hypotheses-v1 through a mocked request, renders supported checks first with exact figures and a collapsed rest list, and checks vote ordering and toggling. */

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
const here = dirname(fileURLToPath(import.meta.url));
const { HypothesisList, evidenceRows, hypothesesPath, loadHypotheses, withVote } = load(resolve(here, "../src/app/workspace/insights/hypotheses.tsx"));

const root = "/workspaces/w1/datasets/d1/uploads/u1";
const item = (id, kind, status, extra = {}) => ({
  id, kind, origin: "server", status, statement: `Statement ${id}`, finding: `Finding ${id}`, question: `Question ${id}?`, feedback: null,
  evidence: { group_average: "8.083333333333", other_average: "5.791666666667", rule: "Supported when …", query_id: "q1" }, ...extra,
});
const payload = {
  version: "hypotheses-v1", limitations: ["A supported pattern is not proof of a cause."],
  items: [item("a", "group_gap", "not_supported"), item("b", "relationship", "supported"), item("c", "recent_change", "not_enough_data"), item("d", "concentration", "supported")],
};

test("the endpoint maps the upload root and hides itself when unavailable", async () => {
  assert.deepEqual(hypothesesPath(root), { list: "/workspaces/w1/uploads/u1/hypotheses", feedback: "/workspaces/w1/hypothesis-feedback" });
  const seen = [];
  const loaded = await loadHypotheses(root, async path => { seen.push(path); return payload; });
  assert.equal(loaded.status, "done");
  assert.deepEqual(seen, ["/workspaces/w1/uploads/u1/hypotheses"]);
  assert.equal((await loadHypotheses(root, async () => { throw new Error("404"); })).status, "unavailable");
  assert.equal((await loadHypotheses(root, async () => ({ version: "other" }))).status, "unavailable");
  assert.equal((await loadHypotheses("/elsewhere", async () => payload)).status, "unavailable");
});

test("supported checks come first with exact figures and the rest stay collapsed", () => {
  const html = renderToStaticMarkup(createElement(HypothesisList, { ...payload, words: text => text, onQuestion: () => {}, onVote: () => {} }));
  assert.ok(html.includes("Things we checked for you"));
  const [open, collapsed] = html.split("<details");
  assert.ok(open.indexOf("Statement b") < open.indexOf("Statement d"));
  assert.ok(!open.includes("Statement a") && collapsed.includes("Statement a") && collapsed.includes("Statement c"));
  assert.ok(collapsed.includes("Not supported or not enough data (2)"));
  assert.ok(html.includes("8.083333333333") && html.includes("Ask about this"));
  assert.ok(!html.includes(">q1<"));
  assert.ok(html.includes('aria-pressed="false"'));
  assert.deepEqual(evidenceRows(payload.items[0]), [["group average", "8.083333333333"], ["other average", "5.791666666667"]]);
});

test("a dislike sinks that type, a like rises, and clearing restores the order", () => {
  const disliked = withVote(payload.items, "relationship", "dislike");
  assert.deepEqual(disliked.map(entry => entry.id), ["a", "c", "d", "b"]);
  assert.equal(disliked.at(-1).feedback, "dislike");
  assert.deepEqual(withVote(disliked, "relationship", null).map(entry => entry.id), ["a", "c", "d", "b"]);
  assert.deepEqual(withVote(payload.items, "concentration", "like").map(entry => entry.id), ["d", "a", "b", "c"]);
});
