/* Use case: Proves resumable background uploads, the upload tray and the storage bar in a real browser.
What it does: Mocks only the upload-session and storage API with Playwright routes (real sign-in, workspace and final upload) and checks chunking, navigation, pause/resume, leave warnings, quota errors, resume after reload and importing another workbook sheet. */

import { execFileSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { test, expect } from "@playwright/test";
import type { Page, Route } from "@playwright/test";
import { finishInitialReview, navigateTo } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";
const MiB = 1024 * 1024;
const GiB = 1024 * MiB;
const cors = { "Access-Control-Allow-Origin": "http://127.0.0.1:3001", "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS" };

function token(email: string) {
  return execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", email], { cwd: "../..", encoding: "utf8" }).trim();
}

async function signIn(page: Page, session: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(session);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeEnabled();
}

function bigCsv(bytes: number) {
  const line = "region,amount\n";
  const row = "North,12.50\n";
  return Buffer.from(line + row.repeat(Math.floor((bytes - line.length) / row.length)));
}

type Session = { id: string; wid: string; did: string; filename: string; size: number; chunks: Buffer[]; status: string };

function mockUploads(page: Page, session: string, options: { storage?: { used_bytes: number; quota_bytes: number }; quotaExceeded?: boolean; holdChunk?: number; stored?: { type: string; data: Buffer } } = {}) {
  const sessions = new Map<string, Session>();
  const puts: number[] = [];
  let release: () => void = () => undefined;
  let held = options.holdChunk === undefined ? null : new Promise<void>(resolve => { release = resolve; });
  const chunkSize = 8 * MiB;
  const progress = (s: Session) => ({ id: s.id, filename: s.filename, size_bytes: s.size, chunk_size: chunkSize, received_bytes: s.chunks.reduce((sum, chunk) => sum + chunk.length, 0), next_chunk: s.chunks.length, total_chunks: Math.ceil(s.size / chunkSize), status: s.status, expires_at: "2026-10-27T00:00:00Z" });
  const reply = (route: Route, status: number, body?: unknown) => route.fulfill({ status, headers: { ...cors, "Content-Type": "application/json" }, body: body === undefined ? "" : JSON.stringify(body) }).catch(() => undefined);
  const ready = Promise.all([
    page.route(`${api}/me/storage`, route => route.request().method() === "OPTIONS" ? reply(route, 204) : reply(route, 200, { open_upload_bytes: 0, ...(options.storage ?? { used_bytes: 2.1 * GiB, quota_bytes: 5 * GiB }) })),
    page.route(/\/upload-sessions/, async route => {
      const request = route.request();
      const method = request.method();
      const url = new URL(request.url());
      if (method === "OPTIONS") return reply(route, 204);
      const [, wid, sid, action, index] = url.pathname.match(/^\/workspaces\/([^/]+)\/upload-sessions(?:\/([^/]+))?(?:\/(chunks|complete))?(?:\/(\d+))?$/) ?? [];
      if (method === "POST" && !sid) {
        if (options.quotaExceeded) return reply(route, 409, { error: { code: "quota_exceeded", message: "Storage quota exceeded.", used_bytes: 4.9 * GiB, quota_bytes: 5 * GiB, requested_bytes: 30 * MiB } });
        const body = request.postDataJSON();
        expect(body.purpose).toBe("upload");
        const created: Session = { id: randomUUID(), wid, did: body.dataset_id, filename: body.filename, size: body.size_bytes, chunks: [], status: "open" };
        sessions.set(created.id, created);
        return reply(route, 201, progress(created));
      }
      if (method === "GET" && !sid) return reply(route, 200, [...sessions.values()].filter(item => item.status === "open").map(progress));
      const current = sessions.get(sid);
      if (!current) return reply(route, 404, { error: { code: "not_found", message: "Upload not found." } });
      if (method === "PUT" && action === "chunks") {
        const position = Number(index);
        puts.push(position);
        if (held && position === options.holdChunk) await held;
        const bytes = request.postDataBuffer() ?? Buffer.alloc(0);
        if (request.headers()["x-chunk-sha256"] !== createHash("sha256").update(bytes).digest("hex")) return reply(route, 422, { error: { code: "chunk_checksum_mismatch", message: "Checksum mismatch." } });
        if (position !== current.chunks.length) return reply(route, 409, { error: { code: "chunk_out_of_order", message: "Out of order." } });
        current.chunks.push(bytes);
        const value = progress(current);
        return reply(route, 200, { received_bytes: value.received_bytes, next_chunk: value.next_chunk, status: current.status });
      }
      if (method === "POST" && action === "complete") {
        current.status = "complete";
        const stored = await page.request.post(`${api}/workspaces/${current.wid}/datasets/${current.did}/uploads?filename=${encodeURIComponent(current.filename)}`, { headers: { Authorization: `Bearer ${session}`, "Content-Type": options.stored?.type ?? "text/csv" }, data: options.stored?.data ?? Buffer.from("region,amount\nNorth,12.50\nSouth,7.25\n") });
        return reply(route, 201, { upload: await stored.json() });
      }
      if (method === "DELETE") { sessions.delete(sid); return reply(route, 204); }
      return reply(route, 200, progress(current));
    }),
  ]);
  return { ready, sessions, puts, release: () => { held = null; release(); } };
}

const tray = (page: Page) => page.getByRole("region", { name: "Uploads", exact: true });

test("a 30 MB file uploads in chunks in the background, survives navigation and pauses/resumes", async ({ page }) => {
  test.setTimeout(150_000);
  const session = token(`chunks-${randomUUID()}@example.test`);
  const server = mockUploads(page, session, { holdChunk: 1 });
  await server.ready;
  await signIn(page, session);
  const file = bigCsv(30 * MiB);
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "big.csv", mimeType: "text/csv", buffer: file });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(tray(page)).toContainText("Uploading 1 file");
  const bar = tray(page).getByRole("progressbar", { name: "big.csv upload progress" });
  await expect(bar).toHaveAttribute("aria-valuenow", "26");
  await expect(tray(page)).toContainText("8 MB of");
  await navigateTo(page, "Team & settings");
  await expect(page.getByRole("region", { name: "Your storage" })).toContainText("2.1 GB of 5 GB used");
  await expect(tray(page)).toContainText("2.1 GB of 5 GB used");
  await expect(tray(page)).toBeVisible();
  await tray(page).getByRole("button", { name: "Pause", exact: true }).click();
  await expect(tray(page)).toContainText("Paused");
  server.release();
  await tray(page).getByRole("button", { name: "Resume", exact: true }).click();
  await expect(tray(page)).toContainText("Done", { timeout: 60_000 });
  const [stored] = [...server.sessions.values()];
  expect(stored.chunks.map(chunk => chunk.length)).toEqual([8 * MiB, 8 * MiB, 8 * MiB, file.length - 24 * MiB]);
  expect(Buffer.concat(stored.chunks).equals(file)).toBe(true);
  expect(server.puts.filter(index => index === 0)).toHaveLength(1);
  await expect(page.locator('.notice[role="status"]')).toContainText("big.csv finished uploading");
  await tray(page).getByRole("button", { name: "Open", exact: true }).click();
  await finishInitialReview(page);
  await expect(page.getByLabel("Dataset", { exact: true }).locator("option:checked")).toHaveText("big");
  await expect(tray(page)).toHaveCount(0);
  await page.setViewportSize({ width: 320, height: 720 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("leaving or signing out during an upload asks for confirmation", async ({ page }) => {
  const session = token(`leave-${randomUUID()}@example.test`);
  const server = mockUploads(page, session, { holdChunk: 0 });
  await server.ready;
  await signIn(page, session);
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "leave.csv", mimeType: "text/csv", buffer: bigCsv(2 * MiB) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(tray(page)).toContainText("Uploading 1 file");
  const confirm = page.waitForEvent("dialog");
  void page.getByRole("button", { name: "Sign out", exact: true }).click();
  const signOutDialog = await confirm;
  expect(signOutDialog.type()).toBe("confirm");
  expect(signOutDialog.message()).toContain("upload is still running");
  await signOutDialog.dismiss();
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeVisible();
  const unload = page.waitForEvent("dialog");
  await page.close({ runBeforeUnload: true });
  const leave = await unload;
  expect(leave.type()).toBe("beforeunload");
  await leave.dismiss();
  server.release();
});

test("a full storage quota is explained before any bytes are sent", async ({ page }) => {
  const session = token(`quota-${randomUUID()}@example.test`);
  const server = mockUploads(page, session, { quotaExceeded: true, storage: { used_bytes: 4.6 * GiB, quota_bytes: 5 * GiB } });
  await server.ready;
  await signIn(page, session);
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "over.csv", mimeType: "text/csv", buffer: bigCsv(MiB) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.getByRole("alert", { name: "Request error" })).toContainText("Not enough storage space");
  await expect(tray(page)).toContainText("Failed");
  await expect(tray(page)).toContainText("4.6 GB of 5 GB used");
  await expect(tray(page)).toContainText("Your storage is almost full.");
  await expect(tray(page).getByRole("progressbar", { name: "Storage used" })).toHaveAttribute("aria-valuenow", "92");
  await expect(tray(page).getByRole("button", { name: "Retry", exact: true })).toHaveCount(0);
  expect(server.puts).toEqual([]);
});

test("after a reload the user reselects the same file and the upload continues from the next chunk", async ({ page }) => {
  test.setTimeout(150_000);
  const session = token(`reload-${randomUUID()}@example.test`);
  const server = mockUploads(page, session, { holdChunk: 1 });
  await server.ready;
  await signIn(page, session);
  const file = bigCsv(20 * MiB);
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "resume.csv", mimeType: "text/csv", buffer: file });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(tray(page).getByRole("progressbar", { name: "resume.csv upload progress" })).toHaveAttribute("aria-valuenow", "40");
  expect(await page.evaluate(() => window.localStorage.getItem("execplus.uploads.v1"))).not.toContain("North");
  page.once("dialog", dialog => void dialog.accept());
  await page.reload();
  server.release();
  await page.getByLabel("Session token").fill(session);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(tray(page)).toContainText("Waiting for the file");
  const picker = tray(page).getByLabel("Resume upload — reselect the file");
  await picker.setInputFiles({ name: "resume.csv", mimeType: "text/csv", buffer: bigCsv(MiB) });
  await expect(tray(page)).toContainText("Choose the same file: resume.csv");
  await picker.setInputFiles({ name: "resume.csv", mimeType: "text/csv", buffer: file });
  await expect(tray(page)).toContainText("Done", { timeout: 60_000 });
  const [stored] = [...server.sessions.values()];
  expect(Buffer.concat(stored.chunks).equals(file)).toBe(true);
  expect(server.puts.filter(index => index === 0)).toHaveLength(1);
  expect(await page.evaluate(() => window.localStorage.getItem("execplus.uploads.v1"))).toBe("[]");
});

