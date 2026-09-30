/* Use case: Checks the live hybrid conversation and interactive private-demo dashboard.
What it does: Uses only fictional city data and records sanitized outcomes and screenshots. */

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { chromium, expect as baseExpect } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 90_000 });
const [sessionPath, outputDirectory] = process.argv.slice(2);
if (!sessionPath || !outputDirectory) throw new Error("Pass private session path and output directory");
const sessions = JSON.parse(await readFile(sessionPath, "utf8"));
if (sessions.scope !== "private-fictional-demo") throw new Error("Only fictional demo sessions are allowed");
const account = sessions.accounts[0];
async function api(path, options = {}) {
  const response = await fetch(`http://localhost:18401${path}`, { signal: AbortSignal.timeout(20000), ...options, headers: { Authorization: `Bearer ${account.token}`, "Content-Type": "application/json" } });
  if (!response.ok) throw new Error(`Demo API status ${response.status}`);
  return response.json();
}
const workspace = `/workspaces/${sessions.workspace_id}`;
let sample;
for (const dataset of await api(`${workspace}/datasets`)) {
  const uploads = await api(`${workspace}/datasets/${dataset.id}/uploads`);
  sample = uploads.find((upload) => upload.sample_id === "cities-v1");
  if (sample) { sample.dataset_id = dataset.id; break; }
}
if (!sample) sample = await api(`${workspace}/samples/cities-v1`, { method: "POST" });
await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1512, height: 1050 } });
const page = await context.newPage();
page.setDefaultTimeout(90_000);
const results = [];
const runtimeErrors = [];
page.on("pageerror", () => runtimeErrors.push("browser-runtime-error"));
let stage = "sign_in";
try {
  await page.goto("http://localhost:18400/workspace");
  await page.getByLabel("Session token").fill(account.token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText(`Signed in as ${account.email}`)).toBeVisible();
  await page.getByLabel("Dataset", { exact: true }).selectOption(sample.dataset_id);
  await page.getByLabel("Profile upload").selectOption(sample.id);
  const dashboard = page.getByRole("region", { name: "Dataset dashboard" });
  await expect(dashboard.locator(".kpiValue")).not.toHaveCount(0);
  stage = "diagram_and_chart";
  await page.getByText("Explore your column map", { exact: false }).click();
  await expect(page.getByRole("region", { name: "Data journey" }).getByRole("button", { name: "city text" })).toBeVisible();
  await dashboard.locator(".chartPoint").first().focus();
  await expect(dashboard.locator(".chartReadout strong")).not.toBeEmpty();
  results.push({ stage, passed: true });
  console.log(JSON.stringify({ stage, passed: true }));
  stage = "city_records";
  await page.getByLabel("Your question").fill("Show all records of Karachi");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".recordPagination")).toContainText("8 matching");
  await expect(page.locator(".recordResult table")).not.toContainText("Lahore");
  await page.getByText("How this answer was verified", { exact: true }).last().click();
  await expect(page.locator(".answerEvidence").last()).toContainText("selection:qwen3:4b -> hosted:deepseek-v4-pro");
  results.push({ stage, passed: true });
  console.log(JSON.stringify({ stage, passed: true }));
  stage = "follow_up_exact_total";
  await page.getByLabel("Your question").fill("What is their total revenue?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".answerCard .kpiValue").last()).toHaveText("11502");
  results.push({ stage, passed: true });
  console.log(JSON.stringify({ stage, passed: true }));
  stage = "conversation_survives_navigation";
  const navigation = page.getByRole("navigation", { name: "Workspace navigation" });
  await navigation.getByRole("button", { name: "Data library", exact: true }).click();
  await navigation.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(page.locator(".answerCard .kpiValue").last()).toHaveText("11502");
  results.push({ stage, passed: true });
  console.log(JSON.stringify({ stage, passed: true }));
  await page.getByText("How this answer was verified", { exact: true }).first().click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${outputDirectory}/desktop.png`, fullPage: true });
  stage = "new_conversation_and_pagination";
  await page.getByRole("button", { name: "New conversation", exact: true }).click();
  await expect(page.locator(".conversationTurn")).toHaveCount(0);
  await page.getByLabel("Your question").fill("Show the first 20 records");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".recordPagination")).toContainText("1–10 of 20 returned · 24 matching");
  await expect(page.locator(".resultLimit")).toContainText("first 20 records");
  await page.getByRole("button", { name: "Next records", exact: true }).click();
  await expect(page.locator(".recordPagination")).toContainText("11–20");
  results.push({ stage, passed: true });
  console.log(JSON.stringify({ stage, passed: true }));
  stage = "mobile_reduced_motion";
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await dashboard.locator(".barFill").first().evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  await page.screenshot({ path: `${outputDirectory}/mobile.png`, fullPage: true });
  expect(runtimeErrors).toHaveLength(0);
  results.push({ stage, passed: true });
  console.log(JSON.stringify({ stage, passed: true }));
} catch (error) {
  results.push({ stage, passed: false, reason: error.name ?? "check_failed" });
  await page.screenshot({ path: `${outputDirectory}/failure.png`, fullPage: true });
} finally { await browser.close(); }
const report = { scope: "private-fictional-explorer", passed: results.filter((item) => item.passed).length, total: 6, results };
await writeFile(`${outputDirectory}/report.json`, JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report));
process.exitCode = report.passed === report.total ? 0 : 1;
