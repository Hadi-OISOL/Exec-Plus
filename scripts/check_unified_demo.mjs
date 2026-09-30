/* Use case: Verifies unified evidence and catalog discovery on the private VPS demo.
What it does: Uses fictional data and existing private sessions without printing credentials. */

import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { chromium, expect as baseExpect } from "@playwright/test";

const expect = baseExpect.configure({ timeout: 110_000 });
const [sessionsPath, outputPath] = process.argv.slice(2);
if (!sessionsPath || !outputPath) throw new Error("Pass private session and report paths");
const sessions = JSON.parse(await readFile(sessionsPath, "utf8"));
assert.equal(sessions.scope, "private-fictional-demo");
const account = sessions.accounts[0];
const results = [];
let stage = "prepare_fictional_sources";
let browser;
async function api(path, options = {}) {
  const response = await fetch(`http://localhost:18401${path}`, {
    signal: AbortSignal.timeout(120_000), ...options,
    headers: { Authorization: `Bearer ${account.token}`, "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) throw new Error(`Private demo API returned ${response.status}`);
  return response.json();
}
const post = (body) => ({ method: "POST", body: JSON.stringify(body) });
function passed() { results.push({ stage, passed: true }); console.log(JSON.stringify(results.at(-1))); }
try {
  const workspace = await api("/workspaces", post({ name: "Fictional unified walkthrough", seat_limit: 8 }));
  const dataset = await api(`/workspaces/${workspace.id}/datasets`, post({ name: "Fictional city receipts" }));
  const prefix = `/workspaces/${workspace.id}/datasets/${dataset.id}`;
  const upload = await api(`${prefix}/uploads?filename=fictional-receipts.csv`, {
    method: "POST", headers: { "Content-Type": "text/csv" },
    body: "city,revenue\nKarachi,0.10\nLahore,0.20\n",
  });
  const root = `${prefix}/uploads/${upload.id}`;
  await api(`${prefix}/documents?name=fictional-refund.md&shared=true`, {
    method: "POST", headers: { "Content-Type": "text/markdown" },
    body: "Fictional policy: The customer support lead approves standard refunds. The stated ceiling is 100 PKR.",
  });
  passed();
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(110_000);
  async function signIn() {
    await page.goto("http://localhost:18400/workspace");
    await page.getByLabel("Session token").fill(account.token);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByText(`Signed in as ${account.email}`)).toBeVisible();
    await page.getByLabel("Current workspace").selectOption(workspace.id);
    await page.getByLabel("Dataset", { exact: true }).selectOption(dataset.id);
  }
  await signIn();
  stage = "live_mixed_answer_and_citation";
  await page.getByLabel("Your question").fill("What is total revenue, and who approves standard refunds according to the document?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".answerCard .kpiValue")).toHaveText("0.3");
  await expect(page.getByRole("region", { name: "Document evidence" })).toContainText("customer support lead");
  await page.getByRole("button", { name: "Open conversation citation" }).click();
  await expect(page.getByText("Verified conversation source passage", { exact: true })).toBeVisible();
  passed();
  stage = "private_history_reopen";
  await page.reload(); await signIn();
  await page.getByText("Private conversation history", { exact: true }).click();
  await page.getByLabel("Saved conversation").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Open conversation", exact: true }).click();
  await page.getByRole("button", { name: "Load saved answer", exact: true }).click();
  await expect(page.locator(".answerCard .kpiValue")).toHaveText("0.3");
  await expect(page.getByRole("region", { name: "Document evidence" })).toContainText("customer support lead");
  passed();
  stage = "retry_reuses_execution";
  const thread = await api(`${root}/threads`, post({}));
  const request = { question: "Total revenue and refund approver?", request_id: randomUUID() };
  const original = await api(`/workspaces/${workspace.id}/threads/${thread.id}/ask`, post(request));
  assert.equal(original.turn.status, "complete");
  const repeated = await api(`/workspaces/${workspace.id}/threads/${thread.id}/ask`, post(request));
  assert.equal(repeated.turn.id, original.turn.id);
  assert.equal(repeated.answer.data.lineage.query_id, original.answer.data.lineage.query_id);
  passed();
  stage = "catalog_and_mobile";
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Data library", exact: true }).click();
  const catalog = page.getByRole("region", { name: "Find data by meaning" });
  await catalog.getByLabel("Search your catalog").fill("refund");
  await catalog.getByRole("button", { name: "Find data", exact: true }).click();
  await expect(catalog).toContainText("fictional-refund.md");
  await catalog.getByRole("button", { name: "Open Fictional city receipts", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  passed();
} catch (error) {
  results.push({ stage, passed: false, error: error?.name || "Error" });
  console.error(JSON.stringify(results.at(-1)));
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  await writeFile(outputPath, JSON.stringify({ scope: "private-fictional-demo", results }, null, 2));
}
