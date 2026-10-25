/* Use case: Protects how prediction-model choices and results are shown.
What it does: Checks unavailable inputs stay explained, the target is never an input and numbers stay as returned. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/prediction-model-values.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { inputChoices, isPredictionMethod, metricRows, weightLabel } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

const options = {
  model: "prediction-model-v1", state: "ready", available: true, maximum_inputs: 30, maximum_rows: 10000, holdout_percent: 20,
  targets: [{ name: "outcome", task: "classification" }],
  inputs: [
    { name: "outcome", kind: "category", excluded_reason: null },
    { name: "visits", kind: "numeric", excluded_reason: null },
    { name: "call duration", kind: "numeric", excluded_reason: "Known after the outcome." },
  ],
};

test("input choices drop the target and disable leaking fields with their reason", () => {
  const choices = inputChoices(options, "outcome");
  assert.deepEqual(choices.map(item => item.name), ["visits", "call duration"]);
  assert.equal(choices[0].disabled, false);
  assert.equal(choices[1].disabled, true);
  assert.equal(choices[1].excluded_reason, "Known after the outcome.");
});

test("metric rows keep server strings for both tasks", () => {
  const classification = { task: "classification", metrics: { auc: "0.7654", accuracy: "0.8905" }, baseline: { auc: "0.5000", accuracy: "0.8850" } };
  assert.deepEqual(metricRows(classification)[0].slice(1), ["0.7654", "0.5000"]);
  const regression = { task: "regression", metrics: { mae: "1.6000", r2: "0.9000" }, baseline: { mae: "7.5000", r2: "-0.0100" } };
  assert.deepEqual(metricRows(regression).map(row => row.slice(1)), [["1.6000", "7.5000"], ["0.9000", "-0.0100"]]);
});

test("method and weight labels", () => {
  assert.equal(isPredictionMethod("prediction-model-v1"), true);
  assert.equal(isPredictionMethod("reference-mahalanobis-squared-v1"), false);
  assert.equal(weightLabel({ input: "channel", level: "partner" }), "channel = partner");
  assert.equal(weightLabel({ input: "visits", level: null }), "visits");
});
