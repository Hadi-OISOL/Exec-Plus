/* Use case: Keeps the operator session-token sign-in out of production builds.
What it does: Evaluates the Next.js configuration per build phase and checks the sign-in form is gated by its build-time flag. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const source = await readFile(new URL("../next.config.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;

function config(phase, browserBuild) {
  const previous = process.env.EXECPLUS_BROWSER_BUILD;
  if (browserBuild) process.env.EXECPLUS_BROWSER_BUILD = "1";
  else delete process.env.EXECPLUS_BROWSER_BUILD;
  try {
    const module = { exports: {} };
    new Function("require", "module", "exports", javascript)(require, module, module.exports);
    return module.exports.default(phase);
  } finally {
    if (previous === undefined) delete process.env.EXECPLUS_BROWSER_BUILD;
    else process.env.EXECPLUS_BROWSER_BUILD = previous;
  }
}

test("production builds disable operator token sign-in", () => {
  assert.equal(config("phase-production-build", false).env.NEXT_PUBLIC_EXECPLUS_OPERATOR_SIGNIN, "0");
});

test("development servers and browser-test builds enable operator token sign-in", () => {
  assert.equal(config("phase-development-server", false).env.NEXT_PUBLIC_EXECPLUS_OPERATOR_SIGNIN, "1");
  assert.equal(config("phase-production-build", true).env.NEXT_PUBLIC_EXECPLUS_OPERATOR_SIGNIN, "1");
});

test("the session-token form renders only behind the build flag", async () => {
  const page = await readFile(new URL("../src/app/workspace/page.tsx", import.meta.url), "utf8");
  const gate = page.indexOf('process.env.NEXT_PUBLIC_EXECPLUS_OPERATOR_SIGNIN === "1"');
  assert.ok(gate > 0);
  assert.ok(page.indexOf('aria-label="Operator session"') > gate);
  assert.equal(page.split("Session token").length, 2);
});
