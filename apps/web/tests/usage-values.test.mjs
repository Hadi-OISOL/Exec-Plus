/* Use case: Protects the exact daily usage table and limit shares shown to owners and staff.
What it does: Checks zero-filled UTC days, exact server counts and whole-percent shares without rounding up. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/usage-values.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { dailyHistory, usedShare } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

test("daily history covers every day newest first and fills missing days with zero", () => {
  const days = dailyHistory({
    from: "2026-09-25",
    to: "2026-10-24",
    kinds: ["exports", "uploads"],
    rows: [
      { day: "2026-10-24", kind: "exports", count: 4 },
      { day: "2026-10-24", kind: "uploads", count: 1 },
      { day: "2026-10-21", kind: "exports", count: 2 },
      { day: "2026-09-25", kind: "uploads", count: 9007199254740991 },
    ],
  });
  assert.equal(days.length, 30);
  assert.deepEqual(days[0], { day: "2026-10-24", counts: { exports: 4, uploads: 1 }, total: 5 });
  assert.deepEqual(days[1], { day: "2026-10-23", counts: { exports: 0, uploads: 0 }, total: 0 });
  assert.equal(days[3].counts.exports, 2);
  assert.equal(days[29].day, "2026-09-25");
  assert.equal(days[29].counts.uploads, 9007199254740991);
});

test("limit share floors to whole percent and handles unlimited and zero limits", () => {
  assert.equal(usedShare(4, 5), "80%");
  assert.equal(usedShare(799, 1000), "79%");
  assert.equal(usedShare(0, 0), "100%");
  assert.equal(usedShare(3, null), "No plan limit");
  assert.equal(usedShare(null, 10), "No plan limit");
});
