/* Use case: Verifies basic forecasts and audit history in the real browser workflow.
What it does: Covers review, coverage declarations, exact estimates, saved evidence, later actuals and narrow-screen access without mocked results. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

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
  await page.getByLabel("Analysis focus").selectOption("predictive");
}

test("basic forecasts retain exact evidence, compare later actuals and expose authorized audit history", async ({
  page,
}) => {
  test.setTimeout(150_000);
  const token = session();
  await signIn(page, token);
  await upload(page, 40);
  await expect(
    page.getByLabel("Analysis focus").locator('option[value="prescriptive"]'),
  ).toHaveJSProperty("disabled", true);
  await page.getByLabel("Analysis focus").selectOption("predictive");
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
  await expect(result).toContainText("Held-out backtest accuracy");
  await expect(result).toContainText("Last-value baseline MAE:");
  await expect(result).toContainText("no guaranteed coverage");
  await expect(result.locator(".verifiedBadge")).toHaveCount(0);
  await result
    .getByLabel("Inspect a forecast period")
    .selectOption("2024-02-10");
  await expect(result.getByRole("status").first()).toContainText(
    run.result.predictions[0].estimate,
  );
  await result
    .getByText("Method, backtest and source evidence", { exact: true })
    .click();
  await expect(result).toContainText(run.evidence.query_ids[0]);
  await expect(result).toContainText(run.revision_id);
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await result.screenshot({
      path: `../../data/phase4c/forecast-${width}.png`,
    });
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await upload(page, 42, true);
  await page.getByLabel("Analysis focus").selectOption("predictive");
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
  await page
    .getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name: "Audit history", exact: true })
    .click();
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
  await page.getByLabel("Analysis focus").selectOption("all");
  await expect(page.getByLabel("Your question")).toBeVisible();
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
  await page.getByLabel("Analysis focus").selectOption("descriptive");
  await expect(page.getByLabel("Your question")).toBeVisible();
});
