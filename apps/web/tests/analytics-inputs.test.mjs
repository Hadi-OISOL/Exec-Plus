/* Use case: Protects how forecast event dates, simulation ranges and reorder inputs leave the browser.
What it does: Verifies that typed text becomes exact declared strings without converting values into JavaScript numbers. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function load(path) {
  const source = await readFile(new URL(path, import.meta.url), "utf8");
  const javascript = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);
}

const { eventPeriods } = await load("../src/app/workspace/forecast-types.ts");
const { simulationDrivers, simulationCorrelations, driverPairs } = await load("../src/app/workspace/source-scenario-types.ts");
const { reorderItems } = await load("../src/app/workspace/inventory-reorder-types.ts");

test("future event dates split on commas and spaces without inventing dates", () => {
  assert.deepEqual(eventPeriods(" 2024-03-13, 2024-03-20\n2024-03-27 "), ["2024-03-13", "2024-03-20", "2024-03-27"]);
  assert.deepEqual(eventPeriods(""), []);
});

test("only complete low/likely/high rows become simulation drivers, kept as exact strings", () => {
  const blank = { low: "", likely: "", high: "" };
  const drivers = simulationDrivers({
    price: { low: " -10 ", likely: "0", high: "20.000000000000000001" },
    quantity: { low: "-5", likely: "", high: "5" },
    variable_cost: blank,
    fixed_cost: blank,
  });
  assert.deepEqual(drivers, { price: { low: "-10", likely: "0", high: "20.000000000000000001" } });
});

test("only filled correlations between complete simulation drivers leave the browser", () => {
  const range = { low: "-5", likely: "0", high: "5" };
  const drivers = { price: range, quantity: range, variable_cost: range };
  assert.deepEqual(driverPairs(drivers), [["price", "quantity"], ["price", "variable_cost"], ["quantity", "variable_cost"]]);
  assert.deepEqual(
    simulationCorrelations(drivers, { "price|quantity": " 0.60 ", "price|variable_cost": "", "quantity|fixed_cost": "0.5" }),
    [{ first: "price", second: "quantity", value: "0.60" }],
  );
  assert.deepEqual(simulationCorrelations({ price: range }, { "price|quantity": "0.5" }), []);
});

test("typed reorder values stay exact strings and column-backed inputs are left out", () => {
  const rows = [
    { item: " Widget ", stock: " 12.50 ", reorder_point: "20", lead_time_days: "7", unit_cost: "" },
    { item: "  ", stock: "1", reorder_point: "1", lead_time_days: "1", unit_cost: "1" },
  ];
  assert.deepEqual(reorderItems(rows, { reorder_point: "reorder_point" }), [
    { item: "Widget", stock: "12.50", reorder_point: null, lead_time_days: 7, unit_cost: null },
  ]);
});
