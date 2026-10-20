/* Use case: Exercises explicit grouped relationships and allocation selection rules.
What it does: Verifies actual computed evidence, saved replay, responsive controls and keyboard access. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { finishInitialReview, openAnalysisAdvanced } from "./workspace-helpers";

test.use({ actionTimeout: 20_000 });

function session() {
  return execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `depth-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
}
async function upload(page: Page, token: string, csv: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "explicit-comparisons.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
}
async function confirm(page: Page, metrics: string[]) {
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await nav.getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await openAnalysisAdvanced(page);
  await page.getByRole("button", { name: "Review data meanings", exact: true }).click();
  const meanings = page.getByRole("region", { name: "Data understanding", exact: true });
  await meanings.getByLabel("One row represents").selectOption("record");
  for (const name of metrics) {
    await meanings.getByLabel("Column to review").selectOption(name);
    await meanings.getByLabel("Unit of measurement", { exact: true }).fill("units");
  }
  await meanings.getByRole("button", { name: "Confirm business definitions", exact: true }).click();
  await expect(meanings.getByText("confirmed", { exact: true })).toBeVisible();
  await nav.getByRole("button", { name: "Overview", exact: true }).click();
}

test("group comparisons explain a reversal on the same rows and privately replay exact evidence", async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const token = session();
  const csv = "region,amount,response\n" + Array.from({ length: 20 }, (_, i) => `North,${i + 1},${101 + i}\nSouth,${101 + i},${i + 1}\n`).join("") + "Small,3,5\nSmall,4,6\nSmall,5,7\nNorth,,8\n,9,10\n";
  await upload(page, token, csv);
  await confirm(page, ["amount", "response"]);
  const setup = page.locator(".groupComparisonSetup");
  await expect(setup).not.toHaveAttribute("open", "");
  await setup.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(setup.getByRole("button", { name: "Compare these groups", exact: true })).toBeDisabled();
  await setup.getByRole("combobox", { name: "First measure", exact: true }).selectOption("amount");
  await expect(setup.getByRole("combobox", { name: "Second measure", exact: true }).locator('option[value="amount"]')).toHaveJSProperty("disabled", true);
  await setup.getByRole("combobox", { name: "Second measure", exact: true }).selectOption("response");
  await setup.getByRole("combobox", { name: "Group by", exact: true }).selectOption("region");
  const answerResponse = page.waitForResponse(response => /\/jobs\/[^/]+\/result$/.test(response.url()));
  await setup.getByRole("button", { name: "Compare these groups", exact: true }).click();
  const body = await (await answerResponse).json();
  expect(body.answer.patterns.version).toBe("group-relationship-comparison-v1");
  const computed = body.answer.patterns;
  expect(computed.coverage).toMatchObject({ covered_rows: 40, excluded_rows: 5, eligible_groups: 2, sparse_group_rows: 3, missing_category_rows: 1, missing_pair_rows: 1 });
  expect(computed.comparisons.pearson.reversal_groups).toEqual(["North", "South"]);
  const result = page.getByRole("region", { name: "Relationships within groups", exact: true });
  await expect(result).toContainText("The combined view can hide a different direction");
  await expect(result).toContainText(computed.pooled.statistics.pearson);
  await expect(result).toContainText("They do not show that one measure causes the other");
  await expect(result).toContainText("Small: Fewer than 20 complete pairs");
  await result.getByText("See the plotted records and exact values", { exact: true }).click();
  await expect(result.getByRole("table", { name: "Returned chart values", exact: true })).toBeVisible();
  await expect(result.getByRole("table", { name: "Returned chart values", exact: true }).locator("tbody tr")).toHaveCount(40);
  await result.getByText("See the plotted records and exact values", { exact: true }).click();
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await result.locator(".patternOverview").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `../../data/verification/2026-10-16/analytics-depth/group-result-${width}.png` });
    await result.locator(".relationshipPooled").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `../../data/verification/2026-10-16/analytics-depth/group-pooled-${width}.png` });
    await result.locator(".relationshipGroup").first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: `../../data/verification/2026-10-16/analytics-depth/group-within-${width}.png` });
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(await result.evaluate(element => getComputedStyle(element).animationName)).toBe("none");
  await result.getByText("See the plotted records and exact values", { exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await result.locator(".patternScatter").screenshot({ path: "../../data/verification/2026-10-16/analytics-depth/group-plot-320.png" });
  await result.getByText("See the plotted records and exact values", { exact: true }).click();
  await result.getByText("Coverage, method and source evidence", { exact: true }).click();
  await expect(result.getByRole("table", { name: "Every group and its returned scores", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await result.getByText("Coverage, method and source evidence", { exact: true }).click();
  await page.getByRole("button", { name: "New conversation", exact: true }).click();
  await page.locator(".conversationHistory summary").click();
  await page.getByRole("button", { name: "Refresh history", exact: true }).click();
  await expect(page.getByLabel("Saved conversation").locator("option")).toHaveCount(2);
  await page.getByLabel("Saved conversation").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Open conversation", exact: true }).click();
  await page.getByRole("button", { name: "Load saved answer", exact: true }).click();
  await expect(result).toContainText(computed.pooled.statistics.pearson);
  await expect(result).toContainText("Straight-line direction reverses here");
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Data library", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "new-source.csv", mimeType: "text/csv", buffer: Buffer.from("category,value\nX,1\nY,2\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await page.locator(".groupComparisonSetup summary").click();
  await expect(page.locator(".groupComparisonSetup")).toContainText("Confirm two numerical measures");
  await expect(page.locator(".groupComparisonSetup").getByRole("combobox")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("selection rules constrain the allocation, reject self-rules and retain rules on replay", async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const token = session();
  await upload(page, token, "candidate,cost,benefit,hours\nA,3,10,2\nB,2,2,1\nC,3,9,1\n");
  await confirm(page, ["cost", "benefit", "hours"]);
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await nav.getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await openAnalysisAdvanced(page);
  const panel = page.getByRole("region", { name: "Anomalies and decisions", exact: true });
  await panel.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption("allocations");
  await panel.getByLabel("Analysis name", { exact: true }).fill("Choices with prerequisites");
  await panel.getByRole("combobox", { name: "Candidate identifier", exact: true }).selectOption("candidate");
  await panel.getByRole("combobox", { name: "Per-unit cost", exact: true }).selectOption("cost");
  await panel.getByRole("combobox", { name: "Per-unit benefit", exact: true }).selectOption("benefit");
  await panel.getByRole("combobox", { name: "Additional resource limit", exact: true }).selectOption("hours");
  await panel.getByLabel("Total additional resource available", { exact: true }).fill("3");
  await panel.getByLabel("Total budget", { exact: true }).fill("6");
  await panel.getByLabel("Budget quantum", { exact: true }).fill("1");
  const rules = panel.locator(".selectionRulesSetup");
  await rules.locator("summary").focus();
  await page.keyboard.press("Enter");
  await rules.getByRole("button", { name: "Add a prerequisite", exact: true }).click();
  await rules.getByLabel("Choosing candidate 1", { exact: true }).fill("A");
  await rules.getByLabel("Requires candidate 1", { exact: true }).fill("A");
  await rules.getByRole("button", { name: "Add an exclusion", exact: true }).click();
  await rules.getByLabel("First excluded candidate 1", { exact: true }).fill("A");
  await rules.getByLabel("Second excluded candidate 1", { exact: true }).fill("C");
  await panel.getByRole("checkbox", { name: "I confirm fixed per-unit costs", exact: false }).check();
  const rejected = page.waitForResponse(response => response.url().endsWith("/decision-analysis/allocations") && response.request().method() === "POST");
  await panel.getByRole("button", { name: "Calculate and save privately", exact: true }).click();
  expect((await rejected).status()).toBe(422);
  await expect(panel.getByRole("alert")).toBeVisible();
  await expect(panel.getByRole("region", { name: "Saved analysis result", exact: true })).toHaveCount(0);
  await rules.getByLabel("Requires candidate 1", { exact: true }).fill("B");
  await expect(panel.getByRole("checkbox", { name: "I confirm fixed per-unit costs", exact: false })).not.toBeChecked();
  await panel.getByRole("checkbox", { name: "I confirm fixed per-unit costs", exact: false }).check();
  const response = page.waitForResponse(value => value.url().endsWith("/decision-analysis/allocations") && value.request().method() === "POST");
  await panel.getByRole("button", { name: "Calculate and save privately", exact: true }).click();
  const saved = await response;
  expect(saved.status()).toBe(201);
  const body = await saved.json();
  expect(body.run.method_version).toBe("selection-rules-enumeration-v1");
  expect(Number(body.run.result.benefit)).toBe(12);
  expect(Number(body.run.result.cost)).toBe(5);
  expect(body.run.result.allocations.map((item: { candidate: string; quantity: number }) => [item.candidate, item.quantity])).toEqual([["A", 1], ["B", 1], ["C", 0]]);
  const result = panel.getByRole("region", { name: "Saved analysis result", exact: true });
  const savedRules = result.getByRole("region", { name: "Saved selection rules", exact: true });
  await expect(savedRules).toContainText("A requires at least one B.");
  await expect(savedRules).toContainText("A and C cannot both be selected.");
  await expect(result).toContainText(body.run.result.benefit);
  await panel.getByRole("button", { name: "Replay original evidence", exact: true }).click();
  await expect(panel).toContainText("Original source query and analysis reproduced.");
  await expect(savedRules).toContainText("A requires at least one B.");
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await savedRules.screenshot({ path: `../../data/verification/2026-10-16/analytics-depth/selection-rules-${width}.png` });
  }
  await page.reload();
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await nav.getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await openAnalysisAdvanced(page);
  await panel.getByRole("button", { name: "Choices with prerequisites · Allocation", exact: true }).click();
  await expect(savedRules).toContainText("A and C cannot both be selected.");
  await expect(result).toContainText(body.run.result.benefit);
  expect(errors).toEqual([]);
});
