/* Use case: Protects exact evidence while presenting interactive answer charts.
What it does: Exercises missingness, signed scales, unsafe integers and eligibility without duplicating server calculations. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(
  new URL("../src/app/workspace/visualization-values.ts", import.meta.url),
  "utf8",
);
const javascript = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const {
  exactCell,
  plotNumber,
  chartEligible,
  plotPoints,
  plotScale,
  lineSegments,
  compareExactNumeric,
} = await import(
  `data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`
);

test("exact labels preserve decimal scale, category punctuation, false, zero and unsafe integers", () => {
  assert.deepEqual(
    ["9007199254740993.000001", "Alpha.00", false, 0, "-0.000", null].map(
      exactCell,
    ),
    ["9007199254740993.000001", "Alpha.00", "false", "0", "-0.000", "Missing"],
  );
});

test("non-numeric cells cannot become plotted zero or true/false measures", () => {
  for (const value of [
    null,
    undefined,
    true,
    false,
    "",
    " ",
    "0x10",
    "Infinity",
    "NaN",
    "1,000",
    Infinity,
  ])
    assert.equal(plotNumber(value), null);
  assert.equal(plotNumber("0.000"), 0);
  assert.equal(plotNumber("-1.25"), -1.25);
});

test("chart eligibility requires a distinct category and a consistently numeric measure", () => {
  assert.equal(
    chartEligible(
      ["city", "amount"],
      [
        ["North", "0.10"],
        ["South", null],
      ],
    ),
    true,
  );
  assert.equal(
    chartEligible(
      ["city", "amount"],
      [
        ["North", "0.10"],
        ["South", true],
      ],
    ),
    false,
  );
  assert.equal(chartEligible(["city", "amount"], [["North", null]]), false);
  assert.equal(chartEligible(["amount"], [["0.10"]]), false);
  assert.equal(
    chartEligible(["city", "amount"], [["North", "0.10"]], 1, 1),
    false,
  );
});

test("signed bars share a zero baseline and negative values extend in the opposite direction", () => {
  const points = plotPoints(
    [
      ["Loss", "-50"],
      ["Zero", "0"],
      ["Gain", "100"],
    ],
    0,
    1,
  );
  const scale = plotScale(points);
  assert.equal(scale.position(-50), 0);
  assert.equal(scale.position(100), 100);
  assert.ok(scale.position(-50) < scale.zero);
  assert.equal(scale.position(0), scale.zero);
  assert.ok(scale.position(100) > scale.zero);
  assert.equal(plotScale(plotPoints([["Only", "0"]], 0, 1)).position(0), 0);
});

test("finite extreme magnitudes never overflow plot positions", () => {
  const scale = plotScale(
    plotPoints(
      [
        ["a", "-1e308"],
        ["b", "1e308"],
      ],
      0,
      1,
    ),
  );
  assert.equal(scale.position(-1e308), 0);
  assert.equal(scale.zero, 50);
  assert.equal(scale.position(1e308), 100);
});

test("line gaps remain gaps and do not join known values across missing periods", () => {
  const segments = lineSegments(
    plotPoints(
      [
        ["Jan", "1.00"],
        ["Feb", null],
        ["Mar", "-2.00"],
        ["Apr", "0"],
      ],
      0,
      1,
    ),
  );
  assert.deepEqual(
    segments.map((segment) => segment.map((point) => point.index)),
    [[0], [2, 3]],
  );
  assert.equal(segments[0][0].x, 0);
  assert.ok(Math.abs(segments[1][0].x - 200 / 3) < 0.000001);
  assert.equal(segments[1][1].x, 100);
});

test("bounded geometry retains exact source cells and does not sort or mutate returned evidence", () => {
  const rows = [
    ["B", "9007199254740993.000001"],
    ["A", "9007199254740992.000001"],
    ["C", null],
  ];
  const original = structuredClone(rows);
  const points = plotPoints(rows, 0, 1, 2);
  assert.equal(points.length, 2);
  assert.equal(points[0].label, "B");
  assert.equal(points[0].raw, "9007199254740993.000001");
  assert.deepEqual(rows, original);
  assert.equal(
    plotPoints(
      Array.from({ length: 120 }, () => ["a", "1"]),
      0,
      1,
      1000,
    ).length,
    100,
  );
});

test("ranking categories compares decimal values exactly instead of rounding through Number", () => {
  const values = [
    "9007199254740993.000001",
    "9007199254740992.000001",
    "-0.0001",
    "0.0000",
    "-9007199254740993",
    ".01",
    "1e-8",
    "1.200",
    "1.20",
  ];
  assert.deepEqual([...values].sort(compareExactNumeric), [
    "-9007199254740993",
    "-0.0001",
    "0.0000",
    "1e-8",
    ".01",
    "1.200",
    "1.20",
    "9007199254740992.000001",
    "9007199254740993.000001",
  ]);
  assert.equal(compareExactNumeric("-0", "0"), 0);
  assert.equal(compareExactNumeric("0.00000000000000000000000000001", "0"), 1);
});
