/* Use case: Protects the suggested-unit dropdown in the data reading.
What it does: Checks that column-name hints rank first, unitless is always offered and the server suggestion leads. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/unit-choices.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { unitChoices } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

test("column words decide the first suggestions and unitless is always offered", () => {
  assert.deepEqual(unitChoices("total_score").slice(0, 2), ["unitless", "points"]);
  assert.deepEqual(unitChoices("Rainfall_mm").slice(0, 2), ["mm", "cm"]);
  assert.deepEqual(unitChoices("Temperature_C").slice(0, 2), ["°C", "°F"]);
  assert.equal(unitChoices("average_price")[0], "USD");
  assert.ok(!unitChoices("average_price").includes("years"));
  assert.ok(unitChoices("phone_extension").includes("unitless"));
  assert.ok(!unitChoices("phone_extension").includes("pH"));
});

test("the server suggestion leads without duplicates", () => {
  const choices = unitChoices("Field_Area_hectare", "hectare");
  assert.equal(choices[0], "hectare");
  assert.equal(choices.filter((unit) => unit === "hectare").length, 1);
});
