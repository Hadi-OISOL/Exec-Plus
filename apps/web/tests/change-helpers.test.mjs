/* Use case: Protects the month-window, exact add-back and per-period grouping helpers.
What it does: Checks calendar edges, BigInt fraction sums and that saved schedules group by period only. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/change-helpers.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { monthWindows, addsBack, byPeriod } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

test("a month compares with the month before, across a year boundary", () => {
  assert.deepEqual(monthWindows("2026-03", "previous"), ["2026-02-01", "2026-02-28", "2026-03-01", "2026-03-31"]);
  assert.deepEqual(monthWindows("2026-01", "previous"), ["2025-12-01", "2025-12-31", "2026-01-01", "2026-01-31"]);
});

test("same month last year respects leap years", () => {
  assert.deepEqual(monthWindows("2025-02", "year"), ["2024-02-01", "2024-02-29", "2025-02-01", "2025-02-28"]);
});

test("invalid month input fills nothing", () => {
  assert.equal(monthWindows("", "previous"), null);
  assert.equal(monthWindows("2026-13", "previous"), null);
});

test("exact fractions add back without floating point error", () => {
  const tenth = { numerator: "1", denominator: "10" };
  const fifth = { numerator: "1", denominator: "5" };
  assert.equal(addsBack([tenth, fifth], { numerator: "3", denominator: "10" }), true);
  assert.equal(addsBack([tenth, fifth], { numerator: "30000000000000001", denominator: "100000000000000000" }), false);
  assert.equal(addsBack([{ numerator: "31", denominator: "2" }, { numerator: "-1", denominator: "5" }], { numerator: "153", denominator: "10" }), true);
  assert.equal(addsBack([], { numerator: "0", denominator: "1" }), true);
});

test("scheduled actions group by their saved period and unselected actions are left out", () => {
  const rows = [{ candidate: "A", period: 1 }, { candidate: "B", period: 3 }, { candidate: "C", period: null }];
  assert.deepEqual(byPeriod(rows, 3).map(group => group.map(row => row.candidate)), [["A"], [], ["B"]]);
});
