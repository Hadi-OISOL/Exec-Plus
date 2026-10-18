/* Use case: Verifies automatic governed relationship discovery in the actual browser.
What it does: Confirms synthetic meanings explicitly, checks source receipts and replay,
then changes appearance without rerunning calculations or changing exact results. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { finishInitialReview } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";
test("confirmed data automatically shows measured relationships and theme changes preserve evidence", async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `proactive-ui-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` };
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const csv = "Region,revenue,cost\n" + Array.from({ length: 40 }, (_, index) => `${index % 2 ? "North" : "South"},${index + 1},${(index + 1) * 2}\n`).join("");
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "fictional-proactive.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  const workspace = await page.getByLabel("Current workspace").inputValue();
  const root = `/workspaces/${workspace}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}`;
  const initial = await page.request.get(`${api}${root}/understanding`, { headers });
  expect(initial.ok()).toBe(true);
  const current = await initial.json();
  const definition = { ...current.definition, grain: "record", columns: current.definition.columns.map((column: { role: string; unit: string }) => column.role === "metric" ? { ...column, unit: "USD" } : column) };
  const confirmed = await page.request.post(`${api}${root}/understanding`, { headers, data: { revision_id: current.revision_id, expected_version: current.version, state: "confirmed", definition } });
  expect(confirmed.status()).toBe(201);
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await nav.getByRole("button", { name: "Ask ExecPlus", exact: true }).click();
  const discoveryResponse = page.waitForResponse(response => response.url().endsWith(`${root}/discovery`) && response.status() === 200);
  await nav.getByRole("button", { name: "Overview", exact: true }).click();
  const discovery = await (await discoveryResponse).json();
  expect(discovery.patterns_evidence.result.findings.length).toBeGreaterThan(0);
  expect(discovery.patterns_evidence.sources).toEqual(discovery.sources);
  const findings = page.getByRole("region", { name: "First findings from your file", exact: true });
  const patterns = findings.getByRole("region", { name: "Measured data patterns", exact: true });
  await expect(patterns.getByRole("heading", { name: "Here is what stands out", exact: true })).toBeVisible();
  await expect(patterns).toContainText("do not prove that one thing caused another");
  await expect(patterns.locator("svg").first()).toBeVisible();
  await patterns.locator(".patternEvidence summary").click();
  await expect(patterns.locator(".patternEvidence")).toContainText(discovery.patterns_evidence.query_id);
  for (const source of discovery.sources) await expect(patterns.locator(".patternEvidence")).toContainText(source.revision_id);
  const replay = await page.request.post(`${api}/workspaces/${workspace}/queries/${discovery.patterns_evidence.query_id}/replay`, { headers });
  expect(replay.ok()).toBe(true);
  expect((await replay.json()).rows).toHaveLength(40);
  const values = await findings.locator(".discoveryValue").allTextContents();
  let recalculations = 0;
  page.on("request", request => { if (/\/(discovery|dashboard)$/.test(new URL(request.url()).pathname)) recalculations += 1; });
  for (const theme of ["dark", "light"]) {
    await page.getByLabel("Appearance", { exact: true }).selectOption(theme);
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(patterns.locator("svg").first()).toBeVisible();
      await expect(findings.locator(".discoveryValue")).toHaveText(values);
      await expect(findings.locator('[data-chart-renderer="apache-echarts"] svg').first()).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await patterns.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `../../data/verification/2026-10-19/conversation-appearance/proactive-${theme}-${width}.png`, fullPage: true });
    }
  }
  expect(recalculations).toBe(0);
  expect((await (await page.request.get(`${api}${root}/understanding`, { headers })).json()).definition).toEqual(definition);
  expect(errors).toEqual([]);
});
