/* Use case: Verifies conditional scenarios with real numerical source receipts.
What it does: Exercises exact comparisons, immutable succession and narrow layouts. */
import { execFileSync } from "node:child_process";
import { finishInitialReview } from "./workspace-helpers";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("private what-if comparisons reproduce original evidence and preserve predecessors", async ({ page }) => {
  test.setTimeout(150000);
  page.setDefaultTimeout(30000);
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `scenarios-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const errors: string[] = []; page.on("pageerror", e => errors.push(e.message));
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "scenario.csv", mimeType: "text/csv", buffer: Buffer.from("city,amount,cost\nKarachi,0.10,0.05\nLahore,0.20,0.15\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  await expect(page.getByLabel("Analysis focus")).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await nav.getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await page.getByRole("button", { name: "Review data meanings", exact: true }).click();
  const meanings = page.getByRole("region", { name: "Data understanding", exact: true });
  await meanings.getByLabel("One row represents").selectOption("record");
  await meanings.getByLabel("Column to review").selectOption("amount");
  await meanings.getByLabel("Currency code").fill("PKR");
  await meanings.getByRole("button", { name: "Confirm business definitions", exact: true }).click();
  await expect(meanings.getByText("confirmed", { exact: true })).toBeVisible();
  await nav.getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await page.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption("scenarios");
  const panel = page.getByRole("region", { name: "Scenario comparisons", exact: true });
  await panel.getByLabel("Comparison name", { exact: true }).fill("Conditional ten percent");
  await panel.getByRole("combobox", { name: "Scenario measure", exact: true }).selectOption("amount");
  await panel.getByRole("checkbox", { name: "I confirm these are hypothetical", exact: false }).check();
  await panel.getByRole("button", { name: "Calculate and save comparison", exact: true }).click();
  const result = panel.getByRole("region", { name: "Saved scenario result", exact: true });
  await expect(result).toContainText("0.3300000000000");
  await panel.getByRole("button", { name: "Replay comparison evidence", exact: true }).click();
  await expect(panel).toContainText("Baseline, coverage and alternatives reproduced");
  await panel.getByRole("button", { name: "Create successor comparison", exact: true }).click();
  await panel.getByLabel("Assumed value 1", { exact: true }).fill("20");
  await panel.getByRole("checkbox", { name: "I confirm these are hypothetical", exact: false }).check();
  await panel.getByRole("button", { name: "Calculate and save comparison", exact: true }).click();
  await expect(result).toContainText("0.3600000000000");
  await panel.getByRole("button", { name: "Open prior comparison", exact: true }).click();
  await expect(result).toContainText("0.3300000000000");
  await expect(result.getByRole("heading", { name: "Conditional ten percent", exact: true })).toBeVisible();
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await expect(result).toBeVisible();
  }
  expect(errors).toEqual([]);
});
