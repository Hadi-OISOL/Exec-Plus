/* Use case: Verifies the public website keeps its trust promises and drops engineering jargon.
What it does: Checks the landing names the read-only engine and lineage, links to the login and sign-up pages and no longer exposes phases or evaluation gates. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../src/app/page.tsx", import.meta.url), "utf8");

test("the website states the verified-computation promise", () => {
  assert.match(page, /read-only engine/);
  assert.match(page, /Lineage on every answer/);
  assert.match(page, /never supplies or rounds a number/);
});

test("the website links to the account pages and hides engineering state", () => {
  assert.match(page, /href="\/login"/);
  assert.match(page, /href="\/signup"/);
  assert.doesNotMatch(page, /evaluation gates|phase|Explore the foundation|Open your workspace/i);
});
