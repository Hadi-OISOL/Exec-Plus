/* Use case: Verifies chart exploration keeps exact source evidence and executes real filters.
What it does: Exercises signed and missing values, modal keyboard behavior, server drill-down, and narrow screens against actual services. */

import { execFileSync } from "node:child_process";
import { finishInitialReview, openFindings } from "./workspace-helpers";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("chart and table exploration preserve exact values, gaps, source filters and keyboard focus", async ({
  page,
}) => {
  const session = execFileSync(
    "python3",
    [
      "-m",
      "execplus.manage",
      "provision-user",
      "--email",
      `visualization-${randomUUID()}@example.test`,
    ],
    { cwd: "../..", encoding: "utf8" },
  ).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(session);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign out", exact: true }),
  ).toBeEnabled();
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "precise-movements.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "date,region,amount\n2026-01-01,West,-1.25\n2026-01-02,Missing,\n2026-01-03,Zero,0.00\n2026-01-04,East,9007199254740993.000001\n",
    ),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await openFindings(page);
  const discovery = page.getByRole("region", {
    name: "First reading of your data",
    exact: true,
  });
  await expect(discovery.locator(".discoveryValue").first()).toContainText(
    "-1.25",
  );
  expect(await page.evaluate(() => {
    const controls = [...document.querySelectorAll('summary')].find(e => e.textContent?.includes('Charts & dashboard controls'));
    const chat = document.querySelector('.askPanel');
    return Boolean(controls && chat && (controls.compareDocumentPosition(chat) & Node.DOCUMENT_POSITION_FOLLOWING));
  })).toBe(true);
  await page
    .locator("summary")
    .filter({ hasText: "Charts & dashboard controls" })
    .click();
  const dashboard = page.getByRole("region", {
    name: "Dataset dashboard",
    exact: true,
  });
  const trend = dashboard.locator('[data-visualization="Date trend"]');
  const barEngine = dashboard.locator('[data-visualization="Amount by Region"] [data-chart-renderer="apache-echarts"]');
  await expect(barEngine).toHaveAttribute("data-engine-ready", "true");
  await expect(barEngine.locator("svg")).toBeVisible();
  await expect(trend.locator('[data-chart-template="documd-line"]')).toBeVisible();
  const trendEngine = trend.locator('[data-chart-renderer="apache-echarts"]');
  await expect(trendEngine.locator("svg")).toBeVisible();
  await expect(discovery.locator('.discoveryValue').filter({ hasText: '9,007,199,254,740,993' }).first()).toBeVisible();
  expect(await page.locator('.analyticsShell').evaluate(element => getComputedStyle(element).fontFamily.toLowerCase())).toContain('manrope');
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(trendEngine).toHaveAttribute("data-reduced-motion", "false");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(trendEngine).toHaveAttribute("data-reduced-motion", "true");
  await expect(trend).not.toContainText("__value");
  await expect(trend).toContainText("Missing values remain gaps");
  await expect(trend.getByLabel("Chart value range", { exact: true })).toContainText("9,007,199,254,740,993.000001");
  await trend.getByLabel("Inspect returned row for Date trend", { exact: true }).selectOption("3");
  await expect(trend.getByLabel("Exact chart detail for Date trend", { exact: true })).toContainText("9007199254740993.000001");
  await trend.getByLabel("Inspect returned row for Date trend", { exact: true }).selectOption("1");
  await expect(trend.getByLabel("Exact chart detail for Date trend", { exact: true })).toContainText("Missing");
  await trend.getByRole("group", { name: "Date trend interactive chart", exact: true }).focus();
  await page.keyboard.press("End");
  await expect(trend.getByLabel("Exact chart detail for Date trend", { exact: true })).toContainText("9007199254740993.000001");
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await trend.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await trend.screenshot({ path: `../../data/verification/2026-10-16/chart-experience/line-${width}.png`, animations: "disabled" });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: "../../data/interface-polish-20261013/local-charts.png", fullPage: true });
  await trend.getByRole("button", { name: "Table", exact: true }).click();
  const exact = trend.getByRole("region", {
    name: "Exact values for Date trend",
    exact: true,
  });
  await expect(exact).toContainText("9007199254740993.000001");
  await expect(exact).toContainText("Missing");
  await expect(exact).toContainText("-1.250000000000");
  await expect(exact.getByRole("columnheader", { name: "Amount", exact: true })).toBeVisible();
  await expect(trend).toContainText("4 returned rows");
  await expect(trend).toContainText("4 source records analyzed");

  const expand = trend.getByRole("button", {
    name: "Expand Date trend",
    exact: true,
  });
  await expand.click();
  const modal = page.getByRole("dialog", { name: "Date trend", exact: true });
  await expect(modal).toBeVisible();
  await expect(
    modal.getByRole("button", { name: "Close", exact: true }),
  ).toBeFocused();
  await modal.getByRole("button", { name: "Chart", exact: true }).click();
  await modal.getByRole("button", { name: "Bars", exact: true }).click();
  await expect(modal.locator('[data-chart-template="lieflat-g10"]')).toBeVisible();
  await page.setViewportSize({ width: 320, height: 1000 });
  const missingRows = modal.getByLabel("Rows without a value", { exact: true });
  await expect(missingRows).toContainText("Missing values · 1");
  await expect(missingRows.getByRole("listitem")).toHaveText("2026-01-02");
  await expect(missingRows).not.toContainText("2026-01-03");
  await modal.getByLabel("Inspect returned row for Date trend", { exact: true }).selectOption("2");
  await expect(modal.getByLabel("Exact chart detail for Date trend", { exact: true }).locator("strong").last()).toHaveText("0E-12");
  await modal.getByLabel("Inspect returned row for Date trend", { exact: true }).selectOption("1");
  await expect(modal.getByLabel("Exact chart detail for Date trend", { exact: true })).toContainText("Missing");
  await modal.getByRole("button", { name: "Dots", exact: true }).click();
  await expect(modal.getByRole("button", { name: "Dots", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(modal.locator('[data-chart-template="echarts-dots"] svg')).toBeVisible();
  await modal.getByLabel("Inspect returned row for Date trend", { exact: true }).selectOption("3");
  await expect(modal.getByLabel("Exact chart detail for Date trend", { exact: true })).toContainText("9007199254740993.000001");
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await modal.screenshot({ path: `../../data/verification/2026-10-16/chart-experience/dots-${width}.png`, animations: "disabled" });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.keyboard.press("Escape");
  await expect(modal).not.toBeVisible();
  await expect(expand).toBeFocused();

  await dashboard
    .getByText("Customize view & filters", { exact: true })
    .click();
  await dashboard
    .getByRole("combobox", { name: "Filter column", exact: true })
    .selectOption("region");
  await dashboard.getByLabel("Filter equals", { exact: true }).fill("West");
  const filtered = page.waitForResponse(
    (response) =>
      response.url().endsWith("/dashboard") &&
      response.request().method() === "POST",
  );
  await dashboard
    .getByRole("button", { name: "Apply dashboard filter", exact: true })
    .click();
  const filterResponse = await filtered;
  expect(filterResponse.ok()).toBe(true);
  expect(filterResponse.request().postDataJSON().filters).toEqual([
    { column: "region", operator: "eq", value: "West" },
  ]);
  await expect(dashboard.getByLabel("Applied dashboard filters")).toContainText(
    "region = West",
  );
  const drilled = page.waitForResponse(
    (response) =>
      response.url().endsWith("/rows") &&
      response.request().method() === "POST",
  );
  await dashboard
    .getByRole("button", { name: "Expand Amount by Region", exact: true })
    .click();
  const expandedBreakdown = page.getByRole("dialog", {
    name: "Amount by Region",
    exact: true,
  });
  await expandedBreakdown.getByRole("button", { name: "Dots", exact: true }).click();
  await expandedBreakdown.getByRole("button", { name: "View records for West", exact: true }).focus();
  await expect(expandedBreakdown.getByLabel("Exact chart detail for Amount by Region", { exact: true })).toContainText("-1.250000000000");
  await page.keyboard.press("Enter");
  await expect(expandedBreakdown).not.toBeVisible();
  const drillResponse = await drilled;
  expect(drillResponse.ok()).toBe(true);
  expect(drillResponse.request().postDataJSON().filters).toEqual([
    { column: "region", operator: "eq", value: "West" },
    { column: "region", operator: "eq", value: "West" },
  ]);
  const returned = dashboard.locator(".drilldownRows");
  await expect(returned).toContainText("1 of 1 matching records shown");
  await expect(returned).toContainText("-1.250000000000");
  await expect(returned).not.toContainText("East");
  const reset = page.waitForResponse(
    (response) =>
      response.url().endsWith("/dashboard") &&
      response.request().method() === "POST",
  );
  await dashboard
    .getByRole("button", { name: "Remove dashboard filter", exact: true })
    .click();
  expect((await reset).request().postDataJSON().filters).toEqual([]);
  await expect(dashboard.getByLabel("Applied dashboard filters")).toContainText(
    "All source rows",
  );
  await expect(returned).toHaveCount(0);
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect
      .poll(() =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      )
      .toBe(true);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await page.screenshot({
      path: `../../data/interface-reference/execplus-visualization-${width}.png`,
      fullPage: true,
    });
  }
});

