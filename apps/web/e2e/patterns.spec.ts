/* Use case: Exercises real measured patterns and no-date alternatives through the existing chat.
What it does: Checks saved evidence, explicit daily assumptions, exact returned values and narrow layouts. */

import { execFileSync } from "node:child_process";
import { finishInitialReview } from "./workspace-helpers";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("measured patterns replay privately and no-date forecasts lead to explicit daily what-ifs", async ({ page }) => {
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `patterns-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const csv = "group,amount,reading,condition\n" + Array.from({ length: 40 }, (_, index) => `${index < 20 ? "A" : "B"},${index + 1},${(index + 1) * 2},${index < 20 ? "Dry" : "Wet"}\n`).join("");
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "measured-patterns.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await nav.getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await page.getByRole("button", { name: "Review data meanings", exact: true }).click();
  const meanings = page.getByRole("region", { name: "Data understanding", exact: true });
  await meanings.getByLabel("One row represents").selectOption("record");
  for (const name of ["amount", "reading"]) {
    await meanings.getByLabel("Column to review").selectOption(name);
    await meanings.getByLabel("Unit of measurement", { exact: true }).fill("mm");
  }
  await meanings.getByRole("button", { name: "Confirm business definitions", exact: true }).click();
  await expect(meanings.getByText("confirmed", { exact: true })).toBeVisible();
  await nav.getByRole("button", { name: "Forecasts", exact: true }).click();
  await expect(page.getByRole("heading", { name: "This file has no timeline to forecast" })).toBeVisible();
  await page.getByRole("button", { name: "Find patterns", exact: false }).click();
  const patterns = page.getByRole("region", { name: "Measured data patterns", exact: true });
  await expect(patterns.getByRole("heading", { name: "Here is what stands out", exact: true })).toBeVisible();
  await expect.poll(async () => {
    const heading = await patterns.getByRole("heading", { name: "Here is what stands out", exact: true }).boundingBox();
    const log = await page.getByRole("log", { name: "Conversation", exact: true }).boundingBox();
    return Boolean(heading && log && heading.y >= log.y && heading.y + heading.height <= log.y + log.height);
  }).toBe(true);
  await expect(patterns).toContainText("40 rows");
  await expect(patterns.locator(".patternFinding")).not.toHaveCount(0);
  await expect(patterns).toContainText("do not prove that one thing caused another");
  await expect(patterns.locator("svg")).not.toHaveCount(0);
  const chart = patterns.locator(".patternFinding").filter({ has: page.locator(".patternScatter") }).first();
  const recordPlot = chart.getByRole("group", { name: /^Record chart for/ });
  await recordPlot.focus();
  await page.keyboard.press("ArrowRight");
  await expect(chart.getByRole("status")).toContainText("Record 2");
  await chart.getByLabel("Inspect a plotted record").selectOption("0");
  await expect(chart.getByRole("status")).toContainText("Record 1");
  await chart.locator("circle").last().hover();
  await expect(chart.getByRole("status")).toContainText(`Record ${await chart.locator("circle").count()}`);
  await recordPlot.focus();
  await page.keyboard.press("ArrowRight");
  await expect(chart.getByRole("status")).toContainText("Record 2");
  await expect(chart.locator("polyline, path")).toHaveCount(0);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(chart).toHaveCSS("animation-name", "none");
  await patterns.locator(".patternDetails summary").first().click();
  await expect(patterns.getByRole("table").first()).toBeVisible();
  await patterns.locator(".patternDetails summary").first().click();
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    const picker = chart.getByLabel("Inspect a plotted record");
    const pickerSize = await picker.boundingBox();
    expect(pickerSize).not.toBeNull();
    expect(pickerSize!.height).toBeGreaterThanOrEqual(44);
    expect(pickerSize!.height).toBeLessThanOrEqual(60);
    expect(await picker.evaluate(element => element.getBoundingClientRect().width <= element.parentElement!.clientWidth + 1)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await patterns.locator(".patternOverview").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `../../data/verification/2026-10-14/patterns/patterns-${width}.png`, fullPage: true });
  }
  for (const viewport of [{ width: 375, height: 812 }, { width: 844, height: 390 }]) {
    await page.setViewportSize(viewport);
    await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
    expect(await chart.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    await expect(chart.getByLabel("Inspect a plotted record")).toBeVisible();
    await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "New conversation", exact: true }).click();
  await page.locator(".conversationHistory summary").click();
  await page.getByRole("button", { name: "Refresh history", exact: true }).click();
  await expect(page.getByLabel("Saved conversation").locator("option")).toHaveCount(2);
  await page.getByLabel("Saved conversation").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Open conversation", exact: true }).click();
  await page.getByRole("button", { name: "Load saved answer", exact: true }).click();
  await expect(patterns.getByRole("heading", { name: "Here is what stands out", exact: true })).toBeVisible();
  await nav.getByRole("button", { name: "Forecasts", exact: true }).click();
  await page.getByRole("button", { name: "Try a daily what-if", exact: false }).click();
  const scenarios = page.getByRole("region", { name: "Scenario comparisons", exact: true });
  await expect(scenarios.getByRole("combobox", { name: "Change type 1", exact: true })).toHaveValue("daily_change");
  await expect(scenarios.getByLabel("Change per day 1", { exact: false })).toHaveValue("");
  await expect(scenarios.getByLabel("Number of days 1", { exact: true })).toHaveValue("");
  await scenarios.getByRole("combobox", { name: "Scenario measure", exact: true }).selectOption("amount");
  await scenarios.getByRole("combobox", { name: "Baseline calculation", exact: true }).selectOption("avg");
  await scenarios.getByLabel("Change per day 1", { exact: false }).fill("-2");
  await scenarios.getByLabel("Number of days 1", { exact: true }).fill("3");
  await scenarios.getByRole("checkbox", { name: "I confirm these are hypothetical", exact: false }).check();
  const responsePromise = page.waitForResponse(response => response.url().endsWith("/decision-analysis/scenarios") && response.request().method() === "POST");
  await scenarios.getByRole("button", { name: "Calculate and save comparison", exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(201);
  const saved = await response.json();
  expect(Number(saved.run.result.baseline)).toBe(20.5);
  expect(Number(saved.run.result.alternatives[0].result)).toBe(14.5);
  const daily = scenarios.getByRole("region", { name: "Daily what-if: My daily assumption", exact: true });
  await expect(daily).toContainText("YOUR ASSUMPTION · NOT A FORECAST");
  await expect(daily).toContainText(saved.run.result.alternatives[0].result);
  for (const point of saved.run.result.alternatives[0].path) await expect(daily).toContainText(point.value);
  await scenarios.getByRole("button", { name: "Replay comparison evidence", exact: true }).click();
  await expect(scenarios).toContainText("Baseline, coverage and alternatives reproduced");
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: `../../data/verification/2026-10-14/patterns/daily-${width}.png`, fullPage: true });
    await daily.screenshot({ path: `../../data/verification/2026-10-14/patterns/daily-result-${width}.png` });
  }
  expect(errors).toEqual([]);
});

test("weak and sparse pattern presentations explain their limits instead of inventing findings", async ({ page }) => {
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `pattern-empty-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "sparse.csv", mimeType: "text/csv", buffer: Buffer.from("region,amount\nNorth,1\nSouth,2\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  let status = "no_strong_patterns";
  await page.route(/\/jobs\/[^/]+\/result$/, async route => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ json: { ...body, answer: { kind: "patterns", patterns: { version: "presentation-fixture", engine_version: "fixture", status, findings: [], coverage: { source_rows: 2, filtered_rows: 2, eligible_columns: 2, checked_candidates: 0, suppressed_candidates: 0, selected_findings: 0 }, limitations: ["Presentation fixture only; no numerical findings."], exclusions: [] } } } });
  });
  await page.getByRole("button", { name: "Understand this data", exact: true }).click();
  await expect(page.getByRole("heading", { name: "No clear pattern found", exact: true })).toBeVisible();
  status = "insufficient_data";
  await page.getByLabel("Your question", { exact: true }).fill("Help me understand my data");
  await page.getByLabel("Your question", { exact: true }).press("Enter");
  await expect(page.getByRole("heading", { name: "A little more data is needed", exact: true })).toBeVisible();
  await expect(page.locator(".patternFinding")).toHaveCount(0);
  await page.setViewportSize({ width: 320, height: 1000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
});

