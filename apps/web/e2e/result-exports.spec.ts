/* Use case: Exercises exact, authenticated downloads from the actual workspace.
What it does: Independently opens Excel/CSV/PNG/PDF files, checks all returned evidence and responsive export controls, and verifies explicit retry and download behavior. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import { finishInitialReview, openConversation, openFindings } from "./workspace-helpers";

const evidence = "../../data/verification/2026-10-16/remaining-work/exports/browser";
async function file(page: Page, controls: Locator, format: string, name: string) {
  await controls.getByRole("combobox", { name: "File type", exact: true }).selectOption(format);
  const waiting = page.waitForEvent("download");
  await controls.getByRole("button", { name: `Download ${format === "xlsx" ? "Excel" : format === "csv" ? "CSV bundle" : format.toUpperCase()}`, exact: true }).click();
  const result = await waiting;
  const path = `${evidence}/${name}.${format === "csv" ? "zip" : format}`;
  await result.saveAs(path);
  expect(await result.failure()).toBeNull();
  await expect(controls.getByRole("status")).toContainText("Download started");
  return path;
}

test("portable result downloads preserve exact rows and graphs with source evidence", async ({ page }) => {
  test.setTimeout(120_000);
  page.setDefaultTimeout(20_000);
  mkdirSync(evidence, { recursive: true });
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `exports-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` };
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "exact-export.csv", mimeType: "text/csv", buffer: Buffer.from("date,region,amount\n2026-01-01,West,-1.25\n2026-01-02,Missing,\n2026-01-03,Zero,0\n2026-01-04,East,9007199254740993.000001\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  const wid = await page.getByLabel("Current workspace").inputValue();
  const root = `/workspaces/${wid}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}`;
  const before = await (await page.request.get(`http://127.0.0.1:8001${root}/understanding`, { headers })).json();
  const definition = { ...before.definition, grain: "record", columns: before.definition.columns.map((column: { role: string; name: string }) => ({ ...column, meaning: `Saved meaning of ${column.name}`, unit: column.role === "metric" ? "USD" : "" })) };
  const confirmed = await page.request.post(`http://127.0.0.1:8001${root}/understanding`, { headers, data: { revision_id: before.revision_id, expected_version: before.version, state: "confirmed", definition } });
  expect(confirmed.ok(), await confirmed.text()).toBe(true);
  const saved = await (await page.request.get(`http://127.0.0.1:8001${root}/understanding`, { headers })).json();
  // The fixture updated meanings outside React; reopen the overview to load that version.
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Data library", exact: true }).click();
  await openFindings(page);
  await expect(page.getByRole("region", { name: "Charts & dashboard controls", exact: true })).toBeVisible();
  const dashboard = page.getByRole("region", { name: "Dataset dashboard", exact: true });
  const controls = dashboard.locator("details").filter({ has: page.locator("summary", { hasText: "Download this dashboard" }) });
  await controls.locator(":scope > summary").click();
  await controls.getByRole("combobox", { name: "File type", exact: true }).selectOption("xlsx");
  await page.route("**/exports/dashboard", route => route.fulfill({ status: 503, json: { error: { message: "Temporary export failure. Please retry." } } }));
  await controls.getByRole("button", { name: "Download Excel", exact: true }).click();
  await expect(controls.getByRole("alert")).toContainText("Temporary export failure");
  await page.unroute("**/exports/dashboard");
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let requested = false;
  await page.route("**/exports/dashboard", async route => { requested = true; await gate; await route.continue(); });
  const excelDownload = file(page, controls, "xlsx", "dashboard");
  await expect.poll(() => requested).toBe(true);
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  release();
  const excel = await excelDownload;
  await page.unroute("**/exports/dashboard");
  const csv = await file(page, controls, "csv", "dashboard");
  const png = await file(page, controls, "png", "dashboard");
  execFileSync("python3", ["-c", `import sys,json,zipfile\nfrom openpyxl import load_workbook\nfrom PIL import Image\nw=load_workbook(sys.argv[1]); tables=[list(s.values) for s in w]; regional=next(t for t in tables if t and t[0]==('region','__value')); rows=dict(regional[1:]); assert rows['East']=='9007199254740993.000001000000'; assert rows['Missing'] is None; assert rows['West']=='-1.250000000000'; assert rows['Zero']=='0E-12'\nz=zipfile.ZipFile(sys.argv[2]); e=json.loads(z.read('evidence.json')); assert any(c['value']=='9007199254740993.000001000000' for t in e['tables'] for r in t['rows'] for c in r); assert any(c['type']=='null' for t in e['tables'] for r in t['rows'] for c in r)\ni=Image.open(sys.argv[3]); assert i.format=='PNG'; c=json.loads(i.info['ExecPlus chart']); assert len(c['labels'])==4; assert '9007199254740993.000001' in i.info['ExecPlus evidence']`, excel, csv, png]);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await controls.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await controls.screenshot({ path: `${evidence}/controls-${width}.png`, animations: "disabled" });
  }
  await openConversation(page);
  await page.getByLabel("Your question", { exact: true }).fill("Draw a diagram of this data");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("region", { name: "Data organisation diagram", exact: true })).toBeVisible();
  const diagramControls = page.locator(".conversationTurn").last().locator("details").filter({ has: page.locator("summary", { hasText: "Download result" }) });
  await diagramControls.locator(":scope > summary").click();
  const pdf = await file(page, diagramControls, "pdf", "data-map");
  execFileSync("python3", ["-c", `import sys\nfrom pypdf import PdfReader\nr=PdfReader(sys.argv[1]); text=' '.join(p.extract_text() for p in r.pages); assert 'Saved meaning of amount' in text and 'USD' in text; assert sum(len(p.images) for p in r.pages)>0`, pdf]);
  expect(await (await page.request.get(`http://127.0.0.1:8001${root}/understanding`, { headers })).json()).toEqual(saved);
  expect(errors).toEqual([]);
});
