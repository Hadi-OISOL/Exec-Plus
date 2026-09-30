/* Use case: Verifies the deployed private demo in eight independent browser sessions.
What it does: Exercises real sign-in, model answers and source citations without saving tokens. */

import { readFile, writeFile } from "node:fs/promises";
import { chromium, expect as baseExpect } from "@playwright/test";

const expect = baseExpect.configure({ timeout: 60_000 });

const [sessionsPath, outputPath] = process.argv.slice(2);
if (!sessionsPath || !outputPath) throw new Error("Pass private session and report paths");
const sessions = JSON.parse(await readFile(sessionsPath, "utf8"));
if (sessions.scope !== "private-fictional-demo" || sessions.accounts.length !== 8) {
  throw new Error("Expected the eight-account fictional demo file");
}
const browser = await chromium.launch({ headless: true });
let results;
try {
  results = await Promise.all(sessions.accounts.map(async (account, index) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    page.setDefaultTimeout(60_000);
    let stage = "sign_in";
    try {
      await page.goto("http://localhost:18400/workspace");
      await page.getByLabel("Session token").fill(account.token);
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await expect(page.getByText(`Signed in as ${account.email}`)).toBeVisible();
      await page.getByLabel("Current workspace").selectOption(sessions.workspace_id);
      await page.getByLabel("Dataset", { exact: true }).selectOption(sessions.dataset_id);
      await page.getByLabel("Profile upload").selectOption(sessions.upload_id);
      stage = "question";
      await page.getByLabel("Your question").fill("What is total revenue?");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      await expect(page.locator(".answerCard .kpiValue")).toHaveText(/^10000(?:\.0+)?$/);
      stage = "citation";
      await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Documents", exact: true }).click();
      await page.getByLabel("Search documents").fill("Who approves standard refunds?");
      await page.getByRole("button", { name: "Search knowledge", exact: true }).click();
      await page.getByRole("button", { name: "Open citation", exact: true }).first().click();
      await expect(page.getByText("Verified source passage", { exact: true })).toBeVisible();
      await expect(page.locator("details[open]").filter({ hasText: "Verified source passage" }))
        .toContainText("The customer support lead approves standard refunds.");
      return { user: index + 1, passed: true, stage: "complete" };
    } catch {
      return { user: index + 1, passed: false, stage };
    } finally {
      await context.close();
    }
  }));
} finally {
  await browser.close();
}
const report = {
  scope: "private-fictional-demo", concurrent_browsers: 8,
  passed: results.filter(item => item.passed).length, total: results.length, results,
};
await writeFile(outputPath, JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report));
process.exitCode = report.passed === report.total ? 0 : 1;
