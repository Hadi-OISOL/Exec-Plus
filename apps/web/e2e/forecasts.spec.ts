/* Use case: Verifies basic forecasts and audit history in the real browser workflow.
What it does: Covers review, coverage declarations, exact estimates, saved evidence, later actuals and narrow-screen access without mocked results. */

import { execFileSync } from "node:child_process";
import { finishInitialReview, selectAnalysisFocus, navigateTo } from "./workspace-helpers";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const pageErrors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  pageErrors.set(page, errors);
  page.on("pageerror", error => errors.push(error.message));
});
test.afterEach(async ({ page }) => {
  expect(pageErrors.get(page) ?? []).toEqual([]);
});

test("advanced smoothing keeps rolling evidence, exact saved estimates and portable exports", async ({ page }) => {
  test.setTimeout(150_000);
  await signIn(page, session());
  await upload(page, 50);
  await selectAnalysisFocus(page, "predictive");
  await review(page);
  await page.getByRole("combobox", { name: "Period", exact: true }).selectOption("daily");
  await page.getByRole("combobox", { name: "Forecast approach", exact: true }).selectOption("advanced-v2");
  await expect(page.getByText(/This choice needs at least 30 complete days/)).toBeVisible();
  await page.getByLabel("Advanced method family").selectOption("holt_winters_additive");
  await page.getByLabel("I confirm the source covers every complete period in this range.").check();
  await expect(page.getByRole("button", { name: "Create forecast", exact: true })).toBeDisabled();
  await expect(page.getByText(/declare the repeating cycle before continuing/)).toBeVisible();
  await page.getByLabel("Advanced method family").selectOption("auto");
  const created = page.waitForResponse(response => response.request().method() === "POST" && /\/uploads\/[^/]+\/forecasts$/.test(new URL(response.url()).pathname));
  await page.getByRole("button", { name: "Create forecast", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const run = await response.json();
  expect(run.result.version).toBe("forecast-v2");
  expect(run.result.method.id).toBe("holt");
  expect(Number(run.result.predictions[0].estimate)).toBe(5.1);
  expect(run.result.selection.folds).toHaveLength(3);
  const result = page.getByRole("article", { name: "Forecast result: amount forecast", exact: true });
  await expect(result).toContainText("Empirical validation-error range");
  await expect(result).toContainText("A separate later window measures its error");
  await expect(result.locator(".verifiedBadge")).toHaveCount(0);
  await result.getByLabel("Inspect a forecast period").selectOption(run.result.predictions[0].period);
  await expect(result.getByRole("status").first()).toContainText(run.result.predictions[0].estimate);
  await result.getByText("Method, backtest and source evidence", { exact: true }).click();
  await expect(result.getByRole("heading", { name: "Rolling validation windows", exact: true })).toBeVisible();
  await expect(result).toContainText("smoothing-grid-v1");
  await expect(result).toContainText(run.evidence.query_ids[0]);
  await result.getByText("Method, backtest and source evidence", { exact: true }).click();
  for (const width of [1440, 390, 320]) {
    const theme = width === 390 ? "dark" : "light";
    await page.getByLabel("Appearance", { exact: true }).selectOption(theme);
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(await result.locator(".forecastChart").evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    const choice = await page.getByLabel("Advanced method family").boundingBox();
    expect(choice?.height).toBeGreaterThanOrEqual(44);
    expect(choice?.height).toBeLessThanOrEqual(64);
    await result.screenshot({ path: `../../data/verification/2026-10-18/intelligence-upgrade/advanced-forecast-${theme}-${width}.png` });
  }
  await result.getByText("Download saved forecast", { exact: true }).click();
  await result.getByRole("combobox", { name: "File type", exact: true }).selectOption("xlsx");
  const download = page.waitForEvent("download");
  await result.getByRole("button", { name: "Download Excel", exact: true }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/\.xlsx$/);
  expect(await file.failure()).toBeNull();
  await page.getByRole("combobox", { name: "Saved forecast", exact: true }).selectOption(run.id);
  const reopened = page.waitForResponse(value => value.request().method() === "GET" && value.url().endsWith(`/forecasts/${run.id}`));
  await page.getByRole("button", { name: "Open saved forecast", exact: true }).click();
  expect((await (await reopened).json()).result).toEqual(run.result);
});

test("calendar effects are compared with the best smoothing method before use", async ({ page }) => {
  test.setTimeout(150_000);
  await signIn(page, session());
  await upload(page, 50);
  await selectAnalysisFocus(page, "predictive");
  await review(page);
  await page.getByRole("combobox", { name: "Period", exact: true }).selectOption("daily");
  await page.getByRole("combobox", { name: "Forecast approach", exact: true }).selectOption("advanced-v4");
  await expect(page.getByLabel("Known event column · optional, 0 or 1 per row")).toHaveValue("");
  await page.getByLabel("I confirm the source covers every complete period in this range.").check();
  const created = page.waitForResponse(response => response.request().method() === "POST" && /\/uploads\/[^/]+\/forecasts$/.test(new URL(response.url()).pathname));
  await page.getByRole("button", { name: "Create forecast", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const run = await response.json();
  expect(run.result.version).toBe("forecast-v4");
  expect(run.request.event_column).toBeUndefined();
  const comparison = page.getByRole("region", { name: "Calendar effects comparison", exact: true });
  await expect(comparison).toContainText(run.result.regressors.best_without_regressors.validation_mae);
  await expect(comparison).toContainText(run.result.regressors.selected === "calendar_regression" ? "so this forecast uses them" : "so they are not used");
  await page.setViewportSize({ width: 320, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
});

test("holidays are tried only after smoothing and calendar effects and their comparison is shown", async ({ page }) => {
  test.setTimeout(150_000);
  await signIn(page, session());
  await upload(page, 50);
  await selectAnalysisFocus(page, "predictive");
  await review(page);
  await page.getByRole("combobox", { name: "Period", exact: true }).selectOption("daily");
  await page.getByRole("combobox", { name: "Forecast approach", exact: true }).selectOption("advanced-v5");
  const declared = page.getByRole("group", { name: "Holidays and outside predictors", exact: true });
  await declared.getByRole("checkbox", { name: "Use the built-in", exact: false }).check();
  await declared.getByLabel("Holiday or closure dates · history and forecast periods").fill("2024-01-20, 2024-02-01");
  await expect(declared.getByRole("combobox", { name: "Outside predictor 1 · optional", exact: true })).toHaveValue("");
  await page.getByLabel("I confirm the source covers every complete period in this range.").check();
  const created = page.waitForResponse(response => response.request().method() === "POST" && /\/uploads\/[^/]+\/forecasts$/.test(new URL(response.url()).pathname));
  await page.getByRole("button", { name: "Create forecast", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const run = await response.json();
  expect(run.result.version).toBe("forecast-v5");
  expect(run.request).toMatchObject({ engine: "advanced-v5", holiday_calendar: "pk-public-fixed-v1", holiday_dates: ["2024-01-20", "2024-02-01"] });
  expect(run.request.predictors).toBeUndefined();
  const comparison = page.getByRole("region", { name: "Holidays and predictors comparison", exact: true });
  await expect(comparison).toContainText(run.result.regressors.best_with_declared.validation_mae);
  await expect(comparison).toContainText(run.result.regressors.selected === "declared_regressors" ? "so this forecast uses them" : "so they are not used");
  await page.setViewportSize({ width: 320, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
});

function session() {
  return execFileSync(
    "python3",
    [
      "-m",
      "execplus.manage",
      "provision-user",
      "--email",
      `forecast-${randomUUID()}@example.test`,
    ],
    { cwd: "../..", encoding: "utf8" },
  ).trim();
}
async function signIn(page: Page, token: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}
function daily(count: number) {
  const rows = ["day,amount"];
  for (let index = 0; index < count; index += 1) {
    const day = new Date(Date.UTC(2024, 0, index + 1))
      .toISOString()
      .slice(0, 10);
    rows.push(`${day},${Math.floor((index + 1) / 10)}.${(index + 1) % 10}`);
  }
  return Buffer.from(rows.join("\n") + "\n");
}
async function upload(page: Page, count: number, existing = false) {
  if (existing) {
    await page
      .getByRole("navigation", { name: "Workspace navigation" })
      .getByRole("button", { name: "Data library", exact: true })
      .click();
    const options = page.locator(".uploadOptions").filter({
      hasText: "Add context or choose where to save",
    });
    if (
      !(await options.evaluate(
        (element) => (element as HTMLDetailsElement).open,
      ))
    )
      await options.locator("summary").click();
    await page
      .getByRole("combobox", { name: "Save this file", exact: true })
      .selectOption("existing");
  }
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: `daily-${count}.csv`,
    mimeType: "text/csv",
    buffer: daily(count),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  await expect(page.getByLabel("Analysis focus")).toBeVisible();
}
async function review(page: Page) {
  await page
    .getByRole("button", { name: "Review data meanings", exact: true })
    .click();
  const meanings = page.getByRole("region", {
    name: "Data understanding",
    exact: true,
  });
  await meanings.getByLabel("One row represents").selectOption("record");
  await meanings.getByLabel("Column to review").selectOption("amount");
  await meanings.getByLabel("Currency code").fill("PKR");
  await meanings
    .getByRole("button", { name: "Confirm business definitions", exact: true })
    .click();
  await expect(meanings.getByText("confirmed", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Back to overview", exact: true }).click();
  await selectAnalysisFocus(page, "predictive");
  await page.getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name: "Forecasts", exact: true }).click();
  const advanced = page.locator("details.forecastAdvanced");
  await expect(advanced).toBeVisible();
  if (!(await advanced.evaluate((element) => (element as HTMLDetailsElement).open)))
    await advanced.locator("summary.forecastAdvancedSummary").click();
}

test("basic forecasts retain exact evidence, compare later actuals and expose authorized audit history", async ({
  page,
}) => {
  test.setTimeout(150_000);
  const token = session();
  await signIn(page, token);
  await upload(page, 40);
  await page.getByRole("combobox", { name: "Analysis focus", exact: true }).click();
  await expect(page.getByRole("option", { name: /^Prescriptive ·/ })).toBeEnabled();
  await page.keyboard.press("Escape");
  await selectAnalysisFocus(page, "predictive");
  await expect(
    page.getByRole("heading", { name: "Review meanings before forecasting" }),
  ).toBeVisible();
  await review(page);
  await page
    .getByRole("combobox", { name: "Period", exact: true })
    .selectOption("daily");
  await expect(
    page.getByRole("button", { name: "Create forecast", exact: true }),
  ).toBeDisabled();
  await page
    .getByLabel(
      "I confirm the source covers every complete period in this range.",
    )
    .check();
  const createResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/uploads\/[^/]+\/forecasts$/.test(new URL(response.url()).pathname),
  );
  await page
    .getByRole("button", { name: "Create forecast", exact: true })
    .click();
  const response = await createResponse;
  expect(response.status()).toBe(201);
  const run = await response.json();
  expect(run.result.method.id).toBe("linear_trend");
  expect(run.result.predictions[0].estimate).toMatch(/^4\.10*$/);
  const result = page.getByRole("article", {
    name: "Forecast result: amount forecast",
    exact: true,
  });
  await expect(result).toContainText("Estimate, not an observed result");
  await expect(result.getByRole("heading", { name: "Held-out backtest accuracy", exact: true })).toBeHidden();
  await result.getByText("How accurate was this forecast?", { exact: true }).click();
  await expect(result.getByRole("heading", { name: "Held-out backtest accuracy", exact: true })).toBeVisible();
  await result.getByText("How accurate was this forecast?", { exact: true }).click();
  await expect(result).toContainText("Last-value baseline MAE:");
  await expect(result).toContainText("no guaranteed coverage");
  await expect(result.locator(".verifiedBadge")).toHaveCount(0);
  await result
    .getByLabel("Inspect a forecast period")
    .selectOption("2024-02-10");
  await expect(result.getByRole("status").first()).toContainText(
    run.result.predictions[0].estimate,
  );
  const plot = result.getByRole("group", { name: "Forecast chart. Use left and right arrow keys to inspect periods.", exact: true });
  await plot.focus();
  await page.keyboard.press("ArrowRight");
  await expect(result.getByRole("status").first()).toContainText(run.result.predictions[1].period);
  await result.getByRole("button", { name: "Inspect previous period", exact: true }).click();
  await expect(result.getByRole("status").first()).toContainText(run.result.predictions[0].period);
  await result.locator(".forecastActual").first().hover();
  await expect(result.getByRole("status").first()).toContainText(run.result.history[0].period);
  await result.getByRole("button", { name: "Inspect next period", exact: true }).click();
  await expect(result.getByRole("status").first()).toContainText(run.result.predictions[1].period);
  await result.locator(".forecastEstimate").last().hover();
  await expect(result.getByRole("status").first()).toContainText(run.result.predictions.at(-1).period);
  await expect(result.locator(".forecastChart polyline, .forecastChart path")).toHaveCount(0);
  await result
    .getByText("Method, backtest and source evidence", { exact: true })
    .click();
  await expect(result).toContainText(run.evidence.query_ids[0]);
  await expect(result).toContainText(run.revision_id);
  await result.getByText("Method, backtest and source evidence", { exact: true }).click();
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    expect(await result.locator(".forecastChart").evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    await expect(result.locator(".forecastEstimate").first()).toHaveCSS("animation-name", "none");
    await result.screenshot({
      path: `../../data/phase4c/forecast-${width}.png`,
    });
  }
  for (const viewport of [{ width: 375, height: 812 }, { width: 844, height: 390 }]) {
    await page.setViewportSize(viewport);
    await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
    expect(await result.locator(".forecastChart").evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    await expect(result.getByLabel("Inspect a forecast period")).toBeVisible();
    await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await upload(page, 42, true);
  await selectAnalysisFocus(page, "predictive");
  await review(page);
  await page
    .getByRole("combobox", { name: "Saved forecast", exact: true })
    .selectOption(run.id);
  await page
    .getByRole("button", { name: "Open saved forecast", exact: true })
    .click();
  await expect(result).toContainText(run.evidence.query_ids[0]);
  const comparison = page.getByRole("region", {
    name: "Compare later actual data",
    exact: true,
  });
  await comparison.getByLabel("Actual coverage start").fill("2024-02-10");
  await comparison.getByLabel("Actual coverage end").fill("2024-02-11");
  await comparison
    .getByLabel(
      "I confirm this source completely covers the declared actual periods.",
    )
    .check();
  const comparedResponse = page.waitForResponse(
    (item) =>
      item.request().method() === "POST" &&
      item.url().endsWith(`/${run.id}/compare`),
  );
  await comparison
    .getByRole("button", { name: "Compare actual data", exact: true })
    .click();
  const compared = await comparedResponse;
  expect(compared.status()).toBe(201);
  const actuals = await compared.json();
  expect(actuals.result.observed_count).toBe(2);
  expect(actuals.result.pending_count).toBe(1);
  expect(actuals.result.rows[0].actual).toBe("4.100000000000");
  await expect(result).toContainText(
    "2 observed periods · 1 awaiting complete actual data",
  );
  await expect(result).toContainText("Accuracy against later actual data");
  await expect(result).toContainText("4.100000000000");
  const sourceUrl = new URL(response.url());
  const datasetRoot = sourceUrl.pathname.split("/uploads/")[0];
  const reopened = await page.request.get(
    `${sourceUrl.origin}${datasetRoot}/forecasts/${run.id}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  expect(reopened.ok()).toBe(true);
  expect((await reopened.json()).result).toEqual(run.result);
  await page.reload();
  await signIn(page, token);
  await page
    .getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name: "Forecasts", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Saved forecast", exact: true })
    .selectOption(run.id);
  await page
    .getByRole("button", { name: "Open saved forecast", exact: true })
    .click();
  await page.getByText("Saved actual comparisons (1)", { exact: true }).click();
  await page
    .getByRole("button", { name: "Open comparison", exact: true })
    .click();
  await expect(result).toContainText(
    "2 observed periods · 1 awaiting complete actual data",
  );
  await navigateTo(page, "Audit history");
  const audit = page.getByRole("region", {
    name: "Workspace audit history",
    exact: true,
  });
  await audit.getByLabel("Search audit history", { exact: true }).fill(run.id);
  await audit
    .getByRole("button", { name: "Apply audit filters", exact: true })
    .click();
  await expect(
    audit.getByRole("region", { name: "Audit events", exact: true }),
  ).toContainText(run.id);
  await audit
    .getByLabel("Search audit history", { exact: true })
    .fill("nothing-matches-this-forecast");
  await audit
    .getByRole("button", { name: "Apply audit filters", exact: true })
    .click();
  await expect(audit).toContainText("No visible events match these filters.");
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
  }
});

test("analysis focus stays optional and insufficient history gives a useful refusal", async ({
  page,
}) => {
  await signIn(page, session());
  await upload(page, 10);
  let forecasts = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/forecasts$/.test(new URL(request.url()).pathname)
    )
      forecasts += 1;
  });
  await selectAnalysisFocus(page, "all");
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Explore basic forecasts", exact: true })
    .click();
  expect(forecasts).toBe(0);
  await review(page);
  await page
    .getByRole("combobox", { name: "Period", exact: true })
    .selectOption("daily");
  await page
    .getByLabel(
      "I confirm the source covers every complete period in this range.",
    )
    .check();
  await page
    .getByRole("button", { name: "Create forecast", exact: true })
    .click();
  await expect(
    page.locator(".forecastWorkspace").getByRole("alert"),
  ).toContainText("28");
  await expect(
    page.getByRole("article", { name: /Forecast result:/ }),
  ).toHaveCount(0);
  expect(forecasts).toBe(1);
  await selectAnalysisFocus(page, "descriptive");
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
});
