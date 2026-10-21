/* Use case: Exercises grouped findings, resource limits and compound scenarios in the browser.
What it does: Verifies real calculations, replay, declared assumptions and mobile layouts. */
import { execFileSync } from "node:child_process";
import { finishInitialReview, openAnalysisAdvanced } from "./workspace-helpers";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("extended analysis preserves group coverage, resource limits and compound evidence", async ({ page }) => {
  test.setTimeout(180000);
  page.setDefaultTimeout(30000);
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `extensions-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
  const csv = "city,segment,amount,cost,hours\n" + Array.from({ length: 8 }, (_, i) => `A${i},Regular,10,1,1\n`).join("") + "Z,Regular,100,1,3\nSparse,Small,20,1,2\n";
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "extension-demo.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  await expect(page.getByLabel("Analysis focus")).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await nav.getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await openAnalysisAdvanced(page);
  const panel = page.getByRole("region", { name: "Anomalies and decisions", exact: true });
  await panel.getByRole("button", { name: "Review data meanings", exact: true }).first().click();
  const meanings = page.getByRole("region", { name: "Data understanding", exact: true });
  await meanings.getByLabel("One row represents").selectOption("record");
  for (const name of ["amount", "cost"]) {
    await meanings.getByLabel("Column to review").selectOption(name);
    await meanings.getByLabel("Currency code").fill("PKR");
  }
  await meanings.getByLabel("Column to review").selectOption("hours");
  await meanings.getByLabel("Unit of measurement", { exact: true }).fill("hours");
  await meanings.getByRole("button", { name: "Confirm business definitions", exact: true }).click();
  await expect(meanings.getByText("confirmed", { exact: true })).toBeVisible();
  await nav.getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await openAnalysisAdvanced(page);
  await panel.getByRole("combobox", { name: "Measure to inspect", exact: true }).selectOption("amount");
  await panel.getByRole("combobox", { name: "Compare within group", exact: true }).selectOption("segment");
  await panel.getByRole("button", { name: "Calculate and save privately", exact: true }).click();
  const result = panel.getByRole("region", { name: "Saved analysis result", exact: true });
  await expect(result).toContainText("9 records evaluated; 1 excluded");
  await expect(result.getByRole("table", { name: "Group coverage" })).toContainText("insufficient support");
  await expect(result).toContainText("1 of 10 records flagged");
  await panel.getByRole("button", { name: "Replay original evidence", exact: true }).click();
  await expect(panel).toContainText("Original source query and analysis reproduced.");
  await panel.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption("allocations");
  await panel.getByRole("combobox", { name: "Candidate identifier", exact: true }).selectOption("city");
  await panel.getByRole("combobox", { name: "Per-unit cost", exact: true }).selectOption("cost");
  await panel.getByRole("combobox", { name: "Per-unit benefit", exact: true }).selectOption("amount");
  await panel.getByRole("combobox", { name: "Additional resource limit", exact: true }).selectOption("hours");
  await panel.getByLabel("Total additional resource available", { exact: true }).fill("1");
  await panel.getByLabel("Total budget", { exact: true }).fill("2");
  await panel.getByLabel("Budget quantum", { exact: true }).fill("1");
  await panel.getByRole("checkbox", { name: "I confirm fixed per-unit costs", exact: false }).check();
  const allocationResponse = page.waitForResponse(r => r.url().endsWith("/decision-analysis/allocations") && r.request().method() === "POST");
  await panel.getByRole("button", { name: "Calculate and save privately", exact: true }).click();
  const allocation = await allocationResponse;
  expect(allocation.status()).toBe(201);
  expect((await allocation.json()).run.result.benefit).toBe("10");
  await expect(result).toContainText("Additional resource used: 1; available: 1; remaining: 0");
  await panel.getByLabel("Review note", { exact: true }).fill("Confirmed one staff hour and two budget units.");
  await panel.getByRole("button", { name: "Approve recommendation", exact: true }).click();
  await expect(result).toContainText("approval applies to the current source");
  await panel.getByRole("button", { name: "Replay original evidence", exact: true }).click();
  await expect(panel).toContainText("Original source query and analysis reproduced.");
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await panel.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption("scenarios");
  const scenarios = page.getByRole("region", { name: "Scenario comparisons", exact: true });
  await scenarios.getByRole("combobox", { name: "Scenario measure", exact: true }).selectOption("amount");
  await scenarios.getByRole("combobox", { name: "Change type 1", exact: true }).selectOption("compound_percent");
  await scenarios.getByLabel("Driver name 1.1", { exact: true }).fill("Volume");
  await scenarios.getByLabel("Driver percent 1.1", { exact: true }).fill("10");
  await scenarios.getByLabel("Driver name 1.2", { exact: true }).fill("Price");
  await scenarios.getByLabel("Driver percent 1.2", { exact: true }).fill("20");
  await scenarios.getByRole("checkbox", { name: "I confirm these are hypothetical", exact: false }).check();
  const scenarioResponse = page.waitForResponse(r => r.url().endsWith("/decision-analysis/scenarios") && r.request().method() === "POST");
  await scenarios.getByRole("button", { name: "Calculate and save comparison", exact: true }).click();
  const comparison = await scenarioResponse;
  expect(comparison.status()).toBe(201);
  expect((await comparison.json()).run.result.alternatives[0].result).toBe("264.00");
  const savedScenario = scenarios.getByRole("region", { name: "Saved scenario result", exact: true });
  await expect(savedScenario).toContainText("Volume: 10% × Price: 20%");
  await scenarios.getByRole("button", { name: "Replay comparison evidence", exact: true }).click();
  await expect(scenarios).toContainText("Baseline, coverage and alternatives reproduced");
  await scenarios.getByRole("button", { name: "Create successor comparison", exact: true }).click();
  await expect(scenarios.getByLabel("Driver percent 1.1", { exact: true })).toHaveValue("10");
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, outside: [...document.querySelectorAll("body *")].filter(node => node.getBoundingClientRect().right > innerWidth + 1).map(node => ({ tag: node.tagName, className: node.className, right: node.getBoundingClientRect().right, text: node.textContent?.slice(0, 75) })).slice(0, 15) }));
    expect(layout.scroll <= width + 1, JSON.stringify(layout)).toBe(true);
  }
  expect(errors).toEqual([]);
});
