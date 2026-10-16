/* Use case: Verifies the question-led analytics shell against real private workspace APIs.
What it does: Covers saved evidence navigation, accessible mobile search and preservation of a second question during active work. */

import { execFileSync } from "node:child_process";
import { finishInitialReview } from "./workspace-helpers";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const api = "http://127.0.0.1:8001";

async function start(page: Page) {
  const token = execFileSync("python3", [
    "-m", "execplus.manage", "provision-user", "--email",
    `analytics-home-${randomUUID()}@example.test`,
  ], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "regional-sales.csv", mimeType: "text/csv",
    buffer: Buffer.from("city,amount\nKarachi,0.10\nLahore,0.20\nKarachi,0.30\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
  return {
    headers: { Authorization: `Bearer ${token}` },
    root: `/workspaces/${await page.getByLabel("Current workspace").inputValue()}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}`,
  };
}

async function navigate(page: Page, name: string) {
  await page.getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name, exact: true }).click();
}

test("analytics home shows saved meaning and a private goal with clear review and exploration actions", async ({ page }) => {
  const { root, headers } = await start(page);
  const original = await (await page.request.get(`${api}${root}/understanding`, { headers })).json();
  const saved = await page.request.post(`${api}${root}/understanding`, {
    headers,
    data: {
      revision_id: original.revision_id, expected_version: original.version, state: "confirmed",
      definition: { ...original.definition, description: "Recorded sales by city, ready for regional comparisons.", grain: "record" },
    },
  });
  expect(saved.ok()).toBe(true);
  expect((await page.request.post(`${api}${root.split("/uploads/")[0]}/preferences`, {
    headers, data: { domain_hint: "sales", goal: "Compare the amount recorded for each city." },
  })).ok()).toBe(true);
  await navigate(page, "Saved work");
  await navigate(page, "Overview");
  const context = page.getByRole("region", { name: "Saved context for this data", exact: true });
  await expect(context.getByRole("heading", { name: "regional-sales.csv", exact: true })).toBeVisible();
  await expect(context).toContainText("Recorded sales by city, ready for regional comparisons.");
  await expect(context).toContainText("Definitions confirmed");
  await expect(context).toContainText("Your goal · Private");
  await expect(context).toContainText("Compare the amount recorded for each city.");
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(context.getByRole("button", { name: "Explore my goal", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  await context.getByRole("button", { name: "Review saved details", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toHaveAttribute("data-section", "overview");
  await expect(page.getByRole("region", { name: "Data understanding", exact: true })).toContainText("confirmed");
  await navigate(page, "Overview");
  await context.getByRole("button", { name: "Explore my goal", exact: true }).click();
  await expect(page.locator("main")).toHaveAttribute("data-section", "ask");
  await expect(page.locator(".userMessage").last()).toContainText("Analyze my data");
});

test("analytics home opens real saved evidence and mobile search preserves its selected source", async ({ page }) => {
  const { root, headers } = await start(page);
  const calculated = await page.request.post(`${api}${root}/query`, {
    headers, data: { metric: "amount", aggregation: "sum", group_by: ["city"] },
  });
  expect(calculated.ok()).toBe(true);
  const answer = await calculated.json();
  const saved = await page.request.post(`${api}${root}/saved-items`, {
    headers, data: { name: "Regional sales review", kind: "analysis", shared: false, payload: { query_id: answer.lineage.query_id } },
  });
  expect(saved.status()).toBe(201);
  await navigate(page, "Saved work");
  await navigate(page, "Overview");
  const home = page.getByRole("region", { name: "Analytics home", exact: true });
  await expect(home.getByRole("button", { name: /Regional sales review/ })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: "../../data/interface-reference/execplus-home-desktop.png", fullPage: false });
  await home.getByRole("button", { name: /Regional sales review/ }).click();
  const result = page.getByRole("region", { name: "Saved result: Regional sales review", exact: true });
  await expect(result).toBeVisible();
  await expect(result).toContainText(answer.lineage.query_id);
  await expect(result.getByRole("cell", { name: "0.400000000000", exact: true })).toBeVisible();
  await expect(page.getByLabel("Profile upload")).toHaveValue(root.split("/").at(-1)!);
  await navigate(page, "Overview");
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("button", { name: "Search your data", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  await page.getByRole("button", { name: "Search your data", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Dataset dashboard", exact: true })).toBeVisible();
  await expect(page.getByLabel("Profile upload")).toHaveValue(root.split("/").at(-1)!);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: "../../data/interface-reference/execplus-search-mobile.png", fullPage: true });
});

test("a second home question becomes an explicit draft while the real first job finishes", async ({ page }) => {
  await start(page);
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  let submitted = 0;
  await page.route(/\/threads\/[^/]+\/jobs$/, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    submitted += 1;
    if (submitted === 1) await held;
    await route.fulfill({ response });
  });
  try {
    await page.getByLabel("Ask about your data", { exact: true }).fill("Help me understand my data");
    await page.getByRole("button", { name: "Explore this question", exact: true }).click();
    await expect.poll(() => submitted).toBe(1);
    await expect(page.locator("main")).toHaveAttribute("data-section", "ask");
    await navigate(page, "Overview");
    await page.getByLabel("Ask about your data", { exact: true }).fill("What does city mean?");
    await page.getByRole("button", { name: "Explore this question", exact: true }).click();
    await expect(page.getByLabel("Your question")).toHaveValue("What does city mean?");
    await expect(page.getByText("Your next question is saved below. Send it when the current answer finishes.", { exact: true })).toBeVisible();
    expect(submitted).toBe(1);
    release();
    const chat = page.getByRole("region", { name: "Ask a question", exact: true });
    await expect(chat.locator(".datasetGuidance")).toContainText("3 rows and 2 columns");
    await expect(page.getByLabel("Your question")).toHaveValue("What does city mean?");
    await expect(chat.getByRole("button", { name: "Ask", exact: true })).toBeEnabled();
    await page.getByLabel("Your question").press("Enter");
    await expect.poll(() => submitted).toBe(2);
    await expect(chat.locator(".datasetGuidance")).toHaveCount(2);
    await expect(chat.locator(".datasetGuidance").last()).toContainText("city");
    await page.screenshot({ path: "../../data/interface-reference/execplus-conversation-desktop.png", fullPage: false });
    await navigate(page, "Overview");
    await navigate(page, "Ask ExecPlus");
    await expect(chat.locator(".datasetGuidance")).toHaveCount(2);
  } finally {
    release();
  }
});

test("overview keeps charts and first findings open with keyboard view and focus controls", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const { root, headers } = await start(page);
  const before = await (await page.request.get(`${api}${root}/understanding`, { headers })).json();
  const dashboardSection = page.getByRole("region", { name: "Charts & dashboard controls", exact: true });
  const findingsSection = page.getByRole("region", { name: "First findings from your file", exact: true });
  const dashboard = dashboardSection.getByRole("region", { name: "Dataset dashboard", exact: true });
  const findings = findingsSection.getByRole("region", { name: "First reading of your data", exact: true });
  await expect(dashboardSection).toBeVisible();
  await expect(findingsSection).toBeVisible();
  await expect(findings.locator(".discoveryValue")).toHaveText(["0.1", "0.3", "0.2"]);
  await expect(dashboard.locator('[data-chart-renderer="apache-echarts"] svg').first()).toBeVisible();
  expect(await dashboardSection.evaluate(element => element.closest("details") === null)).toBe(true);
  expect(await findingsSection.evaluate(element => element.closest("details") === null)).toBe(true);

  let calculations = 0;
  page.on("request", request => {
    if (request.method() === "POST" && /\/(dashboard|discovery)$/.test(new URL(request.url()).pathname)) calculations += 1;
  });
  const simple = page.getByRole("radio", { name: "Simple", exact: true });
  const expert = page.getByRole("radio", { name: "Expert", exact: true });
  const indicator = page.locator(".analysisViewIndicator");
  const transition = await indicator.evaluate(element => getComputedStyle(element).transitionDuration);
  expect(Number.parseFloat(transition)).toBeGreaterThan(0);
  expect(Number.parseFloat(transition)).toBeLessThanOrEqual(0.5);
  expect(await dashboardSection.evaluate(element => getComputedStyle(element).animationIterationCount)).toBe("1");
  await expect(simple).toBeChecked();
  await simple.focus();
  await page.keyboard.press("ArrowRight");
  await expect(expert).toBeChecked();
  await expect(dashboardSection).toBeVisible();
  await expect(findingsSection).toBeVisible();

  const focus = page.getByRole("combobox", { name: "Analysis focus", exact: true });
  await focus.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("listbox")).toBeVisible();
  await expect(page.getByRole("option", { name: "Descriptive · understand actual data", exact: true })).toBeFocused();
  await page.keyboard.press("End");
  await expect(page.getByRole("option", { name: "Prescriptive · bounded budget allocation", exact: true })).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await expect(page.getByRole("option", { name: "All supported · explore and forecast", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(focus).toContainText("All supported");
  await expect(page.locator("main")).toHaveAttribute("data-section", "overview");
  await expect(focus).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("option", { name: "All supported · explore and forecast", exact: true })).toBeFocused();
  await page.keyboard.press("Home");
  await expect(page.getByRole("option", { name: "Descriptive · understand actual data", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("listbox")).toHaveCount(0);
  await expect(focus).toContainText("All supported");
  await expect(focus).toBeFocused();

  const screenshotRoot = "../../data/verification/2026-10-16/overview-ui";
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect.poll(() => indicator.evaluate(element => getComputedStyle(element).transitionDuration)).toBe("0s");
    expect(await dashboardSection.evaluate(element => getComputedStyle(element).animationName)).toBe("none");
    expect(await findingsSection.evaluate(element => getComputedStyle(element).animationName)).toBe("none");
    await expert.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(simple).toBeChecked();
    await expect(dashboardSection).toBeVisible();
    await expect(findingsSection).toBeVisible();
    await expect(findings.locator(".discoveryValue")).toHaveText(["0.1", "0.3", "0.2"]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await dashboardSection.screenshot({ path: `${screenshotRoot}/dashboard-simple-${width}.png`, animations: "disabled" });
    await findingsSection.screenshot({ path: `${screenshotRoot}/findings-simple-${width}.png`, animations: "disabled" });
    await simple.focus();
    await page.keyboard.press("ArrowRight");
    await expect(expert).toBeChecked();
    await expect(dashboardSection).toBeVisible();
    await expect(findingsSection).toBeVisible();
    await expect(focus).toContainText("All supported");
    await focus.click();
    await expect(page.getByRole("option", { name: "All supported · explore and forecast", exact: true })).toHaveAttribute("aria-selected", "true");
    const menu = page.getByRole("listbox");
    const bounds = await menu.boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width + 1);
    await menu.screenshot({ path: `${screenshotRoot}/focus-menu-${width}.png`, animations: "disabled" });
    await page.keyboard.press("Escape");
    await expect(focus).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  expect(calculations).toBe(0);
  await navigate(page, "Ask ExecPlus");
  await expect(page.getByLabel("Your question", { exact: true })).toBeVisible();
  await expect(dashboardSection).toBeHidden();
  await expect(findingsSection).toBeHidden();
  expect(calculations).toBe(0);
  expect(await (await page.request.get(`${api}${root}/understanding`, { headers })).json()).toEqual(before);
  expect(errors).toEqual([]);
});
