/* Use case: Verifies an explicit two-company worksheet through the actual UI.
What it does: Checks source and mapping drafts, exact balanced adjustments, saved-write/read-failure recovery, private replay, downloads and responsive evidence. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { expect, test } from "@playwright/test";

const api = "http://127.0.0.1:8001";

test("company worksheet keeps explicit mappings, exact layers and private source evidence", async ({ page }) => {
  test.setTimeout(150_000);
  page.setDefaultTimeout(20_000);
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `consolidation-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` };
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", event => { if (event.text().includes("same key")) errors.push(event.text()); });
  const orgResponse = await page.request.post(`${api}/organizations`, { headers, data: { name: "Fictional companies" } });
  expect(orgResponse.status()).toBe(201); const org = await orgResponse.json();
  const companies: { wid: string; did: string; uid: string; name: string; original: Buffer }[] = [];
  for (let index = 0; index < 2; index++) {
    const name = index === 0 ? "Company Alpha" : "Company Beta";
    const workspace = await (await page.request.post(`${api}/workspaces`, { headers, data: { name, seat_limit: 3 } })).json();
    expect((await page.request.post(`${api}/workspaces/${workspace.id}/department`, { headers, data: { organization_id: org.id, name } })).status()).toBe(200);
    const dataset = await (await page.request.post(`${api}/workspaces/${workspace.id}/datasets`, { headers, data: { name: "Prepared ledger" } })).json();
    const original = Buffer.from(index === 0 ? "account,amount,counterparty\nCash,100.00,External\nDue,20.00,B\nEquity,-120.00,External\n" : "account,amount,counterparty\nCash,200.00,External\nDue,-40.00,A\nEquity,-160.00,External\n");
    const uploaded = await page.request.post(`${api}/workspaces/${workspace.id}/datasets/${dataset.id}/uploads?filename=ledger.csv`, { headers: { ...headers, "Content-Type": "text/csv" }, data: original });
    expect(uploaded.status()).toBe(201); const upload = await uploaded.json();
    const sourceRoot = `${api}/workspaces/${workspace.id}/datasets/${dataset.id}/uploads/${upload.id}`;
    const before = await (await page.request.get(sourceRoot + "/understanding", { headers })).json();
    const currency = index === 0 ? "USD" : "EUR";
    const confirmed = await page.request.post(sourceRoot + "/understanding", { headers, data: { revision_id: before.revision_id, expected_version: before.version, state: "confirmed", definition: { ...before.definition, domain: "finance", grain: "record", columns: before.definition.columns.map((column: { name: string }) => ({ ...column, role: column.name === "amount" ? "metric" : "dimension", meaning: `Recorded ${column.name}`, unit: column.name === "amount" ? currency : "", currency: column.name === "amount" ? currency : "" })) } } });
    expect(confirmed.status()).toBe(201);
    companies.push({ wid: workspace.id, did: dataset.id, uid: upload.id, name, original });
  }
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Team & settings", exact: true }).click();
  const panel = page.getByRole("region", { name: "Company consolidation", exact: true });
  await panel.getByRole("combobox", { name: "Worksheet organization", exact: true }).selectOption(org.id);
  await panel.getByLabel("Worksheet name", { exact: true }).fill("Group annual review");
  await panel.getByLabel("Reporting currency", { exact: true }).fill("USD");
  await panel.getByLabel("Period start", { exact: true }).fill("2026-01-01");
  await panel.getByLabel("Period end", { exact: true }).fill("2026-12-31");
  for (let index = 0; index < 2; index++) {
    const card = panel.getByRole("article", { name: `Company ${index + 1} source` });
    await card.getByRole("combobox", { name: "Company workspace", exact: true }).selectOption(companies[index].wid);
    await card.getByRole("combobox", { name: "Prepared ledger file", exact: true }).selectOption(`${companies[index].did}:${companies[index].uid}`);
    await card.getByRole("button", { name: "Review ledger fields", exact: true }).click();
    await card.getByRole("combobox", { name: "Account field", exact: true }).selectOption("account");
    await card.getByRole("combobox", { name: "Signed amount field", exact: true }).selectOption("amount");
    await card.getByRole("combobox", { name: "Counterparty field (optional)", exact: true }).selectOption("counterparty");
    await card.getByRole("button", { name: "Read account list", exact: true }).click();
    await expect(card).toContainText("All 3 ledger rows checked");
  }
  await panel.getByRole("button", { name: "Continue to mappings", exact: true }).click();
  for (let index = 0; index < 2; index++) {
    const card = panel.locator("article").filter({ has: page.getByRole("heading", { name: `${companies[index].name} · ${index === 0 ? "USD" : "EUR"} → USD`, exact: true }) });
    await card.getByLabel("Rate name", { exact: true }).fill("declared-closing");
    for (const selection of await card.getByRole("combobox", { name: "Use declared rate", exact: true }).all()) await expect(selection).toHaveValue("declared-closing");
    await card.getByLabel("Exact exchange rate", { exact: true }).fill(index === 0 ? "1" : "0.5");
    await card.getByLabel("Rate reference", { exact: true }).fill("Fictional declared closing rate");
    const mapping = card.locator("div").filter({ has: page.getByRole("heading", { name: "Due", exact: true }) }).filter({ has: page.getByLabel("Group account", { exact: true }) }).last();
    await mapping.getByLabel("Group account", { exact: true }).fill("Internal");
    await card.getByRole("combobox", { name: `Counterparty: ${index === 0 ? "B" : "A"}`, exact: true }).selectOption(companies[1-index].wid);
  }
  await panel.getByRole("button", { name: "Back", exact: true }).click();
  await expect(panel.getByLabel("Worksheet name", { exact: true })).toHaveValue("Group annual review");
  await panel.getByRole("button", { name: "Continue to mappings", exact: true }).click();
  await expect(panel.getByLabel("Exact exchange rate", { exact: true }).nth(1)).toHaveValue("0.5");
  await panel.getByRole("button", { name: "Continue to review", exact: true }).click();
  await panel.getByRole("button", { name: "Add internal adjustment", exact: true }).click();
  await panel.getByLabel("Journal name", { exact: true }).fill("Remove reciprocal balance");
  for (let index = 0; index < 2; index++) {
    await panel.getByRole("combobox", { name: "Source account", exact: true }).nth(index).selectOption("Due");
    await panel.getByRole("combobox", { name: "Other company", exact: true }).nth(index).selectOption(companies[1-index].wid);
    await panel.getByLabel("Signed adjustment (USD)", { exact: true }).nth(index).fill(index === 0 ? "-20" : "20");
  }
  const path = `${api}/organizations/${org.id}/consolidations`;
  let failSave = true, failHistory = true;
  await page.route(path, route => route.request().method() === "POST" && failSave ? route.fulfill({ status: 503, json: { error: { message: "Temporary worksheet save failure" } } }) : route.request().method() === "GET" && failHistory ? route.fulfill({ status: 503, json: { error: { message: "Temporary worksheet list failure" } } }) : route.continue());
  await panel.getByRole("checkbox", { name: "I reviewed the mappings and rates.", exact: false }).check();
  const save = panel.getByRole("button", { name: "Calculate & save worksheet", exact: true });
  await save.click(); await expect(panel.getByRole("alert")).toContainText("Temporary worksheet save failure");
  await expect(panel.getByLabel("Signed adjustment (USD)", { exact: true }).first()).toHaveValue("-20");
  failSave = false;
  const savedResponse = page.waitForResponse(response => response.url() === path && response.status() === 201);
  await save.click(); const value = await (await savedResponse).json();
  expect(value.run.result.totals).toEqual({ combined: "0", eliminations: "0", consolidated: "0" });
  const result = panel.getByRole("region", { name: "Saved company worksheet", exact: true });
  await expect(result.getByRole("heading", { name: "Group annual review", exact: true })).toBeVisible();
  await expect(panel.getByRole("alert")).toContainText("Your worksheet was saved");
  await expect(save).toBeDisabled();
  failHistory = false;
  await panel.getByRole("button", { name: "Reload saved list", exact: true }).click();
  await panel.getByRole("button", { name: "Open worksheet", exact: true }).click();
  const reopened = await (await page.request.get(path + "/" + value.run.id, { headers })).json();
  expect(reopened).toEqual(value);
  await result.getByText("Original ledger rows and private evidence", { exact: true }).click();
  await expect(result).toContainText('"raw_value": "B"');
  await result.getByText("Original ledger rows and private evidence", { exact: true }).click();
  await result.getByText("Download worksheet", { exact: true }).click();
  for (const [format, label, extension, signature] of [["pdf", "PDF", "pdf", "%PDF"], ["xlsx", "Excel", "xlsx", "PK"], ["csv", "CSV bundle", "zip", "PK"], ["png", "PNG", "png", "PNG"]] as const) {
    await result.getByRole("combobox", { name: "File type", exact: true }).selectOption(format);
    const downloaded = page.waitForEvent("download");
    await result.getByRole("button", { name: `Download ${label}`, exact: true }).click();
    const download = await downloaded;
    expect(download.suggestedFilename()).toMatch(new RegExp(`consolidation.*\\.${extension}$`));
    const bytes = readFileSync((await download.path())!);
    expect(bytes.subarray(format === "png" ? 1 : 0, format === "png" ? 4 : signature.length).toString()).toBe(signature);
  }
  const output = process.env.PLAYWRIGHT_JSON_OUTPUT_NAME ? join(dirname(process.env.PLAYWRIGHT_JSON_OUTPUT_NAME), "captures", "consolidation") : "../../data/verification/2026-10-17/two-phase/consolidation-browser"; mkdirSync(output, { recursive: true });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await result.screenshot({ path: `${output}/result-${width}.png` });
    await panel.getByRole("button", { name: "Back", exact: true }).click();
    const editor = panel.locator("form"); await editor.screenshot({ path: `${output}/mapping-${width}.png` });
    await panel.getByRole("button", { name: "Continue to review", exact: true }).click();
  }
  for (const company of companies) expect(await (await page.request.get(`${api}/workspaces/${company.wid}/datasets/${company.did}/uploads/${company.uid}/content`, { headers })).body()).toEqual(company.original);
  expect(errors).toEqual([]);
});
