/* Use case: Verifies private memory and the redesigned studio against real workspace services.
What it does: Exercises cross-file preference persistence, competing edits, explicit forgetting and demo entry points. */

import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { finishInitialReview } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";
const screenshots = "../../data/verification/2026-10-16/studio-ui";

async function start(page: Page) {
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `studio-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await upload(page, "regional-sales.csv");
  return { headers: { Authorization: `Bearer ${token}` }, workspace: await page.getByLabel("Current workspace").inputValue() };
}
async function upload(page: Page, name: string) {
  await page.getByLabel("CSV or Excel file").setInputFiles({ name, mimeType: "text/csv", buffer: Buffer.from("city,amount\nKarachi,0.10\nLahore,0.20\nKarachi,0.30\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
}
async function navigate(page: Page, name: string) {
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name, exact: true }).click();
}

test("private memory survives files and reopening, handles competing edits, and can be forgotten", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const { headers, workspace } = await start(page);
  const memoryPath = `${api}/workspaces/${workspace}/agent-memory`;
  await navigate(page, "My memory");
  const memory = page.getByRole("region", { name: "My private agent memory", exact: true });
  await memory.getByLabel("Your role or perspective", { exact: false }).fill("Retail operations lead");
  await memory.getByLabel("What you usually want to understand", { exact: false }).fill("Explain sales changes simply, then suggest one useful next question.");
  await memory.getByRole("radio", { name: /Step by step/ }).check();
  await memory.getByRole("button", { name: "Save my memory", exact: true }).click();
  await expect(memory.getByRole("status")).toContainText("Memory saved");
  expect((await (await page.request.get(memoryPath, { headers })).json()).version).toBe(1);
  await navigate(page, "Data library");
  await upload(page, "second-retail-file.csv");
  await navigate(page, "My memory");
  await expect(memory.getByLabel("Your role or perspective", { exact: false })).toHaveValue("Retail operations lead");
  await expect(memory.getByRole("radio", { name: /Step by step/ })).toBeChecked();
  mkdirSync(screenshots, { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: `${screenshots}/memory-${width}.png`, animations: "disabled", fullPage: true });
    await page.screenshot({ path: `${screenshots}/memory-viewport-${width}.png`, animations: "disabled", fullPage: false });
  }
  const competing = await page.request.put(memoryPath, { headers, data: { expected_version: 1, role: "Updated from another tab", focus: "Explain data", explanation_style: "concise" } });
  expect(competing.ok()).toBe(true);
  await memory.getByLabel("Your role or perspective", { exact: false }).fill("My unsaved draft");
  await memory.getByRole("button", { name: "Save my memory", exact: true }).click();
  await expect(memory.getByRole("alert")).toContainText("changed in another tab");
  await expect(memory.getByLabel("Your role or perspective", { exact: false })).toHaveValue("My unsaved draft");
  await memory.getByRole("button", { name: "Reload saved memory", exact: true }).click();
  await expect(memory.getByLabel("Your role or perspective", { exact: false })).toHaveValue("Updated from another tab");
  await memory.getByRole("button", { name: "Forget my memory", exact: true }).click();
  await memory.getByRole("button", { name: "Clear saved memory", exact: true }).click();
  await expect(memory.getByRole("status")).toContainText("Memory cleared");
  await navigate(page, "Overview");
  await page.getByRole("button", { name: /Make it your data partner/ }).click();
  await expect(memory.getByLabel("Your role or perspective", { exact: false })).toHaveValue("");
  await expect(memory.getByLabel("What you usually want to understand", { exact: false })).toHaveValue("");
  const final = await (await page.request.get(memoryPath, { headers })).json();
  expect(final).toMatchObject({ role: "", focus: "", explanation_style: "concise", version: 3 });
  expect(errors).toEqual([]);
});

test("studio tool cards navigate real workflows and both fictional demos retain explicit meaning review", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const { workspace, headers } = await start(page);
  const home = page.getByRole("region", { name: "Analytics home", exact: true });
  mkdirSync(screenshots, { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: `${screenshots}/home-${width}.png`, animations: "disabled", fullPage: true });
    await page.screenshot({ path: `${screenshots}/home-viewport-${width}.png`, animations: "disabled", fullPage: false });
  }
  await home.getByRole("button", { name: "Open forecasts and what-ifs", exact: true }).click();
  await expect(page.locator("main")).toHaveAttribute("data-section", "forecasts");
  await navigate(page, "Overview");
  await home.getByRole("button", { name: "Open anomalies and decisions", exact: true }).click();
  await expect(page.locator("main")).toHaveAttribute("data-section", "decisions");
  await navigate(page, "Data library");
  await page.getByRole("button", { name: /Explore retail demo/ }).click();
  await finishInitialReview(page);
  await expect(page.getByLabel("Profile upload")).toContainText("retail");
  const retail = `/workspaces/${workspace}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}`;
  const understanding = await (await page.request.get(`${api}${retail}/understanding`, { headers })).json();
  expect(understanding.state).not.toBe("confirmed");
  await navigate(page, "Data library");
  await page.getByRole("button", { name: /Try decision demo/ }).click();
  await finishInitialReview(page);
  const decision = `/workspaces/${workspace}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}`;
  expect(decision).not.toBe(retail);
  expect((await (await page.request.get(`${api}${decision}/understanding`, { headers })).json()).state).not.toBe("confirmed");
  expect(errors).toEqual([]);
});

test("confirmed version three exposes missing units and saves a unit answer without replacing its meaning", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const { workspace, headers } = await start(page);
  await navigate(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "meaning-regression.csv", mimeType: "text/csv", buffer: Buffer.from("date,category,revenue,cost\n2026-01-01,A,100,60\n2026-01-02,B,120,70\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  const root = `/workspaces/${workspace}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}`;
  let saved = await (await page.request.get(`${api}${root}/understanding`, { headers })).json();
  const definition = { ...saved.definition, grain: "record", description: "Fictional daily revenue and cost by category.", columns: saved.definition.columns.map((column: { name: string; role: string }) => ({ ...column, meaning: `Saved meaning of ${column.name}`, unit: "", currency: "", unit_column: "" })) };
  for (let version = 0; version < 3; version++) {
    expect((await page.request.post(`${api}${root}/understanding`, { headers, data: { revision_id: saved.revision_id, expected_version: version, state: "confirmed", definition } })).status()).toBe(201);
  }
  await navigate(page, "Saved work");
  await navigate(page, "Overview");
  await page.getByRole("button", { name: "Review saved details", exact: true }).click();
  const meaning = page.getByRole("region", { name: "Data understanding", exact: true });
  await expect(meaning).toContainText("Version 3");
  const missing = meaning.getByRole("list", { name: "Missing data details", exact: true });
  await expect(missing.getByRole("listitem")).toHaveCount(2);
  for (const item of await missing.getByRole("listitem").all()) { await expect(item).toBeVisible(); expect((await item.innerText()).trim().length).toBeGreaterThan(10); }
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await meaning.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${screenshots}/missing-details-${width}.png`, animations: "disabled" });
  }
  await meaning.getByRole("button", { name: "Complete missing details", exact: true }).click();
  const reading = page.getByRole("region", { name: "Data reading", exact: true });
  await expect(reading).toContainText('What unit does "revenue" use?');
  await expect(reading.getByRole("button", { name: "Use my answer", exact: true })).toBeDisabled();
  await expect(reading.getByRole("textbox", { name: "What does this column mean?", exact: true })).toHaveValue("Saved meaning of revenue");
  await reading.getByRole("textbox", { name: "Unit of measurement (required)", exact: true }).fill("USD");
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await reading.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${screenshots}/unit-answer-${width}.png`, animations: "disabled" });
  }
  await reading.getByRole("button", { name: "Use my answer", exact: true }).click();
  await expect(reading).toContainText('What unit does "cost" use?');
  await reading.getByRole("button", { name: "Skip this question →", exact: true }).click();
  await reading.getByRole("button", { name: "Save as context for this data", exact: true }).click();
  await expect(reading).toContainText("1 detail still needs review");
  saved = await (await page.request.get(`${api}${root}/understanding`, { headers })).json();
  expect(saved.version).toBe(4);
  expect(saved.definition.columns.find((column: { name: string }) => column.name === "revenue")).toMatchObject({ meaning: "Saved meaning of revenue", unit: "USD" });
  expect(saved.definition.columns.find((column: { name: string }) => column.name === "cost")).toMatchObject({ meaning: "Saved meaning of cost", unit: "" });
  await reading.getByRole("button", { name: "Continue to my insights", exact: true }).click();
  await page.getByRole("button", { name: "Review saved details", exact: true }).click();
  await expect(meaning.getByRole("listitem")).toContainText("cost");
  await meaning.getByText("Edit saved definitions", { exact: true }).click();
  await meaning.getByLabel("Column to review").selectOption("cost");
  await meaning.getByLabel("Unit of measurement", { exact: true }).fill("USD");
  let reloadFails = true;
  let writeCount = 0;
  await page.route(`**${root}/understanding`, async route => {
    if (route.request().method() === "POST") { writeCount += 1; return route.continue(); }
    if (reloadFails) { reloadFails = false; return route.fulfill({ status: 503, json: { error: { message: "Temporary reload failure" } } }); }
    return route.continue();
  });
  await meaning.getByRole("button", { name: "Confirm business definitions", exact: true }).click();
  await expect(meaning.getByRole("status")).toContainText("Business definitions confirmed");
  await expect(meaning.getByRole("alert")).toContainText("definitions were saved");
  await meaning.getByRole("button", { name: "Reload saved details", exact: true }).click();
  await expect(meaning.getByRole("alert")).toHaveCount(0);
  await expect(meaning.getByLabel("Column to review")).toHaveValue("cost");
  await expect(meaning.getByRole("list", { name: "Missing data details", exact: true })).toHaveCount(0);
  expect(writeCount).toBe(1);
  saved = await (await page.request.get(`${api}${root}/understanding`, { headers })).json();
  expect(saved.version).toBe(5); expect(saved.questions).toEqual([]);
  expect(saved.definition.columns.map((column: { meaning: string }) => column.meaning)).toEqual(definition.columns.map((column: { meaning: string }) => column.meaning));
  expect(errors).toEqual([]);
});
