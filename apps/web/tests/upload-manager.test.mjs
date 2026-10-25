/* Use case: Protects resumable background uploads without a web server.
What it does: Checks chunk bounds, per-chunk SHA-256, retries, pause/resume, resume after reload, legacy fallback and friendly quota errors against an in-memory upload-session API. */

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/upload-manager.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { UploadManager, chunkBounds, sha256Hex, withRetry, readRecords, uploadErrorMessage, formatBytes, RESUME_KEY, MAX_UPLOAD_BYTES } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), values };
}

function fail(status, code, message = "failed") {
  return Object.assign(new Error(message), { status, code });
}

function fakeServer({ chunkSize = 4, failures = {}, legacy = false } = {}) {
  const sessions = new Map();
  const log = [];
  let gate = null;
  const reply = (value, status = 200) => new Response(value === undefined ? null : JSON.stringify(value), { status });
  const progress = s => ({ id: s.id, filename: s.filename, size_bytes: s.size, chunk_size: chunkSize, received_bytes: s.received, next_chunk: s.chunks.length, total_chunks: Math.ceil(s.size / chunkSize), status: s.status });
  const transport = async (path, init = {}) => {
    const method = init.method ?? "GET";
    log.push(`${method} ${path}`);
    if (gate && method === "PUT") await gate;
    if (init.signal?.aborted) throw Object.assign(new Error("Aborted"), { name: "AbortError" });
    if (failures[`${method} ${path}`]?.length) throw failures[`${method} ${path}`].shift();
    let match;
    if (legacy && path.includes("upload-sessions")) throw fail(404, undefined, "Not Found");
    if (method === "POST" && /\/upload-sessions$/.test(path)) {
      const request = JSON.parse(init.body);
      const id = `s${sessions.size + 1}`;
      sessions.set(id, { id, filename: request.filename, size: request.size_bytes, request, chunks: [], received: 0, status: "open", bytes: [] });
      return reply(progress(sessions.get(id)), 201);
    }
    if ((match = path.match(/\/upload-sessions\/(\w+)\/chunks\/(\d+)$/))) {
      const s = sessions.get(match[1]);
      if (Number(match[2]) !== s.chunks.length) throw fail(409, "chunk_out_of_order");
      const bytes = new Uint8Array(await init.body.arrayBuffer());
      assert.equal(init.headers["X-Chunk-SHA256"], createHash("sha256").update(bytes).digest("hex"));
      s.chunks.push(Number(match[2]));
      s.bytes.push(...bytes);
      s.received += bytes.length;
      return reply({ received_bytes: s.received, next_chunk: s.chunks.length, status: s.status });
    }
    if ((match = path.match(/\/upload-sessions\/(\w+)\/complete$/))) {
      const s = sessions.get(match[1]);
      s.status = "complete";
      return reply({ upload: { id: `u-${s.id}`, workspace_id: "w1", dataset_id: "d1", filename: s.filename, status: "ready" } }, 201);
    }
    if ((match = path.match(/\/upload-sessions\?status=open$/))) return reply([...sessions.values()].filter(s => s.status === "open").map(progress));
    if ((match = path.match(/\/upload-sessions\/(\w+)$/))) {
      if (method === "DELETE") { sessions.delete(match[1]); return reply(undefined, 204); }
      return reply(progress(sessions.get(match[1])));
    }
    if (method === "POST" && /\/datasets\/d1\/uploads\?filename=/.test(path)) return reply({ id: "legacy-1", workspace_id: "w1", dataset_id: "d1", filename: "legacy.csv", status: "ready" }, 201);
    throw fail(404, "not_found");
  };
  return { transport, sessions, log, hold() { let release; gate = new Promise(resolve => { release = resolve; }); return () => { gate = null; release(); }; } };
}

function namedFile(text, name = "data.csv") {
  return new File([text], name, { type: "text/csv", lastModified: 1 });
}

function finished(manager) {
  return new Promise(resolve => {
    const stop = manager.subscribe(() => {
      const items = manager.snapshot();
      if (items.length && items.every(item => ["done", "failed", "needs-file", "paused"].includes(item.phase))) { stop(); resolve(items); }
    });
  });
}

test("chunk bounds cover the whole file without overlap", () => {
  assert.deepEqual(chunkBounds(0, 4, 10), [0, 4]);
  assert.deepEqual(chunkBounds(2, 4, 10), [8, 10]);
});

