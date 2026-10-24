/* Use case: Protects the "Your chats" list labels and file matching.
What it does: Checks relative activity times and that a chat opens in place only for its own file. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/chat-history-values.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { activityLabel, belongsToSource, chatsPath, groupChats } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

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

test("chats group by recency in the order the server returns them", () => {
  const now = new Date(2026, 9, 24, 15, 0);
  const at = (d, h) => new Date(2026, 9, d, h).toISOString();
  const chats = [at(24, 9), at(24, 0), at(23, 23), at(20, 8), at(17, 12), at(1, 12)].map((last_activity, id) => ({ id, last_activity }));
  assert.deepEqual(
    groupChats(chats, now).map((group) => [group.label, group.chats.map((chat) => chat.id)]),
    [["Today", [0, 1]], ["Yesterday", [2]], ["Previous 7 days", [3, 4]], ["Older", [5]]],
  );
  assert.deepEqual(groupChats([], now), []);
});

test("the next page asks for chats after the last loaded one", () => {
  assert.equal(chatsPath("/workspaces/w", "  sales "), "/workspaces/w/threads?q=sales&limit=50");
  assert.equal(
    chatsPath("/workspaces/w", "", { id: "t1", last_activity: "2026-10-24T10:00:00.123456+00:00" }),
    "/workspaces/w/threads?q=&limit=50&after=2026-10-24T10%3A00%3A00.123456%2B00%3A00%7Ct1",
  );
});
