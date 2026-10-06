/* Use case: Verifies chart exploration keeps exact source evidence and executes real filters.
What it does: Exercises signed and missing values, modal keyboard behavior, server drill-down, and narrow screens against actual services. */

import { execFileSync } from "node:child_process";
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
  const discovery = page.getByRole("region", {
    name: "First reading of your data",
    exact: true,
  });
  await expect(discovery.locator(".discoveryValue").first()).toContainText(
    "-1.25",
  );
  await page
    .locator("summary")
    .filter({ hasText: "Charts & dashboard controls" })
    .click();
  const dashboard = page.getByRole("region", {
    name: "Dataset dashboard",
    exact: true,
  });
  const trend = dashboard.locator('[data-visualization="Date trend"]');
  await expect(dashboard.locator('[data-visualization="Amount by Region"] .barButton').first()).toHaveCSS("display", "grid");
  await expect(trend.locator(".chartPoint")).toHaveCount(3);
  await expect(trend.locator("polyline")).toHaveCount(2);
  await expect(trend).not.toContainText("__value");
  await expect(trend).toContainText("Missing values remain gaps");
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
  await expect(
    modal.getByRole("list", { name: "Date trend", exact: true }),
  ).toContainText("-1.250000000000");
  await expect(
    modal
      .getByRole("listitem")
      .filter({ hasText: "2026-01-03" })
      .locator(".discoveryBarTrack > span"),
  ).toHaveCSS("width", "0px");
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
  await expandedBreakdown
    .getByRole("button", { name: /West.*-1\.250000000000/ })
    .click();
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