test("bundled chart engines navigate every returned row without changing the calculation", async ({ page }) => {
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `chart-window-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const csv = "date,region,amount\n" + Array.from({ length: 45 }, (_, index) => `${new Date(Date.UTC(2026, 0, index + 1)).toISOString().slice(0, 10)},Region ${index % 3},${index === 17 ? "" : index + 1}`).join("\n");
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "complete-chart.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await openFindings(page);
  await page.locator("summary").filter({ hasText: "Charts & dashboard controls" }).click();
  const trend = page.locator('[data-visualization="Date trend"]');
  await expect(trend.getByLabel("Inspect returned row for Date trend").locator("option")).toHaveCount(45);
  let calculations = 0;
  page.on("request", request => { if (request.method() === "POST" && /\/(dashboard|query)$/.test(new URL(request.url()).pathname)) calculations += 1; });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const [name, template] of [["Bars", "lieflat-g10"], ["Dots", "echarts-dots"], ["Line", "documd-line"]] as const) {
    await trend.getByRole("button", { name, exact: true }).click();
    await expect(trend.locator(`[data-chart-template="${template}"] svg`)).toBeVisible();
    if (name === "Bars") {
      const previewBar = trend.locator('svg path[fill="#176c64"]').nth(2);
      await previewBar.hover();
      await expect(trend.getByLabel("Exact chart detail for Date trend").locator("strong").last()).not.toHaveText("1");
      await expect(trend.getByLabel("Inspect returned row for Date trend")).toHaveValue("0");
      await trend.getByRole("button", { name: "Next chart row for Date trend", exact: true }).click();
      await expect(trend.getByLabel("Exact chart detail for Date trend").locator("strong").last()).toHaveText("2");
    }
    await trend.getByRole("button", { name: "Zoom in", exact: true }).click();
    const canvas = trend.getByRole("group", { name: "Date trend interactive chart", exact: true });
    await canvas.focus();
    await page.keyboard.press("End");
    await expect(trend.getByLabel("Exact chart detail for Date trend")).toContainText("2026-02-14");
    await expect(trend.getByLabel("Exact chart detail for Date trend").locator("strong").last()).toHaveText("45");
    await expect(trend.getByRole("group", { name: "Date trend chart navigation" })).toContainText(/–45 of 45 returned rows/);
    await trend.getByLabel("Inspect returned row for Date trend").selectOption("17");
    await expect(trend.getByLabel("Exact chart detail for Date trend")).toContainText("Missing");
    await trend.getByRole("button", { name: "Show all", exact: true }).click();
    await expect(trend.getByRole("group", { name: "Date trend chart navigation" })).toContainText("Viewing 1–45 of 45 returned rows");
    await trend.getByLabel("Inspect returned row for Date trend").selectOption("44");
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await trend.scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      expect(await trend.locator('[data-chart-renderer="apache-echarts"] svg').evaluate(node => /NaN|Infinity/.test(node.innerHTML))).toBe(false);
      await trend.screenshot({ path: `../../data/verification/2026-10-16/chart-experience/engine-${template}-${width}.png`, animations: "disabled" });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  expect(calculations).toBe(0);
});
