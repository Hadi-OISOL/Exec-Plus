/* Use case: Protects the "Your chats" list labels and file matching.
What it does: Checks relative activity times and that a chat opens in place only for its own file. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/chat-history-values.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { activityLabel, belongsToSource } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

test("activity labels read naturally and fall back to a date", () => {
  const now = new Date("2026-10-24T12:00:00Z");
  assert.equal(activityLabel("2026-10-24T11:59:40Z", now), "Just now");
  assert.equal(activityLabel("2026-10-24T11:15:00Z", now), "45 min ago");
  assert.equal(activityLabel("2026-10-24T07:00:00Z", now), "5 h ago");
  assert.equal(activityLabel("2026-10-21T12:00:00Z", now), "3 d ago");
  assert.equal(activityLabel("2026-09-01T12:00:00Z", now), new Date("2026-09-01T12:00:00Z").toLocaleDateString());
  assert.equal(activityLabel("not a date", now), "");
});

test("a chat belongs only to its own dataset and upload", () => {
  const root = "/workspaces/w/datasets/d1/uploads/u1";
  assert.equal(belongsToSource({ dataset_id: "d1", upload_id: "u1" }, root), true);
  assert.equal(belongsToSource({ dataset_id: "d1", upload_id: "u2" }, root), false);
  assert.equal(belongsToSource({ dataset_id: "d2", upload_id: "u1" }, root), false);
  assert.equal(belongsToSource({ dataset_id: "d1", upload_id: "u1" }, ""), false);
});
