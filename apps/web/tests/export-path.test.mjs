/* Use case: Protects the authenticated export boundary in the browser.
What it does: Allows supported private export routes and rejects arbitrary hosts, traversal and malformed identifiers. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/export-path.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { allowedExportPath } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);
const id = "c364ec01-7390-4222-9cc4-a16be97c15fd";

test("all governed answer, analysis, board and company export routes are accepted", () => {
  for (const format of ["pdf", "xlsx", "csv", "png"]) {
    for (const path of [
      `/organizations/${id}/consolidations/${id}/export.${format}`,
      `/workspaces/${id}/threads/${id}/turns/${id}/export.${format}`,
      `/workspaces/${id}/datasets/${id}/forecasts/${id}/export.${format}`,
      `/workspaces/${id}/datasets/${id}/forecasts/${id}/comparisons/${id}/export.${format}`,
      `/workspaces/${id}/datasets/${id}/analyses/${id}/export.${format}`,
      `/workspaces/${id}/study-versions/${id}/export.${format}`,
      `/workspaces/${id}/study-boards/${id}/export.${format}`,
    ]) assert.equal(allowedExportPath(path + "?chart=0"), true, path);
  }
  assert.equal(allowedExportPath(`/workspaces/${id}/exports/dashboard`), true);
});

test("download authentication never accepts external URLs or unrelated application paths", () => {
  const path = `/organizations/${id}/consolidations/${id}/export.pdf`;
  for (const unsafe of [
    `https://example.test${path}`, `//example.test${path}`, `http://localhost:8001${path}`,
    `\\example.test${path}`, path + "/../secret", path + "%3Fsecret", path + "#fragment",
    path.replace(id, "-".repeat(36)), path.replace(id, "../../secret"),
    `/organizations/${id}/members`, `/workspaces/${id}/secrets`, path.replace(".pdf", ".html"),
  ]) assert.equal(allowedExportPath(unsafe), false, unsafe);
});