test("chunk hashes are hex SHA-256 from Web Crypto", async () => {
  assert.equal(await sha256Hex(new Blob(["abc"])), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
});

test("retries transient failures up to three times with backoff, never client errors", async () => {
  let calls = 0;
  assert.equal(await withRetry(async () => { calls += 1; if (calls < 4) throw fail(503); return "ok"; }, 3, 1), "ok");
  assert.equal(calls, 4);
  calls = 0;
  await assert.rejects(withRetry(async () => { calls += 1; throw new TypeError("network"); }, 3, 1), TypeError);
  assert.equal(calls, 4);
  calls = 0;
  await assert.rejects(withRetry(async () => { calls += 1; throw fail(415, "unsupported_format"); }, 3, 1));
  assert.equal(calls, 1);
});

test("uploads every chunk in order, verifies bytes and clears the resume record", async () => {
  const server = fakeServer();
  const storage = memoryStorage();
  const done = [];
  const manager = new UploadManager({ transport: server.transport, userId: "u1", storage, backoffMs: 1, onFinish: item => done.push(item) });
  manager.enqueue(namedFile("0123456789"), "w1", "d1", "text/csv");
  const [item] = await finished(manager);
  assert.equal(item.phase, "done");
  assert.equal(item.result.id, "u-s1");
  assert.equal(Buffer.from(server.sessions.get("s1").bytes).toString(), "0123456789");
  assert.deepEqual(server.sessions.get("s1").chunks, [0, 1, 2]);
  assert.equal(server.sessions.get("s1").request.dataset_id, "d1");
  assert.equal(server.sessions.get("s1").request.purpose, "upload");
  assert.deepEqual(readRecords(storage), []);
  assert.equal(done.length, 1);
});

test("a failed chunk is retried and the upload still completes", async () => {
  const server = fakeServer({ failures: { "PUT /workspaces/w1/upload-sessions/s1/chunks/1": [fail(502), new TypeError("network")] } });
  const manager = new UploadManager({ transport: server.transport, userId: "u1", backoffMs: 1 });
  manager.enqueue(namedFile("0123456789"), "w1", "d1", "text/csv");
  const [item] = await finished(manager);
  assert.equal(item.phase, "done");
  assert.equal(server.log.filter(line => line.endsWith("/chunks/1")).length, 3);
});

test("pause stops sending and resume continues from the server's next chunk", async () => {
  const server = fakeServer();
  const manager = new UploadManager({ transport: server.transport, userId: "u1", backoffMs: 1 });
  const release = server.hold();
  const key = manager.enqueue(namedFile("0123456789"), "w1", "d1", "text/csv");
  await new Promise(resolve => setTimeout(resolve, 20));
  manager.pause(key);
  release();
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(manager.snapshot()[0].phase, "paused");
  assert.equal(manager.active(), false);
  manager.resume(key);
  const [item] = await finished(manager);
  assert.equal(item.phase, "done");
  assert.deepEqual(server.sessions.get("s1").chunks, [0, 1, 2]);
  assert.ok(server.log.includes("GET /workspaces/w1/upload-sessions/s1"));
});

test("only one file uploads at a time by default", async () => {
  const server = fakeServer();
  const manager = new UploadManager({ transport: server.transport, userId: "u1", backoffMs: 1 });
  const release = server.hold();
  manager.enqueue(namedFile("abcd", "a.csv"), "w1", "d1", "text/csv");
  manager.enqueue(namedFile("efgh", "b.csv"), "w1", "d1", "text/csv");
  assert.deepEqual(manager.snapshot().map(item => item.phase), ["uploading", "queued"]);
  release();
  const items = await finished(manager);
  assert.deepEqual(items.map(item => item.phase), ["done", "done"]);
});

test("after a reload the same file resumes from next_chunk; a different file is refused", async () => {
  const server = fakeServer({ failures: { "PUT /workspaces/w1/upload-sessions/s1/chunks/1": [fail(400, "connection_lost")] } });
  const storage = memoryStorage();
  const first = new UploadManager({ transport: server.transport, userId: "u1", storage, backoffMs: 1 });
  first.enqueue(namedFile("0123456789"), "w1", "d1", "text/csv");
  await finished(first);
  first.reset();
  const sent = server.sessions.get("s1").chunks.length;
  assert.equal(sent, 1);
  assert.equal(readRecords(storage)[0].sessionId, "s1");
  assert.ok(!storage.values.get(RESUME_KEY).includes("0123"));

  const reloaded = new UploadManager({ transport: server.transport, userId: "u1", storage, backoffMs: 1 });
  await reloaded.restore();
  const [waiting] = reloaded.snapshot();
  assert.equal(waiting.phase, "needs-file");
  assert.equal(waiting.sentBytes, sent * 4);
  assert.equal(reloaded.attach(waiting.key, namedFile("01234567", "data.csv")), false);
  assert.match(reloaded.snapshot()[0].error, /Choose the same file/);
  assert.equal(reloaded.attach(waiting.key, namedFile("0123456789")), true);
  const [item] = await finished(reloaded);
  assert.equal(item.phase, "done");
  assert.equal(Buffer.from(server.sessions.get("s1").bytes).toString(), "0123456789");
  assert.deepEqual(readRecords(storage), []);
});

test("records of other users or closed sessions are not offered for resume", async () => {
  const server = fakeServer();
  const storage = memoryStorage({ [RESUME_KEY]: JSON.stringify([{ sessionId: "gone", workspaceId: "w1", userId: "u1", filename: "x.csv", size: 4, lastModified: 0 }, { sessionId: "other", workspaceId: "w1", userId: "u2", filename: "y.csv", size: 4, lastModified: 0 }]) });
  const manager = new UploadManager({ transport: server.transport, userId: "u1", storage });
  await manager.restore();
  assert.deepEqual(manager.snapshot(), []);
  assert.deepEqual(readRecords(storage).map(record => record.sessionId), ["other"]);
});

test("falls back to the single upload endpoint when upload sessions are unavailable", async () => {
  const server = fakeServer({ legacy: true });
  const manager = new UploadManager({ transport: server.transport, userId: "u1", backoffMs: 1 });
  manager.enqueue(namedFile("a,b\n1,2\n", "legacy.csv"), "w1", "d1", "text/csv");
  const [item] = await finished(manager);
  assert.equal(item.phase, "done");
  assert.equal(item.result.id, "legacy-1");
});

test("quota and size failures produce clear messages", async () => {
  const server = fakeServer({ failures: { "POST /workspaces/w1/upload-sessions": [fail(409, "quota_exceeded", "Storage quota exceeded.")] } });
  const manager = new UploadManager({ transport: server.transport, userId: "u1", backoffMs: 1 });
  manager.enqueue(namedFile("0123456789"), "w1", "d1", "text/csv");
  const [item] = await finished(manager);
  assert.equal(item.phase, "failed");
  assert.match(item.error, /Not enough storage space/);
  assert.throws(() => manager.enqueue({ name: "huge.csv", size: MAX_UPLOAD_BYTES + 1 }, "w1", "d1", "text/csv"), /up to 500 MB/);
  assert.match(uploadErrorMessage("unsupported_format", "", 1), /not supported/);
  assert.equal(formatBytes(2.1 * 1024 ** 3), "2.1 GB");
  assert.equal(formatBytes(5 * 1024 ** 3), "5 GB");
});

test("a finalize step completes the session into a refresh candidate without ingesting or remembering it", async () => {
  const server = fakeServer();
  const storage = memoryStorage();
  const finalized = [];
  const manager = new UploadManager({ transport: server.transport, userId: "u1", storage, backoffMs: 1 });
  manager.enqueue(namedFile("city,amount\nK,1\n"), "w1", "d1", "text/csv", async (sessionId, signal) => {
    finalized.push(sessionId);
    assert.ok(signal instanceof AbortSignal);
    assert.deepEqual(readRecords(storage), []);
    return { id: "candidate-1", status: "queued" };
  });
  const [item] = await finished(manager);
  assert.equal(item.phase, "done");
  assert.deepEqual(item.outcome, { id: "candidate-1", status: "queued" });
  assert.deepEqual(finalized, ["s1"]);
  assert.equal(Buffer.from(server.sessions.get("s1").bytes).toString(), "city,amount\nK,1\n");
  assert.equal(server.log.some(line => line.endsWith("/complete")), false);
  assert.equal(storage.values.has(RESUME_KEY), false);
});

test("finalized uploads never fall back to the legacy dataset upload", async () => {
  const server = fakeServer({ legacy: true });
  const manager = new UploadManager({ transport: server.transport, userId: "u1", backoffMs: 1 });
  manager.enqueue(namedFile("city,amount\n"), "w1", "d1", "text/csv", async () => ({}));
  const [item] = await finished(manager);
  assert.equal(item.phase, "failed");
  assert.equal(server.log.some(line => line.includes("/uploads?filename=")), false);
});
