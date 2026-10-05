/* Use case: Protects truthful, resumable conversation activity in the browser.
What it does: Checks terminal semantics, immutable event ordering and aborted polling without a web server. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(
  new URL("../src/app/workspace/conversation-job.ts", import.meta.url),
  "utf8",
);
const javascript = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const {
  isTerminalJob,
  jobHeadline,
  mergeJobEvents,
  pollPause,
  stageLabel,
  reconcileJob,
} = await import(
  `data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`
);

test("cancellation stays pending until the server confirms a terminal result", () => {
  const cancelling = {
    status: "running",
    cancel_requested: true,
    current_stage: "executing_query",
  };
  assert.equal(isTerminalJob(cancelling), false);
  assert.match(jobHeadline(cancelling), /Cancellation requested/);
  assert.equal(
    jobHeadline({ ...cancelling, status: "succeeded" }),
    "Request completed",
  );
  assert.equal(
    jobHeadline({ ...cancelling, status: "cancelled" }),
    "Request cancelled",
  );
  assert.equal(isTerminalJob({ status: "expired" }), true);
});

test("activity renders only allowlisted server actions and never unknown model prose", () => {
  assert.equal(
    stageLabel("executing_query"),
    "Running a read-only calculation",
  );
  const fallback = "Waiting for a recorded activity update";
  assert.equal(stageLabel("I secretly reasoned about revenue"), fallback);
  assert.equal(stageLabel(null), fallback);
  assert.equal(
    jobHeadline({ status: "claimed", current_stage: null }),
    fallback,
  );
});

test("an older in-flight poll cannot undo confirmed cancellation or a cancellation request", () => {
  const previous = {
    id: "same-job",
    status: "cancelled",
    cancel_requested: true,
    updated_at: "2026-10-04T12:00:02Z",
  };
  const stale = {
    ...previous,
    status: "running",
    cancel_requested: false,
    updated_at: "2026-10-04T12:00:01Z",
  };
  assert.equal(reconcileJob(previous, stale), previous);
  const requested = { ...previous, status: "cancelling" };
  assert.equal(reconcileJob(requested, stale), requested);
  assert.equal(
    reconcileJob(requested, { ...stale, updated_at: "2026-10-04T12:00:03Z" })
      .cancel_requested,
    true,
  );
});

test("overlapping event pages remain ordered without replacing an already recorded action", () => {
  const original = { sequence: 2, stage: "planning", status: "started" };
  const result = mergeJobEvents(
    [original],
    [
      { sequence: 3, stage: "planning", status: "completed" },
      { sequence: 2, stage: "executing_query", status: "completed" },
      { sequence: 1, stage: "queued", status: "completed" },
    ],
  );
  assert.deepEqual(
    result.map((event) => event.sequence),
    [1, 2, 3],
  );
  assert.equal(result[1], original);
});

test("detaching immediately ends a pending poll delay without requesting server cancellation", async () => {
  const controller = new AbortController();
  const waiting = pollPause(controller.signal, 60_000);
  controller.abort();
  await assert.rejects(waiting, { name: "AbortError" });
  await assert.rejects(pollPause(controller.signal, 60_000), {
    name: "AbortError",
  });
});
