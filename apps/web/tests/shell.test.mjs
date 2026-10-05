/* Use case: Verifies the initial product shell remains honest about delivery state.
What it does: Protects trust language and distinguishes verified analytics from pending provider evaluations. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const pageUrl = new URL("../src/app/page.tsx", import.meta.url);

test("the shell states the verified-computation promise", async () => {
  const page = await readFile(pageUrl, "utf8");

  assert.match(page, /Trust the answer/);
  assert.match(page, /controlled query engine/);
  assert.match(page, /Answer and lineage/);
});

test("the shell distinguishes verified analytics from pending provider evaluations", async () => {
  const page = await readFile(pageUrl, "utf8");

  assert.match(page, /Remaining evaluation gates/);
  assert.match(page, /verified dashboards, saved analyses and workspace sharing are available/);
  assert.match(page, /href="\/workspace"/);
  assert.match(page, /Proactive insights and hybrid knowledge/);
});

