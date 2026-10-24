/* Use case: Protects how forecast event dates, holidays, predictors and simulation ranges leave the browser.
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

const { declaredRegressors, eventPeriods } = await load("../src/app/workspace/forecast-types.ts");
const { simulationDrivers } = await load("../src/app/workspace/source-scenario-types.ts");

test("future event dates split on commas and spaces without inventing dates", () => {
  assert.deepEqual(eventPeriods(" 2024-03-13, 2024-03-20\n2024-03-27 "), ["2024-03-13", "2024-03-20", "2024-03-27"]);
  assert.deepEqual(eventPeriods(""), []);
});

test("holidays and outside predictors leave the browser as exact declared strings", () => {
  const blank = { column: "", aggregation: "avg", future: "" };
  assert.deepEqual(declaredRegressors("", "", [blank, blank, blank]), {});
  assert.deepEqual(
    declaredRegressors("pk-public-fixed-v1", " 2024-04-10, 2024-04-11 ", [
      { column: "visits", aggregation: "sum", future: "120, 118.50 130.000000000000000001" },
      blank,
      blank,
    ]),
    {
      holiday_calendar: "pk-public-fixed-v1",
      holiday_dates: ["2024-04-10", "2024-04-11"],
      predictors: [{ column: "visits", aggregation: "sum", future_values: ["120", "118.50", "130.000000000000000001"] }],
    },
  );
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