const WORKBOOK = [
  "import base64, io, openpyxl",
  "book = openpyxl.Workbook(); book.active.title = 'Cover'",
  "rows = {'Leads': [('name', 'amount'), ('Ana', '0.10'), ('Bo', '0.20')], 'Archive': [('name', 'amount')] + [('old%d' % i, '%d.5' % i) for i in range(4)], 'Notes': [('note',), ('call back',)]}",
  "for name, values in rows.items():\n    sheet = book.create_sheet(name)\n    [sheet.append(row) for row in values]",
  "out = io.BytesIO(); book.save(out); print(base64.b64encode(out.getvalue()).decode())",
].join("\n");

test("a workbook with several sheets offers to import another sheet as its own dataset", async ({ page }) => {
  test.setTimeout(150_000);
  const session = token(`sheets-${randomUUID()}@example.test`);
  const data = Buffer.from(execFileSync("python3", ["-c", WORKBOOK], { encoding: "utf8" }).trim(), "base64");
  const server = mockUploads(page, session, { stored: { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", data } });
  await server.ready;
  await signIn(page, session);
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "leads.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: data });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  const sheets = page.getByRole("region", { name: "Other sheets in this file", exact: true });
  test.skip(!(await sheets.isVisible({ timeout: 15_000 }).catch(() => false)) && process.env.EXECPLUS_COLUMNAR_INGEST_ENABLED !== "true", "needs EXECPLUS_COLUMNAR_INGEST_ENABLED=true and the DuckDB excel extension");
  await expect(sheets).toContainText("This file has 3 sheets: Leads (2 rows), Archive (4 rows), Notes (1 row). Imported: Leads.");
  await sheets.getByLabel("Sheet").selectOption("Archive");
  await sheets.getByRole("button", { name: "Import another sheet", exact: true }).click();
  await finishInitialReview(page);
  await expect(page.getByLabel("Dataset", { exact: true }).locator("option:checked")).toHaveText("leads - Archive");
  await expect(page.getByRole("region", { name: "Other sheets in this file", exact: true })).toContainText("Imported: Archive.");
});