test("a real weak relationship remains inspectable without becoming a strong finding", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `pattern-weak-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const csv = "amount,reading\n" + Array.from({ length: 80 }, (_, index) => `${index + 1},${(index + 1) * 17 % 83}\n`).join("");
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "weak-measurements.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await nav.getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await page.getByRole("button", { name: "Review data meanings", exact: true }).click();
  const meanings = page.getByRole("region", { name: "Data understanding", exact: true });
  await meanings.getByLabel("One row represents").selectOption("record");
  for (const name of ["amount", "reading"]) {
    await meanings.getByLabel("Column to review").selectOption(name);
    await meanings.getByLabel("Unit of measurement", { exact: true }).fill("mm");
  }
  await meanings.getByRole("button", { name: "Confirm business definitions", exact: true }).click();
  await expect(meanings.getByText("confirmed", { exact: true })).toBeVisible();
  await nav.getByRole("button", { name: "Overview", exact: true }).click();
  await page.getByRole("button", { name: "Find patterns", exact: true }).click();
  const patterns = page.getByRole("region", { name: "Measured data patterns", exact: true });
  await expect(patterns.getByRole("heading", { name: "No clear pattern found", exact: true })).toBeVisible();
  const exploratory = patterns.getByRole("region", { name: "Exploratory relationships", exact: true });
  await expect(exploratory).toContainText("Weak relationship · exploratory");
  await expect(exploratory).toContainText("80 rows");
  await expect(patterns.locator('.patternFinding[data-strength="screened"]')).toHaveCount(0);
  await exploratory.locator(".patternDetails summary").click();
  await expect(exploratory).toContainText("0.072949");
  await expect(exploratory.getByRole("table")).toBeVisible();
  await exploratory.locator(".patternDetails summary").click();
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await patterns.locator(".patternOverview").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `../../data/verification/2026-10-14/patterns/weak-${width}.png`, fullPage: true });
  }
  expect(errors).toEqual([]);
});
