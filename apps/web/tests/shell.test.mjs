/* Use case: Verifies the initial product shell remains honest about delivery state.
What it does: Protects trust language and distinguishes available uploads from planned profiling. */

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

test("the shell distinguishes available ingestion from planned profiling", async () => {
  const page = await readFile(pageUrl, "utf8");

  assert.match(page, /Next delivery phase/);
  assert.match(page, /Secure CSV and XLSX ingestion is available in the local workspace flow/);
  assert.match(page, /href="\/workspace"/);
  assert.match(page, /Dataset profiling and quality/);
  assert.match(page, /Week 1 · Secure ingestion/);
});

