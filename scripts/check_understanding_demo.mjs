/* Use case: Verifies reviewed business meaning on the deployed private demo.
What it does: Uses fictional data, live planning and real browser controls without printing tokens. */

import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { chromium, expect as baseExpect } from "@playwright/test";

const expect = baseExpect.configure({ timeout: 90_000 });
const [sessionsPath, outputPath] = process.argv.slice(2);
if (!sessionsPath || !outputPath)
  throw new Error("Pass private sessions and report paths");
const sessions = JSON.parse(await readFile(sessionsPath, "utf8"));
assert.equal(sessions.scope, "private-fictional-demo");
const account = sessions.accounts[0];
const results = [];
let stage = "prepare_fictional_source";
let browser;
async function api(path, options = {}) {
  const response = await fetch(`http://localhost:18401${path}`, {
    signal: AbortSignal.timeout(120_000),
    ...options,
    headers: {
      Authorization: `Bearer ${account.token}`,
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!response.ok)
    throw new Error(`Private demo API returned ${response.status}`);
  return response.json();
}
const post = (body) => ({ method: "POST", body: JSON.stringify(body) });
function passed() {
  results.push({ stage, passed: true });
  console.log(JSON.stringify(results.at(-1)));
}

try {
  const workspace = await api(
    "/workspaces",
    post({ name: "Fictional definition walkthrough", seat_limit: 8 }),
  );
  const dataset = await api(
    `/workspaces/${workspace.id}/datasets`,
    post({ name: "Fictional paid orders" }),
  );
  const upload = await api(
    `/workspaces/${workspace.id}/datasets/${dataset.id}/uploads?filename=fictional-paid.csv`,
    {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: "custno,city,amount,status\n1001,Karachi,0.10,paid\n1002,Lahore,0.20,cancelled\n",
    },
  );
  const root = `/workspaces/${workspace.id}/datasets/${dataset.id}/uploads/${upload.id}`;
  const original = await api(
    `${root}/query`,
    post({ metric: "amount", aggregation: "sum" }),
  );
  assert.match(original.rows[0][0], /^0\.30*$/);
  passed();
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(90_000);
  stage = "confirm_in_browser";
  await page.goto("http://localhost:18400/workspace");
  await page.getByLabel("Session token").fill(account.token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText(`Signed in as ${account.email}`)).toBeVisible();
  await page.getByLabel("Current workspace").selectOption(workspace.id);
  await page.getByLabel("Dataset", { exact: true }).selectOption(dataset.id);
  await page.getByLabel("Profile upload").selectOption(upload.id);
  const meaning = page.getByRole("region", {
    name: "Data understanding",
    exact: true,
  });
  await meaning.getByLabel("One row represents").selectOption("order_item");
  await meaning
    .getByLabel("Dataset description")
    .fill("Fictional amounts; paid rows only.");
  await meaning.getByLabel("Column to review").selectOption("custno");
  await meaning.getByLabel("Column role").selectOption("identifier");
  await meaning.getByLabel("Column to review").selectOption("amount");
  await meaning.getByLabel("Currency code").fill("PKR");
  await meaning
    .getByText("Metric definitions and required filters", { exact: true })
    .click();
  await meaning.getByRole("button", { name: "Add metric definition" }).click();
  await meaning.getByLabel("Metric name", { exact: true }).fill("Paid amount");
  await meaning.getByRole("button", { name: "Add required filter" }).click();
  await meaning
    .getByRole("combobox", { name: "Filter column", exact: true })
    .selectOption("status");
  await meaning.getByLabel("Filter value", { exact: true }).fill("paid");
  await meaning
    .getByRole("button", { name: "Confirm business definitions" })
    .click();
  await expect(meaning.getByText("confirmed", { exact: true })).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Dataset dashboard" })
      .locator(".kpiValue"),
  ).toHaveText("0.1");
  passed();
  stage = "live_model_uses_confirmed_rule";
  await page.getByLabel("Your question").fill("What is the total paid amount?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".answerCard .kpiValue").last()).toHaveText("0.1");
  await page
    .getByText("How this answer was verified", { exact: true })
    .last()
    .click();
  await expect(page.locator(".answerEvidence").last()).toContainText(
    "hosted:deepseek-v4-pro",
  );
  passed();
  stage = "new_conversation_keeps_meaning";
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .click();
  await page
    .getByLabel("Your question")
    .fill("Total amount according to the confirmed definition?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".answerCard .kpiValue").last()).toHaveText("0.1");
  passed();
  stage = "old_receipt_stays_exact";
  const replay = await api(
    `/workspaces/${workspace.id}/queries/${original.lineage.query_id}/replay`,
    { method: "POST" },
  );
  assert.deepEqual(replay.rows, original.rows);
  const definition = await api(`${root}/understanding`);
  const historic = await api(
    `/workspaces/${workspace.id}/datasets/${dataset.id}/understandings/${definition.history[0].id}`,
  );
  assert.equal(historic.definition.metrics[0].filters[0].value, "paid");
  passed();
  stage = "mobile_layout";
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  passed();
} catch (error) {
  results.push({ stage, passed: false, reason: error.name });
} finally {
  if (browser) await browser.close();
}
const report = {
  scope: "private-fictional-understanding",
  passed: results.filter((item) => item.passed).length,
  total: 6,
  results,
};
await writeFile(outputPath, JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report));
process.exitCode = report.passed === report.total ? 0 : 1;
