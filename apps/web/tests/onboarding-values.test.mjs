/* Use case: Protects the questionnaire rules the first-run flow relies on.
What it does: Checks when the flow shows, chip toggling and the exact payload sent to /me/profile. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/onboarding/onboarding-values.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { profileNeeded, toggleChoice, hasAnswer, profilePayload, progressLabel } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

test("the flow shows only for self-service accounts without a decided profile", () => {
  assert.equal(profileNeeded({ status: "pending" }, "local_password"), true);
  assert.equal(profileNeeded({ status: "pending" }, "external_google"), true);
  assert.equal(profileNeeded({ status: "pending" }, "operator"), false);
  assert.equal(profileNeeded({ status: "skipped" }, "local_password"), false);
  assert.equal(profileNeeded({ status: "completed" }, "local_password"), false);
  assert.equal(profileNeeded(null, "local_password"), false);
});

test("multi-select chips toggle without duplicates and emptiness is detected", () => {
  assert.deepEqual(toggleChoice(undefined, "Forecast"), ["Forecast"]);
  assert.deepEqual(toggleChoice(["Forecast"], "Track KPIs"), ["Forecast", "Track KPIs"]);
  assert.deepEqual(toggleChoice(["Forecast", "Track KPIs"], "Forecast"), ["Track KPIs"]);
  assert.equal(hasAnswer("  "), false);
  assert.equal(hasAnswer([]), false);
  assert.equal(hasAnswer("Retail"), true);
});

test("the payload keeps only real answers, trims text and never nests the name", () => {
  const payload = profilePayload(2, "  Hadi  ", { role: "Analyst", goals: [], anything_else: "  ", regions_currency: " PKR ", preferred_name: "x" }, "skipped");
  assert.deepEqual(payload, { expected_version: 2, preferred_name: "Hadi", answers: { role: "Analyst", regions_currency: "PKR" }, status: "skipped" });
  assert.equal(progressLabel(2, 18), "3 of 18");
});
