/* Use case: Protects exact immutable forecasts during later-actual presentation.
What it does: Verifies pending periods and comparison overlays without converting server decimals into JavaScript numbers. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(
  new URL("../src/app/workspace/forecast-types.ts", import.meta.url),
  "utf8",
);
const javascript = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const { forecastRows } = await import(
  `data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`
);
const predictions = [
  {
    period: "2027-01-01",
    estimate: "9007199254740993.000001",
    lower: "9007199254740992.000001",
    upper: "9007199254740994.000001",
  },
  {
    period: "2027-02-01",
    estimate: "0.000000000000000001",
    lower: "-0.1",
    upper: "0.1",
  },
];

test("a forecast with no actual comparison preserves exact strings and shows pending values", () => {
  const rows = forecastRows(predictions);
  assert.equal(rows[0].estimate, "9007199254740993.000001");
  assert.equal(rows[1].estimate, "0.000000000000000001");
  assert.equal(rows[0].actual, null);
  assert.equal(rows[0].status, "pending");
  assert.equal(predictions[0].actual, undefined);
});

test("later observations are matched by period and cannot overwrite saved estimates or intervals", () => {
  const rows = forecastRows(predictions, {
    result: {
      rows: [
        {
          period: "2027-01-01",
          actual: "0",
          error: "-9007199254740993.000001",
          absolute_error: "9007199254740993.000001",
          estimate: "999",
          lower: "888",
          upper: "1111",
          status: "observed",
        },
        { period: "2028-01-01", actual: "99", status: "observed" },
      ],
    },
  });
  assert.equal(rows.length, 2);
  assert.equal(rows[0].estimate, predictions[0].estimate);
  assert.equal(rows[0].lower, predictions[0].lower);
  assert.equal(rows[0].actual, "0");
  assert.equal(rows[0].status, "observed");
  assert.equal(rows[1].actual, null);
  assert.equal(rows[1].status, "pending");
});
